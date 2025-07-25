from pwn import *
# context.log_level='debug'
context.arch='amd64'
# context.terminal = ['tmux', 'splitw', '-h', '-F' '#{pane_pid}', '-P']
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
ru(b"ected Input: ")
info(ru(b"\n").decode())
# p.interactive()
p.close()
r.close()
