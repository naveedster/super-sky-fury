#!/usr/bin/env python3
import sys
p = sys.argv[1]; d = bytearray(open(p, "rb").read())
H = 0x7FC0
d[H+0x1C:H+0x20] = b"\xff\xff\x00\x00"
s = sum(d) & 0xFFFF
d[H+0x1C] = (s ^ 0xFFFF) & 0xFF; d[H+0x1D] = (s ^ 0xFFFF) >> 8
d[H+0x1E] = s & 0xFF; d[H+0x1F] = s >> 8
open(p, "wb").write(d)
print(f"{p}: {len(d)} bytes, checksum ${s:04X}, complement ${s ^ 0xFFFF:04X}")
