"""Read-only connection check for the Tektronix MSO24: identity and current setup."""
import sys
import pyvisa

ADDR = sys.argv[1] if len(sys.argv) > 1 else 'TCPIP0::192.168.0.42::inst0::INSTR'

rm = pyvisa.ResourceManager('@py')
s = rm.open_resource(ADDR)
s.timeout = 10000
s.read_termination = '\n'
s.write_termination = '\n'
print('IDN:', s.query('*IDN?'))
for q in ['HORizontal:SCAle?', 'HORizontal:RECOrdlength?', 'HORizontal:SAMPLERate?', 'ACQuire:STATE?',
          'ACQuire:STOPAfter?', 'TRIGger:A:TYPe?', 'TRIGger:A:EDGE:SOUrce?', 'TRIGger:A:LEVel:CH1?',
          'TRIGger:A:MODe?', 'OPTion:INSTalled?', 'LICense:LIST?']:
    try:
        print(f'{q:28s}', s.query(q))
    except Exception as e:
        print(f'{q:28s} ERR {e}')
for ch in range(1, 5):
    try:
        print(f'CH{ch}', s.query(f'DISplay:GLObal:CH{ch}:STATE?'), s.query(f'CH{ch}:SCAle?'),
              s.query(f'CH{ch}:OFFSet?'), s.query(f'CH{ch}:POSition?'), s.query(f'CH{ch}:COUPling?'),
              s.query(f'CH{ch}:TERmination?'), s.query(f'CH{ch}:BANdwidth?'))
    except Exception as e:
        print(f'CH{ch} ERR {e}')
s.close()
