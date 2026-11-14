import sys,struct,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from coff import parse
def table(p):
    d,h,secs,syms=parse(p)
    # full symbol index list including aux
    d0=d; magic,nsec,ts,symptr,nsym,opth,fl=struct.unpack('<HHIIIHH',d[:20])
    strtab=symptr+18*nsym; idx={}
    for i in range(nsym):
        e=d[symptr+18*i:symptr+18*i+18]
        if e[:4]==b'\0\0\0\0':
            so=struct.unpack('<I',e[4:8])[0]; j=d.index(b'\0',strtab+so); name=d[strtab+so:j].decode('latin1')
        else: name=e[:8].rstrip(b'\0').decode('latin1')
        idx[i]=(name,struct.unpack('<I',e[8:12])[0],struct.unpack('<h',e[12:14])[0])
    addr2={}
    for n,v,scn,t,c in syms:
        if scn==1 and c in(2,3) and not n.startswith('$') and not n.startswith('.'): addr2.setdefault(v,n)
    sec=[s for s in secs if s['name']=='.TIGAEXT'][0]
    raw=d[sec['ptr']:sec['ptr']+sec['size']//8]
    rel={}
    for k in range(sec['nreloc']):
        va,si,ty=struct.unpack('<IIH',d[sec['relptr']+10*k:sec['relptr']+10*k+10])
        rel[va-sec['vaddr']]=idx.get(si,('?',0,0))
    out=[]
    for i in range(0,len(raw),4):
        v=struct.unpack('<I',raw[i:i+4])[0]
        r=rel.get(i*8)
        name=None
        if r:
            if r[0].startswith('.text'): name=addr2.get(v,f'.text+{v:x}')
            else: name=r[0]
        out.append(name or f'0x{v:08x}')
    return out
if __name__=='__main__':
    for p in sys.argv[1:]:
        t=table(p); print('####',os.path.basename(p),len(t))
        print('  '+'  '.join(f'[{i}]{n}' for i,n in enumerate(t)))
