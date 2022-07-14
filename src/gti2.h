#ifndef GTI2_H
#define GTI2_H

#include <stddef.h>
#include <stdint.h>

typedef unsigned long ulong;

void gti2_dispatcher(void);
void gti2_read(uint8_t *buffer, size_t length);
void gti2_write(const uint8_t *buffer, size_t length);

extern uint8_t gti2_memory[4 * 1024];

#endif
