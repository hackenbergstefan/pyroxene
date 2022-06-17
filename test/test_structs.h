#ifndef TEST_STRUCTS_H
#define TEST_STRUCTS_H

#include <stdint.h>

typedef enum
{
    TEST_ENUM_1_A,
    TEST_ENUM_1_B,
    TEST_ENUM_1_C,
} test_enum_1_t;

typedef uint32_t test_enum_2_t;

#define TEST_ENUM_2_A ((test_enum_2_t)1)
#define TEST_ENUM_2_B ((test_enum_2_t)2)
#define TEST_ENUM_2_C ((test_enum_2_t)3)

typedef struct
{
    uint8_t a;
} test_struct_1;

typedef struct
{
    uint8_t a;
    uint32_t b;
} test_struct_2;

typedef struct
{
    test_struct_1 *a;
} test_struct_3;

typedef struct
{
    test_enum_1_t a;
    test_enum_1_t *b;
    test_enum_2_t c;
    test_enum_2_t *d;
} test_struct_4;


#endif
