import argparse
import sys
import unittest

import test


import logging

# logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--psoc", action="store_true")
    args, rest = parser.parse_known_args()
    if args.psoc:
        test.dut = "psoc"

    unittest.main(module=None, argv=[sys.argv[0]] + rest)
