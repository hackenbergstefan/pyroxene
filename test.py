from typing import Tuple
import unittest

import hypothesis
import hypothesis.strategies
import pygdbmi
import proxy

hypothesis.settings.register_profile("default", deadline=None, max_examples=10)
hypothesis.settings.load_profile("default")

lib = None


def connect():
    global lib
    lib = proxy.LibProxy(
        pygdbmi.gdbcontroller.GdbController(
            [
                "gdb",
                "--nx",
                "--quiet",
                "--interpreter=mi3",
                "./examples/host_example",
            ],
            time_to_check_for_additional_output_sec=0.1,
        ),
        proxy.GtiSocketProxy(("localhost", 1234)),
    )
    # global lib
    # lib = proxy.LibProxy(
    #     pygdbmi.gdbcontroller.GdbController(
    #         [
    #             "gdb-multiarch",
    #             "--nx",
    #             "--quiet",
    #             "--interpreter=mi3",
    #             "./build/CY8CPROTO-062-4343W/Debug/mtb-example-psoc6-uart-transmit-receive.elf",
    #         ],
    #         time_to_check_for_additional_output_sec=0.1,
    #     ),
    #     proxy.GtiSerialProxy("/dev/ttyACM0", 576000),
    # )


class PyGti2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not lib:
            connect()

    @hypothesis.given(hypothesis.strategies.binary(min_size=1, max_size=512))
    def test_echo(self, data):
        self.assertEqual(lib._proxy.echo(data), data)

    @hypothesis.given(hypothesis.strategies.binary(min_size=1, max_size=512))
    def test_write_read(self, data):
        lib.gti2_memory[0 : len(data)] = data
        self.assertEqual(lib.gti2_memory[0 : len(data)], data)

    def test_call_0_0(self):
        lib.gti2_memory[0:2] = 2 * b"\x00"
        lib.demo_func_0_0()
        self.assertEqual(lib.gti2_memory[0:2], b"\xde\xad")

    @hypothesis.given(hypothesis.strategies.integers(min_value=0, max_value=2**32 - 1))
    @hypothesis.settings(max_examples=100)
    def test_call_1(self, param1: int):
        lib.demo_func_0_1(param1)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), param1)

        result = lib.demo_func_1_1(param1)
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
        lib.demo_func_0_2(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.demo_func_1_2(*params)
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
        lib.demo_func_0_3(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.demo_func_1_3(*params)
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
        lib.demo_func_0_4(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.demo_func_1_4(*params)
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
        lib.demo_func_0_5(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.demo_func_1_5(*params)
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
        lib.demo_func_0_6(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.demo_func_1_6(*params)
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
        lib.demo_func_0_7(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.demo_func_1_7(*params)
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
        lib.demo_func_0_8(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.demo_func_1_8(*params)
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
        lib.demo_func_0_9(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.demo_func_1_9(*params)
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
        lib.demo_func_0_10(*params)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), sum(params))

        result = lib.demo_func_1_10(*params)
        self.assertEqual(result, 1 + sum(params))

    @hypothesis.given(
        a=hypothesis.strategies.integers(min_value=0, max_value=2**32 - 1),
        b=hypothesis.strategies.integers(min_value=0, max_value=2**32 - 1),
    )
    @hypothesis.settings(max_examples=100)
    def test_call_struct(self, a, b):
        hypothesis.assume(a + b < 2**32)
        demo_struct = lib._new("demo_struct_t *", addr=lib.gti2_memory._addr)

        # TODO: Implement type converter
        demo_struct.a = a
        demo_struct.b = b
        result = lib.demo_struct(demo_struct)
        self.assertEqual(result, 1 + a + b)
