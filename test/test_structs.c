#include "test_structs.h"
#include "../src/gti2.h"


ulong test_structs_1(test_struct_1 *s)
{
    return 1 + s->a;
}

test_struct_1 *test_structs_2(test_struct_1 *s)
{
    return s;
}
