import unittest

from cffi_classic import ffi_builder

if __name__ == "__main__":
    ffi_builder.build(
        name="_mymath",
        inc_dirs=["../c"],
        cdef_headers=["../c/mymath.h"],
        src_patterns=["../c/*.c"],
    )

    import _mymath
    import test

    test.lib = _mymath.lib
    test.ffi = _mymath.ffi

    unittest.main(module=None)
