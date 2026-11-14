"""Record a LEO 438VP serial-link capture from the Teensy logger to a file.

Usage examples
  python capture_serial.py COM7 --tag eht_beam_on --label1 "IP->EHT" --label2 "EHT->IP"
  python capture_serial.py COM7 --tag stgvac_pump --label1 "IP->STGVAC" --label2 "STGVAC->IP" --note "pump from vented"
  python capture_serial.py COM7 --probe            (check line polarity, then exit)
  python capture_serial.py --list                  (show serial ports)

Every line from the logger is written to the file unchanged. The script adds
header lines (labels, note, host start time) and a "# HOSTTIME" line after each
logger heartbeat so device time can be matched to wall-clock time.
Stop with Ctrl+C.  Needs: pip install pyserial
"""
import argparse
import datetime as dt
import os
import sys
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    sys.exit('pyserial is not installed: run  pip install pyserial')


def printable(bs):
    out = []
    for b in bs:
        if b == 13: out.append('\\r')
        elif b == 10: out.append('\\n')
        elif 32 <= b < 127: out.append(chr(b))
        else: out.append(f'<{b:02X}>')
    return ''.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('port', nargs='?', help='Teensy USB serial port, e.g. COM7')
    ap.add_argument('--list', action='store_true', help='list serial ports and exit')
    ap.add_argument('--tag', default='capture', help='short name for this capture (used in the file name)')
    ap.add_argument('--out', help='output file (default: captures/<date>_<tag>.log)')
    for ch in (1, 2, 3, 4):
        ap.add_argument(f'--label{ch}', default=f'ch{ch}', help=f'name for channel {ch}, e.g. "IP->EHT"')
    ap.add_argument('--note', default='', help='free text describing what was done during the capture')
    ap.add_argument('--cmd', action='append', default=[], help='logger command to send first, e.g. "B 1 9600" (repeatable)')
    ap.add_argument('--duration', type=float, help='stop after this many seconds')
    ap.add_argument('--probe', action='store_true', help='run the polarity probe, print the result and exit')
    a = ap.parse_args()

    if a.list or not a.port:
        for p in serial.tools.list_ports.comports():
            print(f'{p.device:8s} {p.description}')
        return

    ser = serial.Serial(a.port, 115200, timeout=0.2)
    ser.dtr = True
    time.sleep(0.3)

    if a.probe:
        ser.reset_input_buffer()
        ser.write(b'P\n')
        end = time.time() + 2
        while time.time() < end:
            line = ser.readline().decode('ascii', 'replace').rstrip()
            if line.startswith('# PROBE'):
                print(line)
        return

    stamp = dt.datetime.now()
    out = a.out or os.path.join('captures', f'{stamp:%Y%m%d_%H%M%S}_{a.tag}.log')
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)

    for c in a.cmd:
        ser.write((c.strip() + '\n').encode())
        time.sleep(0.1)
    ser.write(b'S\n')

    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    recent = {1: bytearray(), 2: bytearray(), 3: bytearray(), 4: bytearray()}
    t_start = time.time()
    last_show = 0.0
    with open(out, 'w', newline='\n') as f:
        f.write(f'# HOST start={stamp.isoformat(timespec="seconds")} port={a.port}\n')
        f.write(f'# TAG {a.tag}\n')
        f.write(f'# LABEL ch1={a.label1}\n# LABEL ch2={a.label2}\n# LABEL ch3={a.label3}\n# LABEL ch4={a.label4}\n')
        if a.note:
            f.write(f'# NOTE {a.note}\n')
        for c in a.cmd:
            f.write(f'# SENT {c}\n')
        print(f'Recording to {out}   (Ctrl+C to stop)')
        try:
            while True:
                raw = ser.readline()
                if raw:
                    line = raw.decode('ascii', 'replace').rstrip('\r\n')
                    f.write(line + '\n')
                    if line.startswith('#'):
                        if line.startswith('# HB'):
                            f.write(f'# HOSTTIME {dt.datetime.now().isoformat(timespec="milliseconds")}\n')
                        else:
                            print(line)
                    else:
                        parts = line.split()
                        if len(parts) == 3 and parts[0] in ('1', '2', '3', '4'):
                            ch = int(parts[0])
                            counts[ch] += 1
                            recent[ch].append(int(parts[2], 16))
                            del recent[ch][:-40]
                now = time.time()
                if now - last_show > 1.0:
                    last_show = now
                    f.flush()
                    shown = '  '.join(f'{getattr(a, "label%d" % ch)}:{counts[ch]}' for ch in (1, 2, 3, 4))
                    print(f'[{now - t_start:7.1f}s] {shown}')
                    for ch in (1, 2, 3, 4):
                        if recent[ch]:
                            print(f'    {getattr(a, "label%d" % ch):>12s} … {printable(recent[ch])}')
                            recent[ch].clear()
                if a.duration and now - t_start > a.duration:
                    break
        except KeyboardInterrupt:
            pass
        ser.write(b'S\n')
        time.sleep(0.3)
        while ser.in_waiting:
            f.write(ser.readline().decode('ascii', 'replace').rstrip('\r\n') + '\n')
        f.write(f'# HOST end={dt.datetime.now().isoformat(timespec="seconds")}\n')
    print(f'Saved {out}  bytes: ' + ', '.join(f'ch{c}={n}' for c, n in counts.items()))


if __name__ == '__main__':
    main()
