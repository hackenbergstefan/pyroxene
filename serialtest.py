import pygdbmi
import pygdbmi.gdbcontroller

import proxy


def pprint(bytes):
    if not bytes:
        return
    print(" ".join(f"{b:02x}" for b in bytes))


def main():
    libproxy = proxy.LibProxy(
        pygdbmi.gdbcontroller.GdbController(
            [
                "gdb-multiarch",
                "--nx",
                "--quiet",
                "--interpreter=mi3",
                "./build/CY8CPROTO-062-4343W/Debug/mtb-example-psoc6-uart-transmit-receive.elf",
            ],
            time_to_check_for_additional_output_sec=0.1,
        ),
        proxy.GtiSerialProxy("/dev/ttyACM0", 576000),
    )
    # Demo variable read and write
    libproxy.scratch_buffer[0:16] = 16 * b"\xff"
    print(libproxy.scratch_buffer[0:32])
    libproxy.scratch_buffer[0:16] = 16 * b"\x00"
    print(libproxy.scratch_buffer[0:32])

    # Demo function call
    pprint(libproxy.myfunc1())
    pprint(libproxy.myfunc2())
    pprint(libproxy.myfunc3(43))

    print(libproxy.scratch_buffer[0:32])


def gdbmi():
    mi = pygdbmi.gdbcontroller.GdbController(
        [
            "gdb-multiarch",
            "--nx",
            "--quiet",
            "--interpreter=mi3",
        ],
        time_to_check_for_additional_output_sec=0.1,
    )

    print(
        mi.write(
            "-file-exec-and-symbols ./build/CY8CPROTO-062-4343W/Debug/mtb-example-psoc6-uart-transmit-receive.elf"
        )
    )
    print(mi.write("-data-evaluate-expression myfunc1"))
    print(mi.write("-data-evaluate-expression myfunc4"))
    print(mi.write("-data-evaluate-expression scratch_buffer"))
    print(mi.write("-data-evaluate-expression &scratch_buffer"))
    print(mi.write("-data-evaluate-expression &scratch_buffer"))
    print(mi.write("-symbol-info-variables --name scratch_buffer"))
    print(mi.write("-symbol-info-functions --name myfunc3"))


if __name__ == "__main__":
    main()
