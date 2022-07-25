import glob
import os
import re
import subprocess
import tempfile

import cffi
import pycparser
import pycparser.c_ast
import pycparser.c_generator


root_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "c"))


def read(file):
    with open(file) as fp:
        return fp.read()


class IncludeFileNotFoundError(Exception):
    pass


class CFFIGenerator(pycparser.c_generator.CGenerator):
    def __init__(self, source):
        super().__init__()
        self.source = source

    # pylint: disable=invalid-name
    def visit_Decl(self, n, *args, **kwargs):
        # pylint: disable=signature-differs
        result = super().visit_Decl(n, *args, **kwargs)
        if n.name and n.name.startswith("__cdecl"):
            return ""
        if n.name and isinstance(n.type, pycparser.c_ast.FuncDecl) and n.name not in self.source:
            return ""
        return result

    def visit_BinaryOp(self, n, *args, **kwargs):
        # pylint: disable=unused-argument
        return "..."

    def visit_UnaryOp(self, n, *args, **kwargs):
        # pylint: disable=unused-argument
        return "..."

    def visit_Cast(self, n, *args, **kwargs):
        # pylint: disable=unused-argument
        return "..."

    def visit_FuncDef(self, n, *args, **kwargs):
        # pylint: disable=unused-argument
        if "extern" in n.decl.storage:
            return ""
        if n.decl.name and n.decl.name.startswith("__"):
            return ""
        return super().visit_Decl(n.decl) + ";\n"


def preprocess(cpp, source, include_directories=None):
    os.environ.pop("LD_PRELOAD", None)
    define_params = ["-D__attribute__(x)=", "-D_WINSOCK2API_"]
    include_options = ["-I" + path for path in include_directories or []]
    if os.name == "nt":
        source = "\n".join(
            (
                "#define __attribute__(x)",
                "#define __declspec(x)",
                "#define __int32 long",
                "#define __int64 long long",
                "#define __ptr64",
                source,
            )
        )
        try:
            programfiles = os.environ["PROGRAMFILES(X86)"]
        except KeyError:
            programfiles = os.environ["PROGRAMFILES"]
        vcdir = os.path.join(programfiles, "Microsoft Visual Studio 14.0\\VC")
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            try:
                fp.write(source.encode())
                fp.close()
                result = subprocess.check_output(
                    ["call", os.path.join(vcdir, "vcvarsall.bat"), "&&", "cl.exe"]
                    + include_options
                    + ["-EP", fp.name],
                    shell=True,
                    universal_newlines=True,
                )
            finally:
                fp.close()
                os.unlink(fp.name)
    else:
        result = subprocess.check_output(
            cpp + define_params + include_options + ["-E", "-P", "-"],
            input=source,
            universal_newlines=True,
        )
    return re.sub(
        "|".join(
            [
                "(\x0c",
                "__asm__[^;]*",
                "__asm[ \t]+{[^}]+}",
                "(?<=__cdecl)[ ]+",
                "__extension__",
                "__fastcall",
                "__forceinline",
                "__inline",
                "__pragma.*",
                "#pragma.*",
                "__restrict",
                "__stdcall",
                "^\\s*\\.[\\w\\.]+ = )",
            ]
        ),
        "",
        result,
        flags=re.MULTILINE,
    )


def build(name, cdef_headers, inc_dirs, src_patterns, externs=[], cpp=["gcc"], call_c_compiler=True):
    inc_dirs = [os.path.join(root_directory, dir) for dir in inc_dirs]

    cdef_files = []
    for file in cdef_headers:
        candidates = [os.path.join(dir, file) for dir in inc_dirs]
        candidates = list(filter(os.path.exists, candidates))
        if not candidates:
            raise IncludeFileNotFoundError(f"Include file '{file}' not found")
        cdef_files.append(candidates[0])

    src_files = sum(
        (glob.glob(os.path.join(root_directory, pat)) for pat in src_patterns),
        [],
    )
    cdef = preprocess(
        cpp,
        source="\n".join(read(f) for f in cdef_files),
        include_directories=inc_dirs,
    )
    cdef = CFFIGenerator(source="\n".join(read(f) for f in cdef_files)).visit(pycparser.CParser().parse(cdef))
    cdef += "\n" + "\n".join(
        statement.group(1) + " ..."
        for file in cdef_files
        for statement in re.finditer(
            "(#define[ \t]+[a-zA-Z0-9_]+)[ \t]+(\\S+[)]|[(])?[ \t]*-?(0x[0-9a-fA-F]+|[A-Z0-9_]+)",
            read(file),
        )
    )
    cdef += "\n" + "\n".join(externs)

    ffibuilder = cffi.FFI()
    ffibuilder.cdef(cdef, override=True)
    ffibuilder.set_source(
        module_name=name,
        source="\n".join(f'#include "{file}"' for file in cdef_files),
        sources=src_files,
        include_dirs=inc_dirs,
        call_c_compiler=call_c_compiler,
    )
    ffibuilder.compile(target=f"../{name}.*", tmpdir=f"./_build_{name}")
