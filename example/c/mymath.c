#include "mymath.h"

#define MAX(X, Y) (((X) > (Y)) ? (X) : (Y))


mymath_status_t mymath_add(const mpi_t *operand1, const mpi_t *operand2, mpi_t *result)
{
    if (operand1 == NULL || operand2 == NULL || result == NULL)
    {
        return MYMATH_STATUS_ARGUMENT_NULL;
    }
    if (operand1->data_length & 3 || operand2->data_length & 3 || result->data_length & 3)
    {
        return MYMATH_STATUS_ARGUMENT_MALFORMED;
    }
    if (MAX(operand1->data_length, operand2->data_length) > result->data_length)
    {
        return MYMATH_STATUS_ARGUMENT_TOO_SMALL;
    }

    if (operand2->data_length > operand1->data_length)
    {
        const mpi_t *tmp = operand1;
        operand1 = operand2;
        operand2 = tmp;
    }

    uint64_t carry = 0;
    size_t i = 0;
    for (; i < operand2->data_length / sizeof(uint32_t); i++)
    {
        carry = (uint64_t)((uint32_t *)operand1->data)[i] + (uint64_t)((uint32_t *)operand2->data)[i] + (carry >> 32);
        ((uint32_t *)result->data)[i] = (uint32_t)carry;
    }
    for (; i < operand1->data_length / sizeof(uint32_t); i++)
    {
        ((uint32_t *)result->data)[i] = ((uint32_t *)operand1->data)[i] + (carry >> 32);
        carry = 0;
    }
    if (carry != 0)
    {
        ((uint32_t *)result->data)[i] = carry >> 32;
    }
    return MYMATH_STATUS_OK;
}
