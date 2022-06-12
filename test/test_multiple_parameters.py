from typing import Tuple
import unittest

import hypothesis

from . import connect

lib = connect()


class PyGti2TestMultipleParameters(unittest.TestCase):
    @hypothesis.given(hypothesis.strategies.binary(min_size=1, max_size=512))
    def test_echo(self, data):
        self.assertEqual(lib._proxy.echo(data), data)

    @hypothesis.given(hypothesis.strategies.binary(min_size=1, max_size=512))
    def test_write_read(self, data):
        lib.gti2_memory[0 : len(data)] = data
        self.assertEqual(lib.gti2_memory[0 : len(data)], data)

    def test_call_0_0(self):
        lib.gti2_memory[0:2] = 2 * b"\x00"
        lib.test_func_0_0()
        self.assertEqual(lib.gti2_memory[0:2], b"\xde\xad")

    @hypothesis.given(hypothesis.strategies.integers(min_value=0, max_value=2**32 - 1))
    @hypothesis.settings(max_examples=100)
    def test_call_1(self, param1: int):
        lib.test_func_0_1(param1)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), param1)

        result = lib.test_func_1_1(param1)
        self.assertEqual(result, 1 + param1)

    @hypothesis.given(
        hypothesis.strategies.lists(
            hypothesis.strategies.integers(min_value=0, max_value=2**31 - 1),
            min_size=2,
            max_size=2,
        )
    )
    @hypothesis.settings(max_examples=100)
    def test_call_2(self, params: Tuple[int]):
        hypothesis.assume(sum(params) < 2**32)
        lib.test_func_0_2(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.test_func_1_2(*params)
        self.assertEqual(result, 1 + sum(params))

    @hypothesis.given(
        hypothesis.strategies.lists(
            hypothesis.strategies.integers(min_value=0, max_value=2**32 - 1),
            min_size=3,
            max_size=3,
        )
    )
    @hypothesis.settings(max_examples=100)
    def test_call_3(self, params: Tuple[int]):
        hypothesis.assume(sum(params) < 2**32)
        lib.test_func_0_3(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.test_func_1_3(*params)
        self.assertEqual(result, 1 + sum(params))

    @hypothesis.given(
        hypothesis.strategies.lists(
            hypothesis.strategies.integers(min_value=0, max_value=2**32 - 1),
            min_size=4,
            max_size=4,
        )
    )
    @hypothesis.settings(max_examples=100)
    def test_call_4(self, params: Tuple[int]):
        hypothesis.assume(sum(params) < 2**32)
        lib.test_func_0_4(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.test_func_1_4(*params)
        self.assertEqual(result, 1 + sum(params))

    @hypothesis.given(
        hypothesis.strategies.lists(
            hypothesis.strategies.integers(min_value=0, max_value=2**32 - 1),
            min_size=5,
            max_size=5,
        )
    )
    @hypothesis.settings(max_examples=100)
    def test_call_5(self, params: Tuple[int]):
        hypothesis.assume(sum(params) < 2**32)
        lib.test_func_0_5(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.test_func_1_5(*params)
        self.assertEqual(result, 1 + sum(params))

    @hypothesis.given(
        hypothesis.strategies.lists(
            hypothesis.strategies.integers(min_value=0, max_value=2**32 - 1),
            min_size=6,
            max_size=6,
        )
    )
    @hypothesis.settings(max_examples=100)
    def test_call_6(self, params: Tuple[int]):
        hypothesis.assume(sum(params) < 2**32)
        lib.test_func_0_6(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.test_func_1_6(*params)
        self.assertEqual(result, 1 + sum(params))

    @hypothesis.given(
        hypothesis.strategies.lists(
            hypothesis.strategies.integers(min_value=0, max_value=2**32 - 1),
            min_size=7,
            max_size=7,
        )
    )
    @hypothesis.settings(max_examples=100)
    def test_call_7(self, params: Tuple[int]):
        hypothesis.assume(sum(params) < 2**32)
        lib.test_func_0_7(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.test_func_1_7(*params)
        self.assertEqual(result, 1 + sum(params))

    @hypothesis.given(
        hypothesis.strategies.lists(
            hypothesis.strategies.integers(min_value=0, max_value=2**32 - 1),
            min_size=8,
            max_size=8,
        )
    )
    @hypothesis.settings(max_examples=100)
    def test_call_8(self, params: Tuple[int]):
        hypothesis.assume(sum(params) < 2**32)
        lib.test_func_0_8(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.test_func_1_8(*params)
        self.assertEqual(result, 1 + sum(params))

    @hypothesis.given(
        hypothesis.strategies.lists(
            hypothesis.strategies.integers(min_value=0, max_value=2**32 - 1),
            min_size=9,
            max_size=9,
        )
    )
    @hypothesis.settings(max_examples=100)
    def test_call_9(self, params: Tuple[int]):
        hypothesis.assume(sum(params) < 2**32)
        lib.test_func_0_9(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.test_func_1_9(*params)
        self.assertEqual(result, 1 + sum(params))

    @hypothesis.given(
        hypothesis.strategies.lists(
            hypothesis.strategies.integers(min_value=0, max_value=2**32 - 1),
            min_size=10,
            max_size=10,
        )
    )
    @hypothesis.settings(max_examples=100)
    def test_call_10(self, params: Tuple[int]):
        hypothesis.assume(sum(params) < 2**32)
        lib.test_func_0_10(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.test_func_1_10(*params)
        self.assertEqual(result, 1 + sum(params))
