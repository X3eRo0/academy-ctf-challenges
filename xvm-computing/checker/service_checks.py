import os
import random


def expected_menu_text() -> bytes:
    return (
        b"================================\n"
        b" XVM COMPUTE SERVICES PVT LTD   \n"
        b"================================\n"
        b"  Secure virtual code execution \n"
        b"\n"
        b"[1] Upload xvm file.\n"
        b"[2] Execute xvm file.\n"
        b"[3] Info about xvm file.\n"
        b"[4] Exit\n"
    )


def _prelude() -> str:
    return ".section .text\n_start:\n"


def _write_func() -> str:
    return (
        "write:\n"
        "\tpush\t$bp\n"
        "\tmov\t$bp, $sp\n"
        "\tmov\t$r0, #0x1\n"
        "\tsyscall\n"
        "\tmov\t$sp, $bp\n"
        "\tpop\t$bp\n"
        "\tret\n"
    )


def _bytes_dir(data: bytes) -> str:
    return ", ".join(f"#0x{b:02x}" for b in data)


def build_print_marker_program(marker: bytes) -> str:
    # Ensure a trailing newline delimiter for robustness
    marker_nl = marker + b"\n"
    n = len(marker_nl)
    asm = []
    asm.append(_prelude())
    asm.append(
        f"\tmov\t$r5, #{n}\n"
        "\tmov\t$r2, msg\n"
        "\tmov\t$r1, #0x1\n"
        "\tcall\twrite\n"
        "\thlt\n\n"
    )
    asm.append(_write_func())
    asm.append("\n.section .data\nmsg:\n\t.db " + _bytes_dir(marker_nl) + "\n")
    return "".join(asm)


def build_xor_io_program(secret: bytes) -> str:
    n = len(secret)
    asm = []
    asm.append(_prelude())
    asm.append(
        f"\tmov\t$r5, #{n}\n"     # read n bytes
        "\tmov\t$r2, inbuf\n"
        "\tmov\t$r1, #0x0\n"       # fd=stdin
        "\tmov\t$r0, #0x0\n"       # read
        "\tsyscall\n"
        f"\tmov\t$r3, #{n}\n"     # loop counter
        "\tmov\t$r7, outbuf\n"
        "\tmov\t$r8, secret\n"
        "\tmov\t$r9, inbuf\n"
        "xor_loop:\n"
        "\tcmp\t$r3, #0\n"
        "\tjz\txor_done\n"
        "\tmovb\t$ra, [$r8]\n"
        "\tmovb\t$rb, [$r9]\n"
        "\txorb\t$ra, $rb\n"
        "\tmovb\t[$r7], $ra\n"
        "\tinc\t$r8\n"
        "\tinc\t$r9\n"
        "\tinc\t$r7\n"
        "\tdec\t$r3\n"
        "\tjmp\txor_loop\n"
        "xor_done:\n"
        f"\tmov\t$r5, #{n}\n"
        "\tmov\t$r2, outbuf\n"
        "\tmov\t$r1, #0x1\n"
        "\tcall\twrite\n"
        "\thlt\n\n"
    )
    asm.append(_write_func())
    asm.append(
        "\n.section .data\n"
        + "secret:\n\t.db " + _bytes_dir(secret) + "\n"
        + "inbuf:\n\t.db " + ", ".join(["#0x00"] * n) + "\n"
        + "outbuf:\n\t.db " + ", ".join(["#0x00"] * n) + "\n"
    )
    return "".join(asm)


def build_echo_program(n: int) -> str:
    n = max(1, min(n, 256))
    asm = []
    asm.append(_prelude())
    asm.append(
        f"\tmov\t$r5, #{n}\n"
        "\tmov\t$r2, buf\n"
        "\tmov\t$r1, #0x0\n"
        "\tmov\t$r0, #0x0\n"
        "\tsyscall\n"
        f"\tmov\t$r5, #{n}\n"
        "\tmov\t$r2, buf\n"
        "\tmov\t$r1, #0x1\n"
        "\tcall\twrite\n"
        "\thlt\n\n"
    )
    asm.append(_write_func())
    asm.append("\n.section .data\nbuf:\n\t.db " + ", ".join(["#0x00"] * n) + "\n")
    return "".join(asm)


def build_open_close_program(path: bytes = b"/etc/passwd\x00") -> str:
    asm = []
    asm.append(_prelude())
    asm.append(
        "\tmov\t$r1, path\n"
        "\tmov\t$r2, #0x0\n"     # flags = 0
        "\tmov\t$r0, #0x5\n"     # OPEN
        "\tsyscall\n"
        "\tmov\t$r6, $r0\n"      # save fd
        # check for -1 (0xFFFFFFFF)
        "\tcmp\t$r6, #0xFFFFFFFF\n"
        "\tjz\tprint_err\n"
        # close fd
        "\tmov\t$r1, $r6\n"
        "\tmov\t$r0, #0x6\n"     # CLOSE
        "\tsyscall\n"
        # print OK
        "\tmov\t$r5, #2\n"
        "\tmov\t$r2, ok\n"
        "\tmov\t$r1, #0x1\n"
        "\tcall\twrite\n"
        "\tjmp\tend\n"
        "print_err:\n"
        "\tmov\t$r5, #2\n"
        "\tmov\t$r2, er\n"
        "\tmov\t$r1, #0x1\n"
        "\tcall\twrite\n"
        "end:\n"
        "\thlt\n\n"
    )
    asm.append(_write_func())
    asm.append(
        "\n.section .data\npath:\n\t.asciz \"" + path.decode('latin1') + "\"\n" +
        "ok:\n\t.db #0x4f, #0x4b\n" +
        "er:\n\t.db #0x45, #0x52\n"
    )
    return "".join(asm)


def build_map_unmap_program(addr: int = 0x20000000, size: int = 0x1000) -> str:
    asm = []
    asm.append(_prelude())
    asm.append(
        f"\tmov\t$r1, #{size}\n"    # size
        f"\tmov\t$r2, #{addr}\n"    # addr
        "\tmov\t$r5, #0x3\n"        # READ|WRITE
        "\tmov\t$r0, #0x2\n"        # MAP
        "\tsyscall\n"
        # write a byte
        f"\tmov\t$r7, #{addr}\n"
        "\tmovb\t[$r7], #0x41\n"
        # read back
        "\tmovb\t$r9, [$r7]\n"
        # unmap
        f"\tmov\t$r1, #{addr}\n"
        "\tmov\t$r0, #0x3\n"        # UNMAP
        "\tsyscall\n"
        # print OK
        "\tmov\t$r5, #2\n"
        "\tmov\t$r2, ok\n"
        "\tmov\t$r1, #0x1\n"
        "\tcall\twrite\n"
        "\thlt\n\n"
    )
    asm.append(_write_func())
    asm.append("\n.section .data\nok:\n\t.db #0x4f, #0x4b\n")
    return "".join(asm)


def build_socket_dns_program() -> str:
    # UDP DNS query to 8.8.8.8:53; prints whatever bytes are received
    q = b"\xAA\xAA\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\x03com\x00\x00\x01\x00\x01"
    n = len(q)
    asm = []
    asm.append(_prelude())
    asm.append(
        "\tmov\t$r1, #0x2\n"       # AF_INET
        "\tmov\t$r2, #0x2\n"       # SOCK_DGRAM
        "\tmov\t$r5, #0x0\n"       # proto
        "\tmov\t$r0, #0xC\n"       # SOCKET
        "\tsyscall\n"
        "\tmov\t$r6, $r0\n"       # sock fd
        # connect("8.8.8.8", 53)
        "\tmov\t$r1, $r6\n"
        "\tmov\t$r2, ip\n"
        "\tmov\t$r5, #53\n"
        "\tmov\t$r0, #0xD\n"       # CONNECT
        "\tsyscall\n"
        # send
        f"\tmov\t$r5, #{n}\n"
        "\tmov\t$r4, #0\n"
        "\tmov\t$r2, dnsq\n"
        "\tmov\t$r1, $r6\n"
        "\tmov\t$r0, #0xB\n"       # SEND
        "\tsyscall\n"
        # recv
        "\tmov\t$r1, $r6\n"
        "\tmov\t$r2, rbuf\n"
        "\tmov\t$r4, #0\n"
        "\tmov\t$r5, #64\n"
        "\tmov\t$r0, #0xA\n"       # RECV
        "\tsyscall\n"
        # write 'OK' regardless of recv result to signal success path
        "\tmov\t$r5, #2\n"
        "\tmov\t$r2, ok\n"
        "\tmov\t$r1, #0x1\n"
        "\tcall\twrite\n"
        "\thlt\n\n"
    )
    asm.append(_write_func())
    asm.append(
        "\n.section .data\n"
        + "ip:\n\t.asciz \"8.8.8.8\\0\"\n"
        + "dnsq:\n\t.db " + _bytes_dir(q) + "\n"
        + "rbuf:\n\t.db " + ", ".join(["#0x00"] * 64) + "\n"
        + "ok:\n\t.db #0x4f, #0x4b\n"
    )
    return "".join(asm)


def build_debug_symbols_program(symbol_count: int = 6) -> str:
    # At most 10 symbols
    symbol_count = min(max(symbol_count, 1), 10)
    labels = [f"sym{i}" for i in range(symbol_count)]
    asm = []
    asm.append(_prelude())
    # reference each label to ensure they appear
    for i in range(symbol_count):
        asm.append(f"\tmov\t$r6, {labels[i]}\n")
    asm.append("\thlt\n\n")
    asm.append(_write_func())
    # data labels
    asm.append("\n.section .data\n")
    for i in range(symbol_count):
        asm.append(f"{labels[i]}:\n\t.db #0x{i:02x}\n")
    return "".join(asm)


