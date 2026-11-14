import sys,re
n=int(sys.argv[2]) if len(sys.argv)>2 else 5
d=open(sys.argv[1],'rb').read()
for m in re.finditer(rb'[\x20-\x7e\t]{%d,}'%n,d): print(hex(m.start()), m.group().decode())
for m in re.finditer(rb'(?:[\x20-\x7e]\x00){%d,}'%n,d): print(hex(m.start()),'U:', m.group().decode('utf-16le'))
