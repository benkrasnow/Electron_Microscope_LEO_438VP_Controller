# scan TMS340 .text for MOVI IL (0x09E0|r) and MOVE @abs (various) 32-bit constants not covered by relocations
import sys,struct,os,collections,bisect
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from coff import parse
p=sys.argv[1]
d,h,secs,syms=parse(p)
tx=[s for s in secs if s['name']=='.text'][0]
raw=d[tx['ptr']:tx['ptr']+tx['size']//8]
rel=set()
for k in range(tx['nreloc']):
    va,si,ty=struct.unpack('<IIH',d[tx['relptr']+10*k:tx['relptr']+10*k+10])
    rel.add(va//8)
funcs=sorted((v//8,n) for n,v,scn,t,c in syms if scn==1 and c in(2,3) and not n.startswith('$') and not n.startswith('.'))
fa=[f[0] for f in funcs]
def fn(o):
    k=bisect.bisect_right(fa,o)-1; return funcs[k][1] if k>=0 else '?'
cnt=collections.defaultdict(set)
for i in range(0,len(raw)-6,2):
    w=struct.unpack('<H',raw[i:i+2])[0]
    if (w&0xffe0)==0x09e0 and (i+2) not in rel:
        v=struct.unpack('<I',raw[i+2:i+6])[0]
        if v>=0x00100000 and v not in(0xffffffff,) and (v&0xf)==0:
            cnt[v].add(fn(i))
    # MOVE @L,Rd  0x05A0|Rd? / MOVE Rs,@L 0x0580|Rs ; MOVE @L,@L 0x05C0?
    if (w&0xffc0) in(0x0580,0x05a0) or (w&0xffe0)==0x05c0 or (w&0xfe00)==0xb600 or (w&0xfe00)==0x9600 or (w&0xfe00)==0x8600 or (w&0xfe00)==0xa600:
        pass
for v in sorted(cnt):
    if v>=int(sys.argv[2],16) if len(sys.argv)>2 else True:
        print(f'{v:08x}  (byte {v>>3:07x})  ' + ', '.join(sorted(cnt[v]))[:200])
