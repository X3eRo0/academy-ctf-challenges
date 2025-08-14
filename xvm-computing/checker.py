#!/usr/bin/env python3

from __future__ import annotations

import os
import random
import string
import subprocess
import tempfile
import time
from typing import Callable, List, Tuple, Optional, Dict
import sys

from ctf_gameserver import checkerlib
from pwn import remote, context
import logging


class XVMComputingChecker(checkerlib.BaseChecker):
    """
    Checker for the xvm-computing service.

    Service protocol (TCP, line-oriented with raw upload for payload):
      1) After connect, service prints a menu. We select options by sending e.g. b"1\n".
      2) Upload flow:
         - Send "1\n" -> prompt: "Enter file size (max 4KB): "
         - Send f"{len(payload)}\n" -> prompt: "Feed binary: "
         - Send raw 'payload' bytes
         - Response includes line: "Your Token: <hex>" (we store this token)
      3) Execute flow:
         - Send "2\n" -> prompt: "Enter token: "
         - Send token (hex) + "\n"
         - Service executes file with ./xvm and forwards stdout, then prints numeric exit status
    """

    SERVICE_PORT: int = 7777
    CONNECT_TIMEOUT_S: float = 6.0
    IO_TIMEOUT_S: float = 6.0
    MAX_UPLOAD: int = 4096

    # Paths to local toolchain used by the checker to assemble XVM binaries
    XASM_PATH: str = os.path.join("/opt/checker/xvm-computing", "build", "xasm")

    # -------------------- checkerlib entrypoints --------------------
    def place_flag(self, tick: int) -> checkerlib.CheckResult:
        # 1) connect
        try:
            r = self._connect()
        except Exception as e:
            print(f"[DEBUG] place_flag: connect failed: {e}", flush=True)
            return checkerlib.CheckResult.DOWN

        try:
            # 2) pick template and 3) assemble
            flag = checkerlib.get_flag(tick)
            # Ensure script directory on sys.path for module import
            try:
                script_dir = os.path.dirname(__file__)
                if script_dir and script_dir not in sys.path:
                    sys.path.insert(0, script_dir)
                import flag_templates as ft
            except Exception as e:
                print(f"[DEBUG] place_flag: failed to import flag_templates: {e}", flush=True)
                return checkerlib.CheckResult.FAULTY
            asm_src = ft.choose_random_flag_template(flag)

            # 4) assemble to bytes
            try:
                bin_bytes = self._assemble(asm_src)
            except Exception as e:
                print(f"[DEBUG] place_flag: assemble failed: {e}", flush=True)
                return checkerlib.CheckResult.FAULTY

            if len(bin_bytes) >= self.MAX_UPLOAD:
                print(f"[DEBUG] place_flag: binary too large: {len(bin_bytes)} bytes", flush=True)
                return checkerlib.CheckResult.FAULTY

            # 5) upload and save token
            try:
                token = self._upload_xvm(r, bin_bytes)
            except Exception as e:
                print(f"[DEBUG] place_flag: upload threw exception: {e}", flush=True)
                return checkerlib.CheckResult.FAULTY
            if not token:
                print("[DEBUG] place_flag: upload returned empty token", flush=True)
                return checkerlib.CheckResult.FAULTY
            
            checkerlib.store_state(str(tick), token)
            return checkerlib.CheckResult.OK
        finally:
            try:
                r.close()
            except Exception:
                pass

    def check_flag(self, tick: int) -> checkerlib.CheckResult:
        token = checkerlib.load_state(str(tick))
        if not token:
            print("[DEBUG] check_flag: no stored token", flush=True)
            return checkerlib.CheckResult.FLAG_NOT_FOUND

        try:
            r = self._connect()
        except Exception as e:
            print(f"[DEBUG] check_flag: connect failed: {e}", flush=True)
            return checkerlib.CheckResult.DOWN

        try:
            output = self._execute_xvm(r, token)
        except Exception as e:
            print(f"[DEBUG] check_flag: execute failed: {e}", flush=True)
            return checkerlib.CheckResult.DOWN
        finally:
            try:
                r.close()
            except Exception:
                pass

        if not output:
            print("[DEBUG] check_flag: empty output", flush=True)
            return checkerlib.CheckResult.FAULTY

        # Normalize output to a single line payload (bytes)
        first_line = output.split(b"\n", 1)[0] if output else b""
        expected = checkerlib.get_flag(tick).encode()
        if first_line == expected:
            return checkerlib.CheckResult.OK

        print(f"[DEBUG] check_flag: mismatch expected={expected!r} got={first_line!r}", flush=True)
        return checkerlib.CheckResult.FLAG_NOT_FOUND

    def check_service(self) -> checkerlib.CheckResult:
        # Randomized checks per tick: pick 2-3 tests
        tests = [
            self._test_menu_integrity,
            self._test_print_marker,
            self._test_xor_io,
            self._test_echo,
            self._test_open_close,
            self._test_map_unmap,
            self._test_dns_socket,
            self._test_xinfo_basic,
        ]
        test = random.choice(tests)
        return test()

    # -------------------- helpers for service checks --------------------
    def _upload_and_execute(self, bin_bytes: bytes, input_bytes: Optional[bytes] = None) -> Optional[bytes]:
        token: Optional[str] = None
        # upload
        try:
            r = self._connect()
        except Exception as e:
            print(f"[DEBUG] _upload_and_execute: connect upload failed: {e}", flush=True)
            return None
        try:
            token = self._upload_xvm(r, bin_bytes)
            if not token:
                print("[DEBUG] _upload_and_execute: upload returned empty token", flush=True)
                return None
        finally:
            try:
                r.close()
            except Exception:
                pass

        # execute
        try:
            r = self._connect()
        except Exception as e:
            print(f"[DEBUG] _upload_and_execute: connect exec failed: {e}", flush=True)
            return None
        try:
            r.sendlineafter(b"> ", b"2", timeout=self.IO_TIMEOUT_S)
            r.sendlineafter(b"Enter token: ", token, timeout=self.IO_TIMEOUT_S)
            if input_bytes:
                r.send(input_bytes)
            data = r.recvuntil(b"================================", timeout=self.IO_TIMEOUT_S)
            out = (data.split(b"================================", 1)[0]).replace(b"\r", b"")
            return out
        except Exception as e:
            print(f"[DEBUG] _upload_and_execute: exec exception: {e}", flush=True)
            return None
        finally:
            try:
                r.close()
            except Exception:
                pass

    def _test_menu_integrity(self) -> checkerlib.CheckResult:
        try:
            r = self._connect()
        except Exception as e:
            print(f"[DEBUG] _test_menu_integrity: connect failed: {e}", flush=True)
            return checkerlib.CheckResult.DOWN
        try:
            menu = r.recvuntil(b"> ", timeout=self.IO_TIMEOUT_S) or b""
            try:
                import sys as _sys, os as _os
                _dir = _os.path.dirname(__file__)
                if _dir and _dir not in _sys.path:
                    _sys.path.insert(0, _dir)
                import service_checks as sc
                expected = sc.expected_menu_text()
            except Exception as e:
                print(f"[DEBUG] _test_menu_integrity: import service_checks failed: {e}", flush=True)
                return checkerlib.CheckResult.FAULTY
            if expected.split(b"\n")[0] not in menu:
                print("[DEBUG] _test_menu_integrity: unexpected header", flush=True)
                return checkerlib.CheckResult.FAULTY
            return checkerlib.CheckResult.OK
        finally:
            try:
                r.close()
            except Exception:
                pass

    def _test_print_marker(self) -> checkerlib.CheckResult:
        try:
            import service_checks as sc
            marker = os.urandom(8)
            asm = sc.build_print_marker_program(marker)
            bin_bytes = self._assemble(asm)
        except Exception as e:
            print(f"[DEBUG] _test_print_marker: assemble failed: {e}", flush=True)
            return checkerlib.CheckResult.FAULTY
        out = self._upload_and_execute(bin_bytes)
        if not out:
            return checkerlib.CheckResult.FAULTY
        # Accept either exact marker or marker followed by newline
        if marker not in out and (marker + b"\n") not in out:
            print("[DEBUG] _test_print_marker: output mismatch", flush=True)
            return checkerlib.CheckResult.FAULTY
        return checkerlib.CheckResult.OK

    def _test_xor_io(self) -> checkerlib.CheckResult:
        try:
            import service_checks as sc
            secret = os.urandom(8)
            asm = sc.build_xor_io_program(secret)
            bin_bytes = self._assemble(asm)
        except Exception as e:
            print(f"[DEBUG] _test_xor_io: assemble failed: {e}", flush=True)
            return checkerlib.CheckResult.FAULTY
        inp = os.urandom(len(secret))
        out = self._upload_and_execute(bin_bytes, input_bytes=inp)
        if not out:
            return checkerlib.CheckResult.FAULTY
        expected = bytes(a ^ b for a, b in zip(secret, inp))
        if expected not in out:
            print("[DEBUG] _test_xor_io: output mismatch", flush=True)
            return checkerlib.CheckResult.FAULTY
        return checkerlib.CheckResult.OK

    def _test_echo(self) -> checkerlib.CheckResult:
        try:
            import service_checks as sc
            n = random.randint(4, 16)
            asm = sc.build_echo_program(n)
            bin_bytes = self._assemble(asm)
        except Exception as e:
            print(f"[DEBUG] _test_echo: assemble failed: {e}", flush=True)
            return checkerlib.CheckResult.FAULTY
        echo_in = os.urandom(n)
        out = self._upload_and_execute(bin_bytes, input_bytes=echo_in)
        if not out:
            return checkerlib.CheckResult.FAULTY
        if echo_in not in out:
            print("[DEBUG] _test_echo: output mismatch", flush=True)
            return checkerlib.CheckResult.FAULTY
        return checkerlib.CheckResult.OK

    def _test_xinfo_basic(self) -> checkerlib.CheckResult:
        try:
            import service_checks as sc
            asm = sc.build_debug_symbols_program(symbol_count=6)
            bin_dbg = self._assemble(asm, debug=True)
        except Exception as e:
            print(f"[DEBUG] _test_xinfo_basic: assemble failed: {e}", flush=True)
            return checkerlib.CheckResult.FAULTY

        # Upload
        try:
            r = self._connect()
        except Exception as e:
            print(f"[DEBUG] _test_xinfo_basic: connect upload failed: {e}", flush=True)
            return checkerlib.CheckResult.DOWN
        try:
            token = self._upload_xvm(r, bin_dbg)
            if not token:
                print("[DEBUG] _test_xinfo_basic: upload returned empty token", flush=True)
                return checkerlib.CheckResult.FAULTY
        finally:
            try:
                r.close()
            except Exception:
                pass

        # Info
        try:
            r = self._connect()
        except Exception as e:
            print(f"[DEBUG] _test_xinfo_basic: connect info failed: {e}", flush=True)
            return checkerlib.CheckResult.DOWN
        try:
            info_text = self._execute_info(r, token)
            if not info_text:
                print("[DEBUG] _test_xinfo_basic: empty xinfo output", flush=True)
                return checkerlib.CheckResult.FAULTY
            if b"Dumping Section Info" not in info_text or b"Dumping SymTab" not in info_text:
                print("[DEBUG] _test_xinfo_basic: missing sections", flush=True)
                return checkerlib.CheckResult.FAULTY
            return checkerlib.CheckResult.OK
        finally:
            try:
                r.close()
            except Exception:
                pass

    def _test_open_close(self) -> checkerlib.CheckResult:
        try:
            import service_checks as sc
            asm = sc.build_open_close_program()
            bin_bytes = self._assemble(asm)
        except Exception as e:
            print(f"[DEBUG] _test_open_close: assemble failed: {e}", flush=True)
            return checkerlib.CheckResult.FAULTY
        out = self._upload_and_execute(bin_bytes)
        if not out:
            print("[DEBUG] _test_open_close: empty output", flush=True)
            return checkerlib.CheckResult.FAULTY
        if b"ER" in out:
            print("[DEBUG] _test_open_close: open failed (ER)", flush=True)
            return checkerlib.CheckResult.FAULTY
        return checkerlib.CheckResult.OK

    def _test_map_unmap(self) -> checkerlib.CheckResult:
        try:
            import service_checks as sc
            asm = sc.build_map_unmap_program()
            bin_bytes = self._assemble(asm)
        except Exception as e:
            print(f"[DEBUG] _test_map_unmap: assemble failed: {e}", flush=True)
            return checkerlib.CheckResult.FAULTY
        out = self._upload_and_execute(bin_bytes)
        if not out:
            print("[DEBUG] _test_map_unmap: empty output", flush=True)
            return checkerlib.CheckResult.FAULTY
        return checkerlib.CheckResult.OK

    def _test_dns_socket(self) -> checkerlib.CheckResult:
        try:
            import service_checks as sc
            asm = sc.build_socket_dns_program()
            bin_bytes = self._assemble(asm)
        except Exception as e:
            print(f"[DEBUG] _test_dns_socket: assemble failed: {e}", flush=True)
            return checkerlib.CheckResult.FAULTY
        out = self._upload_and_execute(bin_bytes)
        if not out or b"OK" not in out:
            print("[DEBUG] _test_dns_socket: no OK marker", flush=True)
            return checkerlib.CheckResult.FAULTY
        return checkerlib.CheckResult.OK

    # -------------------- networking helpers --------------------
    def _connect(self):
        # Silence pwntools logging
        context.log_level = "critical"
        logging.getLogger("pwnlib").setLevel(logging.CRITICAL)
        host = getattr(self, "address", None) or getattr(self, "ip", None)
        if not host:
            # Fallback to a computed address if checkerlib exposes helper; otherwise rely on address provided
            host = checkerlib.get_service_address(self.team) if hasattr(checkerlib, "get_service_address") else None
        if not host:
            raise OSError("No service address available")
        r = remote(host, self.SERVICE_PORT, timeout=self.CONNECT_TIMEOUT_S)
        r.timeout = self.IO_TIMEOUT_S
        return r

    def _upload_xvm(self, r, payload: bytes) -> str:
        if len(payload) >= self.MAX_UPLOAD:
            return ""
        try:
            r.sendlineafter(b"> ", b"1", timeout=self.IO_TIMEOUT_S)
            r.sendlineafter(b"Enter file size (max 4KB): ", str(len(payload)).encode(), timeout=self.IO_TIMEOUT_S)
            r.sendafter(b"Feed binary: ", payload, timeout=self.IO_TIMEOUT_S)
            r.recvuntil(b"Your Token: ", timeout=self.IO_TIMEOUT_S)
            token = (r.recvline(timeout=self.IO_TIMEOUT_S) or b"").strip()
        except Exception as e:
            print(f"[DEBUG] _upload_xvm: exception: {e}", flush=True)
            return ""
        return token

    def _execute_xvm(self, r, token: str) -> str:
        try:
            r.sendlineafter(b"> ", b"2", timeout=self.IO_TIMEOUT_S)
            r.sendlineafter(b"Enter token: ", token, timeout=self.IO_TIMEOUT_S)
            # Execution prints program stdout, then server prints numeric exit code, then menu reappears
            # Read until the next menu prompt, collect all output
            data = r.recvuntil(b"> ", timeout=self.IO_TIMEOUT_S) or b""
        except Exception as e:
            print(f"[DEBUG] _execute_xvm: exception: {e}", flush=True)
            return ""
        # Strip the trailing menu text to isolate run output
        # The menu begins with "================================" on this server
        run_output = data.split(b"================================", 1)[0]
        text = run_output.replace(b"\r", b"")
        return text

    def _execute_info(self, r, token: str) -> str:
        """Request xinfo for token and return raw output text."""
        try:
            r.sendlineafter(b"> ", b"3", timeout=self.IO_TIMEOUT_S)
            r.sendlineafter(b"Enter token: ", token, timeout=self.IO_TIMEOUT_S)
            data = r.recvuntil(b"> ", timeout=self.IO_TIMEOUT_S) or b""
        except Exception as e:
            print(f"[DEBUG] _execute_info: exception: {e}", flush=True)
            return ""
        run_output = data.split(b"================================", 1)[0]
        text = run_output.replace(b"\r", b"")
        return text

    # -------------------- assembly generation and build --------------------
    def _build_flag_program(self, flag: str) -> bytes:
        variant_builders: List[Callable[[bytes], str]] = [
            self._template_xor_linear,
            self._template_add_linear,
            self._template_xor_two_stage,
            self._template_indexed_sub,
            self._template_reverse_then_xor_print,
        ]
        flag_bytes = flag.encode()
        builder = random.choice(variant_builders)
        asm_src = builder(flag_bytes)
        return self._assemble(asm_src)

    def _build_marker_program(self, text: str) -> bytes:
        # Use a simple XOR template for the availability marker
        return self._assemble(self._template_xor_linear(text.encode()))

    def _assemble(self, asm_source: str, debug: bool = False) -> bytes:
        if not os.path.isfile(self.XASM_PATH) or not os.access(self.XASM_PATH, os.X_OK):
            raise RuntimeError("Assembler not available")
        with tempfile.TemporaryDirectory(prefix="xvm_chk_") as td:
            asm_path = os.path.join(td, "prog.asm")
            bin_path = os.path.join(td, "prog.xvm")
            with open(asm_path, "w", encoding="utf-8") as f:
                f.write(asm_source)
            cmd = [self.XASM_PATH]
            if debug:
                cmd.append("-d")
            cmd += ["-i", asm_path, "-o", bin_path]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            if proc.returncode != 0:
                raise RuntimeError("Assembly failed")
            with open(bin_path, "rb") as f:
                data = f.read()
            if not data:
                raise RuntimeError("Empty binary")
            return data

    # Templates removed for clean slate

    # -------------------- utils --------------------
    def _random_ascii(self, n: int) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(random.choice(alphabet) for _ in range(n))


if __name__ == "__main__":
    checkerlib.run_check(XVMComputingChecker)