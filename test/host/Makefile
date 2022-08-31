host_test: main.c ../../src/pyroxene.c $(wildcard ../test_*.c)
	gcc -I../../src -o $@ $? \
		-O2 -static \
		-g3 -gdwarf-3 -fno-eliminate-unused-debug-symbols


.PHONY: host_test
