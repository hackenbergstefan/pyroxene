import unittest

import hypothesis

import test

lib = test.connect()


class PyGti2TestArrays(unittest.TestCase):
    def test_gti2_memory_1(self):
        lib.gti2_memory[0] = 1
        self.assertEqual(lib.gti2_memory[0], 1)

    def test_gti2_memory_2(self):
        lib.gti2_memory[0:10] = 10 * [0xFF]
        self.assertEqual(lib.gti2_memory[0:10], 10 * b"\xff")

    def test_array_1(self):
        test_struct = lib.new("uint8_t [10]")
        test_struct[0] = 1
        self.assertEqual(test_struct[0], 1)

        test_struct[0:5] = 5 * b"\xff"
        self.assertEqual(test_struct[0:5], 5 * b"\xff")

    def test_array_2(self):
        test_struct = lib.new("uint32_t [10]")
        test_struct[0] = 0x012345678
        self.assertEqual(test_struct[0], 0x012345678)

        test_struct[0:5] = 5 * [0x012345678]
        self.assertEqual(test_struct[0:5], 5 * [0x012345678])


class PyGti2TestStructs(unittest.TestCase):
    @hypothesis.given(
        a=hypothesis.strategies.integers(min_value=0, max_value=2**8 - 1),
    )
    @hypothesis.settings(max_examples=100)
    def test_structs_1(self, a):
        test_struct = lib.new("test_struct_1 *")
        test_struct.a = a
        self.assertEqual(test_struct.a, a)

    @hypothesis.given(
        a=hypothesis.strategies.integers(min_value=0, max_value=2**8 - 1),
        b=hypothesis.strategies.integers(min_value=0, max_value=2**32 - 1),
    )
    @hypothesis.settings(max_examples=100)
    def test_structs_2(self, a, b):
        test_struct = lib.new("test_struct_2 *")
        test_struct.a = a
        test_struct.b = b
        self.assertEqual(test_struct.a, a)
        self.assertEqual(test_struct.b, b)

    def test_structs_3(self):
        test_struct_1 = lib.new("test_struct_1 *")
        test_struct_2 = lib.new("test_struct_3 *")
        test_struct_2.a = test_struct_1
        self.assertEqual(test_struct_2.a, test_struct_1)

    def test_structs_4(self):
        test_struct = lib.new("test_struct_4 *")
        test_struct.a = lib.TEST_ENUM_1_A
        self.assertEqual(test_struct.a, lib.TEST_ENUM_1_A)


class PyGti2TestStructsInFunctions(unittest.TestCase):
    @hypothesis.given(
        a=hypothesis.strategies.integers(min_value=0, max_value=2**8 - 1),
    )
    @hypothesis.settings(max_examples=100)
    def test_structs_1(self, a):
        test_struct = lib.new("test_struct_1 *")

        test_struct.a = a
        result = lib.test_structs_1(test_struct)
        self.assertEqual(result, a + 1)

    @hypothesis.given(
        a=hypothesis.strategies.integers(min_value=0, max_value=2**8 - 1),
    )
    @hypothesis.settings(max_examples=100)
    def test_structs_2(self, a):
        test_struct = lib.new("test_struct_1 *")
        result = lib.test_structs_2(test_struct)
        self.assertEqual(result._addr, test_struct._addr)
