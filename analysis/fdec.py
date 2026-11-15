# Symbolic decompiler for the TI 340x0 C compiler's software floating point.
# The compiler evaluates float expressions on the A14 parameter stack: operands are pushed
# ("MOVE x,*A14+"), the FS$/FD$ library routines pop two and push one, results are popped
# ("MOVE -*A14,Rx"). Called functions get their arguments above a "MOVE A14,-*SP" marker and
# leave the result in a slot the caller reserved with ADDK/ADDI on A14.
# Usage: python fdec.py <g200.440> <function> [...]   -> readable statements with constants.
import sys, os, re, struct, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t34 import Mod

BIN = {'ADD': '+', 'SUB': '-', 'MUL': '*', 'DIV': '/'}
CMP = {'LT': '<', 'GT': '>', 'LE': '<=', 'GE': '>=', 'EQ': '==', 'NE': '!='}
UNARY_LIB = {'_SQRT': 'sqrt', '_SIN': 'sin', '_COS': 'cos', '_TAN': 'tan', '_ATAN': 'atan', '_EXP': 'exp',
             '_LOG': 'log', '_LOG10': 'log10', '_FABS': 'fabs', '_ASIN': 'asin', '_ACOS': 'acos'}


class Data:
    def __init__(self, m):
        self.m = m
        self.ds = [s for s in m.secs if s['name'] == '.data'][0]
        self.raw = m.d[self.ds['ptr']:self.ds['ptr'] + self.ds['size'] // 8]
        self.bss = sorted((v, n) for (scn, v), n in m.addr2.items() if scn == 3)
        self.dat = sorted((v, n) for (scn, v), n in m.addr2.items() if scn == 2)

    def bytes_at(self, bitaddr, n):
        o = (bitaddr - self.ds['vaddr']) // 8
        return self.raw[o:o + n] if 0 <= o < len(self.raw) else None

    def double(self, bitaddr):
        b = self.bytes_at(bitaddr, 8)
        if not b or len(b) < 8: return None
        lo, hi = struct.unpack('<II', b)          # GSP doubles: high 32-bit word first
        return struct.unpack('<d', struct.pack('<II', hi, lo))[0]

    def single(self, bitaddr):
        b = self.bytes_at(bitaddr, 4)
        return struct.unpack('<f', b)[0] if b and len(b) == 4 else None

    # Known runtime structures (from the code that indexes them): lens records and calibrations.
    STRUCTS = [(0x172640, 96, 2, 'LCAL'), (0x1723c0, 288, 2, 'LENS'), (0x172760, 288, 1, 'LENS3'), (0x172880, 96, 1, 'LCAL3'), (0x172b20, 192, 1, 'GUNNOW'), (0x172c00, 128, 60, 'GUNTAB'), (0x174be0, 128, 5, 'APER')]

    def name(self, addr):
        for base, size, count, nm in self.STRUCTS:
            if base <= addr < base + size * count:
                i, w = divmod(addr - base, size)
                return f'{nm}[C{i + 1}].w{w // 32}'
        for tab in (self.bss, self.dat):
            vs = [v for v, _ in tab]
            k = bisect.bisect_right(vs, addr) - 1
            if k >= 0 and addr - tab[k][0] < 0x4000:
                v, n = tab[k]
                return n if addr == v else f'{n}+{(addr - v) // 8}'
        return f'g_{addr:x}'


def fmt(x):
    if isinstance(x, float): return f'{x:.10g}'
    return str(x)


def paren(e):
    return e if re.fullmatch(r'[\w.$@\[\]+]+|-?[\d.eE+-]+', e) else f'({e})'


def decompile(m, D, name):
    if name.startswith('0x'):                 # unnamed static function: from address to its RETS
        s = int(name, 16); a = s; e = s
        while True:
            sz, t, info = m.dis1(a); a += sz
            if t.startswith('RETS'): e = a; break
        lst = m.listing(s, e)
    else:
        s, e = m.func(name)
        lst = m.listing(s, e)
    targets = {info['br'] for _, _, _, info in lst if 'br' in info}
    regs, stack, marks, out = {}, [], [], []
    ptr = {}            # register -> [bitaddr, words pushed]
    mem = {}
    cond = None

    def var(off):
        off = int(off)
        return f'arg{(-off) // 32}' if off < 0 else f'loc{off // 32}'

    def reg(r):
        return regs.get(r, r)

    def push(x): stack.append(x)

    def pop():
        return stack.pop() if stack else '?'

    def emit(t, a): out.append(f'  {a:06x}  {t}')

    bssptr = {}         # register -> [bitaddr]: walking a .bss/.data struct
    def fr(r):          # frame offset held in a register ('&frame+N'), else None
        v = regs.get(r, '')
        return int(v[7:]) if isinstance(v, str) and v.startswith('&frame+') else None

    for a, sz, t, info in lst:
        if a in targets:
            out.append(f'L{a:x}:')
            regs.clear(); ptr.clear()
        mm = None
        # ---- frame pointers and struct copies (BLMOVE = .word 0x00f3)
        if t in ('MOVE A13,A8', 'MOVE A13,A12', 'MOVE A13,A6', 'MOVE A13,A10', 'MOVE A13,A4', 'MOVE A13,A0'):
            regs[t.split(',')[1]] = '&frame+0'; continue
        if t == 'MOVE B13,A2':                       # really MOVE A13,B2 (destination of BLMOVE)
            regs['B2'] = '&frame+0'; continue
        if (mm := re.fullmatch(r'ADDI (\d+),(\w+)', t)) and fr(mm.group(2)) is not None:
            regs[mm.group(2)] = f'&frame+{fr(mm.group(2)) + int(mm.group(1))}'; continue
        if (mm := re.fullmatch(r'MOVI (\d+),B7', t)):
            regs['B7'] = mm.group(1); continue
        if (mm := re.fullmatch(r'MOVI 0x([0-9a-f]+)<\.(bss|data)\+[0-9a-f]+>,(\w+)', t)):
            v = int(mm.group(1), 16); r = mm.group(3)
            bssptr[r] = [v]; regs[r] = D.name(v)
            if mm.group(2) == 'data': ptr[r] = [v, 0]
            continue
        if t == '.word 0x00f3' and fr('B2') is not None and 'B0' in bssptr:
            base, off = bssptr['B0'][0], fr('B2')
            n = int(regs.get('B7', '0')) // 32
            for i in range(n):
                mem[off + 32 * i] = D.name(base + 32 * i)
            bssptr['B0'][0] += 32 * n                 # BLMOVE advances the source pointer
            continue
        if (mm := re.fullmatch(r'MOVE \*(\w+)(\+?),\*(\w+)(\+?),1', t)) and mm.group(1) in bssptr and fr(mm.group(3)) is not None and mm.group(3) != 'A14':
            src, dst = mm.group(1), mm.group(3)
            mem[fr(dst)] = D.name(bssptr[src][0])
            if mm.group(2): bssptr[src][0] += 32
            if mm.group(4): regs[dst] = f'&frame+{fr(dst) + 32}'
            continue
        if (mm := re.fullmatch(r'CALLA F[SD]\$(ITOF|ITOD|UTOF|UTOD)', t)):
            push(f'float({reg("A8")})'); continue
        # ---- pushes
        if (mm := re.fullmatch(r'MOVE (A\d+|B\d+),\*A14\+,1', t)):
            r = mm.group(1)
            if r in ptr:
                p = ptr[r]
                if p[1] % 2 == 0:
                    v = D.double(p[0] + 64 * (p[1] // 2))
                    push(fmt(v) if v is not None else D.name(p[0]))
                p[1] += 1
            else:
                push(reg(r))
            continue
        if (mm := re.fullmatch(r'MOVE \*(A\d+)\+,\*A14\+,1', t)):
            r = mm.group(1)
            if r in ptr:
                p = ptr[r]
                if p[1] % 2 == 0:
                    v = D.double(p[0] + 32 * p[1])
                    push(fmt(v) if v is not None else f'*{D.name(p[0] + 32 * p[1])}')
                p[1] += 1
            else:
                push(f'*{reg(r)}++')
            continue
        if (mm := re.fullmatch(r'MOVE \*(A(?:[0-9]|1[0-2])|B\d+)\((-?\d+)\),\*A14\+,1', t)):
            push(f'{paren(reg(mm.group(1)))}.f{int(mm.group(2)) // 8}'); continue
        if (mm := re.fullmatch(r'MOVE \*(A(?:[0-9]|1[0-2]))\+?,\*A14\+,1', t)) and mm.group(1) not in ptr:
            push(f'*{paren(reg(mm.group(1)))}'); continue
        if (mm := re.fullmatch(r'ADDI 0x([0-9a-f]+)<\.(bss|data)\+[0-9a-f]+>,(\w+)', t)):
            regs[mm.group(3)] = f'{D.name(int(mm.group(1), 16))} + {paren(reg(mm.group(3)))}'; continue
        if (mm := re.fullmatch(r'(SLL|SLA) (\d+),(\w+)', t)):
            regs[mm.group(3)] = f'{paren(reg(mm.group(3)))}<<{mm.group(2)}'; continue
        if (mm := re.fullmatch(r'(ADD|SUB|MPYS|MPYU) (\w+),(\w+)', t)) and mm.group(3) not in ('A14', 'A13'):
            o = {'ADD': '+', 'SUB': '-', 'MPYS': '*', 'MPYU': '*'}[mm.group(1)]
            regs[mm.group(3)] = f'{paren(reg(mm.group(3)))} {o} {paren(reg(mm.group(2)))}'; continue
        if (mm := re.fullmatch(r'MOVE \*(A(?:[0-9]|1[0-2]))\((-?\d+)\),(\w+),[01]', t)):
            regs[mm.group(3)] = f'{paren(reg(mm.group(1)))}.f{int(mm.group(2)) // 8}'; continue
        if (mm := re.fullmatch(r'MOVE \*(A(?:[0-9]|1[0-2])),(\w+),[01]', t)):
            regs[mm.group(2)] = f'*{paren(reg(mm.group(1)))}'; continue
        if (mm := re.fullmatch(r'MOVE (\w+),\*(A(?:[0-9]|1[0-2])),[01]', t)):
            emit(f'*{paren(reg(mm.group(2)))} = {reg(mm.group(1))}', a); continue
        if (mm := re.fullmatch(r'MOVE \*A13\((-?\d+)\),\*A14\+,1', t)):
            push(mem.get(int(mm.group(1)), var(mm.group(1)))); continue
        if (mm := re.fullmatch(r'MOVE \*A13,\*A14\+,1', t)):
            push(mem.get(0, var(0))); continue
        if (mm := re.fullmatch(r'MOVE @(\S+?)(?:<\S+>)?,\*A14\+,1', t)):
            push(mm.group(1) if not mm.group(1).startswith('0x') else D.name(int(mm.group(1), 16))); continue
        # ---- pops / register moves
        if (mm := re.fullmatch(r'MOVE -\*A14,(\w+),1', t)):
            x = pop(); regs[mm.group(1)] = x; ptr.pop(mm.group(1), None)
            emit(f'{mm.group(1)} = {x}', a); continue
        if (mm := re.fullmatch(r'MOVI (0x[0-9a-f]+)(<\.(data|bss)\+[0-9a-f]+>)?,(\w+)', t)):
            v = int(mm.group(1), 16)
            if mm.group(3) == 'data': ptr[mm.group(4)] = [v, 0]
            regs[mm.group(4)] = D.name(v) if mm.group(2) else hex(v); continue
        if (mm := re.fullmatch(r'MOVI (-?\d+),(\w+)', t)):
            regs[mm.group(2)] = mm.group(1); ptr.pop(mm.group(2), None); continue
        if (mm := re.fullmatch(r'MOVI ([\w$]+),(\w+)', t)):
            regs[mm.group(2)] = mm.group(1); continue
        if (mm := re.fullmatch(r'MOVK (\d+),(\w+)', t)):
            regs[mm.group(2)] = mm.group(1); continue
        if (mm := re.fullmatch(r'CLR (\w+)', t)):
            regs[mm.group(1)] = '0'; continue
        if (mm := re.fullmatch(r'MOVE (\w+),(\w+)', t)) and mm.group(2) not in ('A14', 'A13'):
            regs[mm.group(2)] = reg(mm.group(1)); continue
        if (mm := re.fullmatch(r'MOVE \*A13\((-?\d+)\),(\w+),[01]', t)):
            regs[mm.group(2)] = mem.get(int(mm.group(1)), var(mm.group(1))); continue
        if (mm := re.fullmatch(r'MOVE \*A13,(\w+),[01]', t)):
            regs[mm.group(1)] = mem.get(0, var(0)); continue
        if (mm := re.fullmatch(r'MOVE @(\S+?)(?:<\S+>)?,(\w+),[01]', t)):
            n = mm.group(1); regs[mm.group(2)] = n if not n.startswith('0x') else D.name(int(n, 16)); continue
        # ---- stores
        if (mm := re.fullmatch(r'MOVE (\w+),\*A13\((-?\d+)\),[01]', t)):
            off = int(mm.group(2)); x = reg(mm.group(1)); mem[off] = var(off)
            emit(f'{var(off)} = {x}', a); continue
        if (mm := re.fullmatch(r'MOVE (\w+),\*A13,[01]', t)):
            x = reg(mm.group(1)); mem[0] = var(0); emit(f'{var(0)} = {x}', a); continue
        if (mm := re.fullmatch(r'MOVE (\w+),@(\S+?)(?:<\S+>)?,[01]', t)):
            n = mm.group(2); n = n if not n.startswith('0x') else D.name(int(n, 16))
            emit(f'{n} = {reg(mm.group(1))}', a); continue
        if (mm := re.fullmatch(r'MOVE (\w+),\*(\w+)\((-?\d+)\),[01]', t)):
            emit(f'{paren(reg(mm.group(2)))}.f{int(mm.group(3)) // 8} = {reg(mm.group(1))}', a); continue
        if (mm := re.fullmatch(r'MOVE \*(\w+)\((-?\d+)\),(\w+),[01]', t)) and mm.group(1) != 'SP':
            regs[mm.group(3)] = f'{reg(mm.group(1))}[{int(mm.group(2)) // 32}]'; continue
        # ---- stack frame bookkeeping
        if (mm := re.fullmatch(r'(ADDK|ADDI) (\d+),A14', t)):
            for _ in range(int(mm.group(2)) // 32): push('_')
            continue
        if (mm := re.fullmatch(r'SUBK (\d+),A14', t)):
            for _ in range(int(mm.group(1)) // 32): pop()
            continue
        if t == 'MOVE A14,-*SP,1':
            marks.append(len(stack)); continue
        if re.fullmatch(r'MOVE \*SP\(\d+\),A14,1', t):
            continue
        if t == 'MOVE *A14(-32),*A13(-32),1':
            emit(f'return {stack[-1] if stack else "?"}', a); continue
        # ---- calls
        if (mm := re.fullmatch(r'CALL[AR] (\S+)', t)):
            f = mm.group(1)
            if f.startswith('?+'): f = 'sub_' + f[4:]
            m2 = re.fullmatch(r'F([SD])\$(\w+)', f)
            if (m2 or f in UNARY_LIB) and marks and len(stack) - marks[-1] in (1, 2):
                k = marks.pop(); args = stack[k:]; del stack[k:]
                while stack and stack[-1] == '_': stack.pop()
                stack.extend(args)          # evaluate as a normal stack op below
            if m2:
                op = m2.group(2)
                if op in BIN:
                    b_, a_ = pop(), pop(); push(f'{paren(a_)} {BIN[op]} {paren(b_)}')
                elif op == 'DIV_R':
                    b_, a_ = pop(), pop(); push(f'{paren(b_)} / {paren(a_)}')
                elif op == 'SUB_R':
                    b_, a_ = pop(), pop(); push(f'{paren(b_)} - {paren(a_)}')
                elif op in CMP:
                    b_, a_ = pop(), pop(); cond = f'{paren(a_)} {CMP[op]} {paren(b_)}'
                elif op in ('FTOD', 'DTOF'):
                    pass
                elif op == 'NEG':
                    push(f'-{paren(pop())}')
                elif op in ('ITOF', 'ITOD', 'UTOF', 'UTOD'):
                    push(f'float({pop()})')
                elif op in ('FTOI', 'DTOI', 'FTOU', 'DTOU'):
                    x = pop(); push(f'int({x})')
                else:
                    push(f'{op}({pop()})')
                continue
            if f in UNARY_LIB and not (marks and marks[-1] < len(stack) - 1):
                push(f'{UNARY_LIB[f]}({pop()})'); continue
            if marks:
                k = marks.pop(); args = stack[k:]; del stack[k:]
                call = f'{f}({", ".join(args)})'
                if stack and stack[-1] == '_': stack[-1] = call
                else: push(call)
                emit(f'call {call}', a)
            else:
                emit(f'call {f}()  [regs A8={reg("A8")}]', a)
            continue
        # ---- branches
        if (mm := re.fullmatch(r'JR(\w+) ([0-9a-f]+)', t)) or (mm := re.fullmatch(r'JA(\w+) ([0-9a-f]+)', t)):
            c, tgt = mm.group(1), mm.group(2)
            if c == 'UC': emit(f'goto L{tgt}', a)
            else: emit(f'if {c} [{cond or "flags"}] goto L{tgt}', a)
            continue
        if t.startswith('RETS'):
            emit('end', a); continue
        if t.startswith(('MMTM', 'MMFM', 'SETF')):
            continue
        emit(f'; {t}', a)
    return out


if __name__ == '__main__':
    path = sys.argv[1]
    m = Mod(path)
    m.secs = [dict(s, vaddr=s.get('vaddr', s.get('addr', 0))) for s in m.secs]
    D = Data(m)
    for f in sys.argv[2:]:
        print(f'===== {f}')
        print('\n'.join(decompile(m, D, f)))
