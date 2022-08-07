#ifndef GTI2_H
#define GTI2_H

#include <stddef.h>
#include <stdint.h>

#ifndef GTI2_HEAP_SIZE
#define GTI2_HEAP_SIZE (4 * 1024)
#endif

typedef unsigned long ulong;

void gti2_dispatcher(void);
void gti2_read(uint8_t *buffer, size_t length);
void gti2_write(const uint8_t *buffer, size_t length);

extern uint8_t gti2_memory[GTI2_HEAP_SIZE];

#endif
