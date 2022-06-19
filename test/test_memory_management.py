import unittest

import test

lib = test.connect()


class PyGti2TestSimpleMemoryManager(unittest.TestCase):
    def test_malloc(self):
        var = lib.new("uint8_t [10]")
        self.assertEqual(var._addr, lib.memory_manager.base_addr)
        self.assertEqual(var._type.base_size, lib.memory_manager.used)

    def test_out_of_memory(self):
        var = lib.new("uint8_t [1024]")
        with self.assertRaises(MemoryError):
            lib.new("uint8_t [10]")
        self.assertIsNotNone(var)
