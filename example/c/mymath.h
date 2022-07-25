#ifndef MYMATH_H
#define MYMATH_H

#include <stddef.h>
#include <stdint.h>

typedef struct
{
    /// Number of allocated bytes in data. Always multiple of 4.
    size_t data_length;
    /// Binary data of multi precision integer. Representation in little endian.
    uint8_t *data;
} mpi_t;

typedef uint32_t mymath_status_t;

#define MYMATH_STATUS_OK ((mymath_status_t)0)
#define MYMATH_STATUS_ERROR ((mymath_status_t)1)
#define MYMATH_STATUS_ARGUMENT_NULL ((mymath_status_t)2)
#define MYMATH_STATUS_ARGUMENT_MALFORMED ((mymath_status_t)3)
#define MYMATH_STATUS_ARGUMENT_TOO_SMALL ((mymath_status_t)4)


mymath_status_t mymath_add(const mpi_t *operand1, const mpi_t *operand2, mpi_t *result);

#endif
