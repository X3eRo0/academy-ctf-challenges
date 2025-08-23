from collections import defaultdict
from pathlib import Path
import subprocess
import tempfile
import hashlib
import time
import stat
import sys
import os

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
    print("Your Token:", hash)


def get_save_file(token):
    for root, dir, files in os.walk(STORE_DIR):
        for file in files:
            file = Path(root, file)

            hash = hashlib.sha256(str(file).encode()).hexdigest()
            if hash == token:
                return file
    return None


def run():
    hash = input("Enter token: ")

    file = get_save_file(hash)
    if file is None:
        print("Err")
        exit()

    res = exec_bin(["./xvm", str(file)])


def info():
    hash = input("Enter token: ")

    file = get_save_file(hash)
    if file is None:
        print("Err")
        breakpoint()
        exit()

    res = exec_bin(["./xinfo", str(file)])


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
