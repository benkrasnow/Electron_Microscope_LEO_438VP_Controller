import sys,os,re,struct
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from coff import parse
from t340 import dis
p=sys.argv[1]
d,h,secs,syms=parse(p)
tx=[s for s in secs if s['name']=='.text'][0]
raw=d[tx['ptr']:tx['ptr']+tx['size']//8]
funcs=sorted((v,n) for n,v,scn,t,c in syms if scn==1 and c in(2,3) and not n.startswith('$') and not n.startswith('.'))
DPV=int(sys.argv[2],16)  # address of _DPRAM var
out={}
for k,(v,fn) in enumerate(funcs[:-1]):
    end=funcs[k+1][0]
    lines=dis(raw[v//8:end//8+8],v,(end-v)//8)
    regbase={}; const={}; ev=[]
    for l in lines:
        m=re.search(r'MOVE   @0x([0-9a-f]+),(\w+),1',l)
        if m and int(m.group(1),16)==DPV: regbase[m.group(2)]=0; continue
        m=re.search(r'ADDI   (-?\d+),(\w+)',l)
        if m and m.group(2) in regbase: regbase[m.group(2)]+=int(m.group(1)); continue
        m=re.search(r'MOVK   (\d+),(\w+)',l)
        if m: const[m.group(2)]=int(m.group(1)); continue
        m=re.search(r'MOVI   (-?\d+) .*,(\w+)$',l)
        if m: const[m.group(2)]=int(m.group(1)); continue
        m=re.search(r'MOVI   0x([0-9a-f]+),(\w+)$',l)
        if m: const[m.group(2)]=int(m.group(1),16); continue
        m=re.search(r'SUB    (\w+),(\w+)$',l)
        if m and m.group(1)==m.group(2): const[m.group(2)]=0; continue
        m=re.search(r'MOVE   (\w+),\*(\w+),1',l)
        if m and m.group(2) in regbase:
            off=regbase[m.group(2)]//32; val=const.get(m.group(1))
            ev.append(('CMD' if off==0x400 else 'W')+f'{off:03X}'+('' if val is None else f'={val:#x}'))
            continue
        m=re.search(r'MOVE   \*(\w+),(\w+),1',l)
        if m and m.group(1) in regbase:
            off=regbase[m.group(1)]//32
            if off!=0x400: ev.append(f'R{off:03X}')
            regbase.pop(m.group(1),None); continue
        m=re.search(r',(\w+)(,\d)?$',l)
        if m: 
            r=m.group(1); const.pop(r,None)
    if ev: out[fn]=ev
for fn,ev in out.items():
    # compress
    s=[]; 
    for e in ev:
        if not s or s[-1]!=e: s.append(e)
    print(f'{fn:32s} '+' '.join(s)[:400])
