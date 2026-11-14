# TMS34010/34020 disassembler (main integer/move/branch subset) with TI COFF relocation + symbol annotation
import sys, os, struct, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coff import parse

CC = ['UC', 'P', 'LS', 'HI', 'LT', 'GE', 'LE', 'GT', 'C', 'NC', 'EQ', 'NE', 'V', 'NV', 'N', 'NN']


def R(r, b):
    if r == 15: return 'SP'
    return ('B' if b else 'A') + str(r)


class Mod:
    def __init__(self, path):
        self.d, self.h, self.secs, self.syms = parse(path)
        d = self.d
        magic, nsec, ts, symptr, nsym, opth, fl = struct.unpack('<HHIIIHH', d[:20])
        strtab = symptr + 18 * nsym
        self.idx = {}
        for i in range(nsym):
            e = d[symptr + 18 * i:symptr + 18 * i + 18]
            if e[:4] == b'\0\0\0\0':
                so = struct.unpack('<I', e[4:8])[0]; j = d.index(b'\0', strtab + so); name = d[strtab + so:j].decode('latin1')
            else:
                name = e[:8].rstrip(b'\0').decode('latin1')
            self.idx[i] = name
        self.tx = [s for s in self.secs if s['name'] == '.text'][0]
        self.raw = d[self.tx['ptr']:self.tx['ptr'] + self.tx['size'] // 8]
        self.rel = {}
        for k in range(self.tx['nreloc']):
            va, si, ty = struct.unpack('<IIH', d[self.tx['relptr'] + 10 * k:self.tx['relptr'] + 10 * k + 10])
            self.rel[va] = self.idx.get(si, '?')
        self.addr2 = {}   # any defined symbol (text/data/bss)
        self.text = {}
        for n, v, scn, t, c in self.syms:
            if scn >= 1 and c in (2, 3) and not n.startswith('$') and not n.startswith('.'):
                self.addr2.setdefault((scn, v), n)
                if scn == 1: self.text.setdefault(v, n)
        self.funcs = sorted(self.text.items())
        self.fa = [f[0] for f in self.funcs]
        self.secbase = {i + 1: s for i, s in enumerate(self.secs)}

    def symval(self, a, imm):
        """annotate a 32-bit immediate at bit address a"""
        r = self.rel.get(a)
        if r is None: return None
        if r in ('.text', '.data', '.bss', '.cinit'):
            scn = {'.text': 1, '.data': 2, '.bss': 3, '.cinit': 4}[r]
            n = self.addr2.get((scn, imm))
            return n or f'{r}+{imm:x}'
        for (scn, v), n in self.addr2.items():
            if n == r:
                return r if imm == v else f'{r}+{(imm - v):#x}'
        return r if imm == 0 else f'{r}+{imm:#x}'

    def fn_at(self, a):
        k = bisect.bisect_right(self.fa, a) - 1
        return self.funcs[k] if k >= 0 else (0, '?')

    def dis1(self, a):
        """decode instruction at bit address a; returns (size_bits, text, info)"""
        o = a // 8
        raw = self.raw
        w = struct.unpack('<H', raw[o:o + 2])[0]
        def w16(n=0): return struct.unpack('<H', raw[o + 2 + 2 * n:o + 4 + 2 * n])[0]
        def s16(n=0): return struct.unpack('<h', raw[o + 2 + 2 * n:o + 4 + 2 * n])[0]
        def l32(n=0): return struct.unpack('<I', raw[o + 2 + 2 * n:o + 6 + 2 * n])[0]
        b = (w >> 4) & 1; rs = R((w >> 5) & 15, b); rd = R(w & 15, b); F = (w >> 9) & 1
        top = w & 0xfe00
        def L(n=0):
            v = l32(n); s = self.symval(a + 16 + 16 * n, v)
            return (f'@{s}' if s and not s.startswith('.') else f'@0x{v:08x}' + (f'<{s}>' if s else '')), v, s
        info = {}
        # 0x0xxx group
        if w & 0xf000 == 0:
            g = w & 0xffe0
            simple = {0x0020: 'REV', 0x0120: 'EXGPC', 0x0140: 'GETPC', 0x0160: 'JUMP', 0x0180: 'GETST', 0x01a0: 'PUTST',
                      0x0380: 'ABS', 0x03a0: 'NEG', 0x03c0: 'NEGB', 0x03e0: 'NOT', 0x0920: 'CALL', 0x0d80: None}
            if w == 0x0300: return 16, 'NOP', info
            if w == 0x0320: return 16, 'CLRC', info
            if w == 0x0360: return 16, 'DINT', info
            if w == 0x0d60: return 16, 'EINT', info
            if w == 0x0de0: return 16, 'SETC', info
            if w == 0x01c0: return 16, 'POPST', info
            if w == 0x01e0: return 16, 'PUSHST', info
            if w == 0x0940: return 16, 'RETI', info
            if g in simple and simple[g]:
                info = {'wr': rd} if g in (0x0020, 0x0140, 0x0180, 0x0380, 0x03a0, 0x03c0, 0x03e0) else {}
                if g == 0x0920: info = {'call': rs.replace('A', 'A') if False else rd}
                return 16, f'{simple[g]} {rd}', info
            if w & 0xffe0 == 0x0960: return 16, f'RETS {w & 31}', {'ret': 1}
            if w & 0xffe0 == 0x0900: return 16, f'TRAP {w & 31}', info
            if g == 0x0980: return 32, f'MMTM {rd},0x{w16():04x}', info
            if g == 0x09a0: return 32, f'MMFM {rd},0x{w16():04x}', {'wrall': 1}
            if g == 0x09c0: v = s16(); return 32, f'MOVI {v},{rd}', {'wr': rd, 'k': v}
            if g == 0x09e0:
                t, v, s = L(); return 48, f'MOVI {t[1:]},{rd}', {'wr': rd, 'k': v, 'ks': s}
            if g == 0x0b00: v = s16(); return 32, f'ADDI {v},{rd}', {'wr': rd, 'addi': v}
            if g == 0x0b20: t, v, s = L(); return 48, f'ADDI {t[1:]},{rd}', {'wr': rd, 'addi': v, 'ks': s}
            if g == 0x0b40: v = (~s16()) & 0xffff; return 32, f'CMPI {v:#x},{rd}', {'cmp': v}
            if g == 0x0b60: v = (~l32()) & 0xffffffff; return 48, f'CMPI {v:#x},{rd}', {'cmp': v}
            if g == 0x0b80: v = (~l32()) & 0xffffffff; return 48, f'ANDI {v:#x},{rd}', {'wr': rd}
            if g == 0x0ba0: v = l32(); return 48, f'ORI {v:#x},{rd}', {'wr': rd}
            if g == 0x0bc0: v = l32(); return 48, f'XORI {v:#x},{rd}', {'wr': rd}
            if g == 0x0be0: v = (~s16()) & 0xffff; return 32, f'SUBI {v:#x},{rd}', {'wr': rd}
            if g == 0x0d00: v = (~l32()) & 0xffffffff; return 48, f'SUBI {v:#x},{rd}', {'wr': rd}
            if w == 0x0d3f: v = s16(); t = a + 32 + v * 16; return 32, f'CALLR {self.text.get(t, hex(t))}', {'call': self.text.get(t, hex(t))}
            if w == 0x0d5f:
                t, v, s = L(); return 48, f'CALLA {t[1:]}', {'call': s if s else hex(v)}
            if g in (0x0d80, 0x0da0, 0x0dc0):
                v = s16(); t = a + 32 + v * 16; return 32, f"{ {0x0d80:'DSJ',0x0da0:'DSJEQ',0x0dc0:'DSJNE'}[g]} {rd},{t:x}", {'wr': rd, 'br': t}
            if top in (0x0400, 0x0600):
                sub = (w >> 5) & 0xf
                if sub in (8, 9): return 16, f"{'SEXT' if sub==8 else 'ZEXT'} {rd},{F}", {'wr': rd}
                if sub in (10, 11): return 16, f'SETF {w & 31 or 32},{(w >> 5) & 1},{F}', info
                if sub == 12:
                    t, v, s = L(); return 48, f'MOVE {rd},{t},{F}', {'st': t, 'src': rd, 'sts': s, 'stv': v}
                if sub == 13:
                    t, v, s = L(); return 48, f'MOVE {t},{rd},{F}', {'wr': rd, 'ld': t, 'lds': s, 'ldv': v}
                if sub == 14:
                    t1, v1, s1 = L(); t2, v2, s2 = L(2); return 80, f'MOVE {t1},{t2},{F}', {'st': t2, 'sts': s2, 'stv': v2, 'srcmem': t1}
                if sub == 15:
                    t, v, s = L()
                    return (48, f'MOVB {rd},{t}', {'st': t, 'src': rd, 'sts': s}) if not F else (48, f'MOVB {t},{rd}', {'wr': rd, 'ld': t, 'lds': s})
            return 16, f'.word 0x{w:04x}', {'unk': 1}
        hi = w >> 10
        k = (w >> 5) & 31
        if hi == 0x04: return 16, f'ADDK {k or 32},{rd}', {'wr': rd, 'addi': k or 32}
        if hi == 0x05: return 16, f'SUBK {k or 32},{rd}', {'wr': rd, 'addi': -(k or 32)}
        if hi == 0x06: return 16, f'MOVK {k or 32},{rd}', {'wr': rd, 'k': k or 32}
        if hi == 0x07: return 16, f'BTST {(~k) & 31},{rd}', info
        if hi in (0x08, 0x09, 0x0a, 0x0b, 0x0c):
            nm = {8: 'SLA', 9: 'SLL', 10: 'SRA', 11: 'SRL', 12: 'RL'}[hi]
            kk = k if hi in (8, 9, 12) else (32 - k) & 31
            return 16, f'{nm} {kk},{rd}', {'wr': rd, 'shift': (nm, kk)}
        if hi in (0x0e, 0x0f):
            d5 = k if hi == 0x0e else -k
            t = a + 16 + d5 * 16
            return 16, f'DSJS {rd},{t:x}', {'wr': rd, 'br': t}
        two = {0x40: 'ADD', 0x42: 'ADDC', 0x44: 'SUB', 0x46: 'SUBB', 0x48: 'CMP', 0x4a: 'BTST', 0x4c: 'MOVE', 0x4e: 'MOVE',
               0x50: 'AND', 0x52: 'ANDN', 0x54: 'OR', 0x56: 'XOR', 0x58: 'DIVS', 0x5a: 'DIVU', 0x5c: 'MPYS', 0x5e: 'MPYU',
               0x60: 'SLA', 0x62: 'SLL', 0x64: 'SRA', 0x66: 'SRL', 0x68: 'RL', 0x6a: 'LMO', 0x6c: 'MODS', 0x6e: 'MODU'}
        if (w >> 9) << 1 in two and w < 0x7000:
            nm = two[(w >> 9) << 1]
            if (w >> 9) << 1 == 0x4e: rs2 = R((w >> 5) & 15, 1 - b); return 16, f'MOVE {rs2},{rd}', {'wr': rd, 'mv': rs2}
            if nm == 'MOVE': return 16, f'MOVE {rs},{rd}', {'wr': rd, 'mv': rs}
            if nm in ('CMP', 'BTST'): return 16, f'{nm} {rs},{rd}', info
            if nm == 'XOR' and rs == rd: return 16, f'CLR {rd}', {'wr': rd, 'k': 0}
            if nm == 'SUB' and rs == rd: return 16, f'CLR {rd}', {'wr': rd, 'k': 0}
            return 16, f'{nm} {rs},{rd}', {'wr': rd, 'op': (nm, rs)}
        mv = {0x80: ('MOVE', '{s},*{d}', 'st'), 0x84: ('MOVE', '*{s},{d}', 'ld'), 0x88: ('MOVE', '*{s},*{d}', 'st'),
              0x90: ('MOVE', '{s},*{d}+', 'st'), 0x94: ('MOVE', '*{s}+,{d}', 'ld'), 0x98: ('MOVE', '*{s}+,*{d}+', 'st'),
              0xa0: ('MOVE', '{s},-*{d}', 'st'), 0xa4: ('MOVE', '-*{s},{d}', 'ld'), 0xa8: ('MOVE', '-*{s},-*{d}', 'st')}
        t2 = (w >> 10) << 2
        if t2 in mv:
            nm, fmt, kind = mv[t2]
            info = {'wr': rd} if kind == 'ld' else {'st': '*' + rd, 'src': rs}
            if t2 in (0x90, 0x94, 0x98): info.setdefault('inc', rd if t2 != 0x94 else rs)
            if t2 == 0x90 and rd == 'A14': info['push'] = rs
            return 16, f'{nm} ' + fmt.format(s=rs, d=rd) + f',{F}', info
        if top == 0x8c00: return 16, f'MOVB {rs},*{rd}', {'st': '*' + rd, 'src': rs}
        if top == 0x8e00: return 16, f'MOVB *{rs},{rd}', {'wr': rd}
        if top == 0x9c00: return 16, f'MOVB *{rs},*{rd}', info
        if top == 0xac00: return 32, f'MOVB {rs},*{rd}({s16()})', {'st': f'*{rd}({s16()})', 'src': rs}
        if top == 0xae00: return 32, f'MOVB *{rs}({s16()}),{rd}', {'wr': rd, 'ldd': (rs, s16())}
        if top == 0xbc00: return 48, f'MOVB *{rs}({s16()}),*{rd}({s16(1)})', info
        if t2 == 0xb0: return 32, f'MOVE {rs},*{rd}({s16()}),{F}', {'st': f'*{rd}({s16()})', 'src': rs}
        if t2 == 0xb4: return 32, f'MOVE *{rs}({s16()}),{rd},{F}', {'wr': rd, 'ldd': (rs, s16())}
        if t2 == 0xb8: return 48, f'MOVE *{rs}({s16()}),*{rd}({s16(1)}),{F}', info
        if t2 == 0xd0: return 32, f'MOVE *{rs}({s16()}),*{rd}+,{F}', info
        if top in (0xd400, 0xd600) and (w & 0x1e0) == 0:
            t, v, s = L(); inf = {'push': t} if rd == 'A14' else {}
            return 48, f'MOVE {t},*{rd}+,{F}', inf
        if 0xd800 <= w <= 0xdfff: return 16, f'COP 0x{w:04x}', {'unk': 1, 'cop': 1}
        if w & 0xf000 == 0xc000:
            c = CC[(w >> 8) & 15]; d8 = w & 0xff
            if d8 == 0: t = a + 32 + s16() * 16; return 32, f'JR{c} {t:x}', {'br': t, 'cc': c}
            if d8 == 0x80: v = l32(); return 48, f'JA{c} {v:x}', {'br': v, 'cc': c}
            dd = d8 - 256 if d8 > 127 else d8; t = a + 16 + dd * 16
            return 16, f'JR{c} {t:x}', {'br': t, 'cc': c}
        return 16, f'.word 0x{w:04x}', {'unk': 1}

    def func(self, name):
        for v, n in self.funcs:
            if n == name:
                k = self.fa.index(v); end = self.funcs[k + 1][0] if k + 1 < len(self.funcs) else self.tx['size']
                return v, end
        raise KeyError(name)

    def listing(self, start, end):
        a = start; out = []
        while a < end:
            try:
                sz, t, info = self.dis1(a)
            except struct.error:
                break
            out.append((a, sz, t, info)); a += sz
        return out


if __name__ == '__main__':
    m = Mod(sys.argv[1])
    for f in sys.argv[2:]:
        s, e = m.func(f)
        print(f'===== {f} {s:x}-{e:x}')
        for a, sz, t, info in m.listing(s, e):
            print(f'{a:08x}: {t}')
