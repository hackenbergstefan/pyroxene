import hypothesis
import hypothesis.strategies

import unittest

lib = None
ffi = None


class TestMyMath(unittest.TestCase):
    def test_null_fails(self):
        self.assertEqual(
            lib.mymath_add(ffi.NULL, ffi.NULL, ffi.NULL),
            lib.MYMATH_STATUS_ARGUMENT_NULL,
        )

    def test_addition(self):
        memory1 = ffi.new("uint8_t[]", b"\x01\x00\x00\x00")
        operand1 = ffi.new("mpi_t *", (4, memory1))
        memory2 = ffi.new("uint8_t[]", b"\x02\x00\x00\x00")
        operand2 = ffi.new("mpi_t *", (4, memory2))

        memory_result = ffi.new("uint8_t[]", 4)
        result = ffi.new("mpi_t *", (len(memory_result), memory_result))

        self.assertEqual(
            lib.mymath_add(operand1, operand2, result),
            lib.MYMATH_STATUS_OK,
        )

        self.assertEqual(bytes(result.data[0:4]), b"\x03\x00\x00\x00")

    @hypothesis.given(
        operand1_data=hypothesis.strategies.binary(min_size=4, max_size=128).filter(
            lambda b: len(b) % 4 == 0
        ),
        operand2_data=hypothesis.strategies.binary(min_size=4, max_size=128).filter(
            lambda b: len(b) % 4 == 0
        ),
    )
    def test_addition_random(self, operand1_data, operand2_data):
        memory1 = ffi.new("uint8_t[]", operand1_data)
        operand1 = ffi.new("mpi_t *", (len(operand1_data), memory1))
        memory2 = ffi.new("uint8_t[]", operand2_data)
        operand2 = ffi.new("mpi_t *", (len(operand2_data), memory2))

        memory_result = ffi.new("uint8_t[]", max(len(operand1_data), len(operand2_data)) + 4)
        result = ffi.new("mpi_t *")
        result.data_length = len(memory_result)
        result.data = memory_result

        self.assertEqual(
            lib.mymath_add(operand1, operand2, result),
            lib.MYMATH_STATUS_OK,
        )

        self.assertEqual(
            int.from_bytes(bytes(memory_result[0 : len(memory_result)]), "little"),
            int.from_bytes(operand1_data, "little") + int.from_bytes(operand2_data, "little"),
        )
