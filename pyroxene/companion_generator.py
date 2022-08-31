from io import StringIO
import logging
import os
import re
import subprocess
from typing import Iterable, List, Tuple

from pcpp.preprocessor import Preprocessor  # type: ignore[import]
import pycparser  # type: ignore[import]
import pycparser.c_ast  # type: ignore[import]
import pycparser.c_generator  # type: ignore[import]

logger = logging.getLogger(__name__)


class NullIO:
    def write(self, *args, **kwargs):
        pass


class MacroCollector:
    statement_indicator = re.compile(r"\b(if|else|while|do|void|inline|__attribute__)\b|#|{|}|\?|:")

    def __init__(self, preprocessor: Preprocessor, paths: Iterable[str]):
        self.preprocessor = preprocessor
        self.paths = [os.path.abspath(p) for p in paths]

        self.macro_numerics, self.macro_strings, self.macro_functions, self.macro_statements = self._collect()

    def _collect(self):
        numerics = {}
        strings = {}
        functions = {}
        statements = {}

        for macroname, macro in self.preprocessor.macros.items():
            # Skip empty macros
            if len(macro.value) == 0:
                continue
            # Skip macros which are not defined in given paths
            if macro.source is not None and not self._macro_defined_in_paths(macro.source):
                continue

            macro_tokens = list(self.preprocessor.expand_macros(macro.value))
            macro_compiled = "".join(tok.value for tok in macro_tokens)

            if len(macro_compiled) == 0:
                continue

            # Throw macro in appropriate bucket
            if self.statement_indicator.search(macro_compiled):
                statements[macroname] = macro
            elif macro.arglist is not None:
                functions[macroname] = macro
            elif any(tok.type == "CPP_STRING" for tok in macro_tokens):
                strings[macroname] = macro
            else:
                numerics[macroname] = macro

        return numerics, strings, functions, statements

    def _macro_defined_in_paths(self, macrosrc):
        if macrosrc == "":
            return False
        macrosrc = os.path.abspath(macrosrc)
        return any([macrosrc.startswith(p) for p in self.paths])


class CompanionCodeGenerator:
    default_defines = [("__extension__", ""), ("__attribute__(x)", ""), ("__restrict", "")]

    def __init__(
        self,
        src_files: Iterable[str],
        inc_paths: Iterable[str],
        defines: Iterable[Tuple[str, str]],
        inline_src: str = "",
        compiler: str = "gcc",
        auto_sysincludes: bool = True,
    ):
        self.src_files = src_files
        self.inc_paths = inc_paths
        self.defines = self.default_defines + list(defines)
        self.inline_src = inline_src
        self.auto_sysincludes = auto_sysincludes
        self.compiler = compiler

        self.preprocessor = Preprocessor()
        self.unprocessed = ""
        self.preprocessed = ""

        self.macro_collector: MacroCollector = None  # type: ignore[assignment]

    def _resolve_sysinclude_paths(self):
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
        return sysincludepaths, sysmacros

    def _prepare_preprocessor(self):
        for inc in self.inc_paths:
            self.preprocessor.add_path(inc)
        for name, value in self.defines:
            self.preprocessor.define(f"{name} {value}")

        if self.auto_sysincludes:
            sysincludes, sysmacros = self._resolve_sysinclude_paths()
            for inc in sysincludes:
                self.preprocessor.add_path(inc)
            for macro in sysmacros:
                self.preprocessor.define(" ".join(macro))
        self.preprocessor.define("__builtin_va_list char *")
        self.preprocessor.define("__asm__(x) ")

    def _prepare_src(self):
        unprocessed = ""
        for file in self.src_files:
            with open(file) as fp:
                unprocessed += fp.read() + "\n"
        unprocessed += self.inline_src
        self.unprocessed = unprocessed

    def preprocess(self):
        self._prepare_src()
        self._prepare_preprocessor()

        self.preprocessor.parse(self.unprocessed)
        out = StringIO()
        self.preprocessor.write(out)
        preprocessed = out.getvalue()
        # TODO: Include next seems to be a problem for pcpp
        preprocessed = re.sub(r"^#include_next.*$", "", preprocessed, flags=re.M)

        self.preprocessed = preprocessed

        self.macro_collector = MacroCollector(self.preprocessor, self.src_files)


PYROXENE_COMPANION_PREFIX = "_pyroxene_"
PYROXENE_COMPANION_PREFIX_PTR = "_pyroxene_ptr_"
PYROXENE_COMPANION_FUNC_DECL_FLAGS = '__attribute__((noinline, used, section(".pyroxene.text")))'
PYROXENE_COMPANION_CONST_DECL_FLAGS = '__attribute__((used, section(".pyroxene.rodata")))'


class CompanionCGenerator(pycparser.c_generator.CGenerator):
    def __init__(self, unprocessed: str, ignore: Iterable[str]):
        super().__init__()
        self.default_generator = pycparser.c_generator.CGenerator()
        self.unprocessed = unprocessed
        self.ignore = ignore

    def _generate_funcdef_default(self, n: pycparser.c_ast.FuncDef):
        return self._generate_funcdecl_default(n.decl)

    def _generate_funcdecl_default(self, n: pycparser.c_ast.FuncDecl):
        # Patch name
        functypedecl = n.type
        while not isinstance(functypedecl, pycparser.c_ast.TypeDecl):
            functypedecl = functypedecl.type
        functypedecl.declname = f"{PYROXENE_COMPANION_PREFIX}{n.name}"

        # Read parameters
        params = ",".join(p.name for p in n.type.args.params if p.name is not None)
        # Create function definition
        decl = self.default_generator.visit_FuncDecl(n.type)
        logger.debug(f"InlineFunctionGenerator: Generate {decl}")
        return " ".join(
            (
                PYROXENE_COMPANION_FUNC_DECL_FLAGS,
                decl,
                f"{{ return {n.name}({params}); }}\n",
            )
        )

    def _generate_funcdef_ptr(self, n: pycparser.c_ast.FuncDef):
        returntype = self.default_generator.visit(n.decl.type.type)
        params = ",".join(p.name for p in n.decl.type.args.params if p.name is not None)
        param_decl = self.default_generator.visit(n.decl.type.args)

        if returntype == "void":
            return ""
        param_decl = f"{returntype} *_" + ("," + param_decl if param_decl != "void" else "")
        decl = f"void {PYROXENE_COMPANION_PREFIX_PTR}{n.decl.name}({param_decl})"
        logger.debug(f"InlineFunctionGenerator: Generate {decl}")
        return " ".join(
            (
                PYROXENE_COMPANION_FUNC_DECL_FLAGS,
                decl,
                f"{{*_ = {n.decl.name}({params}); }}\n",
            )
        )

    def visit_FuncDef(self, n):
        if "inline" not in n.decl.funcspec:
            return ""
        if n.decl.name in self.ignore:
            return ""
        return self._generate_funcdef_default(n) + "\n" + self._generate_funcdef_ptr(n)

    def visit_Decl(self, n, *args, **kwargs):
        if n.name in self.ignore:
            return ""
        if isinstance(n.type, pycparser.c_ast.FuncDecl) and n.name in self.unprocessed:
            return self._generate_funcdecl_default(n)
        return ""

    def visit_Typedef(self, n):
        return ""

    def visit_FileAST(self, n):
        s = ""
        for ext in n.ext:
            if isinstance(ext, pycparser.c_ast.FuncDef):
                s += self.visit(ext)
            elif isinstance(ext, pycparser.c_ast.FuncDecl):
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


def companion_generate_string_macro(macro):
    logger.debug(f"companion_generate_string_macro: Generate {macro.name}")
    return (
        f"{PYROXENE_COMPANION_CONST_DECL_FLAGS} "
        f"const char {PYROXENE_COMPANION_PREFIX + macro.name}[] = {macro.name};\n"
    )


def companion_generate_numeric_macro(macro):
    logger.debug(f"companion_generate_numeric_macro: Generate {macro.name}")
    return (
        f"{PYROXENE_COMPANION_CONST_DECL_FLAGS} "
        f"const long long {PYROXENE_COMPANION_PREFIX + macro.name} = {macro.name};\n"
    )


def companion_generate_function_macro(macro):
    args = ",".join(f"unsigned long {a}" for a in macro.arglist)
    logger.debug(f"companion_generate_function_macro: Generate {macro.name}")
    return (
        f"{PYROXENE_COMPANION_FUNC_DECL_FLAGS} unsigned long "
        f"{PYROXENE_COMPANION_PREFIX}{macro.name}({args}) "
        f"{{ return {macro.name}({','.join(macro.arglist)}); }}\n"
    )


def generate_companion(companion_code_generator: CompanionCodeGenerator, ignore: List[str] = []):
    header = "".join(
        f'#include "{f}"\n' for f in ["stdint.h", "stdlib.h"] + list(companion_code_generator.src_files)
    )

    parsed = pycparser.CParser().parse(companion_code_generator.preprocessed)
    parsed = CompanionCGenerator(companion_code_generator.unprocessed, ignore=ignore).visit(parsed)
    macros = "".join(
        companion_generate_string_macro(m)
        for m in companion_code_generator.macro_collector.macro_strings.values()
        if m.name not in ignore
    )
    macros += "".join(
        companion_generate_function_macro(m)
        for m in companion_code_generator.macro_collector.macro_functions.values()
        if m.name not in ignore
    )
    macros += "".join(
        companion_generate_numeric_macro(m)
        for m in companion_code_generator.macro_collector.macro_numerics.values()
        if m.name not in ignore
    )
    return header + parsed + macros


################################################################################
# CFFI CDef generation
################################################################################


class CDefGenerator(pycparser.c_generator.CGenerator):
    def __init__(self, raw: str, externs: List[str] = []):
        super().__init__()
        self.default_generator = pycparser.c_generator.CGenerator()
        self.raw = raw
        self.externs = externs

    def visit_Decl(self, n, *args, **kwargs):
        if isinstance(n.type, pycparser.c_ast.FuncDecl) and n.name:
            if n.name in self.externs:
                return 'extern "Python+C" ' + super().visit_Decl(n)
            elif n.name in self.raw:
                return super().visit_Decl(n)
        else:
            return super().visit_Decl(n)
        return ""

    def visit_FuncDef(self, n):
        if n.decl.name and n.decl.name in self.raw:
            return self.visit(n.decl) + ";\n"
        return ""

    def visit_BinaryOp(self, n):
        return "..."

    def visit_FileAST(self, n):
        s = ""
        for ext in n.ext:
            if isinstance(ext, pycparser.c_ast.FuncDef):
                s += self.visit_FuncDef(ext)
            else:
                result = self.visit(ext)
                if result:
                    s += result + ";\n"
        return s


def generate_cdef(companion_code_generator: CompanionCodeGenerator, externs: List[str] = []):
    parsed = pycparser.CParser().parse(companion_code_generator.preprocessed)
    parsed = CDefGenerator(companion_code_generator.unprocessed, externs).visit(parsed)
    macros = "\n".join(
        f"#define {m} ..." for m in companion_code_generator.macro_collector.macro_numerics.keys()
    )
    return parsed + macros
