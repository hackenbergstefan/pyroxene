from io import StringIO
import subprocess
import os
import re

import pycparser
import pycparser.c_ast
import pycparser.c_generator

from pcpp.preprocessor import Preprocessor


class NullIO:
    def write(self, *args, **kwargs):
        pass


GTI2_COMPANION_PREFIX = "_gti2_"
GTI2_COMPANION_FUNC_DECL_FLAGS = "__attribute__((noinline,used))"
GTI2_COMPANION_CONST_DECL_FLAGS = "__attribute__((used))"


class InlineFunctionGenerator(pycparser.c_generator.CGenerator):
    def __init__(self):
        super().__init__()
        self.default_generator = pycparser.c_generator.CGenerator()

    def visit_FuncDef(self, n):
        if "inline" not in n.decl.funcspec:
            return ""
        # Patch name
        functypedecl = n.decl.type
        while not isinstance(functypedecl, pycparser.c_ast.TypeDecl):
            functypedecl = functypedecl.type
        functypedecl.declname = f"{GTI2_COMPANION_PREFIX}{n.decl.name}"
        # Read parameters
        params = ",".join(p.name for p in n.decl.type.args.params if p.name is not None)
        # Create function definition
        result = " ".join(
            (
                GTI2_COMPANION_FUNC_DECL_FLAGS,
                self.default_generator.visit_FuncDecl(n.decl.type),
                f"{{ return {n.decl.name}({params}); }}\n",
            )
        )
        return result

    def visit_Decl(self, n, *args, **kwargs):
        if not isinstance(n.type, pycparser.c_ast.FuncDecl):
            return ""
        else:
            return super().visit_Decl(n, *args, **kwargs)

    def visit_Typedef(self, n):
        return ""

    def visit_FileAST(self, n):
        s = ""
        for ext in n.ext:
            if isinstance(ext, pycparser.c_ast.FuncDef):
                s += self.visit(ext)
            elif isinstance(ext, pycparser.c_ast.Pragma):
                result = self.visit(ext)
                if result:
                    s += result + "\n"
            else:
                result = self.visit(ext)
                if result:
                    s += result + ";\n"
        return s


class CompanionGenerator:
    default_sysincludes = ["/usr/include"]
    default_defines = [("__extension__", ""), ("__attribute__(x)", "")]

    def __init__(self, auto_sysincludes=True):
        self.defines = self.default_defines
        self.src_files = []
        self.auto_sysincludes = auto_sysincludes
        self.include_paths = [] if self.auto_sysincludes else self.default_sysincludes

        self.compiler = "gcc"
        self.preprocessor = Preprocessor()

    def resolve_sysinclude_paths(self):
        env = os.environ.copy()
        env["LANG"] = "en_EN.UTF8"
        p = subprocess.Popen(
            self.compiler.split(" ") + ["-E", "-v", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        p.stdin.write(b"\n")
        out, _ = p.communicate()
        sysincludepaths = [
            line.strip()
            for line in re.search(
                r"#include <...> search starts here:\n(.+?)End of search list.",
                out.decode(),
                flags=re.MULTILINE | re.DOTALL,
            )
            .group(1)
            .splitlines()
            if line.strip()
        ]
        defaultinclude = re.findall(r'# 1 "((?!<).+)"', out.decode())

        p = subprocess.Popen(
            self.compiler.split(" ") + ["-E", "-dM", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        p.stdin.write(b"\n")
        out, _ = p.communicate()
        sysmacros = []
        for line in out.decode().splitlines():
            name, _, definition = line.replace("#define ", "").partition(" ")
            if name != "__STDC_HOSTED__":
                sysmacros.append((name, definition))
        return sysincludepaths, defaultinclude, sysmacros

    def parse(self, additional_src: str = None):
        defaultinclude = []
        if self.auto_sysincludes:
            sysincludes, defaultinclude, sysmacros = self.resolve_sysinclude_paths()
            for inc in sysincludes:
                self.preprocessor.add_path(inc)
            for macro in sysmacros:
                self.preprocessor.define(" ".join(macro))

        for inc in self.include_paths:
            self.preprocessor.add_path(inc)
        for name, value in self.defines:
            self.preprocessor.define(f"{name} {value}")

        for file in self.src_files:
            with open(file) as fp:
                self.preprocessor.parse(fp, source=file)
        if additional_src is not None:
            self.preprocessor.parse(additional_src)
        out = StringIO()
        self.preprocessor.write(out)
        return out.getvalue()

    def generate_companion_inlines(self, data: str):
        parsed = pycparser.CParser().parse(data)
        return InlineFunctionGenerator().visit(parsed) + "\n"

    def generate_companion_numeric_macros(self):
        src = ""
        for macro in self.preprocessor.macros.values():
            if macro.source is not None and macro.source not in self.src_files:
                continue
            if macro.arglist:
                args = ",".join(f"unsigned long {a}" for a in macro.arglist)
                src += (
                    f"{GTI2_COMPANION_FUNC_DECL_FLAGS} unsigned long "
                    f"{GTI2_COMPANION_PREFIX}{macro.name}({args}) "
                    f"{{ return {macro.name}({','.join(macro.arglist)}); }}\n"
                )
            else:
                src += (
                    f"{GTI2_COMPANION_CONST_DECL_FLAGS} const unsigned long "
                    f"{GTI2_COMPANION_PREFIX}{macro.name} = {macro.name};\n"
                )

        return src + "\n"

    def parse_and_generate_companion_source(self, additional_src: str = None):
        parsed = self.parse(additional_src)
        return self.generate_companion_inlines(parsed) + self.generate_companion_numeric_macros()
