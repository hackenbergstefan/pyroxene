import re
from typing import List, Union

from . import device_commands, gdbmimiddleware


class CType:
    ctypes = {}

    @staticmethod
    def get(mi: gdbmimiddleware.GdbmiMiddleware, name):
        if name in CType.ctypes:
            return CType.ctypes[name]
        return CType(mi, name)

    def __init__(self, mi: gdbmimiddleware.GdbmiMiddleware, name: str) -> None:
        name = name.strip()
        CType.ctypes[name] = self
        self._mi = mi
        self.name = name
        self.is_array = re.match(r".+\[\d+\]", self.name) is not None
        self.is_pointer = self.is_array or (re.match(r".+\*", self.name) is not None)
        self.is_void = name == "void"
        self.size = self._mi.sizeof(name)

    @property
    def parent(self) -> "CType":
        if self.is_pointer:
            return self.base
        deferred_type = self._mi.whatis(self.name)
        return CType.get(self._mi, deferred_type)

    @property
    def root(self):
        parent = self.parent
        if parent is not self:
            return parent.root
        return self

    @property
    def base(self):
        match = re.match(r"(.+?)\s*(?:\[\d+\]|\*)", self.name)
        if match:
            return CType.get(self._mi, match.group(1))
        return self

    @property
    def is_int(self):
        if not self.is_pointer and re.search("char|short|int|long", self.base.name):
            return True
        return False

    @property
    def is_enum(self):
        return self._mi.whatis(self.name).startswith("enum")

    def __repr__(self) -> str:
        return f"<CType {self.name}>"


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
            self._type = type if isinstance(type, CType) else CType.get(self._libproxy._mi, type)

    def _resolve_type_and_addr(self):
        if self._libproxy._mi.whatis(self._name).startswith("enum"):
            addr = None
            typ = self._name
        else:
            addr = int(self._libproxy._mi.eval(f"&{self._name}").split(" ")[0], 16)
            typ = self._libproxy._mi.symbol_info_variables(self._name)[0]["symbols"][0]["type"]
        return CType.get(self._libproxy._mi, typ), addr

    def __setattr__(self, name: str, value: any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            offset = self._libproxy._mi.offset_of(self._type.name, name)
            if isinstance(value, int):
                size = self._libproxy._mi.sizeof(f"(({self._type.name})0)->{name}")
            elif isinstance(value, VarProxy):
                size = value._type.size
                value = value._marshal()
            else:
                raise ValueError(f"No idea how to set: {value}")
            value = value.to_bytes(size, self._libproxy._proxy.endian)
            return self._libproxy._proxy.memory_write(self._addr + offset, value)

    def __getattr__(self, name: str) -> bytes:
        offset = self._libproxy._mi.offset_of(self._type.name, name)
        typ = CType.get(self._libproxy._mi, self._libproxy._mi._resolve_type(self._type.name, f"->{name}", 0))
        value = self._libproxy._proxy.memory_read(self._addr + offset, typ.size)
        value = int.from_bytes(value, self._libproxy._proxy.endian)
        if typ.is_int or typ.is_enum:
            return value
        elif typ.is_pointer:
            return VarProxy(self._libproxy, addr=value, type=typ)
        else:
            raise ValueError(f"No idea how to get: {value}")

    def __repr__(self) -> str:
        return f"<VarProxy {self._type} {self._name or ''} @ 0x{self._addr:08x}>"

    def __getitem__(self, key):
        if not self._type.is_pointer:
            raise ValueError("No idea how to get items.")

        if isinstance(key, int):
            key = slice(key, key + 1, 1)

        size = self._type.parent.size

        # TODO: Support for types
        result = [
            int.from_bytes(
                self._libproxy._proxy.memory_read(self._addr + k * size, size), self._libproxy._proxy.endian
            )
            for k in range(key.start, key.stop)
        ]
        if size == 1:
            return bytes(result)

        if len(result) == 1:
            result = result[0]
        return result

    def __setitem__(self, key, data):
        if not self._type.is_pointer:
            raise ValueError("No idea how to set items.")

        if isinstance(key, int):
            key = slice(key, key + 1, 1)
            data = [data]

        size = self._type.parent.size
        # TODO: Support for types
        for k, v in zip(range(key.start, key.stop), data):
            if isinstance(v, int):
                v = v.to_bytes(size, self._libproxy._proxy.endian)
            self._libproxy._proxy.memory_write(self._addr + k * size, v)

    def _marshal(self) -> int:
        if self._type.is_pointer:
            return self._addr
        elif self._type.is_enum:
            return int(self._libproxy._mi.eval(f"(ulong){self._name}"))
        raise NotImplementedError()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VarProxy):
            return False
        if all((self._type.is_pointer, other._type.is_pointer, self._addr == other._addr)):
            return True
        return False


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
        return addr, CType.get(self._libproxy._mi, returntype), params

    def __call__(self, *args):
        result = self._libproxy._proxy.call(
            self._addr,
            self._returntype.size,
            self._marshal_args(*args),
        )
        if not self._returntype.is_void:
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
        if self._returntype.is_int:
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

        self._proxy.sizeof_long = self._read_sizeofs()
        self._proxy.endian = self._read_endian()

    def _read_sizeofs(self):
        sizeof_long = self._mi.sizeof("unsigned long")
        if self._mi.sizeof("void *") != sizeof_long:
            raise ValueError("sizeof(void *) != sizeof(unsigned long)")
        return sizeof_long

    def _read_endian(self):
        if "little" in self._mi.console("show endian"):
            return "little"
        return "big"

    def __getattr__(self, name):
        # Find out if name is function or variable
        result = self._mi.symbol_info_functions(name)
        if result:
            return FuncProxy(self, name)
        else:
            var = VarProxy(self, name=name)
            if var._type.is_int or var._type.is_enum:
                return var._marshal()
            return var

    def _new(self, typename, addr, *args):
        return VarProxy(self, addr, typename)
