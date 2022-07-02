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
GTI2_COMPANION_PREFIX_PTR = "_gti2_ptr_"
GTI2_COMPANION_FUNC_DECL_FLAGS = "__attribute__((noinline,used))"
GTI2_COMPANION_CONST_DECL_FLAGS = "__attribute__((used))"


class InlineFunctionGenerator(pycparser.c_generator.CGenerator):
    def __init__(self):
        super().__init__()
        self.default_generator = pycparser.c_generator.CGenerator()

    def _generate_funcdef_default(self, n: pycparser.c_ast.FuncDef):
        # Patch name
        functypedecl = n.decl.type
        while not isinstance(functypedecl, pycparser.c_ast.TypeDecl):
            functypedecl = functypedecl.type
        functypedecl.declname = f"{GTI2_COMPANION_PREFIX}{n.decl.name}"

        # Read parameters
        params = ",".join(p.name for p in n.decl.type.args.params if p.name is not None)
        # Create function definition
        return " ".join(
            (
                GTI2_COMPANION_FUNC_DECL_FLAGS,
                self.default_generator.visit_FuncDecl(n.decl.type),
                f"{{ return {n.decl.name}({params}); }}\n",
            )
        )

    def _generate_funcdef_ptr(self, n: pycparser.c_ast.FuncDef):
        returntype = self.default_generator.visit(n.decl.type.type)
        params = ",".join(p.name for p in n.decl.type.args.params if p.name is not None)
        param_decl = self.default_generator.visit(n.decl.type.args)

        if returntype == "void":
            return ""
        param_decl = f"{returntype} *_" + ("," + param_decl if param_decl != "void" else "")
        return " ".join(
            (
                GTI2_COMPANION_FUNC_DECL_FLAGS,
                f"void {GTI2_COMPANION_PREFIX_PTR}{n.decl.name}({param_decl})",
                f"{{*_ = {n.decl.name}({params}); }}\n",
            )
        )

    def visit_FuncDef(self, n):
        if "inline" not in n.decl.funcspec:
            return ""
        return self._generate_funcdef_default(n) + "\n" + self._generate_funcdef_ptr(n)

    def visit_Decl(self, n, *args, **kwargs):
        return ""

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


class MacroGenerator:
    statement_indicator = re.compile(r"\b(if|else|while|do|void|inline|__attribute__)\b|#|{|}|\?|:")

    def __init__(self, macro, preprocessor: Preprocessor):
        self.macro = macro
        self.has_args = self.macro.arglist is not None and len(self.macro.arglist) > 0
        self.is_empty = len(self.macro.value) == 0
        self.preprocessor = preprocessor
        if not self.is_empty:
            self.compiled = "".join(tok.value for tok in preprocessor.expand_macros(macro.value))
            if not self.compiled.strip():
                self.is_empty = True

    def _generate_code_const(self):
        return (
            f"{GTI2_COMPANION_CONST_DECL_FLAGS} const unsigned long "
            f"{GTI2_COMPANION_PREFIX}{self.macro.name} = {self.macro.name};\n"
        )

    def _generate_code_function_with_args(self):
        args = ",".join(f"unsigned long {a}" for a in self.macro.arglist)
        return (
            f"{GTI2_COMPANION_FUNC_DECL_FLAGS} unsigned long "
            f"{GTI2_COMPANION_PREFIX}{self.macro.name}({args}) "
            f"{{ return {self.macro.name}({','.join(self.macro.arglist)}); }}\n"
        )

    def generate_code(self):
        if self.is_empty:
            return ""
        elif self.statement_indicator.search(self.compiled):
            return ""  # TODO: Can we generate code safely?
        elif self.has_args:
            return self._generate_code_function_with_args()

        return self._generate_code_const()


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
        if self.auto_sysincludes:
            sysincludes, _, sysmacros = self.resolve_sysinclude_paths()
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
        includes_abspath = [os.path.abspath(inc) for inc in self.include_paths]

        def macro_source_in_includes(src):
            if src == "":
                return False
            src = os.path.abspath(src)
            return any([src.startswith(p) for p in includes_abspath])

        src = ""
        for macro in self.preprocessor.macros.values():
            # Check if macro was defined either in src_files or somewhere in include_paths
            if (
                macro.source is not None
                and macro.source not in self.src_files
                and not macro_source_in_includes(macro.source)
            ):
                continue

            src += MacroGenerator(macro, self.preprocessor).generate_code()

        return src + "\n"

    def parse_and_generate_companion_source(self, additional_src: str = None):
        parsed = self.parse(additional_src)
        return (
            "".join(f'#include "{inc}"\n' for inc in self.src_files)
            + self.generate_companion_inlines(parsed)
            + self.generate_companion_numeric_macros()
        )
