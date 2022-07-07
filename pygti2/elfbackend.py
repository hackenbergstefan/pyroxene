import re

from elftools.dwarf.dwarfinfo import DWARFInfo
from elftools.dwarf.dwarf_expr import DW_OP_opcode2name
from elftools.dwarf.descriptions import _DESCR_DW_ATE
from elftools.dwarf.die import DIE
from elftools.elf.elffile import ELFFile


def loc2addr(die: DIE):
    if "DW_AT_location" not in die.attributes:
        return None
    addr = die.attributes["DW_AT_location"].value
    if DW_OP_opcode2name[addr[0]] != "DW_OP_addr":
        raise ValueError("Not an address.")
    addr = addr[1:]
    if len(addr) != die.dwarfinfo.config.default_address_size:
        raise NotImplementedError("No idea how to parse this address.")
    return int.from_bytes(addr, "little" if die.dwarfinfo.config.little_endian else "big")


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
            self.size = -1

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypeBaseType":
        raise TypeError("Abstract method.")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CType):
            if other.typename == self.typename:
                return True
        return False

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} "{self.typename}">'


class CTypeBaseType(CType):
    """
    Types with tag "DW_TAG_base_type"
    """

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypeBaseType":
        encoding = dw_at_encoding(die)
        if encoding in ("(unsigned)", "(signed)", "(unsigned char)", "(signed char)", "(boolean)"):
            return CTypeBaseInt(backend, die)
        elif encoding in ("(float)",):
            return CTypeBaseFloat(backend, die)
        else:
            raise NotImplementedError(f"Unkown encoding: {encoding}")


class CTypeBaseInt(CTypeBaseType):
    """
    Types with tag "DW_TAG_base_type" and integer like encoding
    """

    def __init__(self, backend: "ElfBackend", die: DIE):
        super().__init__(backend, die)
        self.kind = "int"


class CTypeBaseFloat(CTypeBaseType):
    """
    Types with tag "DW_TAG_base_type" and float like encoding
    """

    def __init__(self, backend: "ElfBackend", die: DIE):
        super().__init__(backend, die)
        self.kind = "float"


class CTypePointer(CType):
    def __init__(self, backend: "ElfBackend", die: DIE, base: CType):
        super().__init__(backend, die)
        self.kind = "pointer"
        self.base = base
        if base is not None and self.base.typename != "?":
            self.typename = f"{self.base.typename} *"

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypePointer":
        if "DW_AT_type" not in die.attributes:
            return CTypePointer(backend, None, backend.type_from_string("void"))
        basedie = die.get_DIE_from_attribute("DW_AT_type")
        base = backend.type_from_die(basedie)
        if base is None and "DW_AT_type" in basedie.attributes:
            base = backend.type_from_die(basedie.get_DIE_from_attribute("DW_AT_type"))
        if base is None:
            base = backend.types["void"]
        return CTypePointer(backend, die, base)


class CTypeArray(CType):
    def __init__(self, backend: "ElfBackend", die: DIE, base: CType):
        super().__init__(backend, die)
        self.kind = "array"
        self.length = self._length(self.die)
        if self.length == -1 or base.size == -1:
            self.size = -1
        else:
            self.size = self.length * base.size
        self.base = base

    def _length(self, die: DIE):
        if not die:
            return -1
        for child in die.iter_children():
            if child.tag != "DW_TAG_subrange_type":
                continue
            if "DW_AT_upper_bound" in child.attributes:
                return child.attributes["DW_AT_upper_bound"].value + 1
            return -1

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypeArray":
        base = backend.type_from_die(die.get_DIE_from_attribute("DW_AT_type"))
        return CTypeArray(backend, die, base)

    def update(self, other: "CTypeArray"):
        if self.length == -1 and other.length != -1:
            self.length = other.length
            self.size = other.size


class CTypeTypedef(CType):
    """
    Types with tag "DW_TAG_typedef".
    """

    def __init__(self, backend: "ElfBackend", die: DIE, base: CTypeBaseType):
        CType.__init__(self, backend, die)
        self.size = base.size
        self.base = base

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypeTypedef":
        if "DW_AT_type" not in die.attributes:
            return None
        base = backend.type_from_die(die.get_DIE_from_attribute("DW_AT_type"))
        if base.kind == "int":
            return CTypeTypedefInt(backend, die, base)
        elif base.kind == "struct":
            return CTypeTypedefStruct(backend, die, base)
        elif base.kind == "pointer":
            return CTypeTypedefPointer(backend, die, base)
        elif base.kind == "array":
            return CTypeTypedefArray(backend, die, base)
        elif base.kind == "union":
            return CTypeTypedefUnion(backend, die, base)
        else:
            raise NotImplementedError(f"Unkown base kind: {base}")


class CTypeTypedefInt(CTypeTypedef):
    """
    Types with tag "DW_AT_typedef" and int like.
    """

    def __init__(self, backend: "ElfBackend", die: DIE, base: CTypeBaseType):
        super().__init__(backend, die, base)
        self.kind = "int"


class CTypeStruct(CType):
    """
    Types with tag "DW_TAG_structure_type".
    """

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypeStruct":
        return CTypeStruct(backend, die)

    def __init__(self, backend: "ElfBackend", die: DIE):
        super().__init__(backend, die)
        self.kind = "struct"
        if self.typename != "?":
            self.typename = f"struct {self.typename}"
        # self._create_members(self.die)

    def _create_members(self, die):
        members = {}
        for child in die.iter_children():
            child: DIE = child
            if child.tag != "DW_TAG_member":
                continue
            membertypedie = child.get_DIE_from_attribute("DW_AT_type")
            membertype = self.backend.type_from_die(membertypedie)
            # if membertypedie != die:
            #     membertype = self.backend.type_from_die(membertypedie)
            # else:
            #     membertype = self
            members[child.attributes["DW_AT_name"].value.decode()] = (
                child.attributes["DW_AT_data_member_location"].value,
                membertype,
            )
        self.members = members


class CTypeTypedefStruct(CTypeTypedef, CTypeStruct):
    """
    Types with tag "DW_TAG_typedef" and type CTypeStructure.
    """

    def __init__(self, backend: "ElfBackend", die: DIE, base: CTypeStruct):
        CTypeTypedef.__init__(self, backend, die, base)
        self.kind = "struct"
        self._create_members(self.base.die)


class CTypeUnion(CType):
    """
    Types with tag "DW_TAG_union_type".
    """

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypeUnion":
        return CTypeUnion(backend, die)

    def __init__(self, backend: "ElfBackend", die: DIE):
        super().__init__(backend, die)
        self.kind = "union"
        if self.typename != "?":
            self.typename = f"union {self.typename}"

    def _create_members(self, die):
        members = {}
        for child in die.iter_children():
            child: DIE = child
            if child.tag != "DW_TAG_member":
                continue
            membertypedie = child.get_DIE_from_attribute("DW_AT_type")
            membertype = self.backend.type_from_die(membertypedie)
            members[child.attributes["DW_AT_name"].value.decode()] = (0, membertype)
        self.members = members


class CTypeTypedefUnion(CTypeTypedef, CTypeUnion):
    """
    Types with tag "DW_TAG_typedef" and type CTypeUnionure.
    """

    def __init__(self, backend: "ElfBackend", die: DIE, base: CTypeUnion):
        CTypeTypedef.__init__(self, backend, die, base)
        self.kind = "union"
        self._create_members(self.base.die)


class CTypeTypedefPointer(CTypeTypedef, CTypePointer):
    """
    Types with tag "DW_TAG_typedef" and type CTypePointer.
    """

    def __init__(self, backend: "ElfBackend", die: DIE, base: CTypePointer):
        CTypeTypedef.__init__(self, backend, die, base)
        self.kind = "pointer"


class CTypeTypedefArray(CTypeTypedef, CTypeArray):
    """
    Types with tag "DW_TAG_typedef_type" and type CTypeArray.
    """

    def __init__(self, backend: "ElfBackend", die: DIE, base: CTypeArray):
        CTypeTypedef.__init__(self, backend, die, base)
        self.kind = "array"
        self.size = base.size

    def update(self, other: "CTypeTypedefArray"):
        if self.size == -1:
            self.size = other.size
            self.base.update(other.base)


class CTypeEnumeration(CType):
    """
    Types with tag "DW_TAG_enumeration_type".
    """

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypeBaseType":
        type = CTypeEnumeration(backend, die)
        type.kind = "int"
        return type

    def __init__(self, backend: "ElfBackend", die: DIE):
        super().__init__(backend, die)
        self._create_enums(self.die)

    def _create_enums(self, die):
        for child in die.iter_children():
            child: DIE = child
            if child.tag != "DW_TAG_enumerator":
                continue
            self.backend.enums[child.attributes["DW_AT_name"].value.decode()] = child.attributes[
                "DW_AT_const_value"
            ].value


class CTypeVariable(CType):
    """
    Types with tag "DW_TAG_variable_type".
    """

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypeVariable":
        location = None
        if "DW_AT_specification" in die.attributes:
            location = loc2addr(die)
            die = die.get_DIE_from_attribute("DW_AT_specification")
        typedie = die.get_DIE_from_attribute("DW_AT_type")
        if typedie.tag == "DW_TAG_const_type":
            typedie = typedie.get_DIE_from_attribute("DW_AT_type")
        type = backend.type_from_die(typedie)
        return CTypeVariable(backend, die, type, location)

    def __init__(self, backend: "ElfBackend", die: DIE, type: CType, location: int = None):
        super().__init__(backend, die)
        self.kind = "variable"
        self.type = type
        self.address = location if location is not None else loc2addr(die)
        self.size = type.size

    def update(self, other: "CTypeVariable"):
        if self.address is None:
            self.address = other.address
            self.type = other.type
        if self.size == -1:
            self.size = other.size
            self.type = other.type


class CTypeFunction(CType):
    """
    Types with tag "DW_TAG_function".
    """

    @classmethod
    def _new(cls, backend: "ElfBackend", die: DIE) -> "CTypeFunction":
        if "DW_AT_low_pc" not in die.attributes:
            # Functions without location are useless
            return None
        return CTypeFunction(backend, die)

    def __init__(self, backend: "ElfBackend", die: DIE):
        super().__init__(backend, die)
        self.kind = "function"
        if "DW_AT_abstract_origin" in die.attributes:
            basedie = die.get_DIE_from_attribute("DW_AT_abstract_origin")
        else:
            basedie = die

        if "DW_AT_low_pc" in die.attributes:
            self.address = die.attributes["DW_AT_low_pc"].value
        elif basedie is not None:
            self.address = basedie.attributes["DW_AT_low_pc"].value
        self._create_argument_types(basedie)

    def _create_argument_types(self, die: DIE):
        if "DW_AT_type" in self.die.attributes:
            self.return_type = self.backend.type_from_die(self.die.get_DIE_from_attribute("DW_AT_type"))
        else:
            self.return_type = None
        self.arguments = []
        for child in self.die.iter_children():
            if child.tag != "DW_TAG_formal_parameter":
                continue
            if "DW_AT_type" in child.attributes:
                argdie = child.get_DIE_from_attribute("DW_AT_type")
            elif "DW_AT_abstract_origin" in child.attributes:
                argdie = child.get_DIE_from_attribute("DW_AT_abstract_origin")
            self.arguments.append(self.backend.type_from_die(argdie))


class ElfBackend:
    def __init__(
        self,
        file: str,
        readelf_binary="readelf",
        compilation_unit_filter=lambda _: True,
        tolerant: bool = True,
    ):
        self.types = {}
        self.enums = {}
        self.types["void"] = voidtype = CTypeBaseType(self, None)
        voidtype.typename = "void"
        self._create(file, readelf_binary, compilation_unit_filter, tolerant)

    def type_from_die(self, die: DIE):
        if die.tag == "DW_TAG_base_type":
            type = CTypeBaseType._new(self, die)
        elif die.tag == "DW_TAG_typedef":
            type = CTypeTypedef._new(self, die)
        elif die.tag == "DW_TAG_structure_type":
            type = CTypeStruct._new(self, die)
        elif die.tag == "DW_TAG_union_type":
            type = CTypeUnion._new(self, die)
        elif die.tag == "DW_TAG_pointer_type":
            type = CTypePointer._new(self, die)
        elif die.tag == "DW_TAG_array_type":
            type = CTypeArray._new(self, die)
        elif die.tag == "DW_TAG_variable":
            type = CTypeVariable._new(self, die)
        elif die.tag == "DW_TAG_subprogram":
            type = CTypeFunction._new(self, die)
        elif die.tag == "DW_TAG_enumeration_type":
            type = CTypeEnumeration._new(self, die)
        elif die.tag == "DW_TAG_const_type":
            if "DW_AT_type" in die.attributes:
                type = self.type_from_die(die.get_DIE_from_attribute("DW_AT_type"))
            else:
                type = self.types["void"]
        else:
            return None

        if type is None:
            return None
        if type.typename == "?":
            return type
        if type.typename in self.types:
            other = self.types[type.typename]
            if hasattr(other, "update"):
                other.update(type)
            return other
        else:
            self.types[type.typename] = type
            if type.kind in ("struct", "union") and not hasattr(type, "members"):
                type._create_members(type.die)
            return type

    def _create(
        self,
        file: str,
        readelf_binary="readelf",
        compilation_unit_filter=lambda _: True,
        tolerant=True,
    ):
        with open(file, "rb") as fp:
            self.elffile: ELFFile = ELFFile(fp)
            self.dwarfinfo: DWARFInfo = self.elffile.get_dwarf_info()
            self.endian: str = "little" if self.dwarfinfo.config.little_endian else "big"
            self.sizeof_voidp: int = self.dwarfinfo.config.default_address_size
            for cu in self.dwarfinfo.iter_CUs():
                cuname = cu.get_top_DIE().attributes["DW_AT_name"].value.decode()
                if not compilation_unit_filter(cuname):
                    continue
                depth = 0
                for die in cu.iter_DIEs():
                    if die.is_null():
                        depth -= 1
                        continue
                    if depth == 1:
                        # if "DW_AT_name" in die.attributes:
                        #     print(die.tag, die.attributes["DW_AT_name"].value.decode())
                        self.type_from_die(die)
                    if die.has_children:
                        depth += 1

    def type_from_string(self, decl: str):
        if decl in self.types:
            return self.types[decl]
        match = re.match(
            r"^(?P<base_pointer>[\w ]+\w(?: ?\*)*) ?\*$|"
            r"^(?P<base_array>[\w ]+\w) ?\[(?P<array_length>\d+)\]$",
            decl,
        )
        if not match:
            raise TypeError(f'Cannot create type from "{decl}".')

        if match.group("base_pointer"):
            base = self.types[match.group("base_pointer")]
            type = CTypePointer(self, None, base)
            type.kind = "pointer"
            type.size = self.sizeof_voidp
            type.typename = f"{base.typename} *"
        elif match.group("base_array"):
            base = self.types[match.group("base_array")]
            type = CTypeArray(self, None, base)
            type.kind = "array"
            type.length = int(match.group("array_length"), 0)
            type.size = type.length * base.size
            type.typename = f"{base.typename} [{type.length}]"
        else:
            raise TypeError(f'Cannot create type from "{decl}".')

        if type.typename == "?":
            return type
        if type.typename in self.types:
            return self.types[type.typename]
        else:
            self.types[type.typename] = type
            return type
