#include <stdint.h>

#include "gti2.h"


void demo_func_0_0(void)
{
    gti2_memory[0] = 0xde;
    gti2_memory[1] = 0xad;
}

void demo_func_0_1(uint32_t x)
{
    *(uint32_t *)&gti2_memory[0] = x;
}

unsigned int demo_func_1_0(void)
{
    volatile uint32_t x = 42;
    return x + 1;
}

unsigned int demo_func_1_1(uint32_t x)
{
    return 2 * x;
}
