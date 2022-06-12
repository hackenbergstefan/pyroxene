import functools
import re
from typing import List

from . import device_commands, gdbmimiddleware


class VarProxy:
    def __init__(self, libproxy: "LibProxy", addr=None, type=None, name=None) -> None:
        """
        Create proxy of variable.

        Either reflects a global existing variable given by `name`.
        Or reflects a non-gdb known custom variable at `addr` of `type`.
        """
        self._libproxy = libproxy

        if name:
            self._name = name
            self._type, self._addr = self._resolve_type_and_addr()
        else:
            if not addr or not type:
                raise ValueError("If no name is given, addr and type must be set.")
            self._addr = addr
            self._type = type

        self._ispointer = self._type.endswith("*")

    def _resolve_type_and_addr(self):
        addr = int(self._libproxy._mi.eval(f"&{self._name}").split(" ")[0], 16)
        typ = self._libproxy._mi.symbol_info_variables(self._name)[0]["symbols"][0]["type"]
        return typ, addr

    def __setattr__(self, name: str, value: any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            offset = self._libproxy._mi.offset_of(self._type, name)
            # TODO: Convert types
            if isinstance(value, int):
                size = self._libproxy._mi.sizeof(f"(({self._type})0)->{name}")
                value = value.to_bytes(size, "little")
            return self._libproxy._proxy.memory_write(self._addr + offset, value)

    def __getattr__(self, name: str) -> bytes:
        offset = self._libproxy._mi.offset_of(self._type, name)
        size = self._libproxy._mi.sizeof(self._type, name)
        return self._libproxy._proxy.memory_read(self._addr + offset, size)

    def __repr__(self) -> str:
        return f"<VarProxy {self._type} {self._name or ''} @ 0x{self._addr:08x}>"

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self._libproxy._proxy.memory_read(self._addr + key.start, key.stop - key.start)

    def __setitem__(self, key, data):
        if isinstance(key, slice):
            return self._libproxy._proxy.memory_write(self._addr + key.start, data)

    def _marshal(self):
        if self._ispointer:
            return self._addr
        raise NotImplementedError()


class FuncProxy:
    def __init__(self, libproxy: "LibProxy", name: str):
        self._libproxy = libproxy
        self._name = name
        self._addr, self._returntype, self._params = self._resolve()

    def _resolve(self):
        result = self._libproxy._mi.symbol_info_functions(self._name)
        sig = result[0]["symbols"][0]["type"]  # "returnvalue (param1, param2, ...)"
        sig = re.match(r"(?P<returntype>.+)\((?P<params>.+)\)", sig)
        returntype = sig.group("returntype").strip()
        params = [p.strip() for p in sig.group("params").split(",")]

        addr = int(self._libproxy._mi.eval(f"{self._name}").split(" ")[-2], 16)
        return addr, returntype, params

    def __call__(self, *args):
        result = self._libproxy._proxy.call(
            self._addr,
            self._libproxy._mi.sizeof(self._returntype),
            self._marshal_args(*args),
        )
        if self._returntype != "void":
            return self._unmarshal_returntype(result)

    def _marshal_args(self, *args) -> List[int]:
        """Converts all arguments to integers."""
        packed_args = []
        for arg in args:
            if isinstance(arg, int):
                packed_args.append(arg)
            elif isinstance(arg, VarProxy):
                packed_args.append(arg._marshal())
            else:
                ValueError(f"Cannot marshal {arg}")
        return packed_args

    def _unmarshal_returntype(self, result: int) -> int | VarProxy:
        if self._libproxy._type_is_int(self._returntype):
            return result
        return VarProxy(
            self._libproxy,
            addr=result,
            type=self._returntype,
        )


class LibProxy:
    def __init__(self, mi: gdbmimiddleware.GdbmiMiddleware, proxy: device_commands.PyGti2Command):
        self._mi = mi
        self._proxy = proxy

        self._read_sizeofs()

    def _read_sizeofs(self):
        self._proxy.sizeof_long = self._mi.sizeof("unsigned long")
        if self._mi.sizeof("void *") != self._proxy.sizeof_long:
            raise ValueError("sizeof(void *) != sizeof(unsigned long)")

    def __getattr__(self, name):
        # Find out if name is function or variable
        result = self._mi.symbol_info_functions(name)
        if result:
            return FuncProxy(self, name)
        else:
            return VarProxy(self, name=name)

    def _new(self, typename, addr, *args):
        return VarProxy(self, addr, typename)

    @functools.lru_cache(1024)
    def _type_is_int(self, type: str):
        """Returns True if given type is derived from int."""
        PRIMITIVE_INTS = (
            "char",
            "int",
            "long",
        )
        type = type.strip()
        if type.replace("unsigned ", "") in PRIMITIVE_INTS:
            return True

        deferred_type = self._mi.console(f"whatis {type}").replace("type = ", "").strip()
        if deferred_type == type:
            return False

        return self._type_is_int(deferred_type)
