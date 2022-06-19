from typing import List, Union, Any

from .elfproxy import (
    CType,
    CTypeArrayType,
    CTypeDerived,
    CTypeEnumValue,
    CTypeFunction,
    CTypeMember,
    CTypeStructType,
    CVarElf,
)
from . import device_commands


def junks(thelist, junksize):
    for i in range(0, len(thelist), junksize):
        yield thelist[i : i + junksize]


class VarProxy:
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self._type} @ 0x{self._addr:08x}>"

    def __setitem__(self, key, data):
        if not isinstance(self._type, CTypeArrayType):
            raise TypeError("Not an array.")

        if isinstance(key, slice):
            for k, v in zip(range(key.start, key.stop), data):
                self.__setitem__(k, v)
            return

        self._libproxy._proxy.memory_write(
            self._addr + key * self._type.parent.size,
            self._type.parent.marshal_bytes(data),
        )

    def __getitem__(self, key: slice):
        if not isinstance(self._type, CTypeArrayType):
            raise TypeError("Not an array.")

        if isinstance(key, int):
            key = slice(key, key + 1)

        data = self._libproxy._proxy.memory_read(
            self._addr + key.start * self._type.parent.size,
            self._type.parent.size * (key.stop - key.start),
        )

        # Make output compatible to cffi
        if key.stop - key.start == 1:
            return int.from_bytes(data, self._libproxy.endian)
        if self._type.parent.size == 1:
            return data

        return [int.from_bytes(d, self._libproxy.endian) for d in junks(data, self._type.parent.size)]

    def __setattr__(self, name: str, value: Any):
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            structtype = self._type.parent.parent
            if not isinstance(structtype, CTypeStructType):
                raise ValueError(f"Not a struct: {structtype}")
            membertype: CTypeMember = structtype.members[name]
            self._libproxy._proxy.memory_write(
                self._addr + membertype.offset_in_struct,
                membertype.marshal_bytes(value),
            )

    def __getattr__(self, name: str) -> Any:
        structtype = self._type.parent.parent
        if not isinstance(structtype, CTypeStructType):
            raise ValueError(f"Not a struct: {structtype}")

        membertype: CTypeMember = structtype.members[name]
        memberaddr = self._addr + membertype.offset_in_struct
        content_as_int = int.from_bytes(
            self._libproxy._proxy.memory_read(memberaddr, membertype.size),
            self._libproxy.endian,
        )
        if membertype.is_int:
            return content_as_int
        return NewVarProxy(self._libproxy, membertype.parent, content_as_int)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VarProxy):
            return False
        return self._addr == other._addr


class ElfVarProxy(VarProxy):
    def __init__(self, libproxy: "LibProxy", name: str):
        """
        Create proxy of an a global existing variable given by `name`.
        """
        self._libproxy = libproxy

        self._name: str = name
        self._elfvar: CVarElf = CVarElf._cvars.get(name)
        self._type: CType = self._elfvar._type
        self._addr: int = self._elfvar._addr


class NewVarProxy(VarProxy):
    def __init__(self, libproxy: "LibProxy", type: Union[CType, str], addr: int):
        """
        Create proxy of an a new variable given by type and address.
        """
        self._libproxy = libproxy
        self._addr: int = addr

        if isinstance(type, str):
            typ = CType.get(type)
            if typ is None:
                type = CTypeDerived.create(type)
            else:
                type = typ

        self._type: CType = type


class ElfFuncProxy:
    def __init__(self, libproxy: "LibProxy", name: str):
        self._libproxy = libproxy
        self._name = name
        self._type: CTypeFunction = CType.get(name)
        self._addr = self._type.addr

    def __call__(self, *args):
        result = self._libproxy._proxy.call(
            self._addr,
            self._type.return_type.size if self._type.return_type else 0,
            self._marshal_args(*args),
        )
        if self._type.return_type is not None:
            return self._unmarshal_returntype(result)

    def _marshal_args(self, *args) -> List[int]:
        """Converts all arguments to integers."""
        packed_args = []
        for arg in args:
            if isinstance(arg, int):
                packed_args.append(arg)
            elif isinstance(arg, VarProxy):
                packed_args.append(arg._type.marshal_int(arg))
            else:
                ValueError(f"Cannot marshal {arg}")
        return packed_args

    def _unmarshal_returntype(self, result: int) -> Union[int, VarProxy]:
        if self._type.return_type.is_int:
            return result
        return NewVarProxy(
            self._libproxy,
            type=self._type.return_type,
            addr=result,
        )


class LibProxy:
    def __init__(self, communication: device_commands.PyGti2Command, memory_manager=None):
        self._proxy = communication
        self.memory_manager = memory_manager
        self.endian = "little" if CType.dwarf.config.little_endian else "big"
        self.sizeof_long = communication.sizeof_long = CType.get("long unsigned int").size

        if self.sizeof_long != CType.get("void *").size:
            raise ValueError("sizeof(void *) != sizeof(unsigned long)")

    def __getattr__(self, name):
        type = CType.get(name)
        if type is not None:
            if isinstance(type, CTypeEnumValue):
                return type.value
            if isinstance(type, CTypeFunction):
                return ElfFuncProxy(self, name)
        return ElfVarProxy(self, name)

    def _new(self, type: Union[CType, str], addr: int, *args):
        return NewVarProxy(self, type, addr)

    def new(self, type: Union[CType, str]):
        newvar = NewVarProxy(self, type, 0)
        self.memory_manager.malloc(newvar)
        return newvar
