/******************************************************************************
 * File Name: main.c
 *
 * Description: This example demonstrates the UART transmit and receive
 *              operation using HAL APIs
 *
 * Related Document: See Readme.md
 *
 *******************************************************************************
 * (c) 2019-2021, Cypress Semiconductor Corporation. All rights reserved.
 *******************************************************************************
 * This software, including source code, documentation and related materials
 * ("Software"), is owned by Cypress Semiconductor Corporation or one of its
 * subsidiaries ("Cypress") and is protected by and subject to worldwide patent
 * protection (United States and foreign), United States copyright laws and
 * international treaty provisions. Therefore, you may use this Software only
 * as provided in the license agreement accompanying the software package from
 * which you obtained this Software ("EULA").
 *
 * If no EULA applies, Cypress hereby grants you a personal, non-exclusive,
 * non-transferable license to copy, modify, and compile the Software source
 * code solely for use in connection with Cypress's integrated circuit products.
 * Any reproduction, modification, translation, compilation, or representation
 * of this Software except as specified above is prohibited without the express
 * written permission of Cypress.
 *
 * Disclaimer: THIS SOFTWARE IS PROVIDED AS-IS, WITH NO WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING, BUT NOT LIMITED TO, NONINFRINGEMENT, IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. Cypress
 * reserves the right to make changes to the Software without notice. Cypress
 * does not assume any liability arising out of the application or use of the
 * Software or any product or circuit described in the Software. Cypress does
 * not authorize its products for use in any products where a malfunction or
 * failure of the Cypress product may reasonably be expected to result in
 * significant property damage, injury or death ("High Risk Product"). By
 * including Cypress's product in a High Risk Product, the manufacturer of such
 * system or application assumes all risk of such use and in doing so agrees to
 * indemnify Cypress against all liability.
 *******************************************************************************/

#include "cy_pdl.h"
#include "cy_retarget_io.h"
#include "cybsp.h"
#include "cyhal.h"

/*******************************************************************************
 * Function Name: handle_error
 ********************************************************************************
 * Summary:
 * User defined error handling function.
 *
 * Parameters:
 *  void
 *
 * Return:
 *  void
 *
 *******************************************************************************/
void handle_error(void)
{
    /* Disable all interrupts. */
    __disable_irq();

    CY_ASSERT(0);
}

typedef union
{
    struct
    {
        uint16_t cmd;
        uint16_t length;
        uint8_t data[];

    } d;
    uint8_t buffer[1024];
} uart_data_t;

uart_data_t uart_data;

static void read_exact(uint8_t *buffer, size_t length)
{
    for (size_t i = 0; i < length; i++)
    {
        cyhal_uart_getc(&cy_retarget_io_uart_obj, &buffer[i], 0);
    }
}

static void write_exact(uint8_t *buffer, size_t length)
{
    for (size_t i = 0; i < length; i++)
    {
        cyhal_uart_putc(&cy_retarget_io_uart_obj, buffer[i]);
    }
}

void dispatcher(void)
{
    while (1)
    {
        // Read header: cmd[2] | length[2]
        read_exact(uart_data.buffer, 2 + 2);
        uint32_t data_length = __REV16(uart_data.d.length);
        // Read data
        read_exact(uart_data.buffer + 4, data_length);

        switch (__REV16(uart_data.d.cmd))
        {
            case 1: // Read memory [address[4] len[4]]
            {
                uintptr_t address = __REV(*(uintptr_t *)uart_data.d.data);
                size_t len = __REV(*(size_t *)&uart_data.d.data[sizeof(uintptr_t)]);
                write_exact((uint8_t *)address, len);
                break;
            }
            case 2: // Write memory [address[4] data[...]]
            {
                uintptr_t address = __REV(*(uintptr_t *)uart_data.d.data);
                memcpy((uint8_t *)address, &uart_data.d.data[sizeof(uintptr_t)], data_length - sizeof(uintptr_t));
                break;
            }
            case 3: // Call [address[4] numparam_out[2] numparam_in[2] param_in1[4]? ...]
            {
                uintptr_t address = __REV(*(uintptr_t *)&uart_data.d.data[0]) | 1;
                uint16_t numparam_out = __REV16(*(uint16_t *)&uart_data.d.data[sizeof(uintptr_t)]);
                uint16_t numparam_in = __REV16(*(uint16_t *)&uart_data.d.data[sizeof(uintptr_t) + sizeof(uint16_t)]);
                switch (numparam_in)
                {
                    case 0:
                    {
                        switch (numparam_out)
                        {
                            case 0:
                            {
                                ((void (*)(void))address)();
                                break;
                            }
                            case 1:
                            {
                                unsigned int result = ((unsigned int (*)(void))address)();
                                write_exact((uint8_t *)&result, sizeof(unsigned int));
                                break;
                            }
                            default:
                                break;
                        }
                        break;
                    }
                    case 1:
                    {
                        switch (numparam_out)
                        {
                            case 0:
                            {
                                ((void (*)(unsigned int))address)(
                                    __REV(*(uint32_t *)&uart_data.d
                                               .data[sizeof(uintptr_t) + sizeof(uint16_t) + sizeof(uint16_t)]));
                                break;
                            }
                            case 1:
                            {
                                unsigned int result = ((unsigned int (*)(unsigned int))address)(
                                    __REV(*(uint32_t *)&uart_data.d
                                               .data[sizeof(uintptr_t) + sizeof(uint16_t) + sizeof(uint16_t)]));
                                write_exact((uint8_t *)&result, sizeof(unsigned int));
                                break;
                            }
                            default:
                                break;
                        }
                        break;
                    }
                    default:
                        break;
                }

                break;
            }
            default:
                break;
        }
    }
}

uint8_t scratch_buffer[1024];

__attribute__((used, noinline)) void myfunc1(void)
{
    scratch_buffer[0] = 0xde;
    scratch_buffer[1] = 0xad;
}

__attribute__((used, noinline)) uint32_t myfunc2(void)
{
    volatile uint32_t x = 42;
    return &scratch_buffer[0];
}

__attribute__((used, noinline)) uint32_t myfunc3(uint32_t x)
{
    volatile uint32_t dummy = 42;
    return x + 1;
}

int main(void)
{
    myfunc1();
    myfunc2();
    myfunc3(41);

    cy_rslt_t result;

    /* Initialize the device and board peripherals */
    result = cybsp_init();
    if (result != CY_RSLT_SUCCESS)
    {
        handle_error();
    }

    /* Initialize retarget-io to use the debug UART port */
    result = cy_retarget_io_init(CYBSP_DEBUG_UART_TX, CYBSP_DEBUG_UART_RX, 576000);
    if (result != CY_RSLT_SUCCESS)
    {
        handle_error();
    }

    __enable_irq();

    cyhal_uart_clear(&cy_retarget_io_uart_obj);
    scratch_buffer[0] = 0;
    dispatcher();
}

/* [] END OF FILE */
