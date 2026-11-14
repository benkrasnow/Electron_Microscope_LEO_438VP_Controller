import sys
S = sys.argv[1]
p = S + '/leo438vp_report.html'
s = open(p, encoding='utf-8').read()
new = open(S + '/sec8.html', encoding='utf-8').read()
a = s.index('<h2 id="dsp">'); b = s.index('<h2 id="other">')
s = s[:a] + new + '\n' + s[b:]
reps = [
('<li><a href="#dsp"><span>8</span>DSP and dual-port RAM</a></li>', '<li><a href="#dsp"><span>8</span>Scan generator path</a></li>'),
("<b>A DSP behind dual-port RAM runs the scan and the EO board</b><p>The electron-optics module never uses a UART. It writes EO registers through a DSP, which also generates the 1024×768 raster. The DSP's variable map survives as a commented text file (<code>SEM_INIT.DAT</code>).</p>",
 "<b>An ADSP-21xx DSP programs a remote raster engine</b><p>The DSP sends start/step/count/flyback values for X and Y, plus all lens and stig set-points, over a 10-bit remote register bus. It derives the pixel clock from its SPORT1 clock pin, halving it per scan-rate step. X/Y samples are not streamed from the PC (§8).</p>"),
('<tr><td>EO</td><td>EO board (lenses, stig, scan coils)</td><td>Driven by the DSP, not the GSP</td><td>Register writes: <code>_DSP_set_EO_register</code>, <code>_write_EO_value</code>; DSP command <code>0x12</code> = "Initialise EO board"</td><td><span class="conf c-md">path confirmed, wire format unknown</span></td></tr>',
 '<tr><td>EO register bus</td><td>EO / scan generator board (lenses, stig, raster engine)</td><td>DSP remote register port, busy-flag handshake, target 0x40</td><td>10-bit address + 16-bit data writes; DSP commands 0x04/0x05/0x12 (§8)</td><td><span class="conf c-md">mechanism confirmed, wire format unknown</span></td></tr>'),
('<tr><td>Scan</td><td>Scan generator / column</td><td>DSP-generated raster, 1024×768 default</td><td>See §8 for DPRAM parameters</td><td><span class="conf c-md">inferred</span></td></tr>',
 '<tr><td>Pixel clock / sync</td><td>Scan generator board</td><td>DSP SPORT1 SCLK, ÷2 per scan-rate step; line/frame timing</td><td>Continuous clock; far-end prescaler reg 0x4A for slow rates (§8)</td><td><span class="conf c-md">strongly inferred</span></td></tr>'),
('<tr><td>Video in</td><td>Detector channels</td><td>Selectable "ports" and "zones" (<code>assign_zone_port</code>, <code>DETECTOR_FROM_PORT</code>)</td><td>Gain/offset/k/alpha/beta per detector set in DPRAM (<code>DETA</code>, <code>DETB</code>, <code>KA</code>…)</td><td><span class="conf c-lo">needs hardware check</span></td></tr>',
 '<tr><td>Detector video</td><td>PMT / detectors</td><td>Analogue into the IP board, digitised there (no fiber)</td><td>Zone gain/offset/mixing set by DSP commands 0x0C/0x0D</td><td><span class="conf c-hi">confirmed by owner</span></td></tr>'),
('<text x="338" y="520" class="t-small t-muted">2 confirmed as UART links; the rest are inferred to carry</text>\n  <text x="338" y="535" class="t-small t-muted">scan/EO data and detector video (see §7)</text>',
 '<text x="338" y="520" class="t-small t-muted">UART A/B + 4 plastic fibers to the scan generator:</text>\n  <text x="338" y="535" class="t-small t-muted">register bus, pixel clock, sync (see §8)</text>'),
('<text x="768" y="356" class="t-small t-muted">SE, VPSE, BSD / 4Q-BSD, chamber scope</text>',
 '<text x="768" y="356" class="t-small t-muted">PMT analogue to IP board (no fiber)</text>'),
('<path d="M756,346 C724,346 726,536 668,536" class="fib" marker-end="url(#ahf)"/>', '<path d="M756,346 C724,346 726,536 668,536" class="wire2" marker-end="url(#ah)"/>'),
('<td>DSP variable map, command codes, DSP image</td>',
 '<td>DSP variable map; ADSP-21xx firmware (command table, remote register port, raster math, SCLK pixel clock)</td>'),
]
for x, y in reps:
    assert x in s, x[:70]
    s = s.replace(x, y)
open(p, 'w', encoding='utf-8').write(s)
print('ok', len(s))
