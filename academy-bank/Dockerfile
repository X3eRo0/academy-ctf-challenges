FROM ubuntu@sha256:7c06e91f61fa88c08cc74f7e1b7c69ae24910d745357e0dfe1d2c0322aaf20f9

RUN apt update
RUN apt -y install gcc make libsqlite3-dev sqlite3

RUN useradd -m ctf
RUN echo "ctf:ctf" | chpasswd

WORKDIR /home/ctf
COPY src src
COPY include include
COPY Makefile .
COPY ynetd .

RUN make 

RUN chown -R root:root /home/ctf/build
RUN chown root:root /home/ctf/ynetd 
RUN chmod 0755 /home/ctf/ynetd
RUN chmod 0755 /home/ctf/build/academy-bank

USER ctf
EXPOSE 6969
CMD ./ynetd -p 6969 "timeout 60 /home/ctf/build/academy-bank"
