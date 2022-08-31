#include <alloca.h>
#include <stdint.h>
#include <string.h>

#include "pyroxene.h"
#include "swap.h"

__attribute__((used, section(".pyroxene.data"))) uint8_t pyroxene_memory[PYROXENE_HEAP_SIZE] = { 0 };

typedef union
{
    struct
    {
        uint16_t cmd;
        uint16_t length;
        uint8_t data[];
    } d;
    uint8_t buffer[1024];
} pyroxene_comdata_t;

static pyroxene_comdata_t comdata;

const static uint8_t PYROXENE_ACK[3] = "ACK";
const static uint8_t PYROXENE_NCK[3] = "NCK";

static void pyroxene_dispatch_echo(uint32_t data_length)
{
    pyroxene_write(PYROXENE_ACK, sizeof(PYROXENE_ACK));
    pyroxene_write(comdata.d.data, data_length);
}

static void pyroxene_dispatch_memoryread(uint32_t data_length)
{
    uintptr_t address = ntohl(*(uintptr_t *)comdata.d.data);
    ulong len = ntohl(*(ulong *)&comdata.d.data[sizeof(uintptr_t)]);
    // printf("pyroxene_dispatch_memoryread 0x%016x %lu\n", address, len);
    // uint8_t *data = alloca(len);
    // memcpy(data, (uint8_t *)address, len);
    pyroxene_write(PYROXENE_ACK, sizeof(PYROXENE_ACK));
    pyroxene_write((uint8_t *)address, len);
}

static void pyroxene_dispatch_memorywrite(uint32_t data_length)
{
    uintptr_t address = ntohl(*(uintptr_t *)comdata.d.data);
    // printf("pyroxene_dispatch_memorywrite 0x%016x", address);
    // for (size_t i = 0; i < data_length - sizeof(uintptr_t); i++)
    // {
    //     printf(" %02x", comdata.d.data[sizeof(uintptr_t) + i]);
    // }
    // printf("\n");
    memcpy((uint8_t *)address, &comdata.d.data[sizeof(uintptr_t)], data_length - sizeof(uintptr_t));
    pyroxene_write(PYROXENE_ACK, sizeof(PYROXENE_ACK));
}

static void pyroxene_dispatch_call(uint32_t data_length)
{
    uintptr_t address = ntohl(*(uintptr_t *)&comdata.d.data[0]);
#ifdef __arm__
    address |= 1;
#endif
    uint16_t numbytes_out = ntoh16(*(uint16_t *)&comdata.d.data[sizeof(uintptr_t)]);
    uint16_t numparam_in = ntoh16(*(uint16_t *)&comdata.d.data[sizeof(uintptr_t) + sizeof(uint16_t)]);

    // printf("pyroxene_dispatch_call 0x%016lx %u %u\n", address, numbytes_out, numparam_in);

#define offset_param1 (sizeof(uintptr_t) + sizeof(uint16_t) + sizeof(uint16_t))
#define param1 (ntohl(*(ulong *)&comdata.d.data[offset_param1]))
#define param2 (ntohl(*(ulong *)&comdata.d.data[offset_param1 + 1 * sizeof(ulong)]))
#define param3 (ntohl(*(ulong *)&comdata.d.data[offset_param1 + 2 * sizeof(ulong)]))
#define param4 (ntohl(*(ulong *)&comdata.d.data[offset_param1 + 3 * sizeof(ulong)]))
#define param5 (ntohl(*(ulong *)&comdata.d.data[offset_param1 + 4 * sizeof(ulong)]))
#define param6 (ntohl(*(ulong *)&comdata.d.data[offset_param1 + 5 * sizeof(ulong)]))
#define param7 (ntohl(*(ulong *)&comdata.d.data[offset_param1 + 6 * sizeof(ulong)]))
#define param8 (ntohl(*(ulong *)&comdata.d.data[offset_param1 + 7 * sizeof(ulong)]))
#define param9 (ntohl(*(ulong *)&comdata.d.data[offset_param1 + 8 * sizeof(ulong)]))
#define param10 (ntohl(*(ulong *)&comdata.d.data[offset_param1 + 9 * sizeof(ulong)]))

#define call_case(_paramin) if (numparam_in == (_paramin))

    // Cases with ulong return
    ulong result = 0;
    call_case(0)
    {
        result = ((uint64_t(*)(void))address)();
    }
    call_case(1)
    {
        result = ((uint64_t(*)(ulong))address)(param1);
    }
    call_case(2)
    {
        result = ((uint64_t(*)(ulong, ulong))address)(param1, param2);
    }
    call_case(3)
    {
        result = ((uint64_t(*)(ulong, ulong, ulong))address)(param1, param2, param3);
    }
    call_case(4)
    {
        result = ((uint64_t(*)(ulong, ulong, ulong, ulong))address)(param1, param2, param3, param4);
    }
    call_case(5)
    {
        result = ((uint64_t(*)(ulong, ulong, ulong, ulong, ulong))address)(param1, param2, param3, param4, param5);
    }
    call_case(6)
    {
        result = ((uint64_t(*)(ulong, ulong, ulong, ulong, ulong, ulong))
                      address)(param1, param2, param3, param4, param5, param6);
    }
    call_case(7)
    {
        result = ((uint64_t(*)(ulong, ulong, ulong, ulong, ulong, ulong, ulong))
                      address)(param1, param2, param3, param4, param5, param6, param7);
    }
    call_case(8)
    {
        result = ((uint64_t(*)(ulong, ulong, ulong, ulong, ulong, ulong, ulong, ulong))
                      address)(param1, param2, param3, param4, param5, param6, param7, param8);
    }
    call_case(9)
    {
        result = ((uint64_t(*)(ulong, ulong, ulong, ulong, ulong, ulong, ulong, ulong, ulong))
                      address)(param1, param2, param3, param4, param5, param6, param7, param8, param9);
    }
    call_case(10)
    {
        result = ((uint64_t(*)(ulong, ulong, ulong, ulong, ulong, ulong, ulong, ulong, ulong, ulong))
                      address)(param1, param2, param3, param4, param5, param6, param7, param8, param9, param10);
    }
    result = ntohl(result);
    // printf("result = %016lx\n", result);
    pyroxene_write(PYROXENE_ACK, sizeof(PYROXENE_ACK));
    pyroxene_write((uint8_t *)&result, numbytes_out);
}

__attribute__((noreturn)) void pyroxene_dispatcher(void)
{
    while (1)
    {
        // Read header: cmd[2] | length[2]
        pyroxene_read(comdata.buffer, 2 + 2);
        uint32_t data_length = (uint32_t)ntoh16(comdata.d.length);
        if (data_length > sizeof(comdata.buffer) - 4)
        {
            pyroxene_write(PYROXENE_NCK, sizeof(PYROXENE_NCK));
            continue;
        }
        // Read data
        pyroxene_read(comdata.buffer + 4, data_length);

        switch (ntoh16(comdata.d.cmd))
        {
            case 0: // Echo
            {
                pyroxene_dispatch_echo(data_length);
                break;
            }
            case 1: // Read memory [address[4] len[4]]
            {
                pyroxene_dispatch_memoryread(data_length);
                break;
            }
            case 2: // Write memory [address[4] data[...]]
            {
                pyroxene_dispatch_memorywrite(data_length);
                break;
            }
            case 3: // Call [address[4] numparam_out[2] numparam_in[2] param_in1[4]? ...]
            {
                pyroxene_dispatch_call(data_length);
                break;
            }
            default:
                break;
        }
    }
}
