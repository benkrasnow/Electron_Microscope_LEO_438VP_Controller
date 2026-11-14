"""Turn a Teensy serial-logger capture into a readable message timeline.

  python decode_serial_log.py captures/20261112_101500_eht_beam_on.log
  python decode_serial_log.py LOG --vocab          (also list distinct command prefixes)
  python decode_serial_log.py LOG --csv out.csv    (one row per message)

Bytes on each channel are grouped into messages. A message ends after a line
feed or carriage return, or when the line is idle for more than --gap character
times (default 300, because the STGVAC controller can pause ~60 ms mid-reply).
The LEO links use ASCII dot-commands ending in CR/LF, so this gives one row per
command or reply.
"""
import argparse
import collections
import csv
import re
import sys


def printable(bs):
    out = []
    for b in bs:
        if b == 13: out.append('<CR>')
        elif b == 10: out.append('<LF>')
        elif 32 <= b < 127: out.append(chr(b))
        else: out.append(f'<{b:02X}>')
    return ''.join(out)


def load(path):
    labels = {1: 'ch1', 2: 'ch2', 3: 'ch3', 4: 'ch4'}
    baud = {1: 9600, 2: 9600, 3: 9600, 4: 9600}
    data = []
    meta = []
    for line in open(path, encoding='ascii', errors='replace'):
        line = line.rstrip('\n')
        if line.startswith('#'):
            m = re.match(r'# LABEL ch(\d)=(.*)', line)
            if m: labels[int(m.group(1))] = m.group(2)
            m = re.match(r'# CFG ch(\d) .*baud=(\d+)', line)
            if m: baud[int(m.group(1))] = int(m.group(2))
            if line.startswith(('# NOTE', '# TAG', '# HOST start', '# CNT', '# SENT')):
                meta.append(line)
            continue
        p = line.split()
        if len(p) == 3 and p[0] in ('1', '2', '3', '4'):
            data.append((int(p[1]), int(p[0]), int(p[2], 16)))
    return labels, baud, data, meta


def group(data, baud, gap_chars):
    """Split each channel's byte stream into messages."""
    msgs = []
    cur = {}
    for t, ch, b in data:
        char_us = 10e6 / baud[ch]
        m = cur.get(ch)
        if m and t - m['t_last'] > gap_chars * char_us:
            msgs.append(m); m = None
        if m is None:
            m = {'ch': ch, 't0': t, 't_last': t, 'bytes': bytearray()}
            cur[ch] = m
        m['bytes'].append(b)
        m['t_last'] = t
        if b == 10 or (b == 13 and not m.get('crlf_wait')):
            # end on LF; on CR wait one byte to see if LF follows
            if b == 13:
                m['crlf_wait'] = True
                continue
            msgs.append(m); cur[ch] = None
        elif m.get('crlf_wait'):
            # CR not followed by LF: split before this byte
            last = m['bytes'].pop()
            m.pop('crlf_wait')
            msgs.append(m)
            cur[ch] = {'ch': ch, 't0': t, 't_last': t, 'bytes': bytearray([last])}
    for m in cur.values():
        if m: msgs.append(m)
    msgs.sort(key=lambda m: m['t0'])
    return msgs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('log')
    ap.add_argument('--gap', type=float, default=300.0,
                    help='idle gap that ends a message without a line ending, in character times '
                         '(default 300, about 0.3 s at 9600; devices may pause mid-line)')
    ap.add_argument('--csv', help='write messages to this CSV file')
    ap.add_argument('--vocab', action='store_true', help='summarise distinct message prefixes per channel')
    ap.add_argument('--hex', action='store_true', help='also print hex bytes for every message')
    a = ap.parse_args()

    labels, baud, data, meta = load(a.log)
    if not data:
        sys.exit('no data lines found')
    for line in meta:
        print(line)
    msgs = group(data, baud, a.gap)
    t0 = data[0][0]
    w = max(len(v) for v in labels.values())
    prev = {}
    for m in msgs:
        dt_prev = '' if m['ch'] not in prev else f"+{(m['t0'] - prev[m['ch']]) / 1e3:9.1f} ms"
        prev[m['ch']] = m['t0']
        print(f"{(m['t0'] - t0) / 1e6:12.6f}  {labels[m['ch']]:<{w}}  {dt_prev:>14s}  {printable(m['bytes'])}")
        if a.hex:
            print(' ' * (16 + w) + ' '.join(f'{b:02X}' for b in m['bytes']))

    if a.csv:
        with open(a.csv, 'w', newline='') as f:
            cw = csv.writer(f)
            cw.writerow(['t_s', 'channel', 'label', 'text', 'hex', 'n_bytes', 'duration_ms'])
            for m in msgs:
                cw.writerow([f"{(m['t0'] - t0) / 1e6:.6f}", m['ch'], labels[m['ch']], printable(m['bytes']),
                             m['bytes'].hex(' ').upper(), len(m['bytes']), f"{(m['t_last'] - m['t0']) / 1e3:.2f}"])
        print(f'wrote {a.csv}')

    print()
    print(f'{len(data)} bytes, {len(msgs)} messages, {(data[-1][0] - t0) / 1e6:.1f} s')
    if a.vocab:
        for ch in sorted({m['ch'] for m in msgs}):
            c = collections.Counter()
            for m in msgs:
                if m['ch'] != ch: continue
                text = printable(m['bytes']).replace('<CR>', '').replace('<LF>', '')
                key = re.match(r'[.!?]?[A-Za-z]{0,3}', text).group(0) or text[:3]
                c[key] += 1
            print(f'\n{labels[ch]}: distinct message prefixes')
            for k, n in c.most_common():
                print(f'   {k!r:10s} {n}')


if __name__ == '__main__':
    main()
