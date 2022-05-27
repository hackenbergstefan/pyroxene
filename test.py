import unittest

import hypothesis
import pygdbmi
import proxy

hypothesis.settings.register_profile("default", deadline=None)
hypothesis.settings.load_profile("default")

lib = None


def connect():
    global lib
    lib = proxy.LibProxy(
        pygdbmi.gdbcontroller.GdbController(
            [
                "gdb-multiarch",
                "--nx",
                "--quiet",
                "--interpreter=mi3",
                "./build/CY8CPROTO-062-4343W/Debug/mtb-example-psoc6-uart-transmit-receive.elf",
            ],
            time_to_check_for_additional_output_sec=0.1,
        ),
        proxy.GtiSerialProxy("/dev/ttyACM0", 576000),
    )


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
    def test_call_0_1(self, number: int):
        lib.demo_func_0_1(number)
        self.assertEqual(int.from_bytes(lib.gti2_memory[0:4], "little"), number)

    @hypothesis.given(hypothesis.strategies.integers(min_value=0, max_value=2**31 - 1))
    @hypothesis.settings(max_examples=100)
    def test_call_1_1(self, number: int):
        result = lib.demo_func_1_1(number)
        self.assertEqual(result, 2 * number)
