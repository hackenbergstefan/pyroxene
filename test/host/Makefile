host_test: main.c ../../pyroxene/cshim/pyroxene.c $(wildcard ../test_*.c)
	gcc -I../../pyroxene/cshim -o $@ $? \
		-O2 -static \
		-g3 -gdwarf-3 -fno-eliminate-unused-debug-symbols


.PHONY: host_test
