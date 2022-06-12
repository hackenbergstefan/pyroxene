import unittest

import hypothesis

import test

lib = test.connect()


class PyGti2TestStructs(unittest.TestCase):
    @hypothesis.given(
        a=hypothesis.strategies.integers(min_value=0, max_value=2**8 - 1),
    )
    @hypothesis.settings(max_examples=100)
    def test_call_struct(self, a):
        test_struct = lib._new("test_struct_1 *", addr=lib.gti2_memory._addr)

        test_struct.a = a
        result = lib.test_structs_1(test_struct)
        self.assertEqual(result, a + 1)
