# TI COFF (TMS340) parser: sections + symbols
import sys,struct
def parse(p):
    d=open(p,'rb').read()
    magic,nsec,ts,symptr,nsym,opthdr,flags=struct.unpack('<HHIIIHH',d[:20])
    off=20+opthdr
    secs=[]
    for i in range(nsec):
        name=d[off:off+8].rstrip(b'\0').decode('latin1')
        paddr,vaddr,size,scnptr,relptr,lnnoptr,nreloc,nlnno,fl,res,page=struct.unpack('<IIIIIIHHHBB',d[off+8:off+40])
        secs.append(dict(name=name,paddr=paddr,vaddr=vaddr,size=size,ptr=scnptr,relptr=relptr,nreloc=nreloc,flags=fl))
        off+=40
    strtab=symptr+18*nsym
    syms=[];i=0
    while i<nsym:
        e=d[symptr+18*i:symptr+18*i+18]
        if e[:4]==b'\0\0\0\0':
            so=struct.unpack('<I',e[4:8])[0]; j=d.index(b'\0',strtab+so); name=d[strtab+so:j].decode('latin1')
        else: name=e[:8].rstrip(b'\0').decode('latin1')
        val,scn,typ,cls,naux=struct.unpack('<IhHBB',e[8:18])
        syms.append((name,val,scn,typ,cls)); i+=1+naux
    return d,dict(magic=magic,nsec=nsec,flags=flags,opthdr=opthdr),secs,syms
if __name__=='__main__':
    d,h,secs,syms=parse(sys.argv[1])
    print(sys.argv[1],h)
    for s in secs: print('  sec',s['name'],hex(s['vaddr']),hex(s['size']),'nreloc',s['nreloc'])
    mode=sys.argv[2] if len(sys.argv)>2 else 'ext'
    for n,v,scn,t,c in syms:
        if mode=='all' or c==2: print(f'    {c:3d} {scn:3d} {v:08x} {n}')
