import logging
import struct
from typing import List


class Communicator:
    def __init__(self):
        self.sizeof_long: int = 0

    def memory_read(self, addr: int, size: int) -> bytes:
        ...

    def memory_write(self, addr: int, data: bytes) -> None:
        ...

    def call(self, addr: int, numbytes_return: int, args: List[int]) -> int:
        ...


class CommunicatorStub(Communicator):
    def __init__(self):
        super().__init__()
        self.memory = {}

    def memory_read(self, addr: int, size: int) -> bytes:
        result = bytes([self.memory.get(location, 0) for location in range(addr, addr + size)])
        logging.getLogger(__name__).debug(f"PyroxeneCommand.memory_read {addr}, {size} -> {result.hex()}")
        return result

    def memory_write(self, addr: int, data: bytes) -> None:
        logging.getLogger(__name__).debug(f"PyroxeneCommand.memory_write {addr}, {data.hex()}")
        for i, b in enumerate(data):
            self.memory[addr + i] = b


class PyroxeneCommunicator(Communicator):
    cmd_max_length = 1024
    cmd_header_length = 4

    def marshal_long(self, x: int) -> bytes:
        return x.to_bytes(self.sizeof_long, "big")

    def unmarshal_long(self, x: bytes) -> int:
        return int.from_bytes(x, "big")

    def command(self, cmd, data, expected):
        self.write(struct.pack("!HH", cmd, len(data)) + data)
        response = self.read(3)
        if response != b"ACK":
            raise Exception(f"Command did not respond successfully. response: {response}")
        response = self.read(expected)
        return response

    def call(self, addr: int, numbytes_return: int, args: List[int]) -> int:
        if numbytes_return > 0:
            numbytes_return = self.sizeof_long
        callargs = (
            self.marshal_long(addr),
            struct.pack("!HH", numbytes_return, len(args)),
            b"".join(self.marshal_long(arg) for arg in args),
        )
        logging.getLogger(__name__).debug(
            f"PyroxeneCommand.call {' '.join(c.hex() for c in callargs)}, {numbytes_return} -> ..."
        )
        result = self.command(3, b"".join(callargs), numbytes_return)
        logging.getLogger(__name__).debug(f"PyroxeneCommand.call ... -> {result}")
        return self.unmarshal_long(result)

    def memory_read(self, addr: int, size: int) -> bytes:
        logging.getLogger(__name__).debug(f"PyroxeneCommand.memory_read 0x{addr:08x}, {size} -> ...")
        result = self.command(
            1,
            self.marshal_long(addr) + self.marshal_long(size),
            size,
        )
        logging.getLogger(__name__).debug(f"PyroxeneCommand.memory_read ... -> {result.hex()}")
        return result

    def memory_write(self, addr: int, data: bytes) -> None:
        if len(data) == 0:
            return
        logging.getLogger(__name__).debug(f"PyroxeneCommand.memory_write 0x{addr:08x}, {data.hex()}")
        while len(data) != 0:
            portion = data[: self.cmd_max_length - self.sizeof_long - self.cmd_header_length]
            self.command(2, self.marshal_long(addr) + portion, 0)
            addr += len(portion)
            data = data[len(portion) :]

    def echo(self, data: bytes) -> bytes:
        result = self.command(0, data, len(data))
        logging.getLogger(__name__).debug(f"PyroxeneCommand.echo {data!r} -> {result!r}")
        return result


class PyroxeneSerialCommunicator(PyroxeneCommunicator):
    def __init__(self, port, baud, sizeof_long):
        self.sizeof_long = sizeof_long
        import serial  # type: ignore[import]

        self.ser = serial.Serial(port, baud)
        while True:
            self.ser.read_all()
            self.ser.timeout = 0.5
            if self.echo(b"hello") == b"hello":
                break
        self.ser.timeout = None

    def read(self, length):
        data = self.ser.read(length)
        if len(data) != length:
            raise TimeoutError("Device took too long to respond.")
        return data

    def write(self, data):
        self.ser.write(data)


class PyroxeneSocketCommunicator(PyroxeneCommunicator):
    def __init__(self, address, sizeof_long):
        self.sizeof_long = sizeof_long
        import socket

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(address)
        if self.echo(b"hello") != b"hello":
            raise Exception("Something went wrong.")

    def read(self, length):
        data = b""
        while len(data) < length:
            data += self.sock.recv(length - len(data))
        return data

    def write(self, data):
        self.sock.sendall(data)

    def __del__(self):
        self.sock.close()
