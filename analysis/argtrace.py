# trace constant/global arguments pushed before calls to given functions (TI 340 C: last push = first arg)
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t34 import Mod
m = Mod(sys.argv[1]); targets = set(sys.argv[2].split(','))
for v, n in m.funcs:
    s, e = m.func(n)
    regs = {}; pushes = []
    for a, sz, t, i in m.listing(s, e):
        if 'push' in i:
            src = i['push']
            pushes.append(regs.get(src, src) if not src.startswith('@') else src)
            continue
        if 'call' in i:
            if i['call'] in targets:
                args = list(reversed(pushes))
                print(f"{n:38s} {i['call']}({', '.join(str(x) for x in args)})")
            pushes = []; regs = {}
            continue
        if 'wr' in i:
            r = i['wr']
            if 'k' in i: regs[r] = (i.get('ks') or i['k']) if 'ks' in i and i['ks'] else i['k']
            elif 'ld' in i: regs[r] = i['ld']
            elif 'mv' in i: regs[r] = regs.get(i['mv'], i['mv'])
            elif 'addi' in i and isinstance(regs.get(r), int): regs[r] += i['addi']
            elif 'ldd' in i: regs[r] = f'*{i["ldd"][0]}({i["ldd"][1]})'
            else: regs[r] = '<expr>'
        if 'br' in i: pass
