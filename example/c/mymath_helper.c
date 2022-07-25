#include "mymath_helper.h"

mymath_status_t mymath_mpi_valid(const mpi_t *operand1)
{
    if (operand1->data_length & 3)
    {
        return MYMATH_STATUS_ERROR;
    }
    return MYMATH_STATUS_OK;
}
