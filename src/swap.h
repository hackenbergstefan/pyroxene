#ifndef SWAP_H
#define SWAP_H

#include <stdint.h>

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

static inline unsigned long ntohl(unsigned long x)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#if __SIZEOF_LONG__ == 8
    return (unsigned long)swap_uint64((uint64_t)x);
#elif __SIZEOF_LONG__ == 4
    return (unsigned long)swap_uint32((uint32_t)x);
#else
#error "Unkown __SIZE_OF_LONG__ " __SIZEOF_LONG__
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

#endif
