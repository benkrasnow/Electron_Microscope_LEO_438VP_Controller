"""Save/restore the MSO24 setup, or configure a fast single-shot capture.

  python scope_setup.py save            store current setup on the scope (C:/claude_orig.set) and locally
  python scope_setup.py restore         recall it
  python scope_setup.py fast <sample_rate> <record_len> <trig_ch> <level_V> [RISe|FALL] [pos_percent]
"""
import sys
import pyvisa

s = pyvisa.ResourceManager('@py').open_resource('TCPIP0::192.168.0.42::inst0::INSTR')
s.timeout = 30000; s.read_termination = '\n'; s.write_termination = '\n'
cmd = sys.argv[1]
if cmd == 'save':
    s.write('SAVe:SETUp "C:/claude_orig.set"'); s.query('*OPC?')
    open('orig_setup.txt', 'w').write(s.query('SET?'))
    print('saved')
elif cmd == 'restore':
    s.write('RECAll:SETUp "C:/claude_orig.set"'); s.query('*OPC?'); print('restored')
elif cmd == 'fast':
    sr, rl, tch, lvl = float(sys.argv[2]), int(float(sys.argv[3])), int(sys.argv[4]), float(sys.argv[5])
    slope = sys.argv[6] if len(sys.argv) > 6 else 'RISe'
    pos = float(sys.argv[7]) if len(sys.argv) > 7 else 10
    s.write('HORizontal:MODe MANual')
    s.write(f'HORizontal:MODe:MANual:CONFIGure HORIZontalscale') if False else None
    s.write(f'HORizontal:MODe:SAMPLERate {sr}')
    s.write(f'HORizontal:MODe:RECOrdlength {rl}')
    s.write(f'HORizontal:POSition {pos}')
    s.write('TRIGger:A:TYPe EDGE'); s.write(f'TRIGger:A:EDGE:SOUrce CH{tch}')
    s.write(f'TRIGger:A:EDGE:SLOpe {slope}'); s.write(f'TRIGger:A:LEVel:CH{tch} {lvl}')
    s.write('TRIGger:A:MODe NORMal')
    s.write('ACQuire:MODe SAMple'); s.write('ACQuire:STOPAfter SEQuence'); s.write('ACQuire:STATE RUN')
    s.query('*OPC?')
    print('SR', s.query('HORizontal:SAMPLERate?'), 'RL', s.query('HORizontal:RECOrdlength?'), 'scale', s.query('HORizontal:SCAle?'), 'state', s.query('ACQuire:STATE?'))
