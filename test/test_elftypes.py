import os
import unittest

from pygti2.elfproxy import (
    CTypeDerived,
    CTypeDerivedArray,
    CTypeDerivedPointer,
    CTypeMacro,
    CTypeTypedef,
    CVarElf,
    create_ctypes,
    CType,
    CTypeArrayType,
    CTypeBaseType,
    CTypeMember,
    CTypePointerType,
)


class PyGti2TestElfTypes(unittest.TestCase):
    def setUp(self):
        if len(CType.ctypes_by_die) == 0:
            create_ctypes(os.path.join(os.path.dirname(__file__), "host_test"))

    def test_unsigned_char(self):
        ctype = CType.get("unsigned char")
        self.assertIsInstance(ctype, CTypeBaseType)
        self.assertEqual(ctype.size, 1)
        self.assertTrue(ctype.is_int)

    def test_uint8(self):
        ctype = CType.get("uint8_t")
        self.assertIsInstance(ctype, CTypeTypedef)
        self.assertEqual(ctype.size, 1)
        self.assertEqual(ctype.root.name, "unsigned char")
        self.assertTrue(ctype.is_int)

    def test_uint8ptr(self):
        ctype = CType.get("uint8_t *")
        self.assertIsInstance(ctype, CTypePointerType)
        self.assertEqual(ctype.size, ctype.die.dwarfinfo.config.default_address_size)
        self.assertEqual(ctype.root.name, "unsigned char")
        self.assertFalse(ctype.is_int)

    def test_uint8arr(self):
        ctype = CType.get("uint8_t [1024]")
        self.assertIsInstance(ctype, CTypeArrayType)
        self.assertEqual(ctype.length, 1024)
        self.assertEqual(ctype.size, 1024)
        self.assertEqual(ctype.root.name, "unsigned char")
        self.assertFalse(ctype.is_int)

    def test_uint32(self):
        ctype = CType.get("uint32_t")
        self.assertIsInstance(ctype, CTypeTypedef)
        self.assertEqual(ctype.size, 4)
        self.assertEqual(ctype.root.size, 4)
        self.assertTrue(ctype.is_int)

    def test_struct_1(self):
        ctype = CType.get("test_struct_1")
        self.assertIsInstance(ctype, CTypeTypedef)
        self.assertEqual(ctype.size, 1)
        self.assertEqual(list(ctype.members.keys()), ["a"])
        self.assertFalse(ctype.is_int)

    def test_struct_2(self):
        ctype = CType.get("test_struct_2")
        self.assertIsInstance(ctype, CTypeTypedef)
        self.assertEqual(ctype.size, 8)
        self.assertFalse(ctype.is_int)
        self.assertEqual(list(ctype.members.keys()), ["a", "b"])

        for membername, membersize in [("a", 1), ("b", 4)]:
            member = ctype.members[membername]
            self.assertIsInstance(member, CTypeMember)
            self.assertEqual(member.size, membersize)

    def test_struct_3(self):
        ctype = CType.get("test_struct_3")
        self.assertIsInstance(ctype, CTypeTypedef)
        self.assertEqual(ctype.size, ctype.die.dwarfinfo.config.default_address_size)
        self.assertFalse(ctype.is_int)

    def test_derived_pointer(self):
        ctype = CTypeDerived.create("test_struct_1 *")
        self.assertIsInstance(ctype, CTypeDerivedPointer)
        self.assertEqual(ctype.parent, CType.get("test_struct_1"))
        self.assertFalse(ctype.is_int)
        self.assertEqual(ctype.size, ctype._parent.die.dwarfinfo.config.default_address_size)

    def test_derived_array(self):
        ctype = CTypeDerived.create("uint32_t [10]")
        self.assertIsInstance(ctype, CTypeDerivedArray)
        self.assertEqual(ctype.parent, CType.get("uint32_t"))
        self.assertFalse(ctype.is_int)
        self.assertEqual(ctype.length, 10)
        self.assertEqual(ctype.size, 10 * 4)


class PyGti2TestElfVars(unittest.TestCase):
    def setUp(self):
        if len(CType.ctypes_by_die) == 0:
            create_ctypes(os.path.join(os.path.dirname(__file__), "host_test"))

    def test_gti_memory(self):
        var = CVarElf._cvars["gti2_memory"]
        self.assertGreater(var._addr, 0)
        self.assertEqual(var._name, "gti2_memory")
        self.assertEqual(var._type, CType.get("uint8_t [1024]"))


class PyGti2TestCTypeMacros(unittest.TestCase):
    def setUp(self):
        if len(CType.ctypes_by_die) == 0:
            create_ctypes(os.path.join(os.path.dirname(__file__), "host_test"))

    def test_enum_macros(self):
        ctype = CType.get("TEST_ENUM_2_A")
        self.assertIsInstance(ctype, CTypeMacro)
        self.assertTrue(ctype.is_int)
        self.assertEqual(ctype.value, 1)

        ctype = CType.get("TEST_ENUM_2_B")
        self.assertIsInstance(ctype, CTypeMacro)
        self.assertTrue(ctype.is_int)
        self.assertEqual(ctype.value, 2)

        ctype = CType.get("TEST_ENUM_2_C")
        self.assertIsInstance(ctype, CTypeMacro)
        self.assertTrue(ctype.is_int)
        self.assertEqual(ctype.value, 3)
