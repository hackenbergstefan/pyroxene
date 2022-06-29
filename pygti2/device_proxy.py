from typing import Union
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


# class ElfFuncProxy:
#     def __init__(self, libproxy: "LibProxy", name: str):
#         self._libproxy = libproxy
#         self._name = name
#         self._type: CTypeFunction = CType.get(name)
#         self._addr = self._type.addr

#     def __call__(self, *args):
#         result = self._libproxy._proxy.call(
#             self._addr,
#             self._type.return_type.size if self._type.return_type else 0,
#             self._marshal_args(*args),
#         )
#         if self._type.return_type is not None:
#             return self._unmarshal_returntype(result)

#     def _marshal_args(self, *args) -> List[int]:
#         """Converts all arguments to integers."""
#         packed_args = []
#         for arg in args:
#             if isinstance(arg, int):
#                 packed_args.append(arg)
#             elif isinstance(arg, VarProxy):
#                 packed_args.append(arg._type.marshal_int(arg))
#             else:
#                 ValueError(f"Cannot marshal {arg}")
#         return packed_args

#     def _unmarshal_returntype(self, result: int) -> Union[int, VarProxy]:
#         if self._type.return_type.is_int:
#             return result
#         return NewVarProxy(
#             self._libproxy,
#             type=self._type.return_type,
#             addr=result,
#         )


# class LibProxy:
#     def __init__(self, communication: device_commands.PyGti2Command, memory_manager=None):
#         self._proxy = communication
#         self.memory_manager = memory_manager
#         self.endian = "little" if CType.dwarf.config.little_endian else "big"
#         self.sizeof_long = communication.sizeof_long = CType.get("long unsigned int").size

#         if self.sizeof_long != CType.dwarf.config.default_address_size:
#             raise ValueError("sizeof(void *) != sizeof(unsigned long)")

#     def __getattr__(self, name):
#         type = CType.get(name)
#         if type is not None:
#             if isinstance(type, CTypeEnumValue):
#                 return type.value
#             if isinstance(type, CTypeFunction):
#                 return ElfFuncProxy(self, name)
#             if isinstance(type, CTypeMacro):
#                 return type.value
#         return ElfVarProxy(self, name)

#     def _new(self, type: Union[CType, str], addr: int, *args):
#         return NewVarProxy(self, type, addr)

#     def new(self, type: Union[CType, str]):
#         newvar = NewVarProxy(self, type, 0)
#         self.memory_manager.malloc(newvar)
#         return newvar

#     def memset(self, addr: int, value: int, length: int):
#         self._proxy.memory_write(addr, length * bytes([value]))

#     def memcpy(self, destination: int, source: int, length: int):
#         content = self._proxy.memory_read(source, length)
#         self._proxy.memory_write(destination, content)
