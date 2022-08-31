import unittest
from pyroxene.device_commands import CommunicatorStub

from pyroxene.device_proxy import VarProxy, VarProxyStruct

from .test_elfbackend import compile


class TestDeviceProxyGcc(unittest.TestCase):
    compiler_cmdline = "gcc -c -g3 {infile} -o {outfile}"

    def test_proxy_int(self):
        elf = compile(
            """
            #include <stdint.h>
            uint8_t a;
            int8_t b;
            """,
            cmdline=self.compiler_cmdline,
        )
        var = VarProxy.new(elf, CommunicatorStub(), elf.type_from_string("unsigned int *"), 0)
        self.assertEqual(var._type, elf.type_from_string("unsigned int"))
        self.assertEqual(var._address, 0)
        self.assertEqual(var[0], 0)
        self.assertEqual(var[1], 0)
        var[0] = 1
        var[1] = 2
        self.assertEqual(var[0], 1)
        self.assertEqual(var[1], 2)

        var = VarProxy.new(elf, CommunicatorStub(), elf.type_from_string("uint8_t *"), 0)
        var[0] = 0xFF
        self.assertEqual(var[0], 0xFF)

        var = VarProxy.new(elf, CommunicatorStub(), elf.type_from_string("int8_t *"), 0)
        var[0] = -1
        self.assertEqual(var[0], -1)

    def test_proxy_struct(self):
        elf = compile(
            """
            #include <stdint.h>
            struct a {
                uint32_t x;
                uint8_t *y;
            } a_;
            """,
            cmdline=self.compiler_cmdline,
        )
        var = VarProxy.new(elf, CommunicatorStub(), elf.type_from_string("struct a *"), 0)
        self.assertIsInstance(var, VarProxyStruct)
        self.assertEqual(var._type, elf.type_from_string("struct a"))
        self.assertEqual(var._address, 0)
        self.assertEqual(var.is_primitive, False)

        self.assertEqual(var.x, 0)
        var.x = 1
        self.assertEqual(var.x, 1)

        var2 = VarProxy(elf, CommunicatorStub(), elf.type_from_string("uint8_t *"), 16)
        var.y = var2

    def test_proxy_array(self):
        elf = compile(
            "#include <stdint.h>",
            cmdline=self.compiler_cmdline,
        )
        var = VarProxy.new(elf, CommunicatorStub(), elf.type_from_string("unsigned int[1]"), 0)
        self.assertEqual(var._type, elf.type_from_string("unsigned int"))
        self.assertEqual(var._address, 0)
        self.assertEqual(var._length, 1)
        self.assertEqual(var[0], 0)
        var[0] = 5
        self.assertEqual(var[0], 5)

    def test_proxy_array_2(self):
        elf = compile(
            "#include <stdint.h>",
            cmdline=self.compiler_cmdline,
        )
        var = VarProxy.new(elf, CommunicatorStub(), elf.type_from_string("unsigned int[2]"), 0)
        self.assertEqual(var._type, elf.type_from_string("unsigned int"))
        self.assertEqual(var._length, 2)
        self.assertEqual(var._address, 0)
        var[0:2] = [1, 2]
        self.assertEqual(var[0:2], [1, 2])

    def test_proxy_typedef_struct(self):
        elf = compile(
            """
            #include <stdint.h>
            typedef struct {
                uint32_t x;
            } a_t;
            a_t _;
            """,
            cmdline=self.compiler_cmdline,
        )
        var = VarProxyStruct(elf, CommunicatorStub(), elf.type_from_string("a_t"), 0)
        self.assertEqual(var.is_primitive, False)
        self.assertEqual(var.x, 0)
        var.x = 1
        self.assertEqual(var.x, 1)

    def test_proxy_typedef_struct_2(self):
        elf = compile(
            """
            #include <stdint.h>
            typedef struct {
                uint64_t x;
            } a_t;
            typedef struct {
                a_t x;
                a_t *y;
            } b_t;
            b_t _;
            """,
            cmdline=self.compiler_cmdline,
        )
        var = VarProxy.new(elf, CommunicatorStub(), elf.type_from_string("b_t *"), 0)
        self.assertIsInstance(var, VarProxyStruct)
        self.assertEqual(var._type, elf.type_from_string("b_t"))

        self.assertIsInstance(var.x, VarProxyStruct)
        self.assertEqual(var.x._type, elf.type_from_string("a_t"))
        self.assertEqual(var.x._address, 0)

        self.assertIsInstance(var.y, VarProxy)
        self.assertEqual(var.y._type, elf.type_from_string("a_t"))
        self.assertEqual(var.y._address, 0)

        var.x.x = 1
        self.assertEqual(var.x.x, 1)
        var.y.x = 2
        self.assertEqual(var.y.x, 2)

        var2 = VarProxy.new(elf, CommunicatorStub(), elf.type_from_string("a_t *"), 16)
        var.y = var2
        self.assertEqual(var.y._address, var2._address)


class TestDeviceProxyGccArm(TestDeviceProxyGcc):
    compiler_cmdline = "arm-none-eabi-gcc -c -g {infile} -o {outfile}"
