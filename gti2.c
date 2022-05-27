#include <string.h>

#ifdef __arm__
#include "cy_pdl.h"
#else
#include <arpa/inet.h>
#endif

#include "gti2.h"

uint8_t gti2_memory[1024];

static inline uint16_t swap_uint16(uint16_t val)
{
    return (val << 8) | (val >> 8);
}

static inline uint32_t swap_uint32(uint32_t val)
{
    val = ((val << 8) & 0xFF00FF00) | ((val >> 8) & 0xFF00FF);
    return (val << 16) | (val >> 16);
}

static inline uint64_t swap_uint64(uint64_t val)
{
    val = ((val << 8) & 0xFF00FF00FF00FF00ULL) | ((val >> 8) & 0x00FF00FF00FF00FFULL);
    val = ((val << 16) & 0xFFFF0000FFFF0000ULL) | ((val >> 16) & 0x0000FFFF0000FFFFULL);
    return (val << 32) | (val >> 32);
}

static inline uintptr_t ntohptr(uintptr_t x)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#if __SIZEOF_POINTER__ == 8
    return (uintptr_t)swap_uint64((uint64_t)x);
#elif __SIZEOF_POINTER__ == 4
    return (uintptr_t)swap_uint32((uint32_t)x);
#else
#error "Unkown __SIZE_OF_POINTER__ " __SIZEOF_POINTER__
#endif
#else
    return x;
#endif
}

static inline unsigned int ntohi(unsigned int x)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#if __SIZEOF_INT__ == 8
    return (unsigned int)swap_uint64((uint64_t)x);
#elif __SIZEOF_INT__ == 4
    return (unsigned int)swap_uint32((uint32_t)x);
#else
#error "Unkown __SIZE_OF_INT__ " __SIZEOF_INT__
#endif
#else
    return x;
#endif
}

static inline uint16_t ntoh16(uint16_t x)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return swap_uint16(x);
#else
    return x;
#endif
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
} gti2_comdata_t;

static gti2_comdata_t comdata;

static void gti2_dispatch_echo(uint32_t data_length)
{
    gti2_write(comdata.d.data, data_length);
}

static void gti2_dispatch_memoryread(uint32_t data_length)
{
    uintptr_t address = ntohptr(*(uintptr_t *)comdata.d.data);
    size_t len = ntohi(*(size_t *)&comdata.d.data[sizeof(uintptr_t)]);
    gti2_write((uint8_t *)address, len);
}

static void gti2_dispatch_memorywrite(uint32_t data_length)
{
    uintptr_t address = ntohptr(*(uintptr_t *)comdata.d.data);
    memcpy((uint8_t *)address, &comdata.d.data[sizeof(uintptr_t)], data_length - sizeof(uintptr_t));
}

static void gti2_dispatch_call(uint32_t data_length)
{
    uintptr_t address = ntohi(*(uintptr_t *)&comdata.d.data[0]) | 1;
    uint16_t numparam_out = ntoh16(*(uint16_t *)&comdata.d.data[sizeof(uintptr_t)]);
    uint16_t numparam_in = ntoh16(*(uint16_t *)&comdata.d.data[sizeof(uintptr_t) + sizeof(uint16_t)]);
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
                case 4:
                {
                    unsigned int result = ((unsigned int (*)(void))address)();
                    gti2_write((uint8_t *)&result, sizeof(unsigned int));
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
                        ntohi(*(uint32_t *)&comdata.d.data[sizeof(uintptr_t) + sizeof(uint16_t) + sizeof(uint16_t)]));
                    break;
                }
                case 4:
                {
                    unsigned int result = ((unsigned int (*)(unsigned int))address)(
                        ntohi(*(uint32_t *)&comdata.d.data[sizeof(uintptr_t) + sizeof(uint16_t) + sizeof(uint16_t)]));
                    gti2_write((uint8_t *)&result, sizeof(unsigned int));
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

__attribute__((noreturn)) void gti2_dispatcher(void)
{
    while (1)
    {
        // Read header: cmd[2] | length[2]
        gti2_read(comdata.buffer, 2 + 2);
        uint32_t data_length = (uint32_t)ntoh16(comdata.d.length);
        // Read data
        gti2_read(comdata.buffer + 4, data_length);

        switch (ntoh16(comdata.d.cmd))
        {
            case 0: // Echo
            {
                gti2_dispatch_echo(data_length);
                break;
            }
            case 1: // Read memory [address[4] len[4]]
            {
                gti2_dispatch_memoryread(data_length);
                break;
            }
            case 2: // Write memory [address[4] data[...]]
            {
                gti2_dispatch_memorywrite(data_length);
                break;
            }
            case 3: // Call [address[4] numparam_out[2] numparam_in[2] param_in1[4]? ...]
            {
                gti2_dispatch_call(data_length);
                break;
            }
            default:
                break;
        }
    }
}
