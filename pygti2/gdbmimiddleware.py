import functools
import logging

from pygdbmi.gdbcontroller import GdbController

# TODO move this to a better place
DEFAULT_GDB_TIMEOUT_SEC = 5

C_INTS = ["int", "uint8_t", "uint16_t", "uint32_t"]  # TODO: expand this


class GdbmiException(Exception):
    pass


class GdbmiMiddleware:
    def __init__(self, mi=None, **kwargs):
        self._mi = mi or GdbController(**kwargs)

    @functools.lru_cache(maxsize=1024)
    def write(
        self,
        command,
        response_messages=("done", "running"),
        response_types=None,
        timeout=DEFAULT_GDB_TIMEOUT_SEC,
    ):
        logging.getLogger(__name__).debug(f">> {command}")
        self._mi.write(command, read_response=False)
        if response_messages is None:
            return None
        while True:
            for response in self._mi.get_gdb_response(timeout):
                logging.getLogger(__name__).debug(f"<< {response}")
                if response["message"] == "error":
                    raise GdbmiException(command, response)
                elif response_messages is not None and response["message"] not in response_messages:
                    continue
                elif response_types is not None and response["type"] not in response_types:
                    continue
                return response

    def eval(self, expression: str) -> str:
        # TODO: proper escaping of expression strings.
        response = self.write(f'-data-evaluate-expression "{expression}"')
        result = response["payload"]["value"]
        return result

    def console(self, command: str) -> str:
        # TODO: proper escaping of commands.
        response = self.write(
            f'-interpreter-exec console "{command}"',
            response_messages=(None,),
            response_types=("console",),
        )
        return response["payload"]

    def _resolve_type(self, typ: str, accessor: str, addr: int) -> str:
        expr_type = self.console(f"whatis (({typ})0x{addr:x}){accessor}").replace("\\n", "", 1)
        if not expr_type.startswith("type = "):
            raise ValueError("WTF?", expr_type)
        typ = expr_type.replace("type = ", "", 1)
        return typ.strip()

    def whatis(self, what: str) -> str:
        expr_type = self.console(f"whatis {what}").replace("\\n", "", 1)
        if not expr_type.startswith("type = "):
            raise ValueError("Not a type", expr_type)
        typ = expr_type.replace("type = ", "", 1)
        return typ.strip()

    def sizeof(self, typ: str) -> int:
        if typ == "void":
            # GDB says void is 1. I regard it as 0 :-)
            return 0
        size = gdb_decode(self.eval(f"sizeof({typ})"), "int")
        return size

    def alignof(self, typ: str) -> int:
        alignment = gdb_decode(self.eval(f"_Alignof({typ})"), "int")
        return alignment

    def offset_of(self, typ: str, member: str) -> int:
        offset = gdb_decode(self.eval(f"&(({typ}) 0)->{member}"), "int")
        return offset

    def symbol_info_functions(self, name: str):
        response = self.write(f"-symbol-info-functions --name {name}")
        try:
            return response["payload"]["symbols"]["debug"]
        except KeyError:
            return None

    def symbol_info_variables(self, name: str):
        response = self.write(f"-symbol-info-variables --name {name}")
        try:
            return response["payload"]["symbols"]["debug"]
        except KeyError:
            return None


def gdb_encode(value, type: str):
    # TODO: support more types
    if type in C_INTS:
        if not isinstance(value, int):
            raise TypeError(f"Expected int, got {type(value)}")
        return str(value)
    else:
        raise TypeError(f"Unsupported Type: {type}")
    # else:  # cdata handles all pointers
    #     if not isinstance(value, metagti.cdata):
    #         raise TypeError("C type annotations require a cdata value")
    #     if value._is_value:
    #         return f"*(({value._type}*)0x{value._addr:x})"
    #     else:
    #         return f"(({value._type}*)0x{value._addr:x})"


def gdb_decode(value, type: str):
    # TODO: support more types
    if type in C_INTS:
        (value, _, _) = value.partition(" ")  # remove gdb string value when querying string pointers
        return int(value, base=0)  # allow 0x hex
    elif type == "void":
        return None
    else:
        raise TypeError(f"Unsupported Type: {type}")
