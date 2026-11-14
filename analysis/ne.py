import sys,struct
def parse(p):
    d=open(p,'rb').read()
    ne=struct.unpack('<I',d[0x3c:0x40])[0]
    h=d[ne:ne+64]
    (entoff,entlen)=struct.unpack('<HH',h[4:8])
    segcnt,modcnt,nrnamsz=struct.unpack('<HHH',h[0x1c:0x22])
    segtab,rsrctab,resnam,modtab,imptab=struct.unpack('<HHHHH',h[0x22:0x2c])
    nrestab=struct.unpack('<I',h[0x2c:0x30])[0]
    align=struct.unpack('<H',h[0x32:0x34])[0]
    segs=[]
    for i in range(segcnt):
        o,l,f,m=struct.unpack('<HHHH',d[ne+segtab+8*i:ne+segtab+8*i+8])
        segs.append((o<<align,l or 0x10000,f,m))
    def names(off):
        out=[];i=off
        while d[i]:
            n=d[i];s=d[i+1:i+1+n].decode('latin1');o=struct.unpack('<H',d[i+1+n:i+3+n])[0];out.append((o,s));i+=3+n
        return out
    res=names(ne+resnam); nres=names(nrestab)
    mods=[]
    for i in range(modcnt):
        o=struct.unpack('<H',d[ne+modtab+2*i:ne+modtab+2*i+2])[0]
        n=d[ne+imptab+o]; mods.append(d[ne+imptab+o+1:ne+imptab+o+1+n].decode())
    # entry table
    ents={};i=ne+entoff;ordn=1
    while True:
        cnt=d[i];
        if cnt==0: break
        ind=d[i+1];i+=2
        for k in range(cnt):
            if ind==0: pass
            elif ind==0xff:
                fl,_,seg,off=struct.unpack('<BHBH',d[i:i+6]);ents[ordn]=(seg,off);i+=6
            else:
                fl,off=struct.unpack('<BH',d[i:i+3]);ents[ordn]=(ind,off);i+=3
            ordn+=1
    return d,segs,res,nres,mods,ents,imptab+ne
if __name__=='__main__':
    d,segs,res,nres,mods,ents,_=parse(sys.argv[1])
    print('segments:',[(hex(o),hex(l),hex(f)) for o,l,f,m in segs])
    print('imports modules:',mods)
    allnames=res+nres
    for o,s in sorted(allnames[1:]+[] ,key=lambda x:x[0]):
        print(o,s,ents.get(o))
