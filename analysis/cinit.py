import sys,struct,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from coff import parse
p=sys.argv[1]
d,h,secs,syms=parse(p)
addr2sym={}
for n,v,scn,t,c in syms:
    if c in(2,3) and scn>0: addr2sym.setdefault(v,n)
ci=[s for s in secs if s['name']=='.cinit'][0]
raw=d[ci['ptr']:ci['ptr']+ci['size']//8]
# relocations for cinit: TI COFF reloc entry 10 bytes: vaddr(4) symndx(4) type(2)
# TMS340 cinit record: 16-bit size in 16-bit words? try: size(16) addr(32) data(size*16 bits)
i=0;out=[]
while i+6<=len(raw):
    sz=struct.unpack('<H',raw[i:i+2])[0]
    if sz==0: break
    addr=struct.unpack('<I',raw[i+2:i+6])[0]
    data=raw[i+6:i+6+sz*2]
    nm=addr2sym.get(addr,'?')
    out.append((addr,nm,data)); i+=6+sz*2
for addr,nm,data in out:
    if len(sys.argv)>2 and not any(k.lower() in nm.lower() for k in sys.argv[2:]): continue
    vals=[struct.unpack('<I',data[j:j+4])[0] for j in range(0,len(data)-3,4)][:8]
    print(f'{addr:08x} {nm:32s} len={len(data):4d}  ' + ' '.join(f'{v:08x}' for v in vals))
