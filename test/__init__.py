import os

import hypothesis
import hypothesis.strategies

import pygti2
import pygti2.device_commands
import pygti2.device_proxy
import pygti2.gdbmimiddleware

# import logging

# logging.basicConfig(level=logging.DEBUG)

hypothesis.settings.register_profile("default", deadline=None, max_examples=10)
hypothesis.settings.load_profile("default")

lib = None


def connect():
    global lib
    if not lib:
        lib = pygti2.device_proxy.LibProxy(
            pygti2.gdbmimiddleware.GdbmiMiddleware(
                command=[
                    "gdb",
                    "--nx",
                    "--quiet",
                    "--interpreter=mi3",
                    os.path.join(os.path.dirname(__file__), "host_test"),
                ],
                # time_to_check_for_additional_output_sec=0.1,
            ),
            pygti2.device_commands.SocketCommand(("localhost", 1234)),
        )
    return lib
    # global lib
    # lib = proxy.LibProxy(
    #     pygdbmi.gdbcontroller.GdbController(
    #         [
    #             "gdb-multiarch",
    #             "--nx",
    #             "--quiet",
    #             "--interpreter=mi3",
    #             "./build/CY8CPROTO-062-4343W/Debug/mtb-example-psoc6-uart-transmit-receive.elf",
    #         ],
    #         time_to_check_for_additional_output_sec=0.1,
    #     ),
    #     proxy.GtiSerialProxy("/dev/ttyACM0", 576000),
    # )
