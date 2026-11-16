"""Decode the enumerated (option) fields of LEO-32's Data.vac with view.exe's code: each option list is a
switch on one byte ("mov al, es:[bx+off]; cwde; jmp switch"), whose cases load "<option>" then "<field label>".
  python datavac_enums.py <view.exe> <Data.vac> [more Data.vac ...]
Prints section, offset, field label, the byte value and the option it selects, for each file.
Caveat: the option lists are paired heuristically and can be misaligned for some fields; switches built as
jump tables (e.g. MASTER machine type at file 0x507: 4 = LEO 435VP, 10 = LEO 438) must be read from the table.
Verified: EO column type at file 0x0ed (3 = LEO 435VP/438VP), EHT filament type at file 0x5b5 (0 = Tungsten).
"""
import sys, os, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ne import parse
from capstone import Cs, CS_ARCH_X86, CS_MODE_16
from datavac import SECTIONS, HEADERS


def enum_fields(view):
    d, segs, *_ = parse(view)
    o, l, _, _ = segs[0]; code = d[o:o + l]
    do, dl, _, _ = segs[1]; data = d[do:do + dl]
    s_at = lambda k: data[k:data.find(b'\0', k)].decode('latin1')
    ins = list(Cs(CS_ARCH_X86, CS_MODE_16).disasm(code, 0))
    loads = [(n, i) for n, i in enumerate(ins) if i.mnemonic == 'mov' and i.op_str.startswith('ax, 0x')]
    fields, sec, cur = [], None, None       # cur = (offset, {value: option})
    for n, i in loads:
        v = int(i.op_str[4:], 16)
        if v >= len(data) or (v and data[v - 1]): continue
        lab = s_at(v)
        if lab in HEADERS: sec = HEADERS[lab]; continue
        if sec is None: continue
        # a byte switch read shortly before starts a new enum field
        back = ins[max(0, n - 12):n]
        sw = [int(m.group(1), 16) for j in back if (m := re.fullmatch(r'al, byte ptr es:\[bx \+ (0x[0-9a-f]+)\]', j.op_str))]
        if sw and any(j.mnemonic == 'cwde' for j in back): cur = {'sec': sec, 'off': sw[-1], 'opts': [], 'label': None}; fields.append(cur)
        if cur is None: continue
        # options and the label alternate: option, label, option, label ...
        if cur['label'] is None and len(cur['opts']) == 1: cur['label'] = lab
        elif lab == cur['label']: pass
        elif cur['label'] is not None and lab != cur['label'] and len(cur['opts']) and cur['opts'][-1] != lab: cur['opts'].append(lab)
        elif not cur['opts']: cur['opts'].append(lab)
    return [f for f in fields if f['label'] and len(f['opts']) >= 2]


if __name__ == '__main__':
    view, vacs = sys.argv[1], sys.argv[2:]
    base = {n: a for n, a, _ in SECTIONS}
    fs = enum_fields(view)
    blobs = [open(p, 'rb').read() for p in vacs]
    for f in fs:
        a = base[f['sec']] + f['off']
        vals = [b[a] if a < len(b) else None for b in blobs]
        opt = lambda v: f['opts'][v] if v is not None and v < len(f['opts']) else f'?{v}'
        print(f"{f['sec']:7s} {a:#06x} {f['label'][:26]:26s} " + '  '.join(f'{v}={opt(v)}' for v in vals) + f"   options: {f['opts']}")
