import os

import hypothesis
import hypothesis.strategies

import pygti2
import pygti2.device_commands
import pygti2.device_proxy
import pygti2.elfproxy
import pygti2.memory_management

# import logging

# logging.basicConfig(level=logging.DEBUG)

hypothesis.settings.register_profile("default", deadline=None, max_examples=10)
hypothesis.settings.load_profile("default")

lib = None


def connect():
    global lib
    if not lib:
        pygti2.elfproxy.create_ctypes(os.path.join(os.path.dirname(__file__), "host_test"))
        lib = pygti2.device_proxy.LibProxy(
            communication=pygti2.device_commands.SocketCommand(("localhost", 1234)),
            memory_manager=pygti2.memory_management.SimpleMemoryManager("gti2_memory"),
        )
    return lib
