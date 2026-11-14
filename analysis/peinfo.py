import sys,pefile,struct,os
for p in sys.argv[1:]:
    d=open(p,'rb').read()
    if d[:2]!=b'MZ': print(os.path.basename(p),'not MZ'); continue
    off=struct.unpack('<I',d[0x3c:0x40])[0]
    sig=d[off:off+2] if off<len(d) else b''
    if sig==b'PE':
        pe=pefile.PE(data=d)
        imps=[]
        for e in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]):
            imps.append(e.dll.decode())
        exps=[x.name.decode() if x.name else '#%d'%x.ordinal for x in getattr(pe,'DIRECTORY_ENTRY_EXPORT',type('',(),{'symbols':[]})).symbols]
        import time
        print(os.path.basename(p),'PE32',time.strftime('%Y-%m-%d',time.gmtime(pe.FILE_HEADER.TimeDateStamp)),'imports:',','.join(imps),'| nexports',len(exps))
    else:
        print(os.path.basename(p),'sig',sig)
