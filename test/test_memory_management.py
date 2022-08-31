import unittest

import hypothesis
import hypothesis.strategies
from pyroxene.device_proxy import VarProxy

from pyroxene.memory_management import SimpleMemoryManager

from .test_pyroxene import compile


class TestSimpleMemoryManager(unittest.TestCase):
    def test_instance(self):
        with compile(
            """
            #include <stdint.h>
            uint8_t heap[1024];
            """
        ) as lib:
            mem = lib.memory_manager = SimpleMemoryManager(lib, "heap")
            self.assertEqual(mem.base_addr, lib.heap._address)
            self.assertEqual(mem.max_size, lib.sizeof(lib.heap))
            self.assertEqual(mem.allocated, [])

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
            self.assertEqual(var._address, lib.heap._address)
            self.assertEqual(mem.allocated, [(var, 10)])

            var2: VarProxy = lib.new("uint8_t *")
            self.assertEqual(var2._address, lib.heap._address + 16)
            self.assertEqual(mem.allocated, [(var, 10), (var2, 1)])

            var3: VarProxy = lib.new("a_t *")
            self.assertEqual(var3._address, lib.heap._address + 24)
            self.assertEqual(
                mem.allocated,
                [(var, 10), (var2, 1), (var3, lib.sizeof(var3))],
            )

    def test_autofree(self):
        with compile(
            """
            #include <stdint.h>
            uint8_t heap[1024];
            """
        ) as lib:
            mem = lib.memory_manager = SimpleMemoryManager(lib, "heap")
            var: VarProxy = lib.new("uint8_t *")
            self.assertEqual(var._address, lib.heap._address)
            self.assertEqual(mem.allocated, [(var, 1)])
            del var
            var2: VarProxy = lib.new("uint8_t *")
            self.assertEqual(mem.allocated, [(var2, 1)])

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
            self.assertEqual(mem.allocated, [(var, 1024)])

    def test_autofree_2(self):
        with compile("") as lib:
            lib.memory_manager = SimpleMemoryManager(lib)

            for _ in range(100):
                var = lib.new("uint8_t[100]")
                self.assertIsNotNone(var)


@hypothesis.strategies.composite
def draw_buffer(draw):
    return TestSimpleMemoryManager2.lib.new("uint8_t []", draw(hypothesis.strategies.integers(0, 100)))


class TestSimpleMemoryManager2(unittest.TestCase):
    @staticmethod
    def setUpClass():
        TestSimpleMemoryManager2.generator = compile(
            """
            #include <stdint.h>
            uint8_t get_element(uint8_t data[100]) { return data[0]; }
            """
        )
        TestSimpleMemoryManager2.lib = lib = TestSimpleMemoryManager2.generator.__enter__()
        lib.memory_manager = SimpleMemoryManager(lib)

    @staticmethod
    def tearDownClass():
        TestSimpleMemoryManager2.generator.__exit__(None, None, None)

    @hypothesis.given(
        var=draw_buffer(),
        size=hypothesis.strategies.integers(10, 1024),
    )
    @hypothesis.settings(max_examples=1000)
    def test_allocation(self, var, size):
        var2 = self.lib.new("uint8_t[]", size)
        self.assertIsNotNone(var)
        self.assertIsNotNone(var2)

    @hypothesis.given(
        data=hypothesis.strategies.binary(min_size=10, max_size=1024),
    )
    @hypothesis.settings(max_examples=1000)
    def test_temporary_allocation(self, data):
        self.assertEqual(self.lib.get_element(data), data[0])
