import sys

from pygti2.device_proxy import NewVarProxy
from pygti2.elfproxy import CTypeArrayType, CTypePointerType, CVarElf


class SimpleMemoryManager:
    def __init__(self, name_of_heap: str):
        var = CVarElf._cvars[name_of_heap]
        self.base_addr = var._addr
        self.max_size = var._type.size

        self.used = 0
        self.allocated = []

    def malloc(self, variable: NewVarProxy):
        self.autofree()

        if not isinstance(variable._type, (CTypePointerType, CTypeArrayType)):
            raise ValueError(f"Only idea how to allocate: {variable}")

        required_size = variable._type.base_size
        if self.max_size - self.used < required_size:
            raise MemoryError("Out of memory.")

        variable._addr = self.base_addr + self.used
        self.used += required_size
        self.allocated.append(variable)

    def autofree(self):
        # 1. Remove objects which are not referenced anymore
        i = 0
        while i < len(self.allocated):
            var = self.allocated[i]
            count = sys.getrefcount(var)
            if count == 3:
                del self.allocated[i]
            i += 1

        # 2. Calculate current highest used address
        highest_used = list(
            sorted([variable._addr + variable._type.base_size for variable in self.allocated])
        )
        if len(highest_used) == 0:
            highest_used = 0
        else:
            highest_used = highest_used[-1] - self.base_addr
        self.used = highest_used
