# import os
# import re

# import hypothesis
# import hypothesis.strategies

# import pygti2
# import pygti2.device_commands
# import pygti2.device_proxy
# import pygti2.elfproxy
# import pygti2.memory_management

# # import logging

# # logging.basicConfig(level=logging.DEBUG)

# hypothesis.settings.register_profile("default", deadline=None, max_examples=10)
# hypothesis.settings.load_profile("default")

# lib = None
# dut = "host"


# def connect():
#     global lib
#     if not lib:
#         if dut == "psoc":
#             elffile = os.path.join(
#                 os.path.dirname(__file__),
#                 "psoc/build/CY8CPROTO-062-4343W/Debug/gti2_test.elf",
#             )
#             comm = pygti2.device_commands.SerialCommand("/dev/ttyACM0", 576000)
#         else:
#             elffile = os.path.join(os.path.dirname(__file__), "host/host_test")
#             comm = pygti2.device_commands.SocketCommand(("localhost", 9999))
#         pygti2.elfproxy.create_ctypes(
#             file=elffile,
#             compilation_unit_filter=lambda cuname: re.match(r".*(gti2|test_\w+|main)\.c", cuname),
#         ),
#         lib = pygti2.device_proxy.LibProxy(
#             communication=comm,
#             memory_manager=pygti2.memory_management.SimpleMemoryManager("gti2_memory"),
#         )
#     return lib
