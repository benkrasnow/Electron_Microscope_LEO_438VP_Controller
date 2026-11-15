# Decode LEO-32's C:\LEO\DATA.VAC (non-volatile machine data) using the field table of the
# LEO "DATA.VAC File Viewer" (view.exe, 1997): each label in view.exe is preceded by the load of
# its field from the section struct ("push word es:[bx+off]" x2 = 4-byte float, x1 = word,
# "mov al, es:[bx+off]" = byte). Section offsets/sizes come from view.exe's read routine.
# Usage: python datavac.py <view.exe> <Data.vac>
import sys, os, struct, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ne import parse
from capstone import Cs, CS_ARCH_X86, CS_MODE_16

SECTIONS = [('NVRAM', 0x000, 5), ('STAGE', 0x005, 12), ('VACUUM', 0x011, 22), ('EO', 0x027, 0x3a8),
            ('MASTER', 0x3cf, 0x1db), ('MODES', 0x5aa, 1), ('DISPLAY', 0x5ab, 1), ('ACQUIRE', 0x5ac, 5),
            ('EHT', 0x5b1, 0x6e)]
HEADERS = {'NVRAM %s :': 'NVRAM', 'Stage %s :': 'STAGE', 'Vacuum %s :': 'VACUUM', 'EO %s :': 'EO',
           'Master %s :': 'MASTER', 'Modes %s :': 'MODES', 'Display %s :': 'DISPLAY',
           'Acquire %s :': 'ACQUIRE', 'EHT %s :': 'EHT'}


def fields(view):
    d, segs, *_ = parse(view)
    o, l, _, _ = segs[0]; code = d[o:o + l]
    do, dl, _, _ = segs[1]; data = d[do:do + dl]

    def s_at(k):
        e = data.find(b'\0', k); return data[k:e].decode('latin1')

    ins = list(Cs(CS_ARCH_X86, CS_MODE_16).disasm(code, 0))
    sec, out, seen = None, [], set()
    for idx, i in enumerate(ins):
        if not (i.mnemonic == 'mov' and i.op_str.startswith('ax, 0x')): continue
        v = int(i.op_str[4:], 16)
        if v >= len(data) or (v and data[v - 1]): continue
        lab = s_at(v)
        if lab in HEADERS: sec = HEADERS[lab]; continue
        if sec is None or not (2 <= len(lab) < 60): continue
        prev = ins[max(0, idx - 8):idx]
        pushes = [int(m.group(1), 16) for j in prev
                  if (m := re.fullmatch(r'word ptr es:\[bx \+ (0x[0-9a-f]+)\]', j.op_str)) and j.mnemonic == 'push']
        byte = [int(m.group(1), 16) for j in prev
                if (m := re.fullmatch(r'al, byte ptr es:\[bx \+ (0x[0-9a-f]+)\]', j.op_str))]
        if len(pushes) >= 2 and pushes[-1] + 2 == pushes[-2]: off, kind = pushes[-1], 'f4'
        elif pushes: off, kind = pushes[-1], 'i2'
        elif byte: off, kind = byte[-1], 'u1'
        else: continue
        key = (sec, lab, off)
        if key in seen: continue
        seen.add(key); out.append((sec, lab, off, kind))
    return out


def main():
    view, vac = sys.argv[1], sys.argv[2]
    blob = open(vac, 'rb').read()
    base = {n: o for n, o, _ in SECTIONS}
    for sec, lab, off, kind in fields(view):
        a = base[sec] + off
        if a + 4 > len(blob): continue
        if kind == 'f4':
            f = struct.unpack('<f', blob[a:a + 4])[0]; val = f'{f:.6g}'
        elif kind == 'i2':
            val = str(struct.unpack('<h', blob[a:a + 2])[0])
        else:
            val = str(blob[a])
        print(f'{sec:8s} {a:#06x} +{off:#05x} {kind}  {lab:32s} {val}')


if __name__ == '__main__':
    main()
