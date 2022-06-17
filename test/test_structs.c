#include "test_structs.h"
#include "../src/gti2.h"

test_struct_1 s1;
test_struct_2 s2;
test_struct_3 s3;
test_struct_4 s4;

ulong test_structs_1(test_struct_1 *s)
{
    return 1 + s->a;
}

test_struct_1 *test_structs_2(test_struct_1 *s)
{
    return s;
}
