import unittest
from pygti2.device_proxy import VarProxy

from pygti2.memory_management import SimpleMemoryManager

from .test_gti2 import compile


class TestSimpleMemoryManager(unittest.TestCase):
    def test_instance(self):
        with compile(
            """
            #include <stdint.h>
            uint8_t heap[1024];
            """
        ) as lib:
            mem = lib.memory_manager = SimpleMemoryManager(lib, "heap")
            self.assertEqual(mem.base_addr, lib.heap.address)
            self.assertEqual(mem.max_size, lib.sizeof(lib.heap))
            self.assertEqual(mem.allocated, [])
            self.assertEqual(mem.used, 0)

    def test_malloc(self):
        with compile(
            """
            #include <stdint.h>
            uint8_t heap[1024];
            typedef struct {
                uint32_t x;
            } a_t;
            a_t a;
            """
        ) as lib:
            mem = lib.memory_manager = SimpleMemoryManager(lib, "heap")
            var: VarProxy = lib.new("uint8_t[10]")
            self.assertEqual(var.address, lib.heap.address)
            self.assertEqual(mem.allocated, [var])
            self.assertEqual(mem.used, 10)

            var2: VarProxy = lib.new("uint8_t *")
            self.assertEqual(var2.address, lib.heap.address + 10)
            self.assertEqual(mem.allocated, [var, var2])
            self.assertEqual(mem.used, 11)

            var3: VarProxy = lib.new("a_t *")
            self.assertEqual(var3.address, lib.heap.address + 11)
            self.assertEqual(mem.allocated, [var, var2, var3])
            self.assertEqual(mem.used, 15)

    def test_autofree(self):
        with compile(
            """
            #include <stdint.h>
            uint8_t heap[1024];
            """
        ) as lib:
            mem = lib.memory_manager = SimpleMemoryManager(lib, "heap")
            var: VarProxy = lib.new("uint8_t *")
            self.assertEqual(var.address, lib.heap.address)
            self.assertEqual(mem.allocated, [var])
            self.assertEqual(mem.used, 1)
            del var
            var2: VarProxy = lib.new("uint8_t *")
            self.assertEqual(mem.allocated, [var2])
            self.assertEqual(mem.used, 1)

    def test_out_of_memory(self):
        with compile(
            """
            #include <stdint.h>
            uint8_t heap[1024];
            """
        ) as lib:
            mem = lib.memory_manager = SimpleMemoryManager(lib, "heap")
            var = lib.new("uint8_t [1024]")
            with self.assertRaises(MemoryError):
                lib.new("uint8_t [10]")
            self.assertEqual(mem.allocated, [var])
