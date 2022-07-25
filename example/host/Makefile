
INCLUDES = -I../../src -I../c

host_example: ../../test/host/main.c $(wildcard ../c/*.c) ../../src/gti2.c
	gcc $(INCLUDES) -o $@ $? \
		-O2 -static \
		-g


.PHONY: host_example
