#ifndef PYROXENE_H
#define PYROXENE_H

#include <stddef.h>
#include <stdint.h>

#ifndef PYROXENE_HEAP_SIZE
#define PYROXENE_HEAP_SIZE (4 * 1024)
#endif

typedef unsigned long ulong;

void pyroxene_dispatcher(void);
void pyroxene_read(uint8_t *buffer, size_t length);
void pyroxene_write(const uint8_t *buffer, size_t length);

extern uint8_t pyroxene_memory[PYROXENE_HEAP_SIZE];

#endif
