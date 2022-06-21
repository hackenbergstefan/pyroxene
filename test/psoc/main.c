/******************************************************************************
 * File Name: main.c
 *
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

#include "gti2.h"


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


void gti2_read(uint8_t *buffer, size_t length)
{
    for (size_t i = 0; i < length; i++)
    {
        cyhal_uart_getc(&cy_retarget_io_uart_obj, &buffer[i], 0);
    }
}

void gti2_write(uint8_t *buffer, size_t length)
{
    for (size_t i = 0; i < length; i++)
    {
        cyhal_uart_putc(&cy_retarget_io_uart_obj, buffer[i]);
    }
}


int main(void)
{
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
    gti2_dispatcher();
}

/* [] END OF FILE */
