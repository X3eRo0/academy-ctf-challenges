import random


def _prelude() -> str:
    return (
        ".section .text\n"
        "_start:\n"
    )


def _write_func() -> str:
    return (
        "write:\n"
        "\tpush\t$bp\n"
        "\tmov\t$bp, $sp\n"
        "\tmov\t$r0, #0x1\n"  # XVM_SYSC_WRITE
        "\tsyscall\n"
        "\tmov\t$sp, $bp\n"
        "\tpop\t$bp\n"
        "\tret\n"
    )


def _bytes_dir(data: bytes) -> str:
    return ", ".join(f"#0x{b:02x}" for b in data)


def tpl_xor_const(flag: str) -> str:
    # XOR with single-byte key; decode to obuf and write obuf+"\n"
    key = random.randint(1, 255)
    enc = bytes(b ^ key for b in flag.encode() + b"\n")
    n = len(enc)
    asm = []
    asm.append(_prelude())
    asm.append(
        f"\tmov\t$r3, #{n}\n"
        f"\tmov\t$r4, #{key}\n"
        "\tmov\t$r7, obuf\n"
        "\tmov\t$r8, enc\n"
        "dec_loop:\n"
        "\tcmp\t$r3, #0\n"
        "\tjz\tdone\n"
        "\tmovb\t$r9, [$r8]\n"
        "\txorb\t$r9, $r4\n"
        "\tmovb\t[$r7], $r9\n"
        "\tinc\t$r8\n"
        "\tinc\t$r7\n"
        "\tdec\t$r3\n"
        "\tjmp\tdec_loop\n"
        "done:\n"
        f"\tmov\t$r5, #{n}\n"
        "\tmov\t$r2, obuf\n"
        "\tmov\t$r1, #0x1\n"
        "\tcall\twrite\n"
        "\thlt\n\n"
    )
    asm.append(_write_func())
    asm.append("\n.section .data\nenc:\n\t.db " + _bytes_dir(enc) + "\n" + "obuf:\n\t.db " + ", ".join(["#0x00"] * n) + "\n")
    return "".join(asm)


def tpl_xor_10byte_key(flag: str) -> str:
    # XOR with 10-byte rolling key; key stored, data encoded; decode to obuf then write
    key_bytes = bytes(random.randint(1, 255) for _ in range(10))
    flag_nl = flag.encode() + b"\n"
    enc = bytes(b ^ key_bytes[i % 10] for i, b in enumerate(flag_nl))
    n = len(enc)
    asm = []
    asm.append(_prelude())
    asm.append(
        f"\tmov\t$r3, #{n}\n"      # remaining
        "\tmov\t$r10, #0\n"        # idx mod 10 (use r10 as counter within range of allowed regs?)
    )
    # Note: Only r0-r9, ra, rb, rc are documented; avoid r10. Use r6 for idx.
    asm[-1] = asm[-1].replace("$r10", "$r6")
    asm.append(
        "\tmov\t$r7, obuf\n"
        "\tmov\t$r8, enc\n"
        "\tmov\t$r9, key\n"
        "loopk:\n"
        "\tcmp\t$r3, #0\n"
        "\tjz\tdonek\n"
        # ensure r6 is within [0,9] before indexing
        "\tmov\t$rb, #10\n"
        "\tcmp\t$r6, $rb\n"
        "\tjz\tpre_resetk\n"
        "\tjmp\tpre_contk\n"
        "pre_resetk:\n"
        "\tmov\t$r6, #0\n"
        "pre_contk:\n"
        "\tmovb\t$ra, [$r8]\n"              # enc byte
        "\tmov\t$rb, $r9\n"
        "\tadd\t$rb, $r6\n"                   # key pointer + idx
        "\tmovb\t$rc, [$rb]\n"               # key byte
        "\txorb\t$ra, $rc\n"                  # decode
        "\tmovb\t[$r7], $ra\n"
        "\tinc\t$r8\n"
        "\tinc\t$r7\n"
        "\tinc\t$r6\n"
        "\tdec\t$r3\n"
        "\tjmp\tloopk\n"
        "donek:\n"
        f"\tmov\t$r5, #{n}\n"
        "\tmov\t$r2, obuf\n"
        "\tmov\t$r1, #0x1\n"
        "\tcall\twrite\n"
        "\thlt\n\n"
    )
    asm.append(_write_func())
    asm.append(
        "\n.section .data\nkey:\n\t.db " + _bytes_dir(key_bytes) + "\n"
        + "enc:\n\t.db " + _bytes_dir(enc) + "\n"
        + "obuf:\n\t.db " + ", ".join(["#0x00"] * n) + "\n"
    )
    return "".join(asm)


def _fib_mod256(i: int) -> int:
    a, b = 0, 1
    for _ in range(i):
        a, b = b, (a + b) & 0xFF
    return a


def tpl_xor_fib(flag: str) -> str:
    # XOR with per-index fib(i) & 0xff; recompute at runtime to avoid storing key
    flag_nl = flag.encode() + b"\n"
    # Pre-encode to avoid plaintext in binary: enc[i] = flag[i] ^ fib(i)
    enc = bytes((b ^ _fib_mod256(i)) & 0xFF for i, b in enumerate(flag_nl))
    n = len(enc)
    asm = []
    asm.append(_prelude())
    asm.append(
        "\tmov\t$r7, obuf\n"
        "\tmov\t$r8, enc\n"
        "\tmov\t$r3, #0\n"   # i
        f"\tmov\t$r5, #{n}\n"  # total
        "loopf:\n"
        "\tcmp\t$r3, $r5\n"
        "\tjz\tdonef\n"
        # compute fib(i) in ra/rb (iterative)
        "\tmov\t$ra, #0\n"   # a
        "\tmov\t$rb, #1\n"   # b
        "\tmov\t$rc, $r3\n"  # cnt
        "fibloop:\n"
        "\tcmp\t$rc, #0\n"
        "\tjz\tfibdone\n"
        "\tmov\t$r9, $ra\n"   # t = a
        "\tadd\t$r9, $rb\n"    # t = a + b
        "\tmov\t$ra, $rb\n"    # a = b
        "\tmov\t$rb, $r9\n"    # b = t
        "\tdec\t$rc\n"
        "\tjmp\tfibloop\n"
        "fibdone:\n"
        # ra holds fib(i)
        "\tmovb\t$r9, [$r8]\n"   # enc byte
        "\txorb\t$r9, $ra\n"
        "\tmovb\t[$r7], $r9\n"
        "\tinc\t$r8\n"
        "\tinc\t$r7\n"
        "\tinc\t$r3\n"
        "\tjmp\tloopf\n"
        "donef:\n"
        f"\tmov\t$r5, #{n}\n"
        "\tmov\t$r2, obuf\n"
        "\tmov\t$r1, #0x1\n"
        "\tcall\twrite\n"
        "\thlt\n\n"
    )
    asm.append(_write_func())
    asm.append("\n.section .data\nenc:\n\t.db " + _bytes_dir(enc) + "\n" + "obuf:\n\t.db " + ", ".join(["#0x00"] * n) + "\n")
    return "".join(asm)


def choose_random_flag_template(flag: str) -> str:
    builders = [tpl_xor_const, tpl_xor_10byte_key, tpl_xor_fib]
    return random.choice(builders)(flag)


