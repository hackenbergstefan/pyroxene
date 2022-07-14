import logging
import sys
from typing import List

from pygti2.device_proxy import LibProxy, VarProxy

logger = logging.getLogger(__name__)


class SimpleMemoryManager:
    def __init__(self, lib: LibProxy, name_of_heap: str = "gti2_memory"):
        self.lib = lib
        var = getattr(lib, name_of_heap)
        self.base_addr = var.address
        self.max_size = lib.sizeof(var)

        self.used = 0
        self.allocated: List[VarProxy] = []

    def malloc(self, variable: VarProxy):
        self.autofree()

        required_size = self.lib.sizeof(variable)
        if self.max_size - self.used < required_size:
            raise MemoryError("Out of memory.")

        variable.address = self.base_addr + self.used
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
            sorted([variable.address + self.lib.sizeof(variable) for variable in self.allocated])
        )
        if len(highest_used) == 0:
            highest_used = 0
        else:
            highest_used = highest_used[-1] - self.base_addr
        self.used = highest_used

    def free(self, variable: VarProxy):
        logger.debug(f"SimpleMemoryManager:free: {self.lib.sizeof(variable)} @ {variable.address:08x}")
        self.allocated.remove(variable)
        # self.autofree()
