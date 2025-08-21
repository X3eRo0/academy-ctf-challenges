all: libvault.so

# Extract and compile zlib
zlib-1.3.1/libz.a:
	tar -xzf zlib-1.3.1.tar.gz
	cd zlib-1.3.1 && CFLAGS="-fPIC" ./configure --static && make

libvault.so: vault.c zlib-1.3.1/libz.a
	gcc -s -shared -fPIC -ggdb -I./zlib-1.3.1 vault.c -o libvault.so ./zlib-1.3.1/libz.a -lcrypto -lssl

clean:
	rm -f libvault.so
	rm -rf zlib-1.3.1
