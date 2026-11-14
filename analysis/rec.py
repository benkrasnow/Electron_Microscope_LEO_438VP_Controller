# recursive-descent 16-bit disassembly of NE code segs; report port I/O, ints, with function context
import sys,struct,os
sys.path.insert(0,os.path.dirname(os.path.abspath(sys.argv[0])))
from ne import parse
from capstone import *
from capstone.x86 import *
md=Cs(CS_ARCH_X86,CS_MODE_16); md.detail=True
p=sys.argv[1]
d,segs,res,nres,mods,ents,impbase=parse(p)
ename={}
for o,s in res+nres:
    if o in ents: ename[ents[o]]=s
seeds={}
for (si,off),s in ename.items(): seeds.setdefault(si,set()).add(off)
# extra seeds: far call targets by scanning reloc additive internal refs
def relocs(si):
    o,l,f,m=segs[si-1]; out=[]
    if not f&0x100: return out
    r=o+l; n=struct.unpack('<H',d[r:r+2])[0]
    for i in range(n):
        st,fl,off,a,b=struct.unpack('<BBHHH',d[r+2+8*i:r+10+8*i])
        if fl&3==0 and (a&0xff)!=0xff:
            # source type 3 far ptr / 2 seg: offset may be in instruction
            out.append((st,fl,off,a&0xff,b))
    return out
for si in range(1,len(segs)+1):
    for st,fl,off,a,b in relocs(si):
        o,l,f,m=segs[si-1]
        if st==2 and off>=2:  # segment selector; offset word precedes
            tgt=struct.unpack('<H',d[o+off-2:o+off])[0] if fl&4 else b
            seeds.setdefault(a,set()).add(tgt)
        elif st==3: seeds.setdefault(a,set()).add(b)
func_of={}
results=[]
for si,(o,l,f,m) in enumerate(segs,1):
    if f&1: continue
    code=d[o:o+l]; seen=set(); work=sorted(seeds.get(si,()))
    funcs=set(work)
    while work:
        start=work.pop()
        if start in seen or start>=l: continue
        pc=start; prev=[]
        while pc<l and pc not in seen:
            try: ins=next(md.disasm(code[pc:pc+16],pc))
            except StopIteration: break
            seen.add(pc)
            prev.append(ins); prev=prev[-6:]
            mn=ins.mnemonic
            if mn in('in','out') or (mn=='int' and ins.op_str not in('3',)):
                results.append((si,ins.address,' | '.join(f'{x.mnemonic} {x.op_str}' for x in prev)))
            if mn in('call','jmp') or mn.startswith('j') or mn=='loop':
                if ins.operands and ins.operands[0].type==X86_OP_IMM and mn!='lcall' and mn!='ljmp':
                    t=ins.operands[0].imm
                    if mn=='call': funcs.add(t)
                    work.append(t)
            if mn in('ret','retf','iret','jmp','ljmp','hlt'): break
            pc+=ins.size
    # map func
    fl_sorted=sorted(funcs)
    for r in results:
        if r[0]!=si: continue
    import bisect
    for i,r in enumerate(results):
        if r[0]==si and len(r)==3:
            k=bisect.bisect_right(fl_sorted,r[1])-1
            fs=fl_sorted[k] if k>=0 else 0
            results[i]=r+(ename.get((si,fs),f'sub_{si}_{fs:04x}'),)
for r in results: print(f'seg{r[0]}:{r[1]:04x} [{r[3]}]  {r[2]}')
