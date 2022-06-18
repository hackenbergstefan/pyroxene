import subprocess
import re
from typing import Optional

from elftools.dwarf.die import DIE
from elftools.elf.elffile import ELFFile


class CType:
    ctypes_by_name = {}
    ctypes_by_die = {}

    @staticmethod
    def get(name):
        return CType.ctypes_by_name[name]

    @staticmethod
    def get_by_die(die: DIE):
        if die in CType.ctypes_by_die:
            return CType.ctypes_by_die[die]
        return {
            "DW_TAG_pointer_type": lambda d: CTypePointerType(d),
            "DW_TAG_base_type": lambda d: CTypeBaseType(d),
            "DW_TAG_structure_type": lambda d: CTypeStructType(d),
            "DW_TAG_typedef": lambda d: CTypeTypedef(d),
            "DW_TAG_member": lambda d: CTypeMember(d),
            "DW_TAG_const_type": lambda d: CTypeConstType(d),
            "DW_TAG_array_type": lambda d: CTypeArrayType(d),
            "DW_TAG_enumeration_type": lambda d: CTypeEnumType(d),
            "DW_TAG_enumerator": lambda d: CTypeEnumValue(d),
        }[die.tag](die)

    def __init__(self, die: DIE):
        CType.ctypes_by_die[die] = self
        self.die = die

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name}>"

    @property
    def parent(self) -> Optional["CType"]:
        if "DW_AT_type" not in self.die.attributes:
            return None
        parent_type = self.die.get_DIE_from_attribute("DW_AT_type")
        return CType.get_by_die(parent_type)

    @property
    def root(self):
        parent = self.parent
        if parent is not None:
            return parent.root
        return self

    @property
    def is_int(self):
        if isinstance(
            self,
            (CTypeArrayType, CTypePointerType, CTypeStructType, CTypeDerivedArray, CTypeDerivedPointer),
        ):
            return False
        if re.search("char|short|int|long", self.root.name):
            return True
        return False


class CTypePointerType(CType):
    def __init__(self, die: DIE):
        super().__init__(die)
        if self.parent is None:
            self.name = "void *"
        else:
            self.name = f"{self.parent.name} *"
        CType.ctypes_by_name[self.name] = self

    @property
    def size(self) -> int:
        return self.die.dwarfinfo.config.default_address_size


class CTypeArrayType(CType):
    def __init__(self, die: DIE):
        super().__init__(die)
        for d in die.iter_children():
            if d.tag == "DW_TAG_subrange_type":
                if "DW_AT_upper_bound" in d.attributes:
                    self.length = d.attributes["DW_AT_upper_bound"].value + 1
                else:
                    self.length = 0
                break
        self.name = f"{self.parent.name} [{self.length}]"
        CType.ctypes_by_name[self.name] = self

    @property
    def size(self) -> int:
        return self.length * self.parent.size


class CTypeTypedef(CType):
    def __init__(self, die: DIE):
        super().__init__(die)
        self.name = die.attributes["DW_AT_name"].value.decode()
        CType.ctypes_by_name[self.name] = self

    def __getattr__(self, d):
        if isinstance(self.parent, CTypeStructType):
            return getattr(self.parent, d)

    @property
    def size(self) -> int:
        if isinstance(self.parent, CTypeStructType):
            return self.parent.size
        else:
            return self.root.size


class CTypeBaseType(CType):
    def __init__(self, die: DIE):
        super().__init__(die)
        self.size = die.attributes["DW_AT_byte_size"].value
        self.name = die.attributes["DW_AT_name"].value.decode()
        CType.ctypes_by_name[self.name] = self


class CTypeStructType(CType):
    def __init__(self, die: DIE):
        super().__init__(die)

        if "DW_AT_sibling" in die.attributes:
            self.typedef = CType.get_by_die(die.get_DIE_from_attribute("DW_AT_sibling"))
        else:
            self.typedef = None
            self.name = die.attributes["DW_AT_name"].value.decode()

        if "DW_AT_byte_size" in die.attributes:
            self.size = die.attributes["DW_AT_byte_size"].value
        else:
            self.size = 0

        self.members = {}
        for d in die.iter_children():
            d = CType.get_by_die(d)
            self.members[d.name] = d

    def __getattr__(self, d):
        return getattr(self.typedef, d)


class CTypeMember(CType):
    def __init__(self, die: DIE):
        super().__init__(die)
        self.name = die.attributes["DW_AT_name"].value.decode()
        self.offset_in_struct = self.die.attributes["DW_AT_data_member_location"].value

    @property
    def size(self) -> int:
        return self.parent.size


class CTypeConstType(CType):
    def __init__(self, die: DIE):
        super().__init__(die)
        self.name = "?"


class CTypeEnumType(CType):
    def __init__(self, die: DIE):
        super().__init__(die)
        self.values = {}
        for d in die.iter_children():
            val = CType.get_by_die(d)
            self.values[val.name] = val
        if "DW_AT_name" in die.attributes:
            self.name = die.attributes["DW_AT_name"].value.decode()
            CType.ctypes_by_name[self.name] = self

    @property
    def size(self) -> int:
        return self.length * self.parent.size


class CTypeEnumValue(CType):
    def __init__(self, die: DIE):
        super().__init__(die)
        self.name = die.attributes["DW_AT_name"].value.decode()
        self.value = die.attributes["DW_AT_const_value"].value
        CType.ctypes_by_name[self.name] = self


class CTypeDerived(CType):
    @staticmethod
    def create(spec: str):
        if spec.endswith("*"):
            return CTypeDerivedPointer(spec)
        elif spec.endswith("]"):
            return CTypeDerivedArray(spec)
        else:
            raise NotImplementedError("What else needed?")

    def __init__(self, spec: str):
        self.name = spec

    @property
    def parent(self) -> Optional["CType"]:
        return self._parent


class CTypeDerivedPointer(CTypeDerived, CTypePointerType):
    def __init__(self, spec: str):
        if not spec.endswith("*"):
            raise ValueError(f"Not a pointer specification: {spec}")
        CTypeDerived.__init__(self, spec)
        self._parent = CType.get(spec[:-1].strip())

    @property
    def size(self) -> int:
        return self._parent.die.dwarfinfo.config.default_address_size


class CTypeDerivedArray(CTypeDerived, CTypeArrayType):
    def __init__(self, spec: str):
        match = re.match(r"(.+?)\s*\[(\d+)\]", spec)
        if not spec:
            raise ValueError(f"Not an array specification: {spec}")
        CTypeDerived.__init__(self, spec)
        self._parent = CType.get(match.group(1))
        self.length = int(match.group(2))

    @property
    def size(self) -> int:
        return self.length * self._parent.size


class CTypeMacro(CType):
    def __init__(self, name: str, value: int):
        self.name = name
        self.value = value
        CType.ctypes_by_name[self.name] = self

    @property
    def parent(self):
        return None

    @property
    def is_int(self):
        return True


def loc2addr(die: DIE):
    addr = die.attributes["DW_AT_location"].value[1:]
    if len(addr) != die.dwarfinfo.config.default_address_size:
        raise NotImplementedError("‍🤔️")
    return int.from_bytes(addr, "little" if die.dwarfinfo.config.little_endian else "big")


class CVar:
    pass


class CVarProxy(CVar):
    def __init__(self, addr=None, type=None):
        self._type = type if isinstance(type, CType) else CType.get(type)

    def __repr__(self) -> str:
        return f"{str(self._type)} @ {hex(self._addr)}"


class CVarElf(CVar):
    _cvars = {}

    def __init__(self, die: DIE):
        if "DW_AT_specification" in die.attributes:
            spec = die.get_DIE_from_attribute("DW_AT_specification")
        else:
            spec = die

        self._type = CType.get_by_die(spec.get_DIE_from_attribute("DW_AT_type"))
        self._addr = loc2addr(die)
        self._name = spec.attributes["DW_AT_name"].value.decode()
        CVarElf._cvars[self._name] = self

    def __repr__(self) -> str:
        return f"{self._name} {str(self._type)} @ {hex(self._addr)}"


def parse_macros(readelf_binary: str, file: str):
    """
    Pyelftools do not support parsing of .debug_macro section. readelf is used instead.

    Support is limited to numeric macros. Note, that false output can be produced.
    """
    macros = subprocess.check_output([readelf_binary, "--debug-dump=macro", file]).decode()
    for line in macros.splitlines():
        line = line.strip()
        if not line.startswith("DW_MACRO_define_strp"):
            continue
        line = line.split(" : ")[-1]
        name, _, rawvalue = line.partition(" ")
        if name.startswith("_"):
            continue
        match = re.search(r"\b0x[0-9a-f]+\b", rawvalue, flags=re.IGNORECASE)
        value = None
        if match:
            value = int(match.group(0), 16)
        else:
            match = re.search(r"\b-?[0-9]+\b", rawvalue)
            if match:
                value = int(match.group(0))
        if not value:
            continue
        CTypeMacro(name, value)


def create_ctypes(file, readelf_binary="readelf"):
    with open(file, "rb") as fp:
        elf = ELFFile(fp)
        dwarf = elf.get_dwarf_info()
        for cu in dwarf.iter_CUs():
            for die in cu.iter_DIEs():
                if die.tag == "DW_TAG_base_type":
                    CType.get_by_die(die)
                    continue
                    print(
                        die.attributes["DW_AT_name"].value.decode(),
                        die.attributes["DW_AT_byte_size"].value,
                    )
                elif die.tag == "DW_TAG_typedef":
                    CType.get_by_die(die)
                    continue

                    print(die)
                    print(
                        die.attributes["DW_AT_name"].value.decode(),
                    )
                    return
                elif die.tag == "DW_TAG_pointer_type":
                    ctype = CType.get_by_die(die)
                    continue
                    print(ctype)
                    # print(die)
                elif die.tag == "DW_TAG_structure_type":
                    ctype = CType.get_by_die(die)
                    continue
                elif die.tag == "DW_TAG_variable" and "DW_AT_specification" in die.attributes:
                    CVarElf(die)
                    pass
                elif die.tag == "DW_TAG_variable":
                    if (
                        "DW_AT_external" in die.attributes
                        and die.attributes["DW_AT_external"].value
                        and "DW_AT_declaration" not in die.attributes
                    ):
                        CVarElf(die)
                    pass
                elif die.tag == "DW_TAG_enumeration_type":
                    ctype = CType.get_by_die(die)
                    continue

    if readelf_binary:
        parse_macros(readelf_binary, file)


if __name__ == "__main__":
    create_ctypes("test/host_test", readelf_binary="readelf")
