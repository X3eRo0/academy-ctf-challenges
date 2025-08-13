from collections import defaultdict
import time
import subprocess
import tempfile
import hashlib
import stat
import sys
import os

mapping = defaultdict()

STORE_DIR = "/tmp/data"


def exec_bin(cmd):
    try:
        # Execute the binary
        status = os.system(" ".join(cmd))
        return status

    except Exception as e:
        print("Err")
        exit()


def upload():
    sz = int(input("Enter file size (max 4KB): "))
    if sz >= 4096:
        print("Err")
        exit()
    fd, path = tempfile.mkstemp(dir=STORE_DIR, suffix=".xvm")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
    os.chown(path, 0, 1000)  # root:ctf
    os.write(1, b"Feed binary: ")
    os.write(fd, os.read(0, sz))
    os.close(fd)
    hash = hashlib.sha256(path.encode()).hexdigest()
    if hash in mapping.keys():
        print("Err")
        exit()
    mapping[hash] = path
    print("Your Token:", hash)


def run():
    hash = input("Enter token: ")
    if hash not in mapping.keys():
        print("Err")
        exit()

    res = exec_bin(["./xvm", mapping[hash]])
    print("%d" % (res))


def info():
    hash = input("Enter token: ")
    if hash not in mapping.keys():
        print("Err")
        breakpoint()
        exit()

    res = exec_bin(["./xinfo", mapping[hash]])


def menu():
    print("================================")
    print(" XVM COMPUTE SERVICES PVT LTD   ")
    print("================================")
    print("  Secure virtual code execution ")
    print("")
    print("[1] Upload xvm file.")
    print("[2] Execute xvm file.")
    print("[3] Info about xvm file.")
    print("[4] Exit")
    try:
        c = int(input("> "))
    except:
        print("Err")
        exit()
    return c


def main():
    functions = [None, upload, run, info, sys.exit]
    choice = 1
    while choice > 0 and choice < 4:
        if not os.path.exists(STORE_DIR):
            os.mkdir(STORE_DIR)
        choice = menu()
        functions[choice]()


if __name__ == "__main__":
    main()
