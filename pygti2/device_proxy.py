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


class FuncProxy:
    def __init__(self, libproxy: "LibProxy", name: str):
        self._libproxy = libproxy
        self._name = name
        self._addr, self._returntype, self._params = self._resolve()

    def _resolve(self):
        result = self._libproxy._mi.symbol_info_functions(self._name)
        sig = result[0]["symbols"][0]["type"]  # "returnvalue (param1, param2, ...)"
        (returnvalue, _, params) = sig.partition(" ")
        params = params[1:-1]  # remove the parentheses to get params..
        params = params.split(", ")

        addr = int(self._libproxy._mi.eval(f"{self._name}").split(" ")[-2], 16)
        return addr, returnvalue, params

    def __call__(self, *args):
        result = self._libproxy._proxy.call(
            self._addr,
            # TODO: Improve!
            0 if self._returntype == "void" else self._libproxy._proxy.sizeof_long,
            *args,
        )

        if "int" in self._returntype or "long" in self._returntype:
            return self._libproxy._proxy.unpack_long(result)
        else:
            return result


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
