import cffi
import glob
import hashlib
import importlib
import os
import unittest

from pyroxene.memory_management import SimpleMemoryManager
from .test_pyroxene import compile


def cdef(cdef, src=""):
    ffi = cffi.FFI()
    ffi.cdef(cdef, override=True)
    modulename = "_test_cffi_compatibility_" + hashlib.sha256((cdef + src).encode()).hexdigest()
    ffi.set_source(modulename, cdef + src)
    ffi.compile()

    mod = importlib.import_module(modulename)
    for f in glob.glob(f"{modulename}*"):
        os.remove(f)
    return mod.ffi, mod.lib


class TestCffiCompatibility(unittest.TestCase):
    def test_struct_member_access(self):
        inc = """
            typedef struct {
                int a;
            } a_t;
            """
        src = """
            a_t a;
            unsigned char heap[1024];
        """
        ffi, _ = cdef(inc)
        with compile(inc + src) as lib:
            lib.memory_manager = SimpleMemoryManager(lib, "heap")
            var_pygti = lib.new("a_t *")
            var_pygti.a = 1
            var_cffi = ffi.new("a_t *")
            var_cffi.a = 1
            self.assertEqual(var_cffi[0].a, 1)
            self.assertEqual(var_cffi.a, 1)
            self.assertEqual(var_pygti[0].a, 1)
            self.assertEqual(var_pygti.a, 1)

    def test_arrays(self):
        inc = """
            typedef struct {
                int a;
                int b[3];
                unsigned char *c;
            } a_t;
            """
        src = """
            a_t a;
            unsigned char heap[1024];
        """
        ffi, _ = cdef(inc)
        with compile(inc + src) as lib:
            lib.memory_manager = SimpleMemoryManager(lib, "heap")
            var_pygti = lib.new("a_t [10]")
            var_cffi = ffi.new("a_t [10]")

            for i in var_cffi:
                i.a = 1
                self.assertEqual(i.a, 1)
            for i in var_pygti:
                i.a = 1
                self.assertEqual(i.a, 1)

            var_pygti = lib.new("int [10]")
            var_cffi = ffi.new("int [10]")
            self.assertEqual(list(var_cffi), 10 * [0])
            self.assertEqual(list(var_pygti), 10 * [0])

            var_pygti = lib.new("unsigned char [10]")
            var_cffi = ffi.new("unsigned char [10]")
            var2_pygti = lib.new("a_t *")
            var2_pygti.c = var_pygti
            var2_cffi = ffi.new("a_t *")
            var2_cffi.c = var_cffi
            self.assertEqual(bytes(var2_cffi.c[0:10]), 10 * b"\x00")
            self.assertEqual(bytes(var2_pygti.c[0:10]), 10 * b"\x00")
            self.assertEqual(bytes(var2_cffi.b), 3 * b"\x00")
            self.assertEqual(bytes(var2_pygti.b), 3 * b"\x00")
            self.assertEqual(bytes(var2_cffi.b[0:3]), 3 * b"\x00")
            self.assertEqual(bytes(var2_pygti.b[0:3]), 3 * b"\x00")

    def test_initializer(self):
        inc = """
            typedef struct {
                int a;
                int b;
            } a_t;
            """
        src = """
            a_t a;
            unsigned char heap[1024];
        """
        ffi, _ = cdef(inc)
        with compile(inc + src) as lib:
            lib.memory_manager = SimpleMemoryManager(lib, "heap")
            var_pygti = lib.new("int *", 1)
            var_cffi = ffi.new("int *", 1)
            self.assertEqual(var_cffi[0], 1)
            self.assertEqual(var_pygti[0], 1)

            var_pygti = lib.new("int [2]", [1, 2])
            var_cffi = ffi.new("int [2]", [1, 2])
            self.assertEqual(list(var_cffi[0:2]), [1, 2])
            self.assertEqual(list(var_pygti[0:2]), [1, 2])

            var_pygti = lib.new("a_t *", (1, 2))
            var_cffi = ffi.new("a_t *", (1, 2))
            self.assertEqual(var_cffi.a, 1)
            self.assertEqual(var_pygti.a, 1)

            var_pygti = lib.new("a_t *", [1, 2])
            var_cffi = ffi.new("a_t *", [1, 2])
            self.assertEqual(var_cffi.a, 1)
            self.assertEqual(var_cffi.b, 2)
            self.assertEqual(var_pygti.a, 1)
            self.assertEqual(var_pygti.b, 2)

            var_pygti = lib.new("a_t [2]", [[1], [2]])
            var_cffi = ffi.new("a_t [2]", [[1], [2]])
            self.assertEqual([v.a for v in var_cffi], [1, 2])
            self.assertEqual([v.a for v in var_pygti], [1, 2])

            var_pygti = lib.new("unsigned char []", b"abc")
            var_cffi = ffi.new("unsigned char []", b"abc")
            self.assertEqual(bytes(var_pygti[0:3]), b"abc")
            self.assertEqual(bytes(var_cffi[0:3]), b"abc")

    def test_stdlib(self):
        inc = """
            typedef struct {
                int a;
            } a_t;
            """
        src = """
            a_t a;
            unsigned char heap[1024];
        """
        ffi, _ = cdef(inc)
        with compile(inc + src) as lib:
            lib.memory_manager = SimpleMemoryManager(lib, "heap")
            var_pygti = lib.new("int [10]", 10 * [1])
            var_cffi = ffi.new("int [10]", 10 * [1])
            var2_pygti = lib.new("int [10]")
            var2_cffi = ffi.new("int [10]")

            lib.memmove(var2_pygti, var_pygti, lib.sizeof(var_pygti))
            ffi.memmove(var2_cffi, var_cffi, ffi.sizeof(var_cffi))

            self.assertEqual(list(var2_pygti), 10 * [1])
            self.assertEqual(list(var2_cffi), 10 * [1])

            var_pygti[0:10] = var_cffi[0:10] = 10 * [2]
            lib.memmove(lib.addressof(var2_pygti), var_pygti, lib.sizeof(var_pygti))
            ffi.memmove(ffi.addressof(var2_cffi), var_cffi, ffi.sizeof(var_cffi))

            self.assertEqual(list(var2_pygti), 10 * [2])
            self.assertEqual(list(var2_cffi), 10 * [2])

    def test_predefined(self):
        inc = """
            typedef struct {
                int a;
            } a_t;
            const int A = 42;
            const a_t B = {42};
            """
        _, ffilib = cdef(inc)
        with compile(inc) as lib:
            lib.memory_manager = SimpleMemoryManager(lib)
            self.assertEqual(lib.A, 42)
            self.assertEqual(ffilib.A, 42)
            self.assertEqual(lib.B.a, 42)
            self.assertEqual(ffilib.B.a, 42)

    def test_functioncalls(self):
        inc = """
            typedef unsigned int uint;
            uint func1(unsigned char *arr);
            uint func2(char *arr);
            void func3(uint *x);
            uint func4(uint x);
            """
        src = """
            uint func1(unsigned char *arr) { return arr[0]; }
            uint func2(char *arr) { return arr[0] + arr[1]; }
            void func3(uint *x) { *x = 42; }
            uint func4(uint x) { return x + 1; }
            """
        ffi, ffilib = cdef(inc, src)
        with compile(inc + src) as lib:
            lib.memory_manager = SimpleMemoryManager(lib)
            self.assertEqual(ffilib.func1(b"abc"), ord("a"))
            self.assertEqual(ffilib.func2(b"abc"), ord("a") + ord("b"))
            var = ffi.new("uint *")
            ffilib.func3(var)
            self.assertEqual(var[0], 42)
            self.assertEqual(ffilib.func4(var[0]), 43)

            self.assertEqual(lib.func1(b"abc"), ord("a"))
            self.assertEqual(lib.func2(b"abc"), ord("a") + ord("b"))
            var = lib.new("uint *")
            lib.func3(var)
            self.assertEqual(var[0], 42)
            self.assertEqual(lib.func4(var[0]), 43)
