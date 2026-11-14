"""Arm the MSO24 to capture the next CH3 register-write burst (frames ~23 us apart).

Trigger: CH3 positive pulse width within 10-100 us (the idle gap between burst frames; per-line frames are 2.8 ms
apart and never match). 25 MS/s, 10 Mpts (400 ms), trigger at 25 %.
usage: python arm_burst.py [wait_seconds]   -> prints 'TRIGGERED' or 'WAITING'
"""
import sys, time
import pyvisa

s = pyvisa.ResourceManager('@py').open_resource('TCPIP0::192.168.0.42::inst0::INSTR')
s.timeout = 30000; s.read_termination = '\n'; s.write_termination = '\n'
for c in ['HORizontal:MODe MANual', 'HORizontal:MODe:SAMPLERate 25e6', 'HORizontal:MODe:RECOrdlength 10000000',
          'HORizontal:POSition 25', 'TRIGger:A:TYPe WIDth', 'TRIGger:A:PULSEWidth:SOUrce CH3',
          'TRIGger:A:PULSEWidth:POLarity POSitive', 'TRIGger:A:PULSEWidth:WHEn WIThin',
          'TRIGger:A:PULSEWidth:LOWLimit 10e-6', 'TRIGger:A:PULSEWidth:HIGHLimit 100e-6',
          'TRIGger:A:LEVel:CH3 1.8', 'TRIGger:A:MODe NORMal', 'ACQuire:MODe SAMple',
          'ACQuire:STOPAfter SEQuence', 'ACQuire:STATE RUN']:
    s.write(c)
print('trigger', s.query('TRIGger:A:TYPe?'), s.query('TRIGger:A:PULSEWidth:WHEn?'),
      s.query('TRIGger:A:PULSEWidth:LOWLimit?'), s.query('TRIGger:A:PULSEWidth:HIGHLimit?'))
wait = float(sys.argv[1]) if len(sys.argv) > 1 else 3
t0 = time.time()
while time.time() - t0 < wait:
    if s.query('ACQuire:STATE?').strip() == '0':
        print('TRIGGERED'); break
    time.sleep(0.3)
else:
    print('WAITING')
