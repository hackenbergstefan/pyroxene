import subprocess
import re
from typing import Optional

from elftools.dwarf.dwarfinfo import DWARFInfo
from elftools.dwarf.dwarf_expr import DW_OP_opcode2name
from elftools.dwarf.descriptions import _DESCR_DW_ATE
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


def dw_at_encoding(die: DIE):
    map = dict(enumerate(_DESCR_DW_ATE.values()))
    return map[die.attributes["DW_AT_encoding"].value]


class CType:
    def __init__(self, backend, die: DIE):
        self.backend = backend
        self.die = die
        self.kind = "none"

        if die and "DW_AT_name" in die.attributes:
            self.typename = die.attributes["DW_AT_name"].value.decode()
        else:
            self.typename = "?"

        if die and "DW_AT_byte_size" in die.attributes:
            self.size = die.attributes["DW_AT_byte_size"].value
        else:
            self.size = 0

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypeBaseType":
        raise TypeError("Abstract method.")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CType):
            if other.typename == self.typename:
                return True
        return False


class CTypeBaseType(CType):
    """
    Types with tag "DW_AT_base_type"
    """

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypeBaseType":
        encoding = dw_at_encoding(die)
        if encoding in ("(unsigned)", "(signed)"):
            return CTypeBaseInt(backend, die)
        elif encoding in ("(unsigned char)", "(signed char)"):
            return CTypeBaseByte(backend, die)
        else:
            raise NotImplementedError(f"Unkown encoding: {encoding}")


class CTypeBaseInt(CTypeBaseType):
    """
    Types with tag "DW_AT_base_type" and integer like encoding
    """

    def __init__(self, backend: "ElfBackend", die: DIE):
        super().__init__(backend, die)
        self.kind = "int"


class CTypeBaseByte(CTypeBaseType):
    """
    Types with tag "DW_AT_base_type" and byte or char like encoding.
    """

    def __init__(self, backend: "ElfBackend", die: DIE):
        super().__init__(backend, die)
        self.kind = "byte"


class CTypeTypedef(CType):
    """
    Types with tag "DW_AT_typedef".
    """

    def __init__(self, backend: "ElfBackend", die: DIE, base: CTypeBaseType):
        super().__init__(backend, die)
        self.size = base.size
        self.base = base

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypeTypedef":
        base = CTypeTypedef._base_type(backend, die)
        if base.kind == "int":
            return CTypeTypedefInt(backend, die, base)
        elif base.kind == "byte":
            return CTypeTypedefByte(backend, die, base)
        elif base.kind == "struct":
            return CTypeTypedefStruct(backend, die, base)
        else:
            raise NotImplementedError(f"Unkown base kind: {base}")

    @classmethod
    def _base_type(cls, backend, die):
        """Corresponding base type."""
        while die.tag != "DW_TAG_base_type":
            if "DW_AT_type" not in die.attributes:
                break
            die = die.get_DIE_from_attribute("DW_AT_type")
        return backend.type_from_die(die)


class CTypeTypedefInt(CTypeTypedef):
    """
    Types with tag "DW_AT_typedef" and int like.
    """

    def __init__(self, backend: "ElfBackend", die: DIE, base: CTypeBaseType):
        super().__init__(backend, die, base)
        self.kind = "int"


class CTypeTypedefByte(CTypeTypedef):
    """
    Types with tag "DW_AT_typedef" and byte like.
    """

    def __init__(self, backend: "ElfBackend", die: DIE, base: CTypeBaseType):
        super().__init__(backend, die, base)
        self.kind = "byte"


class CTypeStruct(CType):
    """
    Types with tag "DW_AT_structure_type".
    """

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypeStruct":
        return CTypeStruct(backend, die)

    def __init__(self, backend: "ElfBackend", die: DIE):
        super().__init__(backend, die)
        self.kind = "struct"
        self._create_members(self.die)

    def _create_members(self, die):
        members = {}
        for child in die.iter_children():
            child: DIE = child
            if child.tag != "DW_TAG_member":
                continue
            membertypedie = child.get_DIE_from_attribute("DW_AT_type")
            if membertypedie != die:
                membertype = self.backend.type_from_die(membertypedie)
            else:
                membertype = self
            members[child.attributes["DW_AT_name"].value.decode()] = (
                child.attributes["DW_AT_data_member_location"].value,
                membertype,
            )
        self.members = members


class CTypeTypedefStruct(CTypeTypedef, CTypeStruct):
    """
    Types with tag "DW_AT_typedef_type" and type CTypeStructure.
    """

    def __init__(self, backend: "ElfBackend", die: DIE, base: CTypeStruct):
        CTypeTypedef.__init__(self, backend, die, base)
        self.kind = "typedef struct"
        self._create_members(self.base.die)


class ElfBackend:
    def __init__(self, file: str, readelf_binary="readelf", compilation_unit_filter=lambda _: True):
        self.types = {}
        self._create(file, readelf_binary, compilation_unit_filter)

    def type_from_die(self, die: DIE):
        if die.tag == "DW_TAG_base_type":
            type = CTypeBaseType._new(self, die)
        elif die.tag == "DW_TAG_typedef":
            type = CTypeTypedef._new(self, die)
        elif die.tag == "DW_TAG_structure_type":
            type = CTypeStruct._new(self, die)
        else:
            return None

        if type.typename == "?":
            return type
        if type.typename in self.types:
            return self.types[type.typename]
        else:
            self.types[type.typename] = type
            return type

    def _create(self, file: str, readelf_binary="readelf", compilation_unit_filter=lambda _: True):
        with open(file, "rb") as fp:
            self.elffile: ELFFile = ELFFile(fp)
            self.dwarfinfo: DWARFInfo = self.elffile.get_dwarf_info()
            self.endian: str = "little" if self.dwarfinfo.config.little_endian else "big"
            for cu in self.dwarfinfo.iter_CUs():
                cuname = cu.get_top_DIE().attributes["DW_AT_name"].value.decode()
                if not compilation_unit_filter(cuname):
                    continue
                for die in cu.iter_DIEs():
                    self.type_from_die(die)
