import unittest
from pygti2.device_commands import CommunicatorStub

from pygti2.device_proxy import VarProxyArray, VarProxyPointer, VarProxyStruct

from .test_elfbackend import compile


class TestDeviceProxyGcc(unittest.TestCase):
    compiler_cmdline = "gcc -c -g3 {infile} -o {outfile}"

    def test_proxy_pointer(self):
        elf = compile(
            "#include <stdint.h>",
            cmdline=self.compiler_cmdline,
        )
        var = VarProxyPointer(elf, CommunicatorStub(), elf.type_from_string("unsigned int *"), "a", 0)
        self.assertEqual(var.type, elf.type_from_string("unsigned int *"))
        self.assertEqual(var.address, 0)
        self.assertEqual(var.name, "a")
        self.assertEqual(var.convert_to_int(), 0)

    def test_proxy_array(self):
        elf = compile(
            "#include <stdint.h>",
            cmdline=self.compiler_cmdline,
        )
        var = VarProxyArray(elf, CommunicatorStub(), elf.type_from_string("unsigned int[1]"), "a", 0)
        self.assertEqual(var.type, elf.type_from_string("unsigned int [1]"))
        self.assertEqual(var.address, 0)
        self.assertEqual(var.name, "a")
        self.assertEqual(var.convert_to_int(), 0)
        self.assertEqual(var.length, 1)

    def test_access_pointer_int(self):
        elf = compile(
            """
            #include <stdint.h>
            uint32_t _;
            """,
            cmdline=self.compiler_cmdline,
        )
        com = CommunicatorStub()
        var1 = VarProxyPointer(elf, com, elf.type_from_string("unsigned int *"), "a", 0)
        self.assertEqual(var1[0], 0)

        var1[0] = 0xFF

        var2 = VarProxyPointer(elf, com, elf.type_from_string("uint32_t *"), "a", 0)
        self.assertEqual(var2[0], 0xFF)

    def test_access_array_int(self):
        elf = compile(
            """
            #include <stdint.h>
            uint32_t _;
            """,
            cmdline=self.compiler_cmdline,
        )
        com = CommunicatorStub()
        var1 = VarProxyArray(elf, com, elf.type_from_string("unsigned int[2]"), "a", 0)
        self.assertEqual(var1[0], 0)

        var1[0] = 0xFF

        var2 = VarProxyArray(elf, com, elf.type_from_string("uint32_t [2]"), "a", 0)
        self.assertEqual(var2[0], 0xFF)

    def test_access_array_int_range(self):
        elf = compile(
            """
            #include <stdint.h>
            uint32_t _;
            """,
            cmdline=self.compiler_cmdline,
        )
        com = CommunicatorStub()
        var = VarProxyArray(elf, com, elf.type_from_string("uint32_t [2]"), "a", 0)
        var[0:2] = [1234, 5678]
        self.assertEqual(var[0:2], [1234, 5678])

    def test_access_array_bytes_range(self):
        elf = compile(
            """
            #include <stdint.h>
            uint8_t _;
            """,
            cmdline=self.compiler_cmdline,
        )
        com = CommunicatorStub()
        var = VarProxyArray(elf, com, elf.type_from_string("uint8_t [2]"), "a", 0)
        var[0:2] = b"ab"
        self.assertEqual(var[0:2], b"ab")

    def test_access_struct(self):
        elf = compile(
            """
            #include <stdint.h>
            typedef struct {
                uint64_t a;
            } a_t;
            typedef struct {
                a_t b1;
                a_t *b2;
            } b_t;
            a_t a;
            b_t b;
            """,
            cmdline=self.compiler_cmdline,
        )
        com = CommunicatorStub()
        com.memory_write(8, 8 * b"\xff")
        var = VarProxyStruct(elf, com, elf.type_from_string("b_t *"), "bt", 0)
        self.assertEqual(var.base_type.size, 8 + elf.sizeof_voidp)
        self.assertIsInstance(var.b1, VarProxyStruct)
        self.assertIsInstance(var.b2, VarProxyStruct)

        var2 = VarProxyStruct(elf, com, elf.type_from_string("a_t *"), "at", 32)
        var.b2 = var2
        self.assertEqual(var.b2.address, 32)


class TestDeviceProxyGccArm(TestDeviceProxyGcc):
    compiler_cmdline = "arm-none-eabi-gcc -c -g {infile} -o {outfile}"
