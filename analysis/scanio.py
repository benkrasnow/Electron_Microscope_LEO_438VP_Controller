import sys,collections
sys.path.insert(0,sys.argv[0].rsplit('/',1)[0])
from ne import parse
from capstone import *
md=Cs(CS_ARCH_X86,CS_MODE_16)
for p in sys.argv[1:]:
    try: d,segs,res,nres,mods,ents,_=parse(p)
    except Exception as e: print(p,'parse fail',e); continue
    names={v:s for (o,s) in res+nres for k,v in [(o,ents.get(o))] if v}
    print('=====',p,mods)
    cnt=collections.Counter()
    for si,(o,l,f,m) in enumerate(segs,1):
        if f&1: continue  # data seg
        code=d[o:o+l]
        insns=list(md.disasm(code,0))
        for k,ins in enumerate(insns):
            if ins.mnemonic in('in','out','insb','insw','outsb','outsw','rep insw','rep outsw') or ins.mnemonic.startswith('int') and ins.op_str not in('3',):
                ctx=' | '.join(f'{x.mnemonic} {x.op_str}' for x in insns[max(0,k-3):k+1])
                cnt[(ins.mnemonic,ins.op_str)]+=1
                if len(sys.argv)<=3: print(f'  seg{si}:{ins.address:04x}  {ctx}')
    print(cnt.most_common(40))
