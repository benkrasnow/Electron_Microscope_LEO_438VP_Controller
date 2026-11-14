# minimal TMS34010/20 disassembler for common move/immediate ops (best effort)
import sys,struct,os,bisect
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from coff import parse
def R(r,ab): return ('B' if ab else 'A')+str(r) if r!=15 else 'SP'
def dis(raw,base,n):
    i=0;out=[]
    while i<n:
        w=struct.unpack('<H',raw[i:i+2])[0]
        rs=(w>>5)&15; ab=(w>>4)&1; rd=w&15
        RS=R(rs,ab); RD=R(rd,ab)
        ext=b'';txt=None
        hi7=w>>9
        if (w&0xffe0)==0x09e0: v=struct.unpack('<I',raw[i+2:i+6])[0]; txt=f'MOVI   0x{v:08x},{RD}'; ext=4
        elif (w&0xffe0)==0x09c0: v=struct.unpack('<h',raw[i+2:i+4])[0]; txt=f'MOVI   {v} (0x{v&0xffff:04x}),{RD}'; ext=2
        elif (w&0xfc00)==0x1800: txt=f'MOVK   {(w>>5)&31 or 32},{RD}'
        elif (w&0xfc00)==0x1000: txt=f'ADDK   {(w>>5)&31 or 32},{RD}'
        elif (w&0xfc00)==0x1400: txt=f'SUBK   {(w>>5)&31 or 32},{RD}'
        elif (w&0xfe00)==0x4c00: txt=f'MOVE   {RS},{RD}'
        elif (w&0xfe00)==0x4000: txt=f'ADD    {RS},{RD}'
        elif (w&0xfe00)==0x4400: txt=f'SUB    {RS},{RD}'
        elif (w&0xfe00)==0x4800: txt=f'CMP    {RS},{RD}'
        elif (w&0xfe00)==0x5000: txt=f'AND    {RS},{RD}'
        elif (w&0xfe00)==0x5400: txt=f'OR     {RS},{RD}'   # ?
        elif (w&0xfe00)==0x5600: txt=f'CLR/XOR {RS},{RD}'
        elif (w&0xfe00)==0x8c00: txt=f'MOVB   {RS},*{RD}'
        elif (w&0xfe00)==0x8e00: txt=f'MOVB   *{RS},{RD}'
        elif (w&0xfe00)==0xae00 or (w&0xfe00)==0xac00:
            dsp=struct.unpack('<h',raw[i+2:i+4])[0]; ext=2
            txt=(f'MOVB   {RS},*{RD}({dsp})' if (w&0xfe00)==0xac00 else f'MOVB   *{RS}({dsp}),{RD}')
        elif (w&0xfc00)==0x8000: txt=f'MOVE   {RS},*{RD},{(w>>9)&1}'
        elif (w&0xfc00)==0x8400: txt=f'MOVE   *{RS},{RD},{(w>>9)&1}'
        elif (w&0xfc00)==0x9000: txt=f'MOVE   {RS},*{RD}+,{(w>>9)&1}'
        elif (w&0xfc00)==0x9400: txt=f'MOVE   *{RS}+,{RD},{(w>>9)&1}'
        elif (w&0xfc00) in (0xb000,0xb400):
            dsp=struct.unpack('<h',raw[i+2:i+4])[0]; ext=2
            txt=(f'MOVE   {RS},*{RD}({dsp}),{(w>>9)&1}' if (w&0xfc00)==0xb000 else f'MOVE   *{RS}({dsp}),{RD},{(w>>9)&1}')
        elif (w&0xfe00)==0x8c00: txt=f'MOVB   {RS},*{RD}'
        elif (w&0xfc00)==0xa000: txt=f'MOVE   {RS},-*{RD},{(w>>9)&1}'
        elif (w&0xfc00)==0xa400: txt=f'MOVE   -*{RS},{RD},{(w>>9)&1}'
        elif (w&0xffe0)==0x0980: v=struct.unpack('<H',raw[i+2:i+4])[0]; ext=2; txt=f'MMTM   {RD},0x{v:04x}'
        elif (w&0xffe0)==0x09a0: v=struct.unpack('<H',raw[i+2:i+4])[0]; ext=2; txt=f'MMFM   {RD},0x{v:04x}'
        elif w==0x0d5f: v=struct.unpack('<I',raw[i+2:i+6])[0]; ext=4; txt=f'CALLA  0x{v:08x}'
        elif w==0x0d3f: v=struct.unpack('<h',raw[i+2:i+4])[0]; ext=2; txt=f'CALLR  {v}'
        elif (w&0xffe0)==0x0b40: v=(~struct.unpack('<h',raw[i+2:i+4])[0])&0xffff; ext=2; txt=f'CMPI   0x{v:04x},{RD}'
        elif (w&0xffe0)==0x0b00: v=struct.unpack('<h',raw[i+2:i+4])[0]; ext=2; txt=f'ADDI   {v},{RD}'
        elif (w&0xffe0)==0x0b20: v=struct.unpack('<i',raw[i+2:i+6])[0]; ext=4; txt=f'ADDI   {v},{RD}'
        elif (w&0xffe0)==0x0b80: v=(~struct.unpack('<I',raw[i+2:i+6])[0])&0xffffffff; ext=4; txt=f'ANDI   0x{v:08x},{RD}'
        elif (w&0xffe0)==0x0ba0: v=struct.unpack('<I',raw[i+2:i+6])[0]; ext=4; txt=f'ORI    0x{v:08x},{RD}'
        elif (w&0xfc00)==0x2000: txt=f'SLA    {(w>>5)&31},{RD}'
        elif (w&0xfc00)==0x2400: txt=f'SLL    {(w>>5)&31},{RD}'
        elif (w&0xfc00)==0x2800: txt=f'SRA    {32-((w>>5)&31)},{RD}'
        elif (w&0xfc00)==0x2c00: txt=f'SRL    {32-((w>>5)&31)},{RD}'
        elif (w&0xf000)==0xc000:
            cc=(w>>8)&15; d8=w&0xff
            if d8==0: v=struct.unpack('<h',raw[i+2:i+4])[0]; ext=2; txt=f'JRcc{cc:x} {base+(i+4)*8+v*16:08x}'
            elif d8==0x80: v=struct.unpack('<I',raw[i+2:i+6])[0]; ext=4; txt=f'JAcc{cc:x} 0x{v:08x}'
            else: dd=d8-256 if d8>127 else d8; txt=f'JRcc{cc:x} {base+(i+2)*8+dd*16:08x}'
        elif (w&0xfde0)==0x0580: v=struct.unpack('<I',raw[i+2:i+6])[0];ext=4; txt=f'MOVE   {RD},@0x{v:08x},{(w>>9)&1}'
        elif (w&0xfde0)==0x05a0: v=struct.unpack('<I',raw[i+2:i+6])[0];ext=4; txt=f'MOVE   @0x{v:08x},{RD},{(w>>9)&1}'
        elif (w&0xffe0)==0x0d5f: pass
        elif w==0x0960 or (w&0xffe0)==0x0960: txt=f'RETS'
        elif (w&0xffe0)==0x0d20: v=struct.unpack('<I',raw[i+2:i+6])[0];ext=4; txt=f'CALLA  0x{v:08x}'
        elif (w&0xff00)==0x0d00 and (w&0xffe0)==0x0d3f: txt='CALLR'
        elif (w&0xff00)==0x5e00 or (w&0xff00)==0x5f00: pass
        elif (w&0xffe0)==0x0b20: v=struct.unpack('<H',raw[i+2:i+4])[0];ext=2; txt=f'ANDI   ~0x{v:04x}? ,{RD}'
        elif (w&0xffe0)==0x0ba0: v=struct.unpack('<H',raw[i+2:i+4])[0];ext=2; txt=f'ORI    0x{v:04x},{RD}'
        elif (w&0xffe0)==0x0b40: v=struct.unpack('<I',raw[i+2:i+6])[0];ext=4; txt=f'ORI    0x{v:08x},{RD}'
        elif (w&0xffe0)==0x0b00 or (w&0xffe0)==0x0b80: v=struct.unpack('<I',raw[i+2:i+6])[0] if (w&0x80)==0 else 0;ext=4; txt=f'ANDI?  0x{v:08x},{RD}'
        if txt is None: txt=f'.word  0x{w:04x}'; ext=0
        e=ext if isinstance(ext,int) else 0
        out.append(f'{base+i*8:08x}: {raw[i:i+2+e].hex():16s} {txt}')
        i+=2+e
    return out
if __name__=='__main__':
    p=sys.argv[1]; d,h,secs,syms=parse(p)
    tx=[s for s in secs if s['name']=='.text'][0]
    raw=d[tx['ptr']:tx['ptr']+tx['size']//8]
    funcs=sorted((v,n) for n,v,scn,t,c in syms if scn==1 and c in(2,3) and not n.startswith('$') and not n.startswith('.'))
    names=dict((n,v) for v,n in funcs); fa=[v for v,n in funcs]
    for f in sys.argv[2:]:
        v=names[f]; k=fa.index(v); end=funcs[k+1][0] if k+1<len(funcs) else tx['size']
        print('=====',f,hex(v),'len',(end-v)//8)
        for l in dis(raw[v//8:end//8+8],v,min((end-v)//8,int(os.environ.get('MAXB','600')))): print(l)
