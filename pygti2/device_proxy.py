from typing import List, Type, Union, Any
from pygti2.device_commands import Communicator

from pygti2.elfbackend import CType, CTypeArray, CTypePointer, CTypeStruct, CTypeTypedefStruct, ElfBackend


def junks(thelist, junksize):
    for i in range(0, len(thelist), junksize):
        yield thelist[i : i + junksize]


class VarProxy:
    allowed_types = (CType,)
    __slots__ = ("backend", "com", "type", "name", "address")

    def __init__(self, backend: ElfBackend, com: Communicator, type: CType, name: str, address: int):
        if not isinstance(type, self.allowed_types):
            raise TypeError(f"Is not a {self.allowed_types}: {type}")

        self.backend = backend
        self.com = com
        self.type = type
        self.name = name
        self.address = address

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.type} @ 0x{self.address:08x}>"

    def convert_any_to_int(self, data):
        if not isinstance(data, list):
            data = [data]
        result = [self._convert_any_to_int_item(d) for d in data]
        if len(result) == 1:
            return result[0]
        else:
            return result

    def _convert_any_to_int_item(self, data):
        if isinstance(data, int):
            return data
        elif isinstance(data, bytes):
            return int.from_bytes(data, self.backend.endian)
        elif isinstance(data, VarProxy):
            return data.convert_to_int()
        else:
            raise TypeError(f"Cannot convert to int: {data}")

    def _deref_pointer(self, address: int):
        return int.from_bytes(self.com.memory_read(address, self.backend.sizeof_voidp), self.backend.endian)

    def _write_pointer(self, address: int, data: int):
        return self.com.memory_write(address, data.to_bytes(self.backend.sizeof_voidp, self.backend.endian))


class VarProxyPointer(VarProxy):
    allowed_types = (CTypePointer,)
    __slots__ = (*VarProxy.__slots__, "base_type")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_type = self.type.base

    def convert_to_int(self):
        return self.address

    def _getitem_range(self, start, stop):
        data = self.com.memory_read(self.address + start, (stop - start) * self.base_type.size)
        if self.base_type.kind == "int":
            return [int.from_bytes(junk, self.backend.endian) for junk in junks(data, self.base_type.size)]
        elif self.base_type.kind == "byte":
            return data
        else:
            raise TypeError(f"Unknown base kind: {self.base_type.kind}")

    def __getitem__(self, index: Union[int, slice]):
        if isinstance(index, slice):
            return self._getitem_range(index.start, index.stop)
        elif isinstance(index, int):
            return self._getitem_range(index, index + 1)[0]
        else:
            raise TypeError("Not slice or int")

    def _setitem_range(self, start, stop, data):
        if len(data) != stop - start:
            raise ValueError(f"Length does not match: {len(data)} != {stop - start}")

        if self.base_type.kind == "byte":
            return self.com.memory_write(self.address + start, data)
        else:
            data = self.convert_any_to_int(data)
            return self.com.memory_write(
                self.address + start,
                b"".join(d.to_bytes(self.base_type.size, self.backend.endian) for d in data),
            )

    def __setitem__(self, index: Union[int, slice], data):
        if isinstance(index, slice):
            return self._setitem_range(index.start, index.stop, data)
        elif isinstance(index, int):
            return self._setitem_range(index, index + 1, [data])
        else:
            raise TypeError("Not slice or int")


class VarProxyArray(VarProxyPointer):
    allowed_types = (CTypeArray,)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.length = self.type.length

    def _getitem_range(self, start, stop):
        if stop > self.length:
            raise IndexError(f"{stop} > {self.length}")
        return super()._getitem_range(start, stop)

    def _setitem_range(self, start, stop, data):
        if stop > self.length:
            raise IndexError(f"{stop} > {self.length}")
        return super()._setitem_range(start, stop, data)


class VarProxyStruct(VarProxyPointer):
    allowed_types = (CTypePointer,)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getitem__(self, *args):
        raise TypeError("Not item accessible.")

    def __setitem__(self, *args):
        raise TypeError("Not item accessible.")

    def __getattr__(self, name: str):
        if name not in self.base_type.members:
            raise ValueError(f"Not a member: {name} of {self.base_type}.")

        attribute_offset, attribute_type = self.base_type.members[name]
        if attribute_type.kind == "int":
            return VarProxyPointer(
                self.backend,
                self.com,
                self.backend.type_from_string(f"{attribute_type.typename} *"),
                name,
                self.address + attribute_offset,
            )[0]
        elif attribute_type.kind == "pointer":
            if attribute_type.base.kind in ("struct", "typedef struct"):
                return VarProxyStruct(
                    self.backend,
                    self.com,
                    attribute_type,
                    name,
                    self._deref_pointer(self.address + attribute_offset),
                )
        elif attribute_type.kind in ("struct", "typedef struct"):
            if attribute_type.base.kind in ("struct", "typedef struct"):
                return VarProxyStruct(
                    self.backend,
                    self.com,
                    self.backend.type_from_string(f"{attribute_type.typename} *"),
                    name,
                    self.address + attribute_offset,
                )

    def __setattr__(self, name: str, data):
        if name in self.__slots__:
            return VarProxyPointer.__setattr__(self, name, data)

        if name not in self.base_type.members:
            raise ValueError(f'"{name}" is not a member of "{self.base_type}".')

        attribute_offset, attribute_type = self.base_type.members[name]
        if attribute_type.kind == "int":
            VarProxyPointer(
                self.backend,
                self.com,
                self.backend.type_from_string(f"{attribute_type.typename} *"),
                name,
                self.address + attribute_offset,
            )[0] = data
        elif attribute_type.kind == "pointer":
            self._write_pointer(self.address + attribute_offset, self.convert_any_to_int(data))


#     def __setitem__(self, key, data):
#         if not isinstance(self._type, CTypeArrayType):
#             raise TypeError("Not an array.")

#         if isinstance(key, slice):
#             for k, v in zip(range(key.start, key.stop), data):
#                 self.__setitem__(k, v)
#             return

#         self._libproxy._proxy.memory_write(
#             self._addr + key * self._type.parent.size,
#             self._type.parent.marshal_bytes(data),
#         )

#     def __getitem__(self, key: slice):
#         if not isinstance(self._type, CTypeArrayType):
#             raise TypeError("Not an array.")

#         if isinstance(key, int):
#             key = slice(key, key + 1)

#         data = self._libproxy._proxy.memory_read(
#             self._addr + key.start * self._type.parent.size,
#             self._type.parent.size * (key.stop - key.start),
#         )

#         # Make output compatible to cffi
#         if key.stop - key.start == 1:
#             return int.from_bytes(data, self._libproxy.endian)
#         if self._type.parent.size == 1:
#             return data

#         return [int.from_bytes(d, self._libproxy.endian) for d in junks(data, self._type.parent.size)]

#     def __setattr__(self, name: str, value: Any):
#         if name.startswith("_"):
#             super().__setattr__(name, value)
#         else:
#             structtype = self._type.parent.parent
#             if not isinstance(structtype, CTypeStructType):
#                 raise ValueError(f"Not a struct: {structtype}")
#             membertype: CTypeMember = structtype.members[name]
#             self._libproxy._proxy.memory_write(
#                 self._addr + membertype.offset_in_struct,
#                 membertype.marshal_bytes(value),
#             )

#     def __getattr__(self, name: str) -> Any:
#         structtype = self._type.parent.parent
#         if not isinstance(structtype, CTypeStructType):
#             raise ValueError(f"Not a struct: {structtype}")

#         membertype: CTypeMember = structtype.members[name]
#         memberaddr = self._addr + membertype.offset_in_struct
#         content_as_int = int.from_bytes(
#             self._libproxy._proxy.memory_read(memberaddr, membertype.size),
#             self._libproxy.endian,
#         )
#         if membertype.is_int:
#             return content_as_int
#         return NewVarProxy(self._libproxy, membertype.parent, content_as_int)

#     def __eq__(self, other: object) -> bool:
#         if not isinstance(other, VarProxy):
#             return False
#         return self._addr == other._addr


# class ElfVarProxy(VarProxy):
#     def __init__(self, libproxy: "LibProxy", name: str):
#         """
#         Create proxy of an a global existing variable given by `name`.
#         """
#         self._libproxy = libproxy

#         self._name: str = name
#         self._elfvar: CVarElf = CVarElf._cvars.get(name)
#         self._type: CType = self._elfvar._type
#         self._addr: int = self._elfvar._addr


# class NewVarProxy(VarProxy):
#     def __init__(self, libproxy: "LibProxy", type: Union[CType, str], addr: int):
#         """
#         Create proxy of an a new variable given by type and address.
#         """
#         self._libproxy = libproxy
#         self._addr: int = addr

#         if isinstance(type, str):
#             typ = CType.get(type)
#             if typ is None:
#                 type = CTypeDerived.create(type)
#             else:
#                 type = typ

#         self._type: CType = type


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
