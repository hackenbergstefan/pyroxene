#include <stdint.h>

#include "demo.h"
#include "gti2.h"


void demo_func_0_0(void)
{
    gti2_memory[0] = 0xde;
    gti2_memory[1] = 0xad;
}

void demo_func_0_1(uint32_t param1)
{
    *(uint32_t *)&gti2_memory[0] = param1;
}

void demo_func_0_2(uint32_t param1, uint32_t param2)
{
    *(uint32_t *)&gti2_memory[0] = param1 + param2;
}

void demo_func_0_3(uint32_t param1, uint32_t param2, uint32_t param3)
{
    *(uint32_t *)&gti2_memory[0] = param1 + param2 + param3;
}

void demo_func_0_4(uint32_t param1, uint32_t param2, uint32_t param3, uint32_t param4)
{
    *(uint32_t *)&gti2_memory[0] = param1 + param2 + param3 + param4;
}

void demo_func_0_5(uint32_t param1, uint32_t param2, uint32_t param3, uint32_t param4, uint32_t param5)
{
    *(uint32_t *)&gti2_memory[0] = param1 + param2 + param3 + param4 + param5;
}

void demo_func_0_6(uint32_t param1, uint32_t param2, uint32_t param3, uint32_t param4, uint32_t param5, uint32_t param6)
{
    *(uint32_t *)&gti2_memory[0] = param1 + param2 + param3 + param4 + param5 + param6;
}

void demo_func_0_7(
    uint32_t param1,
    uint32_t param2,
    uint32_t param3,
    uint32_t param4,
    uint32_t param5,
    uint32_t param6,
    uint32_t param7)
{
    *(uint32_t *)&gti2_memory[0] = param1 + param2 + param3 + param4 + param5 + param6 + param7;
}

void demo_func_0_8(
    uint32_t param1,
    uint32_t param2,
    uint32_t param3,
    uint32_t param4,
    uint32_t param5,
    uint32_t param6,
    uint32_t param7,
    uint32_t param8)
{
    *(uint32_t *)&gti2_memory[0] = param1 + param2 + param3 + param4 + param5 + param6 + param7 + param8;
}

void demo_func_0_9(
    uint32_t param1,
    uint32_t param2,
    uint32_t param3,
    uint32_t param4,
    uint32_t param5,
    uint32_t param6,
    uint32_t param7,
    uint32_t param8,
    uint32_t param9)
{
    *(uint32_t *)&gti2_memory[0] = param1 + param2 + param3 + param4 + param5 + param6 + param7 + param8 + param9;
}

void demo_func_0_10(
    uint32_t param1,
    uint32_t param2,
    uint32_t param3,
    uint32_t param4,
    uint32_t param5,
    uint32_t param6,
    uint32_t param7,
    uint32_t param8,
    uint32_t param9,
    uint32_t param10)
{
    *(uint32_t *)&gti2_memory[0] =
        param1 + param2 + param3 + param4 + param5 + param6 + param7 + param8 + param9 + param10;
}

uint32_t demo_func_1_1(uint32_t param1)
{
    return 1 + param1;
}

uint32_t demo_func_1_2(uint32_t param1, uint32_t param2)
{
    return 1 + param1 + param2;
}

uint32_t demo_func_1_3(uint32_t param1, uint32_t param2, uint32_t param3)
{
    return 1 + param1 + param2 + param3;
}

uint32_t demo_func_1_4(uint32_t param1, uint32_t param2, uint32_t param3, uint32_t param4)
{
    return 1 + param1 + param2 + param3 + param4;
}

uint32_t demo_func_1_5(uint32_t param1, uint32_t param2, uint32_t param3, uint32_t param4, uint32_t param5)
{
    return 1 + param1 + param2 + param3 + param4 + param5;
}

uint32_t demo_func_1_6(
    uint32_t param1, uint32_t param2, uint32_t param3, uint32_t param4, uint32_t param5, uint32_t param6)
{
    return 1 + param1 + param2 + param3 + param4 + param5 + param6;
}

uint32_t demo_func_1_7(
    uint32_t param1,
    uint32_t param2,
    uint32_t param3,
    uint32_t param4,
    uint32_t param5,
    uint32_t param6,
    uint32_t param7)
{
    return 1 + param1 + param2 + param3 + param4 + param5 + param6 + param7;
}

uint32_t demo_func_1_8(
    uint32_t param1,
    uint32_t param2,
    uint32_t param3,
    uint32_t param4,
    uint32_t param5,
    uint32_t param6,
    uint32_t param7,
    uint32_t param8)
{
    return 1 + param1 + param2 + param3 + param4 + param5 + param6 + param7 + param8;
}

uint32_t demo_func_1_9(
    uint32_t param1,
    uint32_t param2,
    uint32_t param3,
    uint32_t param4,
    uint32_t param5,
    uint32_t param6,
    uint32_t param7,
    uint32_t param8,
    uint32_t param9)
{
    return 1 + param1 + param2 + param3 + param4 + param5 + param6 + param7 + param8 + param9;
}

uint32_t demo_func_1_10(
    uint32_t param1,
    uint32_t param2,
    uint32_t param3,
    uint32_t param4,
    uint32_t param5,
    uint32_t param6,
    uint32_t param7,
    uint32_t param8,
    uint32_t param9,
    uint32_t param10)
{
    return 1 + param1 + param2 + param3 + param4 + param5 + param6 + param7 + param8 + param9 + param10;
}

uint32_t demo_struct(demo_struct_t *demo)
{
    // printf("demo_struct %p 1 + %lu + %lu = %lu\n", demo, demo->a, demo->b, 1 + demo->a + demo->b);
    return 1 + demo->a + demo->b;
}
