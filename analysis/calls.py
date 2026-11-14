import sys,os,re,struct,collections
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from coff import parse
from t340 import dis
p=sys.argv[1]; targets=sys.argv[2].split(',')
d,h,secs,syms=parse(p)
magic,nsec,ts,symptr,nsym,opth,fl=struct.unpack('<HHIIIHH',d[:20])
strtab=symptr+18*nsym; idx={}
for i in range(nsym):
    e=d[symptr+18*i:symptr+18*i+18]
    if e[:4]==b'\0\0\0\0':
        so=struct.unpack('<I',e[4:8])[0]; j=d.index(b'\0',strtab+so); name=d[strtab+so:j].decode('latin1')
    else: name=e[:8].rstrip(b'\0').decode('latin1')
    idx[i]=name
tx=[s for s in secs if s['name']=='.text'][0]
raw=d[tx['ptr']:tx['ptr']+tx['size']//8]
rel={}
for k in range(tx['nreloc']):
    va,si,ty=struct.unpack('<IIH',d[tx['relptr']+10*k:tx['relptr']+10*k+10]); rel[va]=idx.get(si,'?')
addr2={}
for n,v,scn,t,c in syms:
    if scn==1 and c in(2,3) and not n.startswith('$') and not n.startswith('.'): addr2.setdefault(v,n)
funcs=sorted(addr2.items())
res=collections.defaultdict(list)
for k,(v,fn) in enumerate(funcs[:-1]):
    end=funcs[k+1][0]
    lines=dis(raw[v//8:end//8+8],v,(end-v)//8)
    pushes=[];const={}
    for l in lines:
        a=int(l[:8],16)
        m=re.search(r'CALLA  0x([0-9a-f]+)',l)
        if m:
            tgt=rel.get(a+16)
            if tgt=='.text':
                tgt=addr2.get(int(m.group(1),16),hex(int(m.group(1),16)))
            if tgt in targets: res[tgt].append((fn,pushes[:]))
            pushes=[];const={}; continue
        m=re.search(r'(MOVK|MOVI)   (-?\d+|0x[0-9a-f]+)\S*,(\w+)$',l)
        if m: const[m.group(3)]=int(m.group(2),0); continue
        m=re.search(r'MOVE   (\w+),\*A14\+,1',l)
        if m: pushes.append(const.get(m.group(1),'v')); continue
        m=re.search(r'SUB    (\w+),(\w+)$',l)
        if m and m.group(1)==m.group(2): const[m.group(1)]=0
for t,l in res.items():
    print('####',t,len(l))
    for fn,ps in l: print('   ',fn,['%#x'%x if isinstance(x,int) else x for x in ps])
