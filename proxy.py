import functools
import re
import struct
from typing import Dict, List

from pygdbmi.gdbcontroller import GdbController
import serial


class GtiSerialProxy:
    def __init__(self, port, baud):
        self.ser = serial.Serial(port, baud)
        while True:
            self.ser.read_all()
            self.ser.timeout = 0.5
            echo = self.echo(b"hello")
            if echo == b"hello":
                break
        self.ser.timeout = None

    def call(self, addr: int, numbytes_return: int, *args):
        packed_args = b""
        for arg in args:
            if isinstance(arg, int):
                packed_args += struct.pack("!I", arg)
            else:
                packed_args += arg
        return self.command(
            3,
            struct.pack("!IHH", addr, numbytes_return, len(args)) + packed_args,
            numbytes_return,
        )

    def command(self, cmd, data, expected):
        self.ser.write(struct.pack("!HH", cmd, len(data)) + data)
        return self.ser.read(expected)

    def memory_read(self, addr: int, size: int) -> bytes:
        return self.command(1, struct.pack("!II", addr, size), size)

    def memory_write(self, addr: int, data: bytes) -> None:
        return self.command(2, struct.pack("!I", addr) + data, 0)

    def echo(self, data: bytes) -> bytes:
        return self.command(0, data, len(data))


class VarProxy:
    def __init__(self, libproxy: "LibProxy", addr, type, name=None) -> None:
        self._libproxy = libproxy
        self._addr = addr
        self._type = type
        self._name = name

    # def _resolve(self):
    #     res = self._libproxy._mi_write(f'-interpreter-exec console "ptype {self._type}"')
    #     type = [r["payload"].strip().replace("type = ", "") for r in res if r["payload"]]
    #     size = 0
    #     for t in type:
    #         if "{" in t or "}" in t:
    #             continue
    #         if t.endswith(";"):
    #             t = " ".join(t.split(" ")[:1])
    #         size += int(
    #             self._libproxy._mi_write(f'-data-evaluate-expression "sizeof({t})"')[-1]["payload"]["value"]
    #         )
    #     self._size = size

    def __setattr__(self, name: str, value: any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            offset = int(
                self._libproxy._mi_write(f'-data-evaluate-expression "&(({self._type} *)0)->{name}"')[-1][
                    "payload"
                ]["value"],
                16,
            )
            return self._libproxy._proxy.memory_write(self._addr + offset, value)

    def __getattr__(self, name: str) -> bytes:
        offset = int(
            self._libproxy._mi_write(f'-data-evaluate-expression "&(({self._type} *)0)->{name}"')[-1][
                "payload"
            ]["value"],
            16,
        )
        size = int(
            self._libproxy._mi_write(f'-data-evaluate-expression "sizeof((({self._type} *)0)->{name})"')[-1][
                "payload"
            ]["value"]
        )
        return self._libproxy._proxy.memory_read(self._addr + offset, size)

    def __repr__(self) -> str:
        return f"<VarProxy {self._type} @ 0x{self._addr:08x}>"

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self._libproxy._proxy.memory_read(self._addr + key.start, key.stop - key.start)

    def __setitem__(self, key, data):
        if isinstance(key, slice):
            return self._libproxy._proxy.memory_write(self._addr + key.start, data)


class FuncProxy:
    def __init__(self, libproxy: "LibProxy", name: str, addr: int, returnvalue: str, *args):
        self._libproxy = libproxy
        self._name = name
        self._addr = addr
        self._returnvalue = returnvalue
        self._args = args

    def __call__(self, *args):
        result = self._libproxy._proxy.call(
            self._addr,
            # TODO: Improve!
            0 if self._returnvalue == "void" else 4,
            *args,
        )

        if "int" in self._returnvalue:
            return struct.unpack("!I", result)[0]
        else:
            return result


class LibProxy:
    def __init__(self, mi: GdbController, proxy: GtiSerialProxy):
        self._mi = mi
        self._proxy = proxy

    def _getattr_function(self, name: str) -> FuncProxy:
        result = self._mi_write(f"-data-evaluate-expression {name}")
        result = result[-1]["payload"]["value"]
        match = re.match(r"{(?P<ret>[\S ]+) \((?P<args>.+)\)} (?P<addr>0x[0-9a-f]+) <(?P<name>\S+)>", result)
        return FuncProxy(
            self,
            name,
            int(match.group("addr"), 16),
            match.group("ret"),
            *match.group("args").split(", "),
        )

    def _getattr_variable(self, name: str) -> VarProxy:
        result = self._mi_write(f"-symbol-info-variables --name {name}")
        # What a fuck!?
        type = result[-1]["payload"]["symbols"]["debug"][0]["symbols"][0]["type"]
        addr = int(
            self._mi_write(f"-data-evaluate-expression &{name}")[-1]["payload"]["value"].split(" ")[0],
            16,
        )
        return VarProxy(self, addr, type, name=name)

    def __getattr__(self, name):
        # Find out if name is function or variable
        result = self._mi_write(f"-symbol-info-functions --name {name}")
        if len(result[-1]["payload"]["symbols"]) > 0:
            return self._getattr_function(name)
        else:
            return self._getattr_variable(name)

    @functools.lru_cache(maxsize=1024)
    def _mi_write(self, cmd: str) -> List[Dict]:
        return self._mi.write(cmd)

    def _new(self, typename, addr, *args):
        return VarProxy(self, addr, typename)
