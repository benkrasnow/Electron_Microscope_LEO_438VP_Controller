#!/bin/sh
# usage: wait_grab_decode.sh <tag> [timeout_s]   (scope must already be armed with arm_burst.py)
tag=$1; to=${2:-600}
out=../scope_captures/$tag
python - "$to" <<'PY'
import sys, time, pyvisa
s = pyvisa.ResourceManager('@py').open_resource('TCPIP0::192.168.0.42::inst0::INSTR'); s.read_termination = '\n'
t0 = time.time()
while time.time() - t0 < float(sys.argv[1]):
    if s.query('ACQuire:STATE?').strip() == '0':
        print('TRIGGERED at', time.strftime('%H:%M:%S')); break
    time.sleep(0.5)
else:
    print('TIMEOUT'); sys.exit(1)
PY
[ $? -eq 0 ] || exit 1
python scope_grab.py $out 1 2 3 4 && python decode_scan_fiber.py $out.npz ch3 > ${out}_ch3.txt
echo "frames: $(wc -l < ${out}_ch3.txt)"; grep -v -c "chip3 DAC4" ${out}_ch3.txt
