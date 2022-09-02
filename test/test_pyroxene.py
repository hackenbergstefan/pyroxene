from contextlib import contextmanager
from tempfile import TemporaryDirectory
import os
import signal
import subprocess
import time
import unittest

from pyroxene.device_commands import PyroxeneSocketCommunicator
from pyroxene.device_proxy import LibProxy, VarProxy
from pyroxene.elfbackend import ElfBackend
from pyroxene.memory_management import SimpleMemoryManager
from pyroxene.companion_generator import CompanionCodeGenerator, generate_companion


@contextmanager
def compile(source: str, print_output=False) -> LibProxy:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    with TemporaryDirectory() as tmpdir:
        tmpdir = "."
        with open(os.path.join(tmpdir, "src.c"), "w") as fp:
            fp.write(source)

        subprocess.check_call(
            "gcc -O2 -static -g -Wl,--no-gc-sections src.c".split(" ")
            + f"{root}/pyroxene/cshim/pyroxene.c {root}/test/host/main.c".split(" ")
            + f"-I{root}/pyroxene/cshim -o prog".split(" "),
            cwd=tmpdir,
        )
        if print_output:
            print(
                subprocess.check_output(
                    "readelf.py --debug-dump=info prog".split(" "),
                    cwd=tmpdir,
                ).decode()
            )
        backend = ElfBackend(os.path.join(tmpdir, "prog"))
        p = subprocess.Popen("./prog", cwd=tmpdir)
        time.sleep(0.1)  # Wait til prog started. TODO: Is there a smarter solution?
        try:
            yield LibProxy(
                backend,
                PyroxeneSocketCommunicator(("localhost", 9999), backend.sizeof_voidp),
            )
        except:  # noqa: E722 do not use bare except
            p.send_signal(signal.SIGTERM)
            p.wait(1)
            p.kill()
            raise
        finally:
            p.send_signal(signal.SIGTERM)
            p.wait(1)
            p.kill()


class TestPyroxene(unittest.TestCase):
    def test_sizeof(self):
        with compile(
            """
            #include <stdint.h>
            """,
        ) as lib:
            self.assertEqual(lib.sizeof(lib.pyroxene_memory), 4096)

            var = lib._new("uint8_t *", lib.pyroxene_memory._address)
            self.assertEqual(lib.sizeof(var), 1)

            var = lib._new("uint8_t [10]", lib.pyroxene_memory._address)
            self.assertEqual(lib.sizeof(var), 10)

            var = lib._new("uint32_t [10]", lib.pyroxene_memory._address)
            self.assertEqual(lib.sizeof(var), 40)

    def test_read_write_pyroxene_memory(self):
        with compile(
            """
            #include <stdint.h>
            """,
        ) as lib:
            mem = lib.pyroxene_memory
            self.assertEqual(mem._type.kind, "int")

            # Write and read single value
            mem[0] = 7
            self.assertEqual(mem[0], 7)

            # Write and read slice
            mem[0:10] = 10 * [0xFF]
            self.assertEqual(mem[0:10], 10 * [0xFF])

    def test_allocation(self):
        with compile(
            """
            #include <stdint.h>
            typedef struct {
                uint8_t a;
            } a_t;
            a_t _;
            """,
        ) as lib:
            var = lib._new("uint8_t [10]", lib.pyroxene_memory._address)
            lib.memset(lib.pyroxene_memory, 0, lib.sizeof(lib.pyroxene_memory))

            # Write and read single value
            var[0] = 7
            self.assertEqual(var[0], 7)

            # Write and read slice
            var[0:10] = 10 * [0xFF]
            self.assertEqual(var[0:10], 10 * [0xFF])

            # Write and read pointer
            var2 = lib._new("uint8_t **", lib.pyroxene_memory._address + 16)
            var2[0] = var
            self.assertEqual(var2[0][0], 0xFF)

            # Write and read struct
            var3 = lib._new("a_t *", lib.pyroxene_memory._address + 32)
            var3.a = var
            self.assertEqual(var3.a, 0xFF)

    def test_function_call(self):
        src = """
            #include <stdint.h>
            int func1(void) { return -42; }
            int func2(int a) { return 1 + a; }
            int func3(int a, int b) { return 1 + a + b; }

            uint64_t func4(uint64_t a) { return (uint64_t)~a; }
            typedef struct {
                uint32_t a;
                uint32_t b;
            } a_t;
            a_t func5(uint32_t a, uint32_t b) { a_t x = { a, b }; return x; }

            typedef struct {
                uint32_t a;
                uint32_t b;
                uint32_t c;
            } b_t;
            b_t func6(uint32_t a, uint32_t b, uint32_t c) { b_t x = { a, b, c }; return x; }
            inline b_t func7(uint32_t a, uint32_t b, uint32_t c) { b_t x = { a, b, c }; return x; }
        """
        gen = CompanionCodeGenerator([], [], [], inline_src=src)
        gen.preprocess()
        src += generate_companion(gen)
        with compile(src) as lib:
            lib.memory_manager = SimpleMemoryManager(lib)
            self.assertEqual(lib.func1(), -42)
            self.assertEqual(lib.func2(41), 42)
            self.assertEqual(lib.func3(21, 20), 42)
            self.assertEqual(lib.func4(1), 0xFFFFFFFFFFFFFFFE)
            self.assertEqual(lib.func4(0xFFFFFFFFFFFFFFFE), 1)
            result = lib.func5(1, 2)
            self.assertEqual(result.a, 1)
            self.assertEqual(result.b, 2)
            # FIXME: Implement generation of companion functions for non-inlines
            # result = lib.func6(1, 2, 3)
            # self.assertEqual(result.a, 1)
            # self.assertEqual(result.b, 2)
            # self.assertEqual(result.c, 3)
            result = lib.func7(4, 5, 6)
            self.assertEqual(result.a, 4)
            self.assertEqual(result.b, 5)
            self.assertEqual(result.c, 6)

    def test_consts(self):
        src = """
            #include <stdint.h>
            const uint32_t X = 42;
            uint32_t Y = 42;
            #define MAGIC ((int32_t)(-42))
            """
        gen = CompanionCodeGenerator([], [], [], inline_src=src)
        gen.preprocess()
        src += generate_companion(gen)
        with compile(src) as lib:
            self.assertEqual(lib.X, 42)
            self.assertEqual(lib.backend.types["X"].data, (42).to_bytes(4, lib.backend.endian))

            self.assertEqual(lib.Y, 42)
            self.assertIsNone(lib.backend.types["Y"].data)

            self.assertEqual(lib.MAGIC, -42)
            VarProxy.cffi_compatibility_mode = False
            self.assertIsNotNone(lib.MAGIC._data)
            self.assertIsNotNone(lib.X._data)
            VarProxy.cffi_compatibility_mode = True

    def test_array_allocation(self):
        with compile("") as lib:
            lib.memory_manager = SimpleMemoryManager(lib)
            var = lib.new("uint8_t[]", 10)
            self.assertEqual(var._length, 10)
            self.assertEqual(len(var), 10)
            self.assertEqual(var[0:10], 10 * [0])

            var = lib.new("uint8_t[]", bytes(range(10)))
            self.assertEqual(var._length, 10)
            self.assertEqual(len(var), 10)
            self.assertEqual(bytes(var[0:10]), bytes(range(10)))

    def test_allocation_with_parameters(self):
        with compile(
            """
            #include <stdint.h>
            uint32_t init32(void) { return 42; }
            """,
        ) as lib:
            lib.memory_manager = SimpleMemoryManager(lib)
            var = lib.new("uint32_t *", 1)
            self.assertEqual(var[0], 1)

            var2 = lib.new("uint32_t *", var)
            self.assertEqual(var2[0], 1)

            var = lib.new("uint32_t *", lib.init32())
            self.assertEqual(var[0], 42)
