"""Find every M007_GETSTATE / M007_PUTSTATE call with a given state id in LEO-32's Win16 DLLs.
  python state_refs.py <LEO-32 dir> <state id, e.g. 0x8c>
Prints module, address and the instructions leading up to each call.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ne import parse
from capstone import Cs, CS_ARCH_X86, CS_MODE_16

SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nedis.py')).read()
RELOCS = SRC[SRC.index('def relocs'):SRC.index('for name in sys.argv[2:]:')]
WANT = {'M007.#26': 'PUTSTATE', 'M007.#27': 'GETSTATE'}


def scan(path, sid):
    d, segs, res, nres, mods, ents, imp = parse(path)
    ns = {'d': d, 'segs': segs, 'mods': mods, 'impbase': imp, 'struct': struct}
    exec(RELOCS, ns)
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    for si in range(1, len(segs) + 1):
        o, l, f, m = segs[si - 1]
        if f & 1: continue                                   # data segment
        code = d[o:o + l]
        R = ns['relocs'](si)
        for k, tgt in R.items():
            if tgt not in WANT or k < 1 or code[k - 1] != 0x9A: continue      # 9A = call far ptr16:16
            call = k - 1
            # back-decode: find a start that disassembles cleanly up to the call
            ctx = None
            for back in range(40, 0, -1):
                ins = list(md.disasm(code[call - back:call + 5], call - back))
                if any(i.address == call for i in ins): ctx = [i for i in ins if i.address <= call]; break
            if not ctx: continue
            pushes = [p.op_str for p in ctx[:-1] if p.mnemonic == 'push']
            if WANT[tgt] == 'GETSTATE' and pushes and pushes[-1] == sid or                WANT[tgt] == 'PUTSTATE' and len(pushes) >= 2 and pushes[-2] == sid:
                yield si, call, WANT[tgt], ctx[-8:]

if __name__ == '__main__':
    root, sid = sys.argv[1], sys.argv[2]
    for f in sorted(os.listdir(root)):
        if not f.lower().endswith(('.dll', '.exe')): continue
        try:
            for si, a, kind, ctx in scan(os.path.join(root, f), sid):
                print(f'== {f} seg{si}:{a:04x} {kind}({sid}{", ..." if kind == "PUTSTATE" else ""})')
                for j in ctx: print(f'   {j.address:04x} {j.mnemonic} {j.op_str}')
        except Exception as e:
            pass
