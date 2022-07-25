import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from pygti2.companion_generator import CompanionGenerator  # noqa: E402 module level import not at top of file

if __name__ == "__main__":
    gen = CompanionGenerator()
    gen.include_paths = ["."]
    gen.src_files = ["./mymath.h"]
    with open("companion.c", "w") as fp:
        fp.write(gen.parse_and_generate_companion_source())
