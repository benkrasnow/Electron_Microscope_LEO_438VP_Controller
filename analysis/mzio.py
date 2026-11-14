import sys,struct
from capstone import *
md=Cs(CS_ARCH_X86,CS_MODE_16)
for p in sys.argv[1:]:
    d=open(p,'rb').read()
    hdr=struct.unpack('<H',d[8:10])[0]*16
    code=d[hdr:]
    insns=list(md.disasm(code,0))
    # linear sweep may desync; also do a sliding search for 'ee/ef/ec/ed' with prior mov dx
    print('=====',p,len(insns))
    for k,ins in enumerate(insns):
        if ins.mnemonic in('in','out'):
            print(f'{ins.address:05x}: '+' | '.join(f'{x.mnemonic} {x.op_str}' for x in insns[max(0,k-5):k+1]))
