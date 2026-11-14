"""Capture every CH3 register burst during a cold boot, one 400 ms shot per burst, re-arming automatically.

Trigger as arm_burst.py (CH3 positive pulse 10-100 us = gap inside a multi-register burst), 25 MS/s, 10 Mpts
(the MSO24 maximum), trigger at 10 %. Waveforms are read as 1-byte data (~1.5 s per channel), so the dead time
between shots is ~8 s. Each shot: <prefix>_NN.npz (+ .png), decoded to <prefix>_NN_ch3.txt; wall-clock trigger
times go to <prefix>_log.txt.
usage: python cold_boot_loop.py <prefix> [max_shots=40] [max_minutes=60] [high_limit_us=100]
high_limit_us = 2750 (at scan speed 5: just under the 2.81 ms line period) also fires on a single extra frame
between two per-line Y writes, so lone register writes are caught too.
Stop early by creating the file STOP in this folder.
"""
import os, sys, time, subprocess
import numpy as np
import pyvisa

prefix = sys.argv[1]
max_shots = int(sys.argv[2]) if len(sys.argv) > 2 else 40
max_min = float(sys.argv[3]) if len(sys.argv) > 3 else 60
high_us = float(sys.argv[4]) if len(sys.argv) > 4 else 100
out_dir = '../scope_captures'
log = open(f'{out_dir}/{prefix}_log.txt', 'a')

def say(msg):
    line = f'{time.strftime("%H:%M:%S")} {msg}'
    print(line, flush=True); log.write(line + '\n'); log.flush()

s = pyvisa.ResourceManager('@py').open_resource('TCPIP0::192.168.0.42::inst0::INSTR')
s.clear(); s.timeout = 60000; s.read_termination = '\n'; s.write_termination = '\n'
for c in ['ACQuire:STATE STOP', 'HORizontal:MODe MANual', 'HORizontal:MODe:SAMPLERate 25e6', 'HORizontal:MODe:RECOrdlength 10000000',
          'HORizontal:POSition 10', 'TRIGger:A:TYPe WIDth', 'TRIGger:A:PULSEWidth:SOUrce CH3',
          'TRIGger:A:PULSEWidth:POLarity POSitive', 'TRIGger:A:PULSEWidth:WHEn WIThin',
          'TRIGger:A:PULSEWidth:LOWLimit 10e-6', f'TRIGger:A:PULSEWidth:HIGHLimit {high_us}e-6',
          'TRIGger:A:LEVel:CH3 1.8', 'TRIGger:A:MODe NORMal', 'ACQuire:MODe SAMple', 'ACQuire:STOPAfter SEQuence']:
    s.write(c)
s.query('*OPC?')

t_start = time.time()
for shot in range(1, max_shots + 1):
    s.write('ACQuire:STATE RUN'); time.sleep(0.5)   # no *OPC? here: it would block until the trigger
    say(f'ARMED shot {shot:02d}')
    while s.query('ACQuire:STATE?').strip() != '0':
        if os.path.exists('STOP') or time.time() - t_start > max_min * 60:
            s.write('ACQuire:STATE STOP'); say('stopped'); sys.exit(0)
        time.sleep(0.2)
    say(f'TRIGGERED shot {shot:02d}')
    name = f'{out_dir}/{prefix}_{shot:02d}'
    data = {}
    rl = int(s.query('HORizontal:RECOrdlength?'))
    for ch in (1, 2, 3, 4):
        s.write(f'DATa:SOUrce CH{ch}'); s.write('DATa:ENCdg RIBinary'); s.write('WFMOutpre:BYT_Nr 1')
        s.write('DATa:STARt 1'); s.write(f'DATa:STOP {rl}')
        ymult = float(s.query('WFMOutpre:YMUlt?')); yoff = float(s.query('WFMOutpre:YOFf?'))
        yzero = float(s.query('WFMOutpre:YZEro?'))
        xinc = float(s.query('WFMOutpre:XINcr?')); xzero = float(s.query('WFMOutpre:XZEro?'))
        raw = s.query_binary_values('CURVe?', datatype='b', container=np.array)
        data[f'ch{ch}'] = ((raw - yoff) * ymult + yzero).astype(np.float32)
        data['t'] = xzero + np.arange(len(raw)) * xinc
    data['wallclock'] = np.array(time.strftime('%Y-%m-%d %H:%M:%S'))
    np.savez_compressed(name + '.npz', **data)
    with open(name + '_ch3.txt', 'w') as fo:
        subprocess.run([sys.executable, 'decode_scan_fiber.py', name + '.npz', 'ch3'], stdout=fo)
    n = sum(1 for _ in open(name + '_ch3.txt'))
    say(f'saved shot {shot:02d}: {n} frames decoded')
say('max shots reached')
