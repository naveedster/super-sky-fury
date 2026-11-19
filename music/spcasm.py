#!/usr/bin/env python3
"""Tiny two-pass SPC700 assembler (subset) used by make_music.py.
Syntax: standard SPC700 mnemonics, '!' prefix = absolute address, '#' = immediate,
'$' = hex, labels end with ':', local labels allowed (any name), ';' comments.
Expressions are Python expressions over symbols ($xx -> 0xxx)."""
import re

IMPL = {'clrc': 0x60, 'setc': 0x80, 'nop': 0x00, 'ret': 0x6F, 'mul ya': 0xCF, 'div ya,x': 0x9E,
        'asl a': 0x1C, 'lsr a': 0x5C, 'rol a': 0x3C, 'ror a': 0x7C, 'xcn a': 0x9F,
        'inc a': 0xBC, 'dec a': 0x9C, 'inc x': 0x3D, 'dec x': 0x1D, 'inc y': 0xFC, 'dec y': 0xDC,
        'mov a,x': 0x7D, 'mov a,y': 0xDD, 'mov x,a': 0x5D, 'mov y,a': 0xFD, 'mov x,sp': 0x9D,
        'mov a,(x)': 0xE6, 'mov a,(x)+': 0xBF, 'mov (x),a': 0xC6, 'mov (x)+,a': 0xAF,
        'push a': 0x2D, 'push x': 0x4D, 'push y': 0x6D, 'pop a': 0xAE, 'pop x': 0xCE, 'pop y': 0xEE}
# (mnemonic, operand-shape) -> opcode ; shapes: i=#imm d=dp dx=dp+x dy=dp+y a=!abs ax=!abs+x ay=!abs+y
#  idy=[dp]+y idx=[dp+x]
OPS = {
 ('mov', 'a', 'i'): 0xE8, ('mov', 'a', 'd'): 0xE4, ('mov', 'a', 'dx'): 0xF4, ('mov', 'a', 'a'): 0xE5,
 ('mov', 'a', 'ax'): 0xF5, ('mov', 'a', 'ay'): 0xF6, ('mov', 'a', 'idy'): 0xF7, ('mov', 'a', 'idx'): 0xE7,
 ('mov', 'x', 'i'): 0xCD, ('mov', 'x', 'd'): 0xF8, ('mov', 'x', 'dy'): 0xF9, ('mov', 'x', 'a'): 0xE9,
 ('mov', 'y', 'i'): 0x8D, ('mov', 'y', 'd'): 0xEB, ('mov', 'y', 'dx'): 0xFB, ('mov', 'y', 'a'): 0xEC,
 ('mov', 'd', 'a_'): 0xC4, ('mov', 'dx', 'a_'): 0xD4, ('mov', 'a', 'a_'): 0xC5, ('mov', 'ax', 'a_'): 0xD5,
 ('mov', 'ay', 'a_'): 0xD6, ('mov', 'idy', 'a_'): 0xD7, ('mov', 'idx', 'a_'): 0xC7,
 ('mov', 'd', 'x_'): 0xD8, ('mov', 'dy', 'x_'): 0xD9, ('mov', 'a', 'x_'): 0xC9,
 ('mov', 'd', 'y_'): 0xCB, ('mov', 'dx', 'y_'): 0xDB, ('mov', 'a', 'y_'): 0xCC,
 ('cmp', 'a', 'i'): 0x68, ('cmp', 'a', 'd'): 0x64, ('cmp', 'a', 'dx'): 0x74, ('cmp', 'a', 'a'): 0x65,
 ('cmp', 'a', 'ax'): 0x75, ('cmp', 'a', 'ay'): 0x76, ('cmp', 'x', 'i'): 0xC8, ('cmp', 'x', 'd'): 0x3E,
 ('cmp', 'y', 'i'): 0xAD, ('cmp', 'y', 'd'): 0x7E,
 ('and', 'a', 'i'): 0x28, ('and', 'a', 'd'): 0x24, ('and', 'a', 'ay'): 0x36, ('and', 'a', 'ax'): 0x35,
 ('or', 'a', 'i'): 0x08, ('or', 'a', 'd'): 0x04, ('or', 'a', 'ay'): 0x16, ('or', 'a', 'ax'): 0x15,
 ('eor', 'a', 'i'): 0x48, ('eor', 'a', 'd'): 0x44,
 ('adc', 'a', 'i'): 0x88, ('adc', 'a', 'd'): 0x84, ('adc', 'a', 'ax'): 0x95, ('adc', 'a', 'ay'): 0x96,
 ('sbc', 'a', 'i'): 0xA8, ('sbc', 'a', 'd'): 0xA4,
 ('asl', 'd'): 0x0B, ('lsr', 'd'): 0x4B, ('rol', 'd'): 0x2B, ('ror', 'd'): 0x6B,
 ('inc', 'd'): 0xAB, ('dec', 'd'): 0x8B, ('inc', 'dx'): 0xBB, ('dec', 'dx'): 0x9B,
 ('addw', 'ya', 'd'): 0x7A, ('subw', 'ya', 'd'): 0x9A, ('cmpw', 'ya', 'd'): 0x5A,
 ('movw', 'ya', 'd'): 0xBA, ('movw', 'd', 'ya_'): 0xDA, ('incw', 'd'): 0x3A, ('decw', 'd'): 0x1A,
 ('call', 'a'): 0x3F, ('jmp', 'a'): 0x5F,
}
BR = {'bra': 0x2F, 'beq': 0xF0, 'bne': 0xD0, 'bcc': 0x90, 'bcs': 0xB0, 'bmi': 0x30, 'bpl': 0x10,
      'bvc': 0x50, 'bvs': 0x70}

class Asm:
    def __init__(self, syms=None):
        self.syms = dict(syms or {})
        self.sections = []   # (org, lines)

    def ev(self, e, final):
        e = e.strip()
        e = re.sub(r'\$([0-9A-Fa-f]+)', lambda m: '0x' + m.group(1), e)
        try:
            return int(eval(e, {'__builtins__': {}}, self.syms))
        except NameError:
            if final:
                raise
            return 0

    def shape(self, op, final):
        o = op.strip()
        ol = o.lower()
        if ol in ('a', 'x', 'y', 'ya'):
            return ol + '_', None
        if o.startswith('#'):
            return 'i', self.ev(o[1:], final)
        m = re.fullmatch(r'\[(.+)\]\+y', ol)
        if m:
            return 'idy', self.ev(o[1:o.lower().rindex(']')], final)
        m = re.fullmatch(r'\[(.+)\+x\]', ol)
        if m:
            return 'idx', self.ev(o[1:-3], final)
        if o.startswith('!'):
            if ol.endswith('+x'):
                return 'ax', self.ev(o[1:-2], final)
            if ol.endswith('+y'):
                return 'ay', self.ev(o[1:-2], final)
            return 'a', self.ev(o[1:], final)
        if ol.endswith('+x'):
            return 'dx', self.ev(o[:-2], final)
        if ol.endswith('+y'):
            return 'dy', self.ev(o[:-2], final)
        return 'd', self.ev(o, final)

    def split_ops(self, s):
        out, depth, cur = [], 0, ''
        for ch in s:
            if ch in '([':
                depth += 1
            elif ch in ')]':
                depth -= 1
            if ch == ',' and depth == 0:
                out.append(cur); cur = ''
            else:
                cur += ch
        if cur.strip():
            out.append(cur)
        return [x.strip() for x in out]

    def assemble_line(self, line, pc, final):
        s = line.split(';')[0].strip()
        if not s:
            return b''
        low = re.sub(r'\s*,\s*', ',', re.sub(r'\s+', ' ', s.lower()))
        if low.startswith('.byte'):
            return bytes(self.ev(x, final) & 0xFF for x in self.split_ops(s[5:]))
        if low.startswith('.word'):
            out = bytearray()
            for x in self.split_ops(s[5:]):
                v = self.ev(x, final); out += bytes((v & 0xFF, (v >> 8) & 0xFF))
            return bytes(out)
        if low in IMPL:
            return bytes((IMPL[low],))
        parts = s.split(None, 1)
        mn = parts[0].lower()
        ops = self.split_ops(parts[1]) if len(parts) > 1 else []
        def rel(target, at):
            t = self.ev(target, final)
            r = t - (pc + at)
            if final and not -128 <= r <= 127:
                raise ValueError(f'branch out of range: {line}')
            return r & 0xFF
        if mn in BR:
            return bytes((BR[mn], rel(ops[0], 2)))
        if mn == 'cbne':
            _, d = self.shape(ops[0], final)
            return bytes((0x2E, d & 0xFF, rel(ops[1], 3)))
        if mn == 'dbnz':
            if ops[0].lower() == 'y':
                return bytes((0xFE, rel(ops[1], 2)))
            _, d = self.shape(ops[0], final)
            return bytes((0x6E, d & 0xFF, rel(ops[1], 3)))
        if mn in ('set1', 'clr1', 'bbs', 'bbc'):
            d, bit = ops[0].rsplit('.', 1)
            d = self.ev(d, final); bit = int(bit)
            base = {'set1': 0x02, 'clr1': 0x12, 'bbs': 0x03, 'bbc': 0x13}[mn] | (bit << 5)
            if mn in ('set1', 'clr1'):
                return bytes((base, d & 0xFF))
            return bytes((base, d & 0xFF, rel(ops[1], 3)))
        if mn in ('call', 'jmp'):
            v = self.ev(ops[0].lstrip('!'), final)
            return bytes((OPS[(mn, 'a')], v & 0xFF, v >> 8))
        shapes = [self.shape(o, final) for o in ops]
        key = (mn,) + tuple(sh for sh, _ in shapes)
        # mov dp,#imm  /  mov dp,dp
        if mn == 'mov' and len(shapes) == 2 and shapes[0][0] == 'd' and shapes[1][0] == 'i':
            return bytes((0x8F, shapes[1][1] & 0xFF, shapes[0][1] & 0xFF))
        if mn == 'mov' and len(shapes) == 2 and shapes[0][0] == 'd' and shapes[1][0] == 'd':
            return bytes((0xFA, shapes[1][1] & 0xFF, shapes[0][1] & 0xFF))
        if mn in ('or', 'and', 'eor') and len(shapes) == 2 and shapes[0][0] == 'd' and shapes[1][0] == 'i':
            op = {'or': 0x18, 'and': 0x38, 'eor': 0x58}[mn]
            return bytes((op, shapes[1][1] & 0xFF, shapes[0][1] & 0xFF))
        # normalise register-first keys
        k2 = tuple(sh.rstrip('_') if i == 0 else sh for i, sh in enumerate(key[1:]))
        k2 = (mn,) + k2
        if k2 in OPS:
            op = OPS[k2]
            vals = [v for sh, v in shapes if v is not None]
            out = bytearray((op,))
            for sh, v in shapes:
                if v is None:
                    continue
                if sh in ('a', 'ax', 'ay'):
                    out += bytes((v & 0xFF, (v >> 8) & 0xFF))
                else:
                    out += bytes((v & 0xFF,))
            return bytes(out)
        raise ValueError(f'unknown instruction: {line!r} key={k2}')

    def assemble(self, sections):
        """sections: list of (org, text). Returns list of (org, bytes)."""
        for final in (False, True, True):
            outs = []
            for org, text in sections:
                pc = org; out = bytearray()
                for raw in text.split('\n'):
                    line = raw.split(';')[0].rstrip()
                    m = re.match(r'^\s*([A-Za-z_.@][\w.@]*):(.*)$', line)
                    if m:
                        self.syms[m.group(1)] = pc
                        line = m.group(2)
                    b = self.assemble_line(line, pc, final)
                    out += b; pc += len(b)
                outs.append((org, bytes(out)))
        return outs
