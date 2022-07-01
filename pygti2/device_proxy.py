from typing import List, Union
from pygti2.companion_generator import GTI2_COMPANION_PREFIX
from pygti2.device_commands import Communicator

from pygti2.elfbackend import CType, ElfBackend


def junks(thelist, junksize):
    for i in range(0, len(thelist), junksize):
        yield thelist[i : i + junksize]


class VarProxy:
    """VarProxy behaves like a pointer to its type."""

    __slots__ = ("backend", "com", "type", "address", "length")

    @staticmethod
    def new(backend: ElfBackend, com: Communicator, type: CType, address: int, length: int = -1):
        if type.kind not in ("pointer", "array"):
            raise TypeError("Only pointer or arrays can be created.")

        if type.kind == "array":
            length = type.length
        return VarProxy.new2(backend, com, type.base, address, length)

    @staticmethod
    def new2(backend: ElfBackend, com: Communicator, type: CType, address: int, length: int = -1):
        if type.kind in ("struct", "typedef struct"):
            cls = VarProxyStruct
        else:
            cls = VarProxy
        return cls(backend, com, type, address, length)

    def __init__(self, backend: ElfBackend, com: Communicator, type: CType, address: int, length: int = -1):
        self.backend = backend
        self.com = com
        self.type = type
        self.address = address
        self.length = length

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.type}[{self.length}] @ 0x{self.address:08x}>"

    def _getitem_single(self, index):
        newvarproxy = self.new2(
            self.backend,
            self.com,
            self.type,
            self.address + index * self.type.size,
        )
        content = newvarproxy.get_value()
        if newvarproxy.is_primitive:
            return content
        elif self.type.kind == "pointer":
            return self.new2(
                self.backend,
                self.com,
                self.type.base,
                int.from_bytes(content, self.backend.endian),
            )
        else:
            raise ValueError("Cannot de-reference.")

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self._getitem_single(i) for i in range(index.start, index.stop)]
        else:
            return self._getitem_single(index)

    def _setitem_single(self, index, data):
        self.new2(
            self.backend,
            self.com,
            self.type,
            self.address + index * self.type.size,
        ).set_value(data)

    def __setitem__(self, index, data):
        if isinstance(index, slice):
            return [self._setitem_single(i, d) for i, d in zip(range(index.start, index.stop), data)]
        else:
            return self._setitem_single(index, data)

    def get_value(self):
        content = self.to_bytes()
        if self.is_primitive:
            return int.from_bytes(content, self.backend.endian)
        return content

    def set_value(self, data: Union[int, "VarProxy"]):
        if isinstance(data, VarProxy) and self.type.kind == "pointer":
            data = data.address
        self.com.memory_write(
            self.address,
            data.to_bytes(self.type.size, self.backend.endian),
        )

    def to_bytes(self, *args):
        return self.com.memory_read(self.address, self.type.size)

    @property
    def is_primitive(self):
        return self.type.kind == "int"


class VarProxyStruct(VarProxy):
    def __getattr__(self, name):
        if name not in self.type.members:
            raise ValueError(f"Unknown member: {name}")
        memberoffset, membertype = self.type.members[name]
        memberproxy = VarProxy.new2(
            self.backend,
            self.com,
            membertype,
            self.address + memberoffset,
        )
        if memberproxy.is_primitive:
            return memberproxy.get_value()
        else:
            return memberproxy

    def __setattr__(self, name, data):
        if name in self.__slots__:
            return VarProxy.__setattr__(self, name, data)
        if name not in self.type.members:
            raise ValueError(f"Unknown member: {name}")

        memberoffset, membertype = self.type.members[name]
        VarProxy.new2(
            self.backend,
            self.com,
            membertype,
            self.address + memberoffset,
        ).set_value(data)


class FuncProxy:
    """FuncProxy behaves like a pointer to its type."""

    __slots__ = ("lib", "backend", "com", "type", "address")

    def __init__(self, lib: "LibProxy", backend: ElfBackend, com: Communicator, type: CType, address: int):
        self.lib = lib
        self.backend = backend
        self.com = com
        self.type = type
        self.address = address

    def __call__(self, *args):
        result = self.com.call(
            self.address,
            self.type.return_type.size if self.type.return_type else 0,
            self.marshal_args(*args),
        )
        if self.type.return_type is not None:
            return self.unmarshal_returntype(result)

    def marshal_args(self, *args) -> List[int]:
        """Converts all arguments to integers."""
        packed_args = []
        for arg in args:
            if isinstance(arg, int):
                packed_args.append(arg)
            elif isinstance(arg, VarProxy):
                if arg.type.kind == "int":
                    packed_args.append(arg.get_value())
                else:
                    packed_args.append(arg.address)
            else:
                ValueError(f"Cannot marshal {arg}")
        return packed_args

    def unmarshal_returntype(self, result: int) -> Union[int, VarProxy]:
        if self.type.return_type.kind == "int":
            return result
        try:
            return VarProxy.new(
                self.backend,
                self.com,
                self.type.return_type,
                result,
            )
        except TypeError:
            var = VarProxy.new2(
                self.backend,
                self.com,
                self.type.return_type,
                self.lib.gti2_memory.address,  # FIXME: Use self.lib.memory_manager
            )
            var.set_value(result)
            return var


class LibProxy:
    def __init__(self, backend: ElfBackend, com: Communicator, memory_manager=None):
        self.backend = backend
        self.com = com
        self.memory_manager = memory_manager

    def __getattr__(self, name):
        if name in self.backend.types:
            type = self.backend.types[name]
        elif GTI2_COMPANION_PREFIX + name in self.backend.types:
            type = self.backend.types[GTI2_COMPANION_PREFIX + name]
        else:
            raise TypeError(f"Unknown type: {name}")

        if type.kind == "variable":
            address = type.address
            if type.type.kind == "array":
                length = type.type.length
                type = type.type.base
            else:
                type = type.type
                length = -1
            return VarProxy.new2(
                self.backend,
                self.com,
                type,
                address,
                length,
            )
        if type.kind == "function":
            return FuncProxy(
                self,
                self.backend,
                self.com,
                type,
                type.address,
            )
        raise TypeError(f"Neither variable or function: {type}")

    def _new(self, type: Union[CType, str], address: int, *args):
        length = -1
        if isinstance(type, str):
            type = self.backend.type_from_string(type)
            if type.kind == "array":
                length = type.length
        return VarProxy.new(self.backend, self.com, type, address, length)

    def new(self, type: Union[CType, str]):
        var = self._new(type, 0)
        self.memory_manager.malloc(var)
        return var

    def memset(self, addr: Union[VarProxy, int], value: int, length: int):
        if isinstance(addr, VarProxy):
            addr = addr.address
        self.com.memory_write(addr, length * bytes([value]))

    def memcpy(self, destination: int, source: int, length: int):
        content = self.com.memory_read(source, length)
        self.com.memory_write(destination, content)

    def sizeof(self, var: VarProxy):
        return var.length * var.type.size if var.length != -1 else var.type.size
