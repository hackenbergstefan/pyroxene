from contextlib import contextmanager
import signal
import subprocess
import os
from tempfile import TemporaryDirectory
import unittest
from pygti2.device_commands import Gti2SocketCommunicator
from pygti2.device_proxy import LibProxy

from pygti2.elfbackend import ElfBackend


@contextmanager
def compile(source: str, print_output=False) -> LibProxy:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    with TemporaryDirectory() as tmpdir:
        tmpdir = "."
        with open(os.path.join(tmpdir, "src.c"), "w") as fp:
            fp.write(source)

        subprocess.check_call(
            "gcc -O2 -static -g -Wl,--no-gc-sections src.c".split(" ")
            + f"{root}/src/gti2.c {root}/test/host/main.c -I{root}/src -o prog".split(" "),
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
        try:
            yield LibProxy(
                backend,
                Gti2SocketCommunicator(("localhost", 9999), backend.sizeof_voidp),
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


class TestPyGti2(unittest.TestCase):
    def test_sizeof(self):
        with compile(
            """
            #include <stdint.h>
            """,
        ) as lib:
            self.assertEqual(lib.sizeof(lib.gti2_memory), 1024)

            var = lib._new("uint8_t *", lib.gti2_memory.address)
            self.assertEqual(lib.sizeof(var), 1)

            var = lib._new("uint8_t [10]", lib.gti2_memory.address)
            self.assertEqual(lib.sizeof(var), 10)

            var = lib._new("uint32_t [10]", lib.gti2_memory.address)
            self.assertEqual(lib.sizeof(var), 40)

    def test_read_write_gti2_memory(self):
        with compile(
            """
            #include <stdint.h>
            """,
        ) as lib:
            mem = lib.gti2_memory
            self.assertEqual(mem.type.kind, "int")

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
            var = lib._new("uint8_t *", lib.gti2_memory.address)
            lib.memset(lib.gti2_memory, 0, lib.sizeof(lib.gti2_memory))

            # Write and read single value
            var[0] = 7
            self.assertEqual(var[0], 7)

            # Write and read slice
            var[0:10] = 10 * [0xFF]
            self.assertEqual(var[0:10], 10 * [0xFF])

            # Write and read pointer
            var2 = lib._new("uint8_t **", lib.gti2_memory.address + 16)
            var2[0] = var
            self.assertEqual(var2[0][0], 0xFF)

            # Write and read struct
            var3 = lib._new("a_t *", lib.gti2_memory.address + 32)
            var3.a = var
            self.assertEqual(var3.a, 0xFF)

    def test_function_call(self):
        with compile(
            """
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
            """,
        ) as lib:
            self.assertEqual(lib.func1(), -42)
            self.assertEqual(lib.func2(41), 42)
            self.assertEqual(lib.func3(21, 20), 42)
            self.assertEqual(lib.func4(1), 0xFFFFFFFFFFFFFFFE)
            self.assertEqual(lib.func4(0xFFFFFFFFFFFFFFFE), 1)
            result = lib.func5(1, 2)
            self.assertEqual(result.a, 1)
            self.assertEqual(result.b, 2)

    def test_consts(self):
        with compile(
            """
            #include <stdint.h>
            const uint32_t X = 42;
            """,
        ) as lib:
            self.assertEqual(lib.X[0], 42)
