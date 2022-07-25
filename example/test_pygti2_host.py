import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from pygti2.device_commands import Gti2SocketCommunicator  # noqa: E402 module level import not at top of file
from pygti2.device_proxy import LibProxy  # noqa: E402 module level import not at top of file
from pygti2.elfbackend import ElfBackend  # noqa: E402 module level import not at top of file
from pygti2.memory_management import SimpleMemoryManager  # noqa: E402 module level import not at top of file


if __name__ == "__main__":
    backend = ElfBackend("./host/host_example")
    lib = LibProxy(backend, Gti2SocketCommunicator(("localhost", 9999), backend.sizeof_voidp))
    lib.memory_manager = SimpleMemoryManager(lib)

    import test

    test.lib = lib
    test.ffi = lib

    unittest.main(module=None)
