import subprocess
import re
from typing import Optional

from elftools.dwarf.dwarfinfo import DWARFInfo
from elftools.dwarf.dwarf_expr import DW_OP_opcode2name
from elftools.dwarf.die import DIE
from elftools.elf.elffile import ELFFile


def loc2addr(die: DIE):
    addr = die.attributes["DW_AT_location"].value
    if DW_OP_opcode2name[addr[0]] != "DW_OP_addr":
        raise ValueError("Not an address.")
    addr = addr[1:]
    if len(addr) != die.dwarfinfo.config.default_address_size:
        raise NotImplementedError("No idea how to parse this address.")
    return int.from_bytes(addr, CType.endian)


class CType:
    dwarf: DWARFInfo = None
    ctypes_by_name = {}
    ctypes_by_die = {}

    @staticmethod
    def get(name) -> Optional["CType"]:
        return CType.ctypes_by_name.get(name)

    @staticmethod
    def get_by_die(die: DIE) -> "CType":
        if die in CType.ctypes_by_die:
            return CType.ctypes_by_die[die]
        supported_types = {
            "DW_TAG_pointer_type": lambda d: CTypePointerType(d),
            "DW_TAG_base_type": lambda d: CTypeBaseType(d),
            "DW_TAG_structure_type": lambda d: CTypeStructType(d),
            "DW_TAG_typedef": lambda d: CTypeTypedef(d),
            "DW_TAG_member": lambda d: CTypeMember(d),
            "DW_TAG_const_type": lambda d: CTypeConstType(d),
            "DW_TAG_array_type": lambda d: CTypeArrayType(d),
            "DW_TAG_enumeration_type": lambda d: CTypeEnumType(d),
            "DW_TAG_enumerator": lambda d: CTypeEnumValue(d),
            "DW_TAG_subprogram": lambda d: CTypeFunction(d),
        }
        if die.tag in supported_types:
            return supported_types[die.tag](die)
        return None

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

    def marshal_int(self, data) -> int:
        if isinstance(data, int):
            return data
        elif hasattr(data, "_addr"):
            return data._addr
            # return data._type.marshal_int(data)
        raise ValueError(f"Cannot marshal {data}.")

    def marshal_bytes(self, data) -> bytes:
        return self.marshal_int(data).to_bytes(self.size, CType.endian)


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

    @property
    def base_size(self) -> int:
        return self.parent.size


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

    @property
    def base_size(self) -> int:
        return self.size


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
        if "DW_AT_name" in die.attributes:
            self.name = die.attributes["DW_AT_name"].value.decode()
        else:
            self.name = ""
        if "DW_AT_byte_size" in die.attributes:
            self.size = die.attributes["DW_AT_byte_size"].value
        else:
            self.size = 0

        self.members = {}
        for d in die.iter_children():
            d = CType.get_by_die(d)
            self.members[d.name] = d


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


class CTypeFunction(CType):
    def __init__(self, die: DIE):
        super().__init__(die)
        if "DW_AT_name" in die.attributes:
            self.name = die.attributes["DW_AT_name"].value.decode()
        elif "DW_AT_abstract_origin" in die.attributes:
            self.name = (
                die.get_DIE_from_attribute("DW_AT_abstract_origin").attributes["DW_AT_name"].value.decode()
            )
        self.addr = die.attributes["DW_AT_low_pc"].value
        self.return_type = (
            CType.get_by_die(die.get_DIE_from_attribute("DW_AT_type"))
            if "DW_AT_type" in die.attributes
            else None
        )

        CType.ctypes_by_name[self.name] = self

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.return_type if self.return_type else 'void'} {self.name}(...) @ {self.addr:08x}>"


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


def create_ctypes(file, readelf_binary="readelf", compilation_unit_filter=lambda: True):
    with open(file, "rb") as fp:
        elf = ELFFile(fp)
        CType.dwarf = elf.get_dwarf_info()
        CType.endian = "little" if CType.dwarf.config.little_endian else "big"
        for cu in CType.dwarf.iter_CUs():
            cuname = cu.get_top_DIE().attributes["DW_AT_name"].value.decode()
            if not compilation_unit_filter(cuname):
                continue
            for die in cu.iter_DIEs():
                if die.tag == "DW_TAG_base_type":
                    CType.get_by_die(die)
                elif die.tag == "DW_TAG_typedef":
                    CType.get_by_die(die)
                elif die.tag == "DW_TAG_pointer_type":
                    CType.get_by_die(die)
                elif die.tag == "DW_TAG_variable" and "DW_AT_specification" in die.attributes:
                    CVarElf(die)
                elif die.tag == "DW_TAG_variable":
                    if (
                        "DW_AT_external" in die.attributes
                        and die.attributes["DW_AT_external"].value
                        and "DW_AT_declaration" not in die.attributes
                    ):
                        CVarElf(die)
                elif die.tag == "DW_TAG_enumeration_type":
                    CType.get_by_die(die)
                elif die.tag == "DW_TAG_subprogram":
                    if "DW_AT_low_pc" not in die.attributes:
                        # No use for functions without an address
                        continue
                    CType.get_by_die(die)

    if readelf_binary:
        parse_macros(readelf_binary, file)
