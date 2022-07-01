import unittest

from pygti2.companion_generator import CompanionGenerator

from .test_gti2 import compile


class TestCompanionGenerator(unittest.TestCase):
    def test_inline_function_call(self):
        src = """
            #include <stdint.h>
            inline int func1(void)
            {
                return 42;
            }
            inline uint32_t func2(int a, int b)
            {
                return 1 + a + b;
            }
            """
        src += "\n" + CompanionGenerator().parse_and_generate_companion_source(src)
        with compile(src) as lib:
            self.assertEqual(lib._gti2_func1(), 42)
            self.assertEqual(lib.func1(), 42)

            self.assertEqual(lib.func2(20, 21), 42)
            self.assertEqual(lib._gti2_func2(20, 21), 42)

    def test_numeric_defines(self):
        src = """
            #include <stdint.h>
            #define MACRO_1 42
            #define MACRO_2(a, b) ((uint32_t)(a) + (b) + 1)
            """
        src += "\n" + CompanionGenerator().parse_and_generate_companion_source(src)
        with compile(src) as lib:
            self.assertEqual(lib.MACRO_1[0], 42)
            self.assertEqual(lib.MACRO_2(20, 21), 42)
