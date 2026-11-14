import sys
S = sys.argv[1]
p = S + '/leo438vp_report.html'
s = open(p, encoding='utf-8').read()
eomap = open(S + '/eomap.html', encoding='utf-8').read().replace(
    'register auto-increments after each write, so consecutive registers share one setup',
    'the DSP post-increments the register number, so consecutive registers are written back-to-back')
fibers = open(S + '/fibers.html', encoding='utf-8').read()

def cut(s, a_marker, b_marker, new):
    a = s.index(a_marker); b = s.index(b_marker)
    return s[:a] + new + '\n' + s[b:]

s = cut(s, '<h3>Remote register map (EO target)</h3>', '<h3>How a raster is defined', eomap)
s = cut(s, '<h3>What this predicts for the four fibers</h3>', '<h3>Still to decode</h3>', fibers)

old_rb = s[s.index('  <li><b>Readback exists.</b>'):]
old_rb = old_rb[:old_rb.index('</li>') + 5]
s = s.replace(old_rb, '  <li><b>Readback is real.</b> The firmware reads remote registers (0x4B, 0x14, 0x30, board ID 0x90) and waits on the busy flag for the reply. The EO board has one fiber transmitter (HFBR-1521) for this return path; see below.</li>')

old_todo = s[s.index('<h3>Still to decode</h3>'):s.index('<h2 id="other">')]
s = s.replace(old_todo, '''<h3>Still to decode</h3>
<ul class="prose">
  <li>The wire format of a register packet (bit order, framing, how the target and read/write are encoded). The init burst gives a known sequence to align against.</li>
  <li>Exact meanings of ramp parameters +3…+7 and the control-word bits. Compare captures of focus wobble (0x8043), stig wobble (0x8063) and scanning (0x8402/0x8422).</li>
  <li>HRRU target (0x20): uses the same chip layout (X at 0x40, Y at 0x60). It only matters if the photo unit is kept.</li>
</ul>
''')
s = s.replace('This section goes deeper than the first pass.', 'This section goes deeper than the first pass and now includes the decoded EO register map.')
open(p, 'w', encoding='utf-8').write(s)
print('ok', len(s))
