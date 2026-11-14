# partial ADSP-2100 family disassembler for DPRAM.IMG (24-bit words stored as 3 bytes + 0xFF pad)
import re,sys,collections
G=[['AX0','AX1','MX0','MX1','AY0','AY1','MY0','MY1','SI','SE','AR','MR0','MR1','MR2','SR0','SR1'],
   ['I0','I1','I2','I3','M0','M1','M2','M3','L0','L1','L2','L3','?','?','?','?'],
   ['I4','I5','I6','I7','M4','M5','M6','M7','L4','L5','L6','L7','?','?','?','?'],
   ['ASTAT','MSTAT','SSTAT','IMASK','ICNTL','CNTR','SB','PX','RX0','TX0','RX1','TX1','IFC','OWRCNTR','?','?']]
COND=['EQ','NE','GT','LE','LT','GE','AV','NOT AV','AC','NOT AC','NEG','POS','MV','NOT MV','NOT CE','']
def load(path):
    d=open(path).read()
    m={int(a,16):int(v,16) for a,v in re.findall(r'([0-9a-fA-F]+)/([0-9a-fA-F]+);',d)}
    pm={}
    for a in m:
        if a%4==0 and a+2 in m: pm[a//4]=(m[a]<<16)|(m[a+1]<<8)|m[a+2]
    return pm
def dis(op):
    t=op>>16
    if t in range(0x80,0xa0):
        grp=(op>>18)&3; addr=(op>>4)&0x3fff; r=G[grp][op&15]
        return (f'DM(0x{addr:04X}) = {r}' if op&0x100000 else f'{r} = DM(0x{addr:04X})'),('dm',addr,bool(op&0x100000))
    if t>>4==4: return f'{G[0][op&15]} = 0x{(op>>4)&0xffff:04X}',None
    if t>>4==3: rg=(op>>18)&3; return f'{G[rg][op&15]} = 0x{(op>>4)&0x3fff:04X}',('ld',G[rg][op&15],(op>>4)&0x3fff)
    if t in(0x18,0x19,0x1a,0x1b): return f'{("IF "+COND[op&15]+" ") if (op&15)!=15 else ""}JUMP 0x{(op>>4)&0x3fff:04X}',('j',(op>>4)&0x3fff)
    if t in(0x1c,0x1d,0x1e,0x1f): return f'{("IF "+COND[op&15]+" ") if (op&15)!=15 else ""}CALL 0x{(op>>4)&0x3fff:04X}',('c',(op>>4)&0x3fff)
    if t in(0x14,0x15,0x16,0x17): return f'DO 0x{(op>>4)&0x3fff:04X} UNTIL {COND[op&15] or "FOREVER"}',None
    if t==0x0a: return ('RTS' if (op&0x10)==0 else 'RTI')+('' if (op&15)==15 else ' IF '+COND[op&15]),None
    if t==0x0d:
        dg=(op>>10)&3; sg=(op>>8)&3; return f'{G[dg][(op>>4)&15]} = {G[sg][op&15]}',('mv',G[dg][(op>>4)&15],G[sg][op&15])
    if t>>5==5:  # 101x: DM(I,M)=imm16
        return f'DM(I{(op>>2)&3 + (4 if op&0x100000 else 0)},M{op&3 + (4 if op&0x100000 else 0)}) = 0x{(op>>4)&0xffff:04X}',None
    if op==0x028000: return 'IDLE',None
    ALU={0x10:'Y',0x11:'Y+1',0x12:'X+Y+C',0x13:'X+Y',0x14:'NOT Y',0x15:'-Y',0x16:'X-Y+C-1',0x17:'X-Y',0x18:'Y-1',0x19:'Y-X',0x1a:'Y-X+C-1',0x1b:'NOT X',0x1c:'X AND Y',0x1d:'X OR Y',0x1e:'X XOR Y',0x1f:'ABS X'}
    MAC={0:'NOP',1:'X*Y(RND)',2:'MR+X*Y(RND)',3:'MR-X*Y(RND)',4:'X*Y(SS)',5:'X*Y(SU)',6:'X*Y(US)',7:'X*Y(UU)',8:'MR+X*Y(SS)',9:'MR+X*Y(SU)',10:'MR+X*Y(US)',11:'MR+X*Y(UU)',12:'MR-X*Y(SS)',13:'MR-X*Y(SU)',14:'MR-X*Y(US)',15:'MR-X*Y(UU)'}
    def alu(z,amf,yop,xop):
        if amf==0: return None
        if amf>=0x10:
            x=['AX0','AX1','AR','MR0','MR1','MR2','SR0','SR1'][xop]; y=['AY0','AY1','AF','0'][yop]
            return ('AF' if z else 'AR')+' = '+ALU[amf].replace('X',x).replace('Y',y)
        x=['MX0','MX1','AR','MR0','MR1','MR2','SR0','SR1'][xop]; y=['MY0','MY1','MF','0'][yop]
        return ('MF' if z else 'MR')+' = '+MAC[amf].replace('X',x).replace('Y',y)
    if (op>>21)==3:  # type 4
        g=(op>>20)&1; d=(op>>19)&1; z=(op>>18)&1; amf=(op>>13)&31; yop=(op>>11)&3; xop=(op>>8)&7
        r=G[0][(op>>4)&15]; I=((op>>2)&3)+4*g; M=(op&3)+4*g
        mem=f'DM(I{I},M{M})'; a=alu(z,amf,yop,xop)
        m=(f'{mem} = {r}' if d else f'{r} = {mem}')
        return (a+', ' if a else '')+m,('dmi',I,d,r)
    if (op>>20)==5:  # type 5 PM
        d=(op>>19)&1; z=(op>>18)&1; amf=(op>>13)&31; yop=(op>>11)&3; xop=(op>>8)&7
        r=G[0][(op>>4)&15]; I=((op>>2)&3)+4; M=(op&3)+4; a=alu(z,amf,yop,xop)
        m=(f'PM(I{I},M{M}) = {r}' if d else f'{r} = PM(I{I},M{M})')
        return (a+', ' if a else '')+m,None
    if (op>>19)==4:  # type 9 conditional ALU
        z=(op>>18)&1; amf=(op>>13)&31; yop=(op>>11)&3; xop=(op>>8)&7; c=op&15
        return (('IF '+COND[c]+' ') if c!=15 else '')+(alu(z,amf,yop,xop) or 'NOP'),None
    if (op>>19)==5:  # type 8 alu + reg transfer
        z=(op>>18)&1; amf=(op>>13)&31; yop=(op>>11)&3; xop=(op>>8)&7
        return (alu(z,amf,yop,xop) or 'NOP')+f', {G[0][(op>>4)&15]} = {G[0][op&15]}',None
    if (op>>22)==3:  # type 1 dual read
        pd=(op>>20)&3; dd=(op>>18)&3; amf=(op>>13)&31; yop=(op>>11)&3; xop=(op>>8)&7
        a=alu(0,amf,yop,xop)
        return (a+', ' if a else '')+f"{['AX0','AX1','MX0','MX1'][dd]} = DM(I{(op>>2)&3},M{op&3}), {['AY0','AY1','MY0','MY1'][pd]} = PM(I{4+((op>>6)&3)},M{4+((op>>4)&3)})",None
    if t==0x0f: return f'SHIFT-IMM sf={(op>>12)&15} x={(op>>8)&7} n={op&0xff if op&0xff<128 else (op&0xff)-256}',None
    if t==0x09: return f'MODIFY(I{((op>>2)&3)+4*((op>>4)&1)},M{(op&3)+4*((op>>4)&1)})',None
    if t==0x0c: return f'MODE 0x{op&0xffff:04X}',None
    if t==0x04: return f'STACK 0x{op&0xffff:04X}',None
    if t==0x0b: return f'{("IF "+COND[op&15]+" ") if (op&15)!=15 else ""}{"CALL" if op&0x10 else "JUMP"} (I{4+((op>>6)&3)})',None
    return f'.op 0x{op:06X}',None
if __name__=='__main__':
    pm=load(sys.argv[1])
    lo=int(sys.argv[2],16); hi=int(sys.argv[3],16)
    for a in range(lo,hi):
        if a in pm: print(f'{a:04X}: {pm[a]:06X}  {dis(pm[a])[0]}')
