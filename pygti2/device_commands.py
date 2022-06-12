import logging
import struct


class PyGti2Command:
    sizeof_long = 4

    def pack_long(self, x: int) -> bytes:
        return x.to_bytes(self.sizeof_long, "big")

    def unpack_long(self, x: bytes) -> int:
        return int.from_bytes(x, "big")

    def command(self, cmd, data, expected):
        self.write(struct.pack("!HH", cmd, len(data)) + data)
        return self.read(expected)

    def call(self, addr: int, numbytes_return: int, *args) -> bytes:
        from .device_proxy import VarProxy

        packed_args = b""
        for arg in args:
            if isinstance(arg, int):
                packed_args += self.pack_long(arg)
            elif isinstance(arg, VarProxy):
                packed_args += self.pack_long(arg._addr)
            else:
                packed_args += arg

        callargs = (
            self.pack_long(addr),
            struct.pack("!HH", numbytes_return, len(args)),
            packed_args,
        )
        result = self.command(3, b"".join(callargs), numbytes_return)
        logging.getLogger(__name__).debug(f"PyGti2Command.call {callargs}, {numbytes_return} -> {result}")
        return result

    def memory_read(self, addr: int, size: int) -> bytes:
        # print("memory_read", hex(addr), size)
        result = self.command(
            1,
            self.pack_long(addr) + self.pack_long(size),
            size,
        )
        logging.getLogger(__name__).debug(f"PyGti2Command.memory_read {addr}, {size} -> {result}")
        return result

    def memory_write(self, addr: int, data: bytes) -> None:
        logging.getLogger(__name__).debug(f"PyGti2Command.memory_write {addr}, {data}")
        return self.command(2, self.pack_long(addr) + data, 0)

    def echo(self, data: bytes) -> bytes:
        result = self.command(0, data, len(data))
        logging.getLogger(__name__).debug(f"PyGti2Command.echo {data} -> {result}")
        return result


class SerialCommand(PyGti2Command):
    def __init__(self, port, baud):
        import serial

        self.ser = serial.Serial(port, baud)
        while True:
            self.ser.read_all()
            self.ser.timeout = 0.5
            if self.echo(b"hello") == b"hello":
                break
        self.ser.timeout = None

    def read(self, length):
        return self.ser.read(length)

    def write(self, data):
        self.ser.write(data)


class SocketCommand(PyGti2Command):
    def __init__(self, address):
        import socket

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(address)

    def read(self, length):
        return self.sock.recv(length)

    def write(self, data):
        self.sock.sendall(data)
