import sys,struct
sys.path.insert(0,sys.argv[0].rsplit('/',1)[0])
from ne import parse
from capstone import *
md=Cs(CS_ARCH_X86,CS_MODE_16)
p=sys.argv[1]
d,segs,res,nres,mods,ents,impbase=parse(p)
byname={s:ents.get(o) for o,s in res+nres}
# relocations: build map seg-> {offset: target string}
def relocs(si):
    o,l,f,m=segs[si-1]
    if not f&0x100: return {}
    r=o+l; n=struct.unpack('<H',d[r:r+2])[0]; out={}
    for i in range(n):
        st,fl,off,a,b=struct.unpack('<BBHHH',d[r+2+8*i:r+10+8*i])
        t=fl&3
        if t==0: tgt=f'seg{a}:{b:04x}'
        elif t==1: tgt=f'{mods[a-1]}.#{b}'
        elif t==2:
            nl=d[impbase+b]; tgt=f'{mods[a-1]}.{d[impbase+b+1:impbase+b+1+nl].decode()}'
        else: tgt='osfix'
        # follow chain if not additive
        cur=off
        seen=0
        while cur!=0xffff and seen<1000:
            out[cur]=tgt
            if fl&4: break
            nxt=struct.unpack('<H',d[o+cur:o+cur+2])[0]
            cur=nxt; seen+=1
    return out
for name in sys.argv[2:]:
    if ':' in name: si,off=name.split(':'); si=int(si); off=int(off,16)
    else: si,off=byname[name]
    o,l,f,m=segs[si-1]; R=relocs(si)
    print(f'===== {name} seg{si}:{off:04x}')
    n=0
    for ins in md.disasm(d[o+off:o+l],off):
        ann=''
        for k in range(ins.address,ins.address+ins.size):
            if k in R: ann='   ; -> '+R[k]
        print(f'{ins.address:04x}: {ins.mnemonic} {ins.op_str}{ann}')
        n+=1
        if ins.mnemonic in('retf','ret','iret') and n>3 or n>int(__import__('os').environ.get('MAXN','120')): break
