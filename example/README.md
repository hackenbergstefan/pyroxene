# Example

This example demonstrates how to use PyGTI2 to test C-code on different backends.
We will see how test the code on:

- Host using CFFI classic approach
- Host using PyGTI2 with socket communication
- PSoC6 using PyGTI2 with serial communication

## The code

In the following we want to test code located in [mymath.c](./c/mymath.c).
It implements a function for adding to long integers.

This example demonstrates clearly how PyGTI2 is capable of handling:

- Nested structs containing pointers
- Defines
- Functions

## The tests

We use the same tests for every approach.
They are located in [test.py](./test.py).
The tests demonstrate:

- Accessing defines as numbers, e.g. `lib.MYMATH_STATUS_OK`.
- Creating new variables in memory, e.g. `ffi.new("uint8_t[]", 4)`.
- Initializing new variables during creation, e.g. `ffi.new("uint8_t[]", b"\x01\x00\x00\x00")`.
- Accessing memory content with slices, e.g. `bytes(result.data[0:4])`
- Calling functions and passing arguments, e.g. `lib.mymath_add(operand1, operand2, operand3)`.

## 1. CFFI classic approach

Python CFFI can be used to test (embedded) C-Code on a host system.
The folder [cffi_classic](./cffi_classic) contains the necessary code to provide the required information to `cdef`.
[test_cffi_classig.py](./test_cffi_classic.py) demonstrates the compilation of C files and the execution of the tests.

## 2. PyGTI2 host approach

This approach demonstrates how to compile, run and test the C-code using PyGTI2 with socket communication.

### 2.1. Generate companion.c

During compilation process (usually) all unused variables and functionality is removed.
Furthermore no information retains about defines.
As PyGTI2 needs these information [c/generate_companion.py](./c/generate_companion.py) can be executed to generate a companion C-file which is used later in the compilation process.

The `CompanionGenerator` uses a pure Python C preprocessor ([pcpp](https://github.com/ned14/pcpp)) and [pycparser](https://github.com/eliben/pycparser) to generate C-code that:

- Prevents the functions in [c/mymath.c](./c/mymath.c) from being removed.
- Creates a constant variable for each define.
- Creates a wrapper function for each `inline` function (not demonstrated here).

### 2.2. Build the code

[host/Makefile](./host/Makefile) contains a target which compiles:

- [c/mymath.c](./c/mymath.c),
- [gti2.c](../src/gti2.c),
- [c/companion.c](./c/companion.c), and
- [host/main.c](../test/host/main.c).

### 2.3. Run the program

The Makefile generates a program which can be executed.
As [host/main.c](../test/host/main.c) shows a socket is opened and the program ends in an infinite dispatching loop which waits for gti2 commands.

### 2.4. Execute the tests

The tests can be executed using [test_pygti2_host.py](./test_pygti2_host.py).

## 3. PyGTI2 PSoC6 approach

This approach demonstrates how to compile and run the code on PSoC6 and execute the tests using PyGTI2 with serial communication.

### 3.1. Generate companion.c

The same [c/companion.c](./c/companion.c) of the host approach can be used for PSoC6.

### 3.2 Build the code

[psoc6/Makefile](./psoc6/Makefile) is a ModusToolbox compliant Makefile that generates (and downloads) a PSoC6 ELF which contains:

- [c/mymath.c](./c/mymath.c),
- [gti2.c](../src/gti2.c),
- [c/companion.c](./c/companion.c), and
- [psoc/main.c](../test/psoc/main.c).

An adjusted [linker file](./psoc6/cy8c6xxa_cm4_dual.ld) is used which instructs the linker to keep all `.gti2.*` sections.

Execute `make getlibs build program` to build and download.

### 3.3. Run the program

As [psoc/main.c](../test/psoc/main.c) shows a serial interface is opened and the program ends in an infinite dispatching loop which waits for gti2 commands.

### 3.4. Execute the tests

The tests can be executed using [test_pygti2_psoc.py](./test_pygti2_psoc.py).

## Highlights

### Minimal communication

As the main target are embedded devices with low performance it is necessary to minimize the overhead.
Therefore the following optimizations are implemented:

- All constants are already read from the ELF file.
- All sliced accesses (e.g. arrays) are issued with one command.
- The communication protocol is minimalistic (maybe too minimalistic... 😉).
