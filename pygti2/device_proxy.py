import functools
import re
from typing import List, Union

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

        self._ispointer = self._type.endswith("*") or self._type.endswith("]")
        self._basetype = self._type.split(" ")[0]

    def _resolve_type_and_addr(self):
        addr = int(self._libproxy._mi.eval(f"&{self._name}").split(" ")[0], 16)
        typ = self._libproxy._mi.symbol_info_variables(self._name)[0]["symbols"][0]["type"]
        return typ, addr

    def __setattr__(self, name: str, value: any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            offset = self._libproxy._mi.offset_of(self._type, name)
            if isinstance(value, int):
                size = self._libproxy._mi.sizeof(f"(({self._type})0)->{name}")
                value = value.to_bytes(size, "little")
            return self._libproxy._proxy.memory_write(self._addr + offset, value)

    def __getattr__(self, name: str) -> bytes:
        offset = self._libproxy._mi.offset_of(self._type, name)
        typ = self._libproxy._mi._resolve_type(self._type, f"->{name}", 0)
        size = self._libproxy._mi.sizeof(typ)
        data = self._libproxy._proxy.memory_read(self._addr + offset, size)
        if self._libproxy._type_is_int(typ):
            return int.from_bytes(data, "little")
        return data

    def __repr__(self) -> str:
        return f"<VarProxy {self._type} {self._name or ''} @ 0x{self._addr:08x}>"

    def __getitem__(self, key):
        if not self._ispointer:
            raise ValueError("No idea how to get items.")

        if isinstance(key, int):
            key = slice(key, key + 1, 1)

        size = self._libproxy._mi.sizeof(self._basetype)

        # TODO: Support for types
        result = [
            int.from_bytes(self._libproxy._proxy.memory_read(self._addr + k * size, size), "little")
            for k in range(key.start, key.stop)
        ]
        if size == 1:
            return bytes(result)

        if len(result) == 1:
            result = result[0]
        return result

    def __setitem__(self, key, data):
        if not self._ispointer:
            raise ValueError("No idea how to set items.")

        if isinstance(key, int):
            key = slice(key, key + 1, 1)
            data = [data]

        size = self._libproxy._mi.sizeof(self._basetype)
        # TODO: Support for types
        for k, v in zip(range(key.start, key.stop), data):
            if isinstance(v, int):
                v = v.to_bytes(size, "little")
            self._libproxy._proxy.memory_write(self._addr + k * size, v)

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

    def _unmarshal_returntype(self, result: int) -> Union[int, VarProxy]:
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
