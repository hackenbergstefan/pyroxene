import unittest
import cffi

from pygti2.memory_management import SimpleMemoryManager
from .test_gti2 import compile


def cdef(src):
    ffi = cffi.FFI()
    ffi.cdef(src)
    return ffi


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
        ffi = cdef(inc)
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
            } a_t;
            """
        src = """
            a_t a;
            unsigned char heap[1024];
        """
        ffi = cdef(inc)
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
        ffi = cdef(inc)
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
        ffi = cdef(inc)
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
