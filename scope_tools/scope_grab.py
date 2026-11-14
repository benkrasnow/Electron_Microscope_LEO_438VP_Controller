"""Grab a screenshot and the displayed waveforms from the MSO24 without changing acquisition settings.

usage: python scope_grab.py <out_prefix> [channels...]
Writes <out_prefix>.png and <out_prefix>.npz (t, ch1..ch4 in volts, plus the setup strings).
"""
import sys, time
import numpy as np
import pyvisa

ADDR = 'TCPIP0::192.168.0.42::inst0::INSTR'
out = sys.argv[1]
chans = [int(c) for c in sys.argv[2:]] or [1, 2, 3, 4]

rm = pyvisa.ResourceManager('@py')
s = rm.open_resource(ADDR)
s.timeout = 30000
s.read_termination = '\n'
s.write_termination = '\n'

# screenshot: save on the scope, read it back, delete it
s.write('SAVe:IMAGe:COMPosition NORMal')
s.write('SAVe:IMAGe "C:/claude_tmp.png"')
s.query('*OPC?')
s.write('FILESystem:READFile "C:/claude_tmp.png"')
img = s.read_raw()
s.write('FILESystem:DELEte "C:/claude_tmp.png"')
open(out + '.png', 'wb').write(img)

# stop so all channels come from the same acquisition, read, then restore the run state
was_running = s.query('ACQuire:STATE?').strip() == '1'
s.write('ACQuire:STATE STOP'); s.query('*OPC?')
data = {}
rl = int(s.query('HORizontal:RECOrdlength?'))
for ch in chans:
    s.write(f'DATa:SOUrce CH{ch}')
    s.write('DATa:ENCdg RIBinary'); s.write('WFMOutpre:BYT_Nr 2')
    s.write('DATa:STARt 1'); s.write(f'DATa:STOP {rl}')
    ymult = float(s.query('WFMOutpre:YMUlt?')); yoff = float(s.query('WFMOutpre:YOFf?')); yzero = float(s.query('WFMOutpre:YZEro?'))
    xinc = float(s.query('WFMOutpre:XINcr?')); xzero = float(s.query('WFMOutpre:XZEro?'))
    raw = s.query_binary_values('CURVe?', datatype='h', is_big_endian=True, container=np.array)
    data[f'ch{ch}'] = (raw - yoff) * ymult + yzero
    data['t'] = xzero + np.arange(len(raw)) * xinc
if was_running:
    s.write('ACQuire:STATE RUN')
data['setup'] = np.array([s.query('HORizontal:SCAle?'), s.query('HORizontal:SAMPLERate?'), str(rl)])
np.savez_compressed(out + '.npz', **data)
print('saved', out, 'points', rl, 'dt', data['t'][1] - data['t'][0])
s.close()
