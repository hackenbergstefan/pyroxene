import unittest

from pyroxene.companion_generator import CompanionCodeGenerator, generate_companion

from .test_pyroxene import compile


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
        gen = CompanionCodeGenerator([], [], [], inline_src=src)
        gen.preprocess()
        src += generate_companion(gen)
        with compile(src) as lib:
            self.assertEqual(lib._pyroxene_func1(), 42)
            self.assertEqual(lib.func1(), 42)

            self.assertEqual(lib.func2(20, 21), 42)
            self.assertEqual(lib._pyroxene_func2(20, 21), 42)

            self.assertEqual(bytes(lib.func3()[0:3]), b"abc")
            self.assertEqual(bytes(lib._pyroxene_func3()[0:3]), b"abc")

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
        gen = CompanionCodeGenerator([], [], [], inline_src=src)
        gen.preprocess()
        src += generate_companion(gen)
        with compile(src) as lib:
            self.assertIn("_pyroxene_func1", lib.backend.types)
            self.assertIn("_pyroxene_ptr_func1", lib.backend.types)
            self.assertIn("_pyroxene_func2", lib.backend.types)
            self.assertIn("_pyroxene_ptr_func2", lib.backend.types)
            self.assertIn("_pyroxene_func3", lib.backend.types)

    def test_numeric_defines(self):
        src = """
            #include <stdint.h>
            #define MACRO_1 42
            #define MACRO_2(a, b) ((uint32_t)(a) + (b) + 1)
            #define MACRO_3 (41 == 41)
            #define MACRO_4() (41 == 41)
            """
        gen = CompanionCodeGenerator([], [], [], inline_src=src)
        gen.preprocess()
        src += generate_companion(gen)
        with compile(src) as lib:
            self.assertEqual(lib.MACRO_1, 42)
            self.assertEqual(lib.MACRO_2(20, 21), 42)
            self.assertEqual(lib.MACRO_3, 1)
            self.assertEqual(lib.MACRO_4(), 1)

    def test_string_defines(self):
        src = """
            #include <stdint.h>
            #define MACRO_1 "abc"
            #define MACRO_2(x) "abc" ## x
            """
        gen = CompanionCodeGenerator([], [], [], inline_src=src)
        gen.preprocess()
        src += generate_companion(gen)
        with compile(src) as lib:
            self.assertEqual(bytes(lib.MACRO_1[0:3]), b"abc")
            self.assertNotIn("_pyroxene_MACRO_2", lib.backend.types)

    def test_ignored(self):
        src = """
            #include <stdint.h>
            // Forward declarations
            extern int foo;
            // Declarations
            int foo_array[2];
            static int foo = 42;
            """
        gen = CompanionCodeGenerator([], [], [], inline_src=src)
        gen.preprocess()
        src = generate_companion(gen)
        self.assertEqual(src.splitlines()[2:], [])

    def test_empty_macro(self):
        src = """
            #include <stdint.h>
            #define JUST_A_DEFINE
            """
        gen = CompanionCodeGenerator([], [], [], inline_src=src)
        gen.preprocess()
        src = generate_companion(gen)
        self.assertEqual(src.splitlines()[2:], [])

    def test_statement_macros(self):
        src = """
            #include <stdint.h>
            #define loop_forever while(1);
            #define macro_1 __attribute__((macro))
            #define macro_2 inline
            #define macro_3(x) __attribute__((macro ## x))
            #define macro_4(x) macro ## x
            #define macro_5 { {0} }
            #define macro_6(x) ((x) > 0 ? 1 : 0)
            """
        gen = CompanionCodeGenerator([], [], [], inline_src=src)
        gen.preprocess()
        src = generate_companion(gen)
        self.assertEqual(src.splitlines()[2:], [])
