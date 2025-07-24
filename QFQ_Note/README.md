# Challenge

This challenge is a simple note-style pwn challenge. I get the original idea from a recent kernel bug I found. (sch_qfq race condition). I also inserted other bugs to make it more interesting for an AWD game.

The whole challege is a server style binary which can handle multiple connections in different threads at same time (we didn't have any lock system, so race condition on shared global objects).

| Bug Type       | Exp    | Fxi  |
| -------------- | ------ | ---- |
| DEBUG INFO     | Easy   | Easy |
| Heap Overflow  | Medium | Easy |
| Race Condition | Medium | Hard |


Since the fix is simple for heap overflow so I made the challenge no-pie so heap exploitation is much easier (or no one would try to exploit it cuz all people can patch it easily).

# DEBUG INFO

When checking the cred, the usage of strncmp is not proper: it uses the user-input's length as the third parameter so it always returns 0 when user doesn't enter anything.

```c
    // Bug 0: Bypass-able strncmp, but we don't allow players to patch this
    // The expected patch is disabling the DEBUG
    if(strncmp(creds,buf,strlen(buf))) 
        goto OUT;
    if(DEBUG==1){   
        do_send(conn_fd,"[DEBUG] [Disable before the game]\n");
        do_send(conn_fd,"\t\tUser Input: ");
        do_send(conn_fd,buf);
        do_send(conn_fd,"\n");

        do_send(conn_fd,"\t\tExpected Input: ");
        do_send(conn_fd,creds);
        do_send(conn_fd,"\n");
    }
```


I don't want the players fixing the strncmp and the expected fix should set DEBUG to 0 so no flag would be leaked.

The fix and exploitation should both be easy.

# Heap Overflow

A simple heap overflow bug is in `note_add`

```c
    struct note * note = calloc(1,size+sizeof(struct list_head));
    if(note==0){
        do_send(fd,"[X] No more space\n");
        return;
    }
    read(fd,note->ctx,size+sizeof(struct list_head)); //Bug 2. 0x10 bytes heap overflow
```

There are 10 bytes overflow which overwrites the next chunk's pre-size and size. So it's like a ordinary heap overflow challenge.

The intended fix should just change the third parameter of read from `size+sizeof(struct list_head)` to `size` (remove one ins in ASM).

# Race Condition

There is no lock so any option could lead to a race condtion. The intended fix should implement a lock sytem for it.

Our check should include a test case spwaning 1+ threads that connects to same process.

# Intended Exploitations

All the exploitations are in ./Exps.

# Dockerize

Done

# Intended Log
```bash
[04:06:01] n132 :: xps  ➜  ~/chal » python3 ./Exps/Race\ Condition/exp.py && python3 ./Exps/DEBUG\ Var/exp.py&& python3 ./Exps/Heap\ Overflow/exp.py
[+] Starting local process './main': pid 4107759
[+] Opening connection to 0.0.0.0 on port 29000: Done
[+] Opening connection to 0.0.0.0 on port 29000: Done
[+] Opening connection to 0.0.0.0 on port 29000: Done
[+] Opening connection to 0.0.0.0 on port 29000: Done
[!] kernelCTF{3be53711-581e-472a-bc12-263cd5989906}
[*] Closed connection to 0.0.0.0 port 29000
[*] Closed connection to 0.0.0.0 port 29000
[*] Closed connection to 0.0.0.0 port 29000
[*] Closed connection to 0.0.0.0 port 29000
[*] Stopped process './main' (pid 4107759)
[+] Starting local process './main': pid 4107815
[+] Opening connection to 0.0.0.0 on port 29000: Done
[*] kernelCTF{3be53711-581e-472a-bc12-263cd5989906}
[*] Closed connection to 0.0.0.0 port 29000
[*] Stopped process './main' (pid 4107815)
[+] Starting local process './main': pid 4107853
[+] Opening connection to 0.0.0.0 on port 29000: Done
[!] kernelCTF{3be53711-581e-472a-bc12-263cd5989906}
[*] Closed connection to 0.0.0.0 port 29000
[*] Stopped process './main' (pid 4107853)
[04:06:44] n132 :: xps  ➜  ~/chal »
```