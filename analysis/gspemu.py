"""TMS34020 emulator for LEO-32's GSP column model (TIGA/g200.440).

Runs the original compiled optics / scan code to get exactly the numbers LEO-32 would send to
the EO board for any kV, WD, probe current, magnification, rotation, ...

- Memory: g200.440's .text/.data loaded at their link addresses (bit addressed, little-endian),
  .bss zeroed, then .cinit applied. Stacks live above the module image.
- CPU: the integer instruction forms the C compiler emits (decoded from t34.py's disassembler).
- The compiler's float library (FS$*/FD$*: A14-stack RPN) and the C math functions
  (_SQRT, _sin, _cos, _log, _exp, _pow: C convention with a saved-A14 marker) are done in Python.
- EO hardware access (_DSP_set_EO_register / _DSP_read_EO_register) is captured; other
  hardware / OS routines are stubbed and logged.
Usage: see analysis/optics/emu_driver.py.
"""
import math, re, struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t34 import Mod
from coff import parse

CC = ['UC', 'P', 'LS', 'HI', 'LT', 'GE', 'LE', 'GT', 'C', 'NC', 'EQ', 'NE', 'V', 'NV', 'N', 'NN']
SENTINEL = 0x7FFFFFF0
MASK = 0xFFFFFFFF


def f32(x):  # round to IEEE single
    try:
        return struct.unpack('<f', struct.pack('<f', x))[0]
    except OverflowError:
        return math.copysign(math.inf, x)


def u2f(u): return struct.unpack('<f', struct.pack('<I', u & MASK))[0]
def f2u(f): return struct.unpack('<I', struct.pack('<f', f32(f)))[0]
def s32(v): v &= MASK; return v - (1 << 32) if v & 0x80000000 else v


class EmuError(Exception):
    pass


class GSP:
    MEMBITS = 1 << 23            # 8 Mbit = 1 MB

    def __init__(self, path, trace=False):
        self.m = Mod(path)
        self.mem = bytearray(self.MEMBITS // 8)
        d, h, secs, syms = parse(path)
        for s in secs:
            if s['name'] in ('.text', '.data') and s['ptr']:
                raw = d[s['ptr']:s['ptr'] + s['size'] // 8]
                self.mem[s['vaddr'] // 8:s['vaddr'] // 8 + len(raw)] = raw
        ci = [s for s in secs if s['name'] == '.cinit'][0]
        raw = d[ci['ptr']:ci['ptr'] + ci['size'] // 8]
        i = 0
        while i + 6 <= len(raw):
            sz = struct.unpack('<H', raw[i:i + 2])[0]
            if sz == 0: break
            addr = struct.unpack('<I', raw[i + 2:i + 6])[0]
            data = raw[i + 6:i + 6 + sz * 2]
            self.mem[addr // 8:addr // 8 + len(data)] = data
            i += 6 + sz * 2
        self.sym = {n: v for v, n in self.m.funcs}
        self.data_sym = {n: v for (scn, v), n in self.m.addr2.items()}
        self.regs = {f'{f}{i}': 0 for f in 'AB' for i in range(15)}
        self.regs['SP'] = 0x7F0000            # system stack (grows down)
        self.regs['A14'] = 0x600000           # parameter stack (grows up)
        self.N = self.Z = self.C = self.V = 0
        self.fs = [[32, 0], [32, 0]]          # field size / sign-extend for F=0, F=1
        self.pc = 0
        self.cache = {}
        self.trace = trace
        self.eo_writes = []                   # (reg, value) in order
        self.eo_regs = {}
        self.log = []
        self.steps = 0
        self.hist = []
        self.markers = set()                  # SP values where a caller saved A14 (C call marker)

    # ------------------------------------------------------------------ memory
    def rd(self, a, n, sext=False):
        if a < 0 or (a + n) > self.MEMBITS:
            self.log.append(f'read outside memory {a:#x}')
            return 0
        if a % 8 == 0 and n % 8 == 0:
            v = int.from_bytes(self.mem[a // 8:a // 8 + n // 8], 'little')
        else:
            b0 = a // 8; nb = (a % 8 + n + 7) // 8
            v = (int.from_bytes(self.mem[b0:b0 + nb], 'little') >> (a % 8)) & ((1 << n) - 1)
        if sext and n < 32 and v & (1 << (n - 1)): v -= 1 << n
        return v & MASK if not sext else v

    def wr(self, a, n, v):
        if a < 0 or (a + n) > self.MEMBITS:
            self.log.append(f'write outside memory {a:#x}')
            return
        v &= (1 << n) - 1
        if a % 8 == 0 and n % 8 == 0:
            self.mem[a // 8:a // 8 + n // 8] = v.to_bytes(n // 8, 'little')
        else:
            b0 = a // 8; nb = (a % 8 + n + 7) // 8
            cur = int.from_bytes(self.mem[b0:b0 + nb], 'little')
            msk = ((1 << n) - 1) << (a % 8)
            cur = (cur & ~msk) | (v << (a % 8))
            self.mem[b0:b0 + nb] = cur.to_bytes(nb, 'little')

    def rd32(self, a): return self.rd(a, 32)
    def wr32(self, a, v): self.wr(a, 32, v)

    def fld_rd(self, a, F):
        n, se = self.fs[F]
        return self.rd(a, n, sext=bool(se))

    def fld_wr(self, a, F, v):
        self.wr(a, self.fs[F][0], v)

    # ------------------------------------------------------------------ registers / flags
    def R(self, r): return self.regs[r] & MASK

    def W(self, r, v): self.regs[r] = v & MASK

    def setnz(self, v):
        v &= MASK
        self.N = 1 if v & 0x80000000 else 0
        self.Z = 1 if v == 0 else 0

    def cond(self, c):
        N, Z, C, V = self.N, self.Z, self.C, self.V
        return {'UC': True, 'P': not N and not Z, 'LS': C or Z, 'HI': not C and not Z, 'LT': (N ^ V) == 1,
                'GE': (N ^ V) == 0, 'LE': (N ^ V) == 1 or Z, 'GT': (N ^ V) == 0 and not Z, 'C': C, 'NC': not C,
                'EQ': Z, 'NE': not Z, 'V': V, 'NV': not V, 'N': N, 'NN': not N}[c]

    def push_sp(self, v):
        self.W('SP', self.R('SP') - 32); self.wr32(self.R('SP'), v)

    def pop_sp(self):
        v = self.rd32(self.R('SP')); self.W('SP', self.R('SP') + 32); return v

    # A14 float stack
    def push_w(self, v):
        self.wr32(self.R('A14'), v); self.W('A14', self.R('A14') + 32)

    def pop_w(self):
        self.W('A14', self.R('A14') - 32); return self.rd32(self.R('A14'))

    def push_f(self, x): self.push_w(f2u(x))
    def pop_f(self): return u2f(self.pop_w())

    def push_d(self, x):
        u = struct.unpack('<Q', struct.pack('<d', x))[0]
        self.push_w(u >> 32); self.push_w(u & MASK)          # high word at the lower address

    def pop_d(self):
        lo = self.pop_w(); hi = self.pop_w()
        return struct.unpack('<d', struct.pack('<Q', (hi << 32) | lo))[0]

    def rd_double(self, a):
        hi, lo = self.rd32(a), self.rd32(a + 32)
        return struct.unpack('<d', struct.pack('<Q', (hi << 32) | lo))[0]

    def wr_double(self, a, x):
        u = struct.unpack('<Q', struct.pack('<d', x))[0]
        self.wr32(a, u >> 32); self.wr32(a + 32, u & MASK)

    # ------------------------------------------------------------------ library / stubs
    def float_lib(self, name):
        m = re.fullmatch(r'F([SD])\$(\w+)', name)
        if not m: return False
        kind, op = m.groups()
        dbl = kind == 'D'
        pop = self.pop_d if dbl else self.pop_f
        push = self.push_d if dbl else self.push_f
        if op in ('ADD', 'SUB', 'MUL', 'DIV', 'SUB_R', 'DIV_R'):
            b = pop(); a = pop()
            if op == 'ADD': r = a + b
            elif op == 'SUB': r = a - b
            elif op == 'MUL': r = a * b
            elif op == 'SUB_R': r = b - a
            else:
                num, den = (a, b) if op == 'DIV' else (b, a)
                if den == 0:
                    r = math.copysign(math.inf, num) if num else math.nan
                    self.log.append(f'{name}: division by zero')
                else:
                    r = num / den
            push(r)
        elif op in ('LT', 'GT', 'LE', 'GE', 'EQ', 'NE'):
            b = pop(); a = pop()
            t = {'LT': a < b, 'GT': a > b, 'LE': a <= b, 'GE': a >= b, 'EQ': a == b, 'NE': a != b}[op]
            self.W('A8', 1 if t else 0); self.setnz(1 if t else 0); self.C = self.V = 0
        elif op == 'ABS': push(abs(pop()))
        elif op == 'NEG': push(-pop())
        elif op == 'FTOD': self.push_d(self.pop_f())
        elif op == 'DTOF': self.push_f(self.pop_d())
        elif op == 'ITOF': self.push_f(float(s32(self.R('A8'))))
        elif op == 'ITOD': self.push_d(float(s32(self.R('A8'))))
        elif op == 'UTOF': self.push_f(float(self.R('A8')))
        elif op == 'UTOD': self.push_d(float(self.R('A8')))
        elif op in ('FTOI', 'DTOI', 'FTOU', 'DTOU'):
            x = self.pop_d() if op[0] == 'D' else self.pop_f()
            v = int(x) if math.isfinite(x) else 0
            self.W('A8', v); self.setnz(v)
        else:
            raise EmuError(f'float op {name} not implemented')
        return True

    MATH1 = {'_SQRT': math.sqrt, '__sqrt': math.sqrt, '_sqrt': math.sqrt, '_sin': math.sin, '_cos': math.cos,
             '_tan': math.tan, '_atan': math.atan, '_exp': math.exp, '_log': math.log, '_log10': math.log10,
             '_fabs': abs, '_asin': math.asin, '_acos': math.acos}

    def c_math(self, name):
        """C double function f(x) / pow(x, y): caller reserved the result slot, saved A14 on SP."""
        if name not in self.MATH1 and name != '_pow': return False
        a14 = self.R('A14')
        x = self.rd_double(a14 - 64)
        if name == '_pow':
            y = x; x = self.rd_double(a14 - 128)          # first argument pushed first
            try: r = x ** y
            except Exception: r = math.nan
        else:
            try: r = self.MATH1[name](x)
            except ValueError: r = math.nan; self.log.append(f'{name}({x}) domain error')
        self.markers.discard(self.R('SP'))
        marker = self.pop_sp()
        self.wr_double(marker - 64, r)
        self.W('A14', marker)
        return True

    def stub(self, name):
        """Hardware / OS routines. Returns True when handled (caller continues after the call)."""
        a14 = self.R('A14')
        if name == '_DSP_set_EO_register':
            reg = self.rd(a14 - 32, 32, True); val = self.rd(a14 - 64, 32)
            self.eo_writes.append((reg & 0xFFFF, val & 0xFFFF)); self.eo_regs[reg & 0xFFFF] = val & 0xFFFF
        elif name == '_DSP_read_EO_register':
            reg = self.rd(a14 - 32, 32, True) & 0xFFFF
            self.W('A8', self.eo_regs.get(reg, 0)); self.setnz(self.R('A8'))
        elif name in ('_EO_board_present',):
            self.W('A8', 1); self.setnz(1)
        else:
            self.log.append(f'stub {name}')
            self.W('A8', 0)
        # C convention: a callee with arguments pops the caller's saved-A14 marker (RETS 2)
        # and restores A14; a call without arguments has no marker.
        if self.R('SP') in self.markers:
            self.markers.discard(self.R('SP'))
            self.W('A14', self.pop_sp())
        return True

    STUBS = {'_DSP_set_EO_register', '_DSP_read_EO_register', '_EO_board_present', '_Pause', '_PutQueue',
             '_draw_debug_string', '_fp_error'}

    # ------------------------------------------------------------------ decode / execute
    def dec(self, a):
        if a in self.cache: return self.cache[a]
        sz, t, info = self.m.dis1(a)
        w = self.rd(a, 16)
        if t == '.word 0x00f3' or w & 0xfffc == 0x00f0:
            t = f'BLMOVE {(w >> 1) & 1},{w & 1}'
        elif w & 0xfc00 == 0x3400:
            k = (w >> 5) & 31 or 32
            t = f'CMPK {k},{"B" if w & 16 else "A"}{w & 15}'
        self.cache[a] = (sz, t, info)
        return sz, t, info

    def imm32(self, a, n=0):
        return self.rd32(a + 16 + 16 * n)

    def ea(self, op):
        """effective address of a memory operand string (no side effects for +/-)."""
        m = re.fullmatch(r'\*(\w+)\((-?\d+)\)', op)
        if m: return (self.R(m.group(1)) + int(m.group(2))) & MASK
        m = re.fullmatch(r'\*(\w+)', op)
        if m: return self.R(m.group(1))
        raise EmuError(f'ea {op}')

    def step(self):
        a = self.pc
        if not (0 <= a < 0xe9a00):
            raise EmuError(f'PC out of code: {a:#x}; last: ' + ' | '.join(f'{x:06x} {y}' for x, y in self.hist[-12:]))
        sz, t, info = self.dec(a)
        self.hist.append((a, t))
        if len(self.hist) > 64: del self.hist[:32]
        if self.trace: print(f'{a:06x} {t}')
        self.steps += 1
        nxt = a + sz
        self.pc = nxt
        mn, _, ops = t.partition(' ')
        o = ops.split(',') if ops else []

        if mn == 'MOVE':
            self.exec_move(a, t, ops, info)
        elif mn == 'MOVB':
            self.exec_movb(a, ops, info)
        elif mn == 'MOVI':
            r = o[-1]; v = self.imm32(a) if sz == 48 else (int(o[0]) & MASK)
            self.W(r, v); self.setnz(v); self.V = 0
        elif mn == 'MOVK':
            self.W(o[1], int(o[0]))
        elif mn == 'CLR':
            self.W(o[0], 0); self.setnz(0); self.V = 0
        elif mn in ('ADDI', 'ADDK', 'SUBK', 'SUBI', 'CMPI', 'CMPK'):
            r = o[-1]
            if mn == 'ADDI': k = self.imm32(a) if sz == 48 else int(o[0])
            elif mn in ('ADDK',): k = int(o[0])
            elif mn == 'SUBK': k = -int(o[0])
            elif mn == 'SUBI': k = -(int(o[0], 16) if sz == 32 else (~self.imm32(a) & MASK))
            if mn == 'SUBI' and sz == 32: k = -((~self.rd(a + 16, 16)) & 0xFFFF)
            if mn in ('CMPI', 'CMPK'):
                v = int(o[0], 16) if o[0].startswith('0x') else int(o[0])
                if mn == 'CMPI': v = (v - (1 << 16)) if sz == 32 and v & 0x8000 else v
                self.sub_flags(self.R(r), v & MASK)
            else:
                self.add_flags(r, k)
        elif mn in ('ADD', 'SUB', 'CMP', 'AND', 'ANDN', 'OR', 'XOR', 'MPYS', 'MPYU', 'DIVS', 'DIVU', 'MODS', 'MODU'):
            self.exec_alu(mn, o[0], o[1])
        elif mn in ('ANDI', 'ORI', 'XORI'):
            v = self.imm32(a)
            if mn == 'ANDI': v = ~v & MASK          # t34 already shows the complemented mask in text; use raw
            r = o[1]; x = self.R(r)
            x = {'ANDI': x & v, 'ORI': x | v, 'XORI': x ^ v}[mn]
            self.W(r, x); self.setnz(x); self.V = 0
        elif mn in ('SLL', 'SLA', 'SRA', 'SRL', 'RL'):
            k = int(o[0]) if not o[0][0] in 'AB' else (self.R(o[0]) & 31)
            r = o[1]; x = self.R(r)
            if mn in ('SLL', 'SLA'): v = (x << k) & MASK; self.C = (x >> (32 - k)) & 1 if k else 0
            elif mn == 'SRA': v = (s32(x) >> k) & MASK
            elif mn == 'SRL': v = x >> k
            else: v = ((x << k) | (x >> (32 - k))) & MASK if k else x
            self.W(r, v); self.setnz(v)
        elif mn in ('SEXT', 'ZEXT'):
            r, F = o[0], int(o[1]); n = self.fs[F][0]; x = self.R(r) & ((1 << n) - 1) if n < 32 else self.R(r)
            if mn == 'SEXT' and n < 32 and x & (1 << (n - 1)): x -= 1 << n
            self.W(r, x); self.setnz(x)
        elif mn in ('NEG', 'ABS', 'NOT'):
            x = s32(self.R(o[0]))
            v = {'NEG': -x, 'ABS': abs(x), 'NOT': ~x}[mn]
            self.W(o[0], v); self.setnz(v)
        elif mn == 'BTST':
            k = int(o[0]); self.Z = 0 if self.R(o[1]) & (1 << k) else 1
        elif mn == 'SETF':
            size, fe, F = int(o[0]), int(o[1]), int(o[2])
            self.fs[F] = [size, fe]
        elif mn.startswith('JR') or mn.startswith('JA'):
            c = mn[2:]
            if self.cond(c): self.pc = int(o[0], 16)
        elif mn in ('DSJ', 'DSJS', 'DSJEQ', 'DSJNE'):
            r = o[0]; tgt = int(o[1], 16)
            if mn == 'DSJEQ' and not self.Z: return
            if mn == 'DSJNE' and self.Z: return
            v = (self.R(r) - 1) & MASK; self.W(r, v)
            if v != 0: self.pc = tgt
        elif mn == 'MMTM':
            mask = int(o[1], 16); f = 'B' if False else 'A'
            for r in range(15):
                if mask & (1 << (15 - r)): self.push_sp(self.R(f'{f}{r}'))
        elif mn == 'MMFM':
            mask = int(o[1], 16)
            for r in range(14, -1, -1):
                if mask & (1 << r): self.W(f'A{r}', self.pop_sp())
        elif mn in ('CALLA', 'CALLR'):
            name = info.get('call')
            tgt = self.imm32(a) if mn == 'CALLA' else None
            self.do_call(name, tgt, nxt)
        elif mn == 'CALL':
            self.do_call(None, self.R(o[0]), nxt)
        elif mn == 'RETS':
            self.pc = self.pop_sp()
            self.W('SP', self.R('SP') + int(o[0]) * 16)
        elif mn == 'BLMOVE':
            S, D = int(o[0]), int(o[1])
            n = self.R('B7'); src = self.R('B0'); dst = self.R('B2')
            for i in range(0, n, 32):
                self.wr(dst + i, min(32, n - i), self.rd(src + i, min(32, n - i)))
            if S: self.W('B0', src + n)
            if D: self.W('B2', dst + n)
        elif mn == 'NOP':
            pass
        else:
            raise EmuError(f'{a:06x}: instruction not implemented: {t}')

    def add_flags(self, r, k):
        x = self.R(r); v = (x + k) & MASK
        self.C = 1 if (x + (k & MASK)) > MASK else 0
        sx, sk, sv = s32(x), s32(k & MASK), s32(v)
        self.V = 1 if (sx >= 0) == (sk >= 0) and (sv >= 0) != (sx >= 0) else 0
        self.W(r, v); self.setnz(v)

    def sub_flags(self, x, y):
        v = (x - y) & MASK
        self.C = 1 if y > x else 0
        sx, sy, sv = s32(x), s32(y), s32(v)
        self.V = 1 if (sx >= 0) != (sy >= 0) and (sv >= 0) != (sx >= 0) else 0
        self.setnz(v)
        return v

    def exec_alu(self, mn, rs, rd):
        x, y = self.R(rd), self.R(rs)
        if mn == 'ADD':
            self.add_flags(rd, y)
        elif mn in ('SUB', 'CMP'):
            v = self.sub_flags(x, y)
            if mn == 'SUB': self.W(rd, v)
        elif mn in ('AND', 'ANDN', 'OR', 'XOR'):
            v = {'AND': x & y, 'ANDN': x & ~y, 'OR': x | y, 'XOR': x ^ y}[mn] & MASK
            self.W(rd, v); self.setnz(v); self.V = 0
        elif mn in ('MPYS', 'MPYU'):
            n = self.fs[1][0]                                  # Rs width = field size 1
            ys = y & ((1 << n) - 1) if n < 32 else y
            if mn == 'MPYS' and n < 32 and ys & (1 << (n - 1)): ys -= 1 << n
            elif mn == 'MPYS': ys = s32(ys)
            p = (s32(x) if mn == 'MPYS' else x) * ys
            idx = int(rd[1:])
            if idx % 2 == 0:                                   # even Rd: 64-bit product in Rd:Rd+1
                self.W(rd, (p >> 32) & MASK); self.W(f'{rd[0]}{idx + 1}', p & MASK)
            else:
                self.W(rd, p & MASK)
            self.N = 1 if p < 0 else 0; self.Z = 1 if p == 0 else 0
        elif mn in ('DIVS', 'DIVU', 'MODS', 'MODU'):
            if y == 0: self.V = 1; return
            idx = int(rd[1:]); ys = s32(y) if mn in ('DIVS', 'MODS') else y
            if mn.startswith('DIV') and idx % 2 == 0:          # even Rd: 64-bit dividend Rd:Rd+1
                lo = self.R(f'{rd[0]}{idx + 1}')
                xx = (x << 32) | lo
                if mn == 'DIVS' and xx & (1 << 63): xx -= 1 << 64
                q = int(xx / ys) if mn == 'DIVS' else xx // ys
                rm = xx - q * ys
                self.W(rd, q); self.W(f'{rd[0]}{idx + 1}', rm); self.setnz(q & MASK); self.V = 0
                return
            xs = s32(x) if mn in ('DIVS', 'MODS') else x
            q = int(xs / ys) if mn in ('DIVS', 'MODS') else xs // ys
            rm = xs - q * ys
            v = q if mn.startswith('DIV') else rm
            self.W(rd, v); self.setnz(v & MASK); self.V = 0

    def exec_move(self, a, t, ops, info):
        o = ops.split(',')
        # register to register (same or cross file; t34 shows cross-file operands with swapped files)
        m = re.fullmatch(r'([AB]\d+|SP),([AB]\d+|SP)', ops)
        if m:
            rs, rd = m.groups()
            if rs[0] != rd[0] and rs != 'SP' and rd != 'SP':
                rs, rd = rd[0] + rs[1:], rs[0] + rd[1:]          # actual: rs in rd's printed file
            v = self.R(rs); self.W(rd, v); self.setnz(v); self.V = 0
            return
        F = int(o[-1]) if o[-1] in ('0', '1') else 1
        src, dst = o[0], o[1]
        w = self.rd(a, 16)
        # absolute operands from the raw instruction stream
        if src.startswith('@') and dst.startswith('@'):
            sa, da = self.imm32(a), self.imm32(a, 2)
            self.fld_wr(da, F, self.fld_rd(sa, F)); return
        if src.startswith('@'):
            sa = self.imm32(a)
            v = self.fld_rd(sa, F)
            self.store(dst, F, v); return
        if dst.startswith('@'):
            da = self.imm32(a)
            self.fld_wr(da, F, self.R(src)); return
        if src[0] in 'AB' or src == 'SP':
            self.store(dst, F, self.R(src))
            if src == 'A14' and dst == '-*SP': self.markers.add(self.R('SP'))
            return
        v = self.load(src, F)
        if dst[0] in 'AB' or dst == 'SP':
            self.W(dst, v); self.setnz(v); self.V = 0
        else:
            self.store(dst, F, v)

    def load(self, op, F):
        m = re.fullmatch(r'\*(\w+)\+', op)
        if m:
            r = m.group(1); v = self.fld_rd(self.R(r), F); self.W(r, self.R(r) + self.fs[F][0]); return v
        m = re.fullmatch(r'-\*(\w+)', op)
        if m:
            r = m.group(1); self.W(r, self.R(r) - self.fs[F][0]); return self.fld_rd(self.R(r), F)
        return self.fld_rd(self.ea(op), F)

    def store(self, op, F, v):
        m = re.fullmatch(r'\*(\w+)\+', op)
        if m:
            r = m.group(1); self.fld_wr(self.R(r), F, v); self.W(r, self.R(r) + self.fs[F][0]); return
        m = re.fullmatch(r'-\*(\w+)', op)
        if m:
            r = m.group(1); self.W(r, self.R(r) - self.fs[F][0]); self.fld_wr(self.R(r), F, v); return
        if op[0] in 'AB' or op == 'SP':
            self.W(op, v); self.setnz(v); return
        self.fld_wr(self.ea(op), F, v)

    def exec_movb(self, a, ops, info):
        src, dst = ops.split(',', 1)
        if src.startswith('@'):
            v = self.rd(self.imm32(a), 8, True)
        elif src[0] in 'AB':
            v = self.R(src)
        else:
            v = self.rd(self.ea(src), 8, True)
        if dst.startswith('@'):
            self.wr(self.imm32(a), 8, v)
        elif dst[0] in 'AB':
            self.W(dst, v); self.setnz(v)
        else:
            self.wr(self.ea(dst), 8, v)

    def do_call(self, name, tgt, ret):
        if name and name.startswith(('FS$', 'FD$')):
            if self.float_lib(name): return
        if name and self.c_math(name): return
        if name in self.STUBS: self.stub(name); return
        if name and name in self.sym: tgt = self.sym[name]
        elif name and name.startswith('?+'): tgt = int(name[2:], 16)
        elif name and name.startswith('0x'): tgt = int(name, 16)
        if tgt is None or not (0 < tgt < 0xe9a00):
            self.log.append(f'call to unresolved {name} {tgt}')
            self.stub(name or '?'); return
        self.push_sp(ret)
        self.pc = tgt

    # ------------------------------------------------------------------ harness
    def call(self, name, *args, ret=None, max_steps=5_000_000):
        """Call a module function C-style. args: values in callee order (arg at A13-32 first);
        each is ('f', x) float, ('d', x) double, ('i', n) int. ret: 'f', 'd', 'i' or None."""
        addr = self.sym[name] if isinstance(name, str) else name
        res_sz = {'f': 32, 'i': 32, 'd': 64, None: 0}[ret]
        self.W('A14', self.R('A14') + res_sz)
        self.push_sp(self.R('A14'))                       # saved-A14 marker
        for kind, v in reversed(args):                    # deepest argument first
            if kind == 'f': self.push_f(v)
            elif kind == 'd': self.push_d(v)
            else: self.push_w(v & MASK)
        marker = self.R('A14') - sum(64 if k == 'd' else 32 for k, _ in args)
        self.push_sp(SENTINEL)
        self.pc = addr
        n0 = self.steps
        while self.pc != SENTINEL:
            self.step()
            if self.steps - n0 > max_steps: raise EmuError(f'{name}: step limit')
        top = self.R('A14')
        if ret == 'f': return u2f(self.rd32(top - 32))
        if ret == 'd': return self.rd_double(top - 64)
        if ret == 'i': return s32(self.R('A8'))
        return None

    # convenience accessors for globals
    def gf(self, addr): return u2f(self.rd32(addr))
    def sf(self, addr, x): self.wr32(addr, f2u(x))
