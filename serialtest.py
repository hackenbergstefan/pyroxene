import time
import struct

import serial

def pprint(bytes):
    if not bytes:
        return
    print(' '.join(f'{b:02x}' for b in bytes))

ser = serial.Serial('/dev/ttyACM0', 576000)
pprint(ser.read_all())

def command(cmd, data, expected):
    ser.write(struct.pack('!HH', cmd, len(data)) + data)
    return ser.read(expected)

def memory_read(addr, len):
    return command(1, struct.pack('!II', addr, len), len)

def memory_write(addr, data):
    command(2, struct.pack('!I', addr) + data, 0)

def call(addr, numparam_return, *params):
    return command(3, struct.pack('!IHH', addr, numparam_return, len(params)) + b''.join(params), numparam_return)

pprint(memory_write(0x080029c8, 16 * b'\x00'))
pprint(memory_read(0x080029c8, 16))
pprint(call(0x100028f4, 0))
pprint(memory_read(0x080029c8, 16))
pprint(call(0x10002900, 1))
