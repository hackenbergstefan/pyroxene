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
            inline const char *func3(void)
            {
                return "abc";
            }
            """
        src += "\n" + CompanionGenerator().parse_and_generate_companion_source(src)
        with compile(src) as lib:
            self.assertEqual(lib._gti2_func1(), 42)
            self.assertEqual(lib.func1(), 42)

            self.assertEqual(lib.func2(20, 21), 42)
            self.assertEqual(lib._gti2_func2(20, 21), 42)

            self.assertEqual(bytes(lib.func3()[0:3]), b"abc")
            self.assertEqual(bytes(lib._gti2_func3()[0:3]), b"abc")

    def test_inline_functions_returning_struct(self):
        src = """
            typedef struct {
                int x;
            } a_t;
            inline a_t func1(void)
            {
                a_t a = {42};
                return a;
            }
            inline a_t func2(int x)
            {
                a_t a = {x};
                return a;
            }
            inline void func3(a_t *a)
            {
                a = 0;
            }
            inline const char *func4(void)
            {
                return "abc";
            }
            """
        src += CompanionGenerator().parse_and_generate_companion_source(src)
        with compile(src) as lib:
            self.assertIn("_gti2_func1", lib.backend.types)
            self.assertIn("_gti2_ptr_func1", lib.backend.types)
            self.assertIn("_gti2_func2", lib.backend.types)
            self.assertIn("_gti2_ptr_func2", lib.backend.types)
            self.assertIn("_gti2_func3", lib.backend.types)
            var = lib._new("a_t *", address=lib.gti2_memory.address)
            lib._gti2_ptr_func1(var)
            self.assertEqual(var.x, 42)
            var = lib._new("char **", address=lib.gti2_memory.address)
            lib._gti2_ptr_func4(var)
            self.assertEqual(bytes(var[0][0:3]), b"abc")

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

    def test_ignored(self):
        src = """
            #include <stdint.h>
            // Functions
            int func(void);
            int func(void)
            {
                return 0;
            }
            // Forward declarations
            extern int foo;
            // Declarations
            int foo_array[2];
            static int foo = 42;
            """
        src = CompanionGenerator().parse_and_generate_companion_source(src)
        self.assertEqual(src.strip(), "")

    def test_empty_macro(self):
        src = """
            #include <stdint.h>
            #define JUST_A_DEFINE
            """
        src = CompanionGenerator().parse_and_generate_companion_source(src)
        self.assertEqual(src.strip(), "")

    def test_statement_macros(self):
        src = """
            #include <stdint.h>
            #define loop_forever while(1);
            #define macro_1 __attribute__((macro))
            #define macro_2 inline
            #define macro_3(x) __attribute__((macro ## x))
            #define macro_4(x) macro ## x
            #define macro_5 { {0} }
            """
        src = CompanionGenerator().parse_and_generate_companion_source(src)
        self.assertEqual(src.strip(), "")
