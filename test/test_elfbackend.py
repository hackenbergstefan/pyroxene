import subprocess
import os
from tempfile import TemporaryDirectory
import unittest

from pyroxene.elfbackend import (
    CTypeArray,
    CTypeBaseType,
    CTypePointer,
    CTypeStruct,
    CTypeTypedef,
    CTypeUnion,
    CTypeVariable,
    ElfBackend,
)


def compile(source: str, source2: str = "", cmdline="gcc -c -g {infile} -o {outfile}", print_output=False):
    with TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "src.c"), "w") as fp:
            fp.write(source)

        with open(os.path.join(tmpdir, "src2.c"), "w") as fp:
            fp.write(source2)

        subprocess.check_call(
            cmdline.format(infile="src.c", outfile="src.o").split(" "),
            cwd=tmpdir,
        )
        subprocess.check_call(
            cmdline.format(infile="src2.c", outfile="src2.o").split(" "),
            cwd=tmpdir,
        )
        if print_output:
            print(
                subprocess.check_output(
                    "readelf.py --debug-dump=info src.o".split(" "),
                    cwd=tmpdir,
                ).decode()
            )
            print(
                subprocess.check_output(
                    "readelf.py --debug-dump=info src2.o".split(" "),
                    cwd=tmpdir,
                ).decode()
            )
        backend = ElfBackend(os.path.join(tmpdir, "src.o"))
        if source2:
            backend._create(os.path.join(tmpdir, "src2.o"))
        return backend


class TestCTypeGcc(unittest.TestCase):
    compiler_cmdline = "gcc -c -g3 {infile} -o {outfile}"

    def test_base_ints(self):
        elf = compile(
            "#include <stdint.h>",
            cmdline=self.compiler_cmdline,
        )

        for sign in ("unsigned ", ""):
            typ: CTypeBaseType = elf.types[f"{sign}int"]
            self.assertEqual(typ.kind, "int")
            self.assertIn(typ.size, (4, 8))

            typ: CTypeBaseType = elf.types[f"long {sign}int"]
            self.assertEqual(typ.kind, "int")
            self.assertIn(typ.size, (4, 8))

            typ: CTypeBaseType = elf.types[f"short {sign}int"]
            self.assertEqual(typ.kind, "int")
            self.assertEqual(typ.size, 2)

        for sign in ("unsigned", "signed"):
            typ: CTypeBaseType = elf.types[f"{sign} char"]
            self.assertEqual(typ.kind, "int")
            self.assertEqual(typ.size, 1)

    def test_stdint(self):
        elf = compile(
            """
            #include <stdint.h>
            int8_t a;
            uint8_t b;
            uint16_t c;
            uint32_t d;
            uint64_t e;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeTypedef = elf.types["uint8_t"]
        self.assertEqual(typ.kind, "int")
        self.assertEqual(typ.size, 1)
        self.assertEqual(typ.signed, False)

        typ: CTypeTypedef = elf.types["int8_t"]
        self.assertEqual(typ.kind, "int")
        self.assertEqual(typ.size, 1)
        self.assertEqual(typ.signed, True)

        for size in (2, 4, 8):
            typ: CTypeTypedef = elf.types[f"uint{size * 8}_t"]
            self.assertEqual(typ.kind, "int")
            self.assertEqual(typ.size, size)

    def test_struct(self):
        elf = compile(
            """
            struct a {} _a;
            struct b {
                unsigned char a;
                unsigned char b;
            } _b;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeStruct = elf.types["struct a"]
        self.assertEqual(typ.kind, "struct")
        self.assertEqual(typ.size, 0)

        typ: CTypeStruct = elf.types["struct b"]
        self.assertEqual(typ.kind, "struct")
        self.assertEqual(typ.size, 2)
        self.assertEqual(len(typ.members), 2)
        (offset, membertyp) = typ.members["a"]
        self.assertEqual(offset, 0)
        self.assertEqual(membertyp, elf.types["unsigned char"])
        (offset, membertyp) = typ.members["b"]
        self.assertEqual(offset, 1)
        self.assertEqual(membertyp, elf.types["unsigned char"])

    def test_struct_nested(self):
        elf = compile(
            """
            struct a {} _a;
            struct b {
                struct a _a;
            } _b;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeStruct = elf.types["struct b"]
        self.assertEqual(typ.kind, "struct")
        self.assertEqual(typ.size, 0)
        self.assertEqual(len(typ.members), 1)
        (offset, membertyp) = typ.members["_a"]
        self.assertEqual(offset, 0)
        self.assertEqual(membertyp, elf.types["struct a"])

    def test_typedefstruct(self):
        elf = compile(
            """
            typedef struct {} a_t;
            typedef struct {
                unsigned char a;
            } b_t;
            a_t a;
            b_t b;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeTypedef = elf.types["a_t"]
        self.assertEqual(typ.kind, "struct")
        self.assertEqual(typ.size, 0)
        typ: CTypeTypedef = elf.types["b_t"]
        self.assertEqual(typ.kind, "struct")
        self.assertEqual(typ.size, 1)
        self.assertIn("a", typ.members)

    def test_typedefpointer(self):
        elf = compile(
            """
            typedef char *charp;
            charp a;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeTypedef = elf.types["charp"]
        self.assertEqual(typ.kind, "pointer")
        self.assertEqual(typ.size, elf.sizeof_voidp)

    def test_typedefarray(self):
        elf = compile(
            """
            #include <stdint.h>
            typedef uint32_t intarr[2];
            intarr a;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeTypedef = elf.types["intarr"]
        self.assertEqual(typ.kind, "array")
        self.assertEqual(typ.size, 8)
        self.assertEqual(typ.typename, "intarr")

    def test_decl_pointer(self):
        elf = compile(
            """
            #include <stdint.h>
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypePointer = elf.type_from_string("unsigned int *")
        self.assertEqual(typ.typename, "unsigned int *")
        self.assertEqual(typ.kind, "pointer")
        self.assertEqual(typ.base, elf.types["unsigned int"])
        self.assertEqual(typ.size, elf.sizeof_voidp)

    def test_decl_pointer_u8(self):
        elf = compile(
            """
            #include <stdint.h>
            uint8_t x;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypePointer = elf.type_from_string("uint8_t *")
        self.assertIsInstance(typ, CTypePointer)
        self.assertEqual(typ.typename, "uint8_t *")
        self.assertEqual(typ.kind, "pointer")
        self.assertEqual(typ.base, elf.types["uint8_t"])
        self.assertEqual(typ.size, elf.sizeof_voidp)

    def test_decl_array(self):
        elf = compile(
            """
            #include <stdint.h>
            uint32_t x;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeArray = elf.type_from_string("uint32_t[2]")
        self.assertIsInstance(typ, CTypeArray)
        self.assertEqual(typ.typename, "uint32_t [2]")
        self.assertEqual(typ.kind, "array")
        self.assertEqual(typ.base, elf.types["uint32_t"])
        self.assertEqual(typ.size, 8)

    def test_predefined_variable(self):
        elf = compile(
            """
            #include <stdint.h>
            uint32_t x = 0;
            const uint32_t y = 0;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeVariable = elf.types["x"]
        self.assertEqual(typ.kind, "variable")
        self.assertEqual(typ.type, elf.types["uint32_t"])
        self.assertEqual(typ.size, 4)
        self.assertEqual(typ.address, 0)
        typ: CTypeVariable = elf.types["y"]
        self.assertEqual(typ.kind, "variable")
        self.assertEqual(typ.type, elf.types["uint32_t"])
        self.assertEqual(typ.size, 4)
        self.assertEqual(typ.address, 0)

    def test_predefined_function(self):
        elf = compile(
            """
            #include <stdint.h>
            uint32_t a(void) { }
            const char *b(void) { }
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeVariable = elf.types["a"]
        self.assertEqual(typ.kind, "function")
        self.assertEqual(typ.address, 0)
        self.assertEqual(typ.return_type, elf.types["uint32_t"])
        self.assertEqual(typ.arguments, [])
        typ: CTypeVariable = elf.types["b"]
        self.assertEqual(typ.kind, "function")
        self.assertEqual(typ.return_type, elf.types["char *"])
        self.assertEqual(typ.arguments, [])

    def test_predefined_function_with_arguments(self):
        elf = compile(
            """
            #include <stdint.h>
            uint32_t a(uint8_t x, uint32_t y) { }
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeVariable = elf.types["a"]
        self.assertEqual(typ.kind, "function")
        self.assertEqual(typ.address, 0)
        self.assertEqual(typ.return_type, elf.types["uint32_t"])
        self.assertEqual(typ.arguments, [elf.types["uint8_t"], elf.types["uint32_t"]])

    def test_const(self):
        elf = compile(
            """
            #include <stdint.h>
            const uint32_t X = 42;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeVariable = elf.types["X"]
        self.assertIsInstance(typ, CTypeVariable)
        self.assertEqual(typ.kind, "variable")
        self.assertEqual(typ.address, 0)

    def test_recursive_declarations(self):
        elf = compile(
            """
            #include <stdint.h>
            struct a;
            struct a {
                struct a *x;
            } a_;

            typedef struct b {
                struct b *x;
            } b_t;
            b_t _;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeStruct = elf.types["struct a"]
        self.assertIsInstance(typ.members["x"][1], CTypePointer)
        self.assertEqual(typ.members["x"][1].base, typ)

        typ: CTypeStruct = elf.types["b_t"]
        self.assertIsInstance(typ.members["x"][1], CTypePointer)
        self.assertEqual(typ.members["x"][1].base, typ.base)

    def test_enums(self):
        elf = compile(
            """
            #include <stdint.h>
            enum a {
                A_A,
                A_B,
                A_C = 0x1234,
            };
            enum a a_;

            typedef enum {
                B_A = 0xabcd,
            } b_e;
            b_e b_;
            """,
            cmdline=self.compiler_cmdline,
        )
        self.assertEqual(elf.enums["A_A"], 0)
        self.assertEqual(elf.enums["A_B"], 1)
        self.assertEqual(elf.enums["A_C"], 0x1234)
        self.assertEqual(elf.enums["B_A"], 0xABCD)

    def test_unions(self):
        elf = compile(
            """
            union a {
                int a;
                int b;
            };
            union a a_;

            typedef union {
                int a;
                int b;
            } b_t;
            b_t b_;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeUnion = elf.types["union a"]
        self.assertIsInstance(typ, CTypeUnion)
        self.assertEqual(typ.kind, "union")
        typ: CTypeUnion = elf.types["b_t"]
        self.assertIsInstance(typ, CTypeUnion)
        self.assertEqual(typ.kind, "union")

    def test_update(self):
        elf = compile(
            source="""
            extern int a;
            extern int b[];
            void init(void) {
                int _ = a;
                _ = b[0];
            }
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeVariable = elf.types["a"]
        self.assertEqual(typ.kind, "variable")
        self.assertIsNone(typ.address)
        typ: CTypeVariable = elf.types["b"]
        self.assertEqual(typ.kind, "variable")
        self.assertIsNone(typ.address)
        self.assertEqual(typ.type.length, -1)
        self.assertEqual(typ.size, -1)

        elf = compile(
            source="""
            extern int a;
            extern int b[];
            void init(void) {
                int _ = a;
                _ = b[0];
            }
            """,
            source2="""
            int a = 5;
            int b[10];
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeVariable = elf.types["a"]
        self.assertEqual(typ.kind, "variable")
        self.assertIsInstance(typ.address, int)
        typ: CTypeVariable = elf.types["b"]
        self.assertEqual(typ.kind, "variable")
        self.assertIsInstance(typ.address, int)
        self.assertEqual(typ.type.length, 10)
        self.assertEqual(typ.size, typ.type.size)


class TestCTypeGccArm(TestCTypeGcc):
    compiler_cmdline = "arm-none-eabi-gcc -c -g {infile} -o {outfile}"
