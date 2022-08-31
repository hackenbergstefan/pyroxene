from typing import List, Type, Union, cast

from .companion_generator import PYROXENE_COMPANION_PREFIX, PYROXENE_COMPANION_PREFIX_PTR
from .device_commands import Communicator
from .elfbackend import CType, CTypeArray, CTypeFunction, ElfBackend


def chunks(thelist, chunksize):
    for i in range(0, len(thelist), chunksize):
        yield thelist[i : i + chunksize]


def uint2int(value, size):
    minus_one = int.from_bytes(size * b"\xff", "big")
    if value >> (8 * size - 1) != 0:
        return value - minus_one - 1
    return value


class VarProxy:
    """VarProxy behaves like a pointer to its type."""

    __slots__ = ("_backend", "_com", "_type", "_address", "_length", "_data")
    cffi_compatibility_mode = True

    @staticmethod
    def new(backend: ElfBackend, com: Communicator, type: CType, address: int, length: int = -1, data=None):
        if type.kind not in ("pointer", "array"):
            raise TypeError("Only pointer or arrays can be created.")

        if type.kind == "array":
            length = cast(CTypeArray, type).length
        return VarProxy.new2(backend, com, type.base, address, length, data)  # type: ignore[attr-defined]

    @staticmethod
    def new2(backend: ElfBackend, com: Communicator, type: CType, address: int, length: int = -1, data=None):
        if type.kind in ("struct", "typedef struct"):
            cls: Type[Union[VarProxy, VarProxyStruct]] = VarProxyStruct
        else:
            cls = VarProxy
        return cls(backend, com, type, address, length, data)

    def __init__(
        self,
        backend: ElfBackend,
        com: Communicator,
        type: CType,
        address: int,
        length: int = -1,
        data=None,
    ):
        self._backend = backend
        self._com = com
        self._type = type
        self._address = address
        self._length = length
        self._data = data

        if self._type.kind == "array":
            self._length = cast(CTypeArray, self._type).length
            self._type = cast(CTypeArray, self._type).base

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self._type}[{self._length}] @ 0x{self._address or 0:08x}>"

    def _getitem_single(self, index, content=None):
        newvarproxy = self.new2(
            self._backend,
            self._com,
            self._type,
            self._address + index * self._type.size,
            data=self._data[index * self._type.size :] if self._data is not None else None,
        )
        if content is None:
            content = newvarproxy.get_value()
        if newvarproxy.is_primitive:
            return content
        elif self._type.kind == "pointer":
            return self.new2(
                self._backend,
                self._com,
                self._type.base,
                int.from_bytes(content, self._backend.endian),
            )
        elif self.cffi_compatibility_mode:
            return newvarproxy
        else:
            raise ValueError("Cannot de-reference.")

    def __getitem__(self, index):
        if isinstance(index, slice):
            if self.is_primitive:
                # Speed up by reading memory at once
                return self.new2(
                    self._backend,
                    self._com,
                    self._type,
                    self._address + index.start * self._type.size,
                    length=index.stop - index.start,
                    data=self._data[index.start * self._type.size : index.stop * self._type.size]
                    if self._data is not None
                    else None,
                ).get_value()
            return [self._getitem_single(i) for i in range(index.start, index.stop)]
        else:
            if self._length != -1 and index >= self._length:
                raise IndexError()
            return self._getitem_single(index)

    def _setitem_single(self, index, data):
        self.new2(
            self._backend,
            self._com,
            self._type,
            self._address + index * self._type.size,
        ).set_value(data)

    def __setitem__(self, index, data):
        if isinstance(index, slice):
            if self._length == -1:
                raise TypeError("Sliced access only possible on arrays.")
            if self.is_primitive:
                if index.stop - index.start != len(data):
                    raise ValueError("Slice does not match length of data.")
                # Speed up by writing memory at once
                return self._com.memory_write(
                    self._address + index.start * self._type.size,
                    b"".join(d.to_bytes(self._type.size, self._backend.endian) for d in data),
                )
            return [self._setitem_single(i, d) for i, d in zip(range(index.start, index.stop), data)]
        else:
            return self._setitem_single(index, data)

    def get_value(self):
        content = self.to_bytes()
        if self.is_primitive:
            values = []
            for part in chunks(content, self._type.size):
                value = int.from_bytes(part, self._backend.endian)
                if getattr(self._type, "signed", False) and value >> (8 * self._type.size - 1) != 0:
                    value = value - int.from_bytes(self._type.size * b"\xff", self._backend.endian) - 1
                values.append(value)
            if len(values) == 1:
                return values[0]
            return values
        return content

    def set_value(self, data: Union[list, int, "VarProxy"]):
        if isinstance(data, VarProxy) and self._type.kind == "pointer":
            data = data._address
        elif isinstance(data, int) and data < 0:
            data = int.from_bytes(self._type.size * b"\xff", self._backend.endian) + data + 1
        elif isinstance(data, (list, tuple)):
            for member, value in zip(getattr(self._type, "members", {}), data):
                setattr(self, member, value)
            return
        self._com.memory_write(
            self._address,
            data.to_bytes(self._type.size, self._backend.endian),
        )

    def to_bytes(self, *args):
        if self._data is not None:
            return self._data
        return self._com.memory_read(
            self._address, self._type.size * (self._length if self._length > 0 else 1)
        )

    @property
    def is_primitive(self):
        return self._type.kind == "int"

    def __len__(self):
        if self._length < 0:
            raise TypeError(f"{self} has no length.")
        return self._length

    def __iter__(self):
        if self._length < 0:
            raise TypeError(f"{self} has no length.")
        if self._length == 0:
            return StopIteration()
        if self._length == 1:
            yield self[0]
            return
        yield from self.__getitem__(slice(0, self._length))

    def __eq__(self, other) -> bool:
        if not isinstance(other, VarProxy):
            raise TypeError(f"Not a VarProxy: {other}")
        return other._address == self._address and other._type == self._type


class VarProxyStruct(VarProxy):
    def __getattr__(self, name):
        if name not in self._type.members:
            raise ValueError(f"Unknown member: {name}")
        memberoffset, membertype = self._type.members[name]
        memberproxy = VarProxy.new2(
            self._backend,
            self._com,
            membertype,
            self._address + memberoffset,
        )
        if memberproxy.is_primitive:
            return memberproxy.get_value()
        elif (
            memberproxy.cffi_compatibility_mode
            and memberproxy._length == -1
            and memberproxy._type.kind in ("pointer", "array")
        ):
            return memberproxy[0]
        else:
            return memberproxy

    def __setattr__(self, name, data):
        if name in self.__slots__:
            return VarProxy.__setattr__(self, name, data)
        if name not in self._type.members:
            raise ValueError(f"Unknown member: {name}")

        memberoffset, membertype = self._type.members[name]
        VarProxy.new2(
            self._backend,
            self._com,
            membertype,
            self._address + memberoffset,
        ).set_value(data)


class FuncProxy:
    """FuncProxy behaves like a pointer to its type."""

    __slots__ = ("lib", "backend", "com", "type", "address")

    def __init__(
        self,
        lib: "LibProxy",
        backend: ElfBackend,
        com: Communicator,
        type: CTypeFunction,
        address: int,
    ):
        self.lib = lib
        self.backend = backend
        self.com = com
        self.type = type
        self.address = address

    def __call__(self, *args):
        # If return value is too large assume different call structure:
        # Instead: bigstruct = func(args)
        # Use: void _pyroxene_ptr_func(bigstruct *, args)
        if self.type.typename.startswith(PYROXENE_COMPANION_PREFIX_PTR):
            returnvalue = self.lib.new(self.type.arguments[0])
            self.com.call(
                self.address,
                0,
                self.marshal_args(returnvalue, *args),
            )
            return returnvalue
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
                packed_args.append(arg._address)
            elif isinstance(arg, bytes):
                var = self.lib.new("uint8_t[]", len(arg))
                var[0 : len(arg)] = arg
                packed_args.append(var._address)
            else:
                raise ValueError(f"Cannot marshal {arg}")
        return packed_args

    def unmarshal_returntype(self, result: int) -> Union[int, VarProxy]:
        rettype = self.type.return_type
        if rettype.kind == "int":
            if rettype.signed:
                return uint2int(result, rettype.size)
            else:
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
                0,
            )
            self.lib.memory_manager.malloc(var)
            var.set_value(result)
            return var

    def __eq__(self, other) -> bool:
        if not isinstance(other, FuncProxy):
            raise TypeError(f"Not a FuncProxy: {other}")
        return self.address == other.address


class LibProxy:
    def __init__(self, backend: ElfBackend, com: Communicator, memory_manager=None):
        self.backend = backend
        self.com = com
        self.memory_manager = memory_manager

    def __getattr__(self, name):
        if name in self.__dict__ or name in dir(self) or name in ("__name__", "__file__"):
            return super().__getattr__(name)
        if name in self.backend.types:
            type = self.backend.types[name]
        elif PYROXENE_COMPANION_PREFIX + name in self.backend.types:
            type = self.backend.types[PYROXENE_COMPANION_PREFIX + name]
        else:
            raise TypeError(f"Unknown type: {name}")

        if type.kind == "variable":
            data = type.data
            address = type.address
            if type.type.kind == "array":
                length = type.type.length
                type = type.type.base
            else:
                type = type.type
                length = -1
            var = VarProxy.new2(
                self.backend,
                self.com,
                type,
                address,
                length,
                data=data,
            )
            if var.cffi_compatibility_mode and var._length == -1 and var._type.kind == "int":
                return var[0]
            return var
        if type.kind == "function":
            # Redirect to "_pyroxene_ptr" variant if return argument is too big
            if getattr(type.return_type, "size", 0) > 8:
                type = self.backend.types[PYROXENE_COMPANION_PREFIX_PTR + name]
            return FuncProxy(
                self,
                self.backend,
                self.com,
                type,
                type.address,
            )
        raise TypeError(f"Neither variable or function: {type}")

    def _new(self, type: Union[CType, str], address: int, *args, defer_set=False):
        length = -1
        if isinstance(type, str):
            type = self.backend.type_from_string(type)  # type: ignore[no-redef]
            type = cast(CType, type)
            if type.kind == "array":
                type = cast(CTypeArray, type)
                if type.length > 0:
                    length = type.length
                elif len(args) == 1 and isinstance(args[0], (list, bytes)):
                    length = len(args[0])
                    type = CTypeArray(type.backend, type.base, length)
                elif len(args) == 1 and isinstance(args[0], int):
                    length = args[0]
                    type = CTypeArray(type.backend, type.base, length)
                else:
                    raise ValueError(f"Cannot create {type}")
        var = VarProxy.new(self.backend, self.com, type, address, length)
        if not defer_set:
            self._set(var, *args)
        return var

    def _set(self, var: VarProxy, *args):
        if not args:
            return
        if len(args) == 1:
            args = args[0]
        if var._length != -1:
            if isinstance(args, (list, tuple, bytes)):
                for i, a in enumerate(args):
                    var[i] = a
        else:
            var[0] = args

    def new(self, type: Union[CType, str], *args):
        var = self._new(type, 0, *args, defer_set=True)
        self.memory_manager.malloc(var)
        self.memset(var._address, 0, self.sizeof(var))
        self._set(var, *args)

        return var

    def memset(self, addr: Union[VarProxy, int], value: int, length: int):
        if isinstance(addr, VarProxy):
            addr = addr._address
        self.com.memory_write(addr, length * bytes([value]))

    def memmove(self, destination: Union[VarProxy, int], source: Union[VarProxy, int], length: int):
        if isinstance(destination, VarProxy):
            destination = destination._address
        if isinstance(source, VarProxy):
            source = source._address
        content = source if isinstance(source, bytes) else self.com.memory_read(source, length)
        self.com.memory_write(destination, content)

    def sizeof(self, var: VarProxy):
        return var._length * var._type.size if var._length != -1 else var._type.size

    def addressof(self, var: VarProxy):
        return var._address
