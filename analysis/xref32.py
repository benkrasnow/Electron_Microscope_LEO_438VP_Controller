# find code xrefs (imm32 / disp32) to strings in a PE32, print context disassembly
import sys,pefile,re,struct
from capstone import *
pe=pefile.PE(sys.argv[1]); base=pe.OPTIONAL_HEADER.ImageBase
data=pe.get_memory_mapped_image()
text=[s for s in pe.sections if s.Name.startswith(b'.text')][0]
tva=base+text.VirtualAddress; tcode=data[text.VirtualAddress:text.VirtualAddress+text.Misc_VirtualSize]
def va_of(sub):
    out=[]
    for m in re.finditer(re.escape(sub),data): out.append(base+m.start())
    return out
md=Cs(CS_ARCH_X86,CS_MODE_32)
targets={}
for s in sys.argv[2:]:
    for v in va_of(s.encode()): targets[v]=s
refs=[]
for v,s in targets.items():
    for m in re.finditer(re.escape(struct.pack('<I',v)),tcode): refs.append((tva+m.start(),s))
for a,s in sorted(refs):
    print(f'---- ref to {s!r} at {a:08x}')
    start=a-0x30
    insns=list(md.disasm(data[start-base:start-base+0x80],start))
    # resync: keep insns after a
    for i in insns:
        if a-0x28<=i.address<=a+0x30: print(f'   {i.address:08x}: {i.mnemonic} {i.op_str}')
