import unittest

from pygti2.device_proxy import CType
from . import connect


lib = connect()


class PyGti2TestCtypes(unittest.TestCase):
    def test_uint8(self):
        ctype = CType.get(lib._mi, "uint8_t")
        self.assertEqual(ctype.is_array, False)
        self.assertEqual(ctype.is_pointer, False)
        self.assertEqual(ctype.size, 1)
        self.assertEqual(ctype.root.name, "unsigned char")
        self.assertEqual(ctype.base, ctype)

    def test_uint8ptr(self):
        ctype = CType.get(lib._mi, "uint8_t *")
        self.assertEqual(ctype.is_array, False)
        self.assertEqual(ctype.is_pointer, True)
        self.assertEqual(ctype.size, lib._mi.sizeof("void *"))
        self.assertEqual(ctype.root.name, "unsigned char")
        self.assertEqual(ctype.base, CType.get(lib._mi, "uint8_t"))

    def test_uint8arr(self):
        ctype = CType.get(lib._mi, "uint8_t [10]")
        self.assertEqual(ctype.is_array, True)
        self.assertEqual(ctype.is_pointer, True)
        self.assertEqual(ctype.size, 10)
        self.assertEqual(ctype.root.name, "unsigned char")
        self.assertEqual(ctype.base, CType.get(lib._mi, "uint8_t"))

    def test_uint32(self):
        ctype = CType.get(lib._mi, "uint32_t")
        self.assertEqual(ctype.is_array, False)
        self.assertEqual(ctype.is_pointer, False)
        self.assertEqual(ctype.size, 4)
        self.assertEqual(ctype.root.size, 4)
        self.assertEqual(ctype.base, ctype)

    def test_uint32arr(self):
        ctype = CType.get(lib._mi, "uint32_t [16]")
        self.assertEqual(ctype.is_array, True)
        self.assertEqual(ctype.is_pointer, True)
        self.assertEqual(ctype.size, 16 * 4)
        self.assertEqual(ctype.root.size, 4)
        self.assertEqual(ctype.base, CType.get(lib._mi, "uint32_t"))
