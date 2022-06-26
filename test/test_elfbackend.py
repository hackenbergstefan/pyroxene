import subprocess
import os
from tempfile import TemporaryDirectory
import unittest

from pygti2.elfbackend import (
    CType,
    CTypeBaseInt,
    CTypeBaseType,
    CTypeStruct,
    CTypeTypedef,
    CTypeTypedefInt,
    ElfBackend,
)


def compile(source: str, cmdline="gcc -c -g {infile} -o {outfile}", print_output=False):
    with TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "src.c"), "w") as fp:
            fp.write(source)

        subprocess.check_call(
            cmdline.format(infile="src.c", outfile="src.o").split(" "),
            cwd=tmpdir,
        )
        if print_output:
            print(
                subprocess.check_output(
                    "readelf.py --debug-dump=info src.o".split(" "),
                    cwd=tmpdir,
                ).decode()
            )
        return ElfBackend(os.path.join(tmpdir, "src.o"))


class TestCTypeGcc(unittest.TestCase):
    compiler_cmdline = "gcc -c -g {infile} -o {outfile}"

    def test_ctype_not_instanceable(self):
        with self.assertRaises(TypeError):
            CType._new(None, None)

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
            self.assertEqual(typ.kind, "byte")
            self.assertEqual(typ.size, 1)

    def test_stdint(self):
        elf = compile(
            """
            #include <stdint.h>
            uint8_t a;
            uint16_t b;
            uint32_t c;
            uint64_t d;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeTypedef = elf.types["uint8_t"]
        self.assertEqual(typ.kind, "byte")
        self.assertEqual(typ.size, 1)

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
        typ: CTypeStruct = elf.types["a"]
        self.assertEqual(typ.kind, "struct")
        self.assertEqual(typ.size, 0)

        typ: CTypeStruct = elf.types["b"]
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
        typ: CTypeStruct = elf.types["b"]
        self.assertEqual(typ.kind, "struct")
        self.assertEqual(typ.size, 0)
        self.assertEqual(len(typ.members), 1)
        (offset, membertyp) = typ.members["_a"]
        self.assertEqual(offset, 0)
        self.assertEqual(membertyp, elf.types["a"])

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
        self.assertEqual(typ.kind, "typedef struct")
        self.assertEqual(typ.size, 0)
        typ: CTypeTypedef = elf.types["b_t"]
        self.assertEqual(typ.kind, "typedef struct")
        self.assertEqual(typ.size, 1)
        self.assertIn("a", typ.members)

    def test_typedefpointer(self):
        elf = compile(
            """
            typedef int *intp;
            intp a;
            """,
            cmdline=self.compiler_cmdline,
        )
        typ: CTypeTypedef = elf.types["intp"]
        self.assertEqual(typ.kind, "typedef pointer")
        self.assertEqual(typ.size, elf.dwarfinfo.config.default_address_size)

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
        self.assertEqual(typ.kind, "typedef array")
        self.assertEqual(typ.size, 8)


class TestCTypeGccArm(TestCTypeGcc):
    compiler_cmdline = "arm-none-eabi-gcc -c -g {infile} -o {outfile}"
