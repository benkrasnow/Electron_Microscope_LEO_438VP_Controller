# LEO 438VP web control page

This is the operator interface for the microscope. It runs in **Chrome or Edge** and uses three connections:

| Connection | Path | API |
|---|---|---|
| Control box (Teensy) | USB serial, protocol in `../firmware/PROTOCOL.md` | Web Serial |
| Imaging (OBI / Glasgow) | WebSocket `/obi` → `bridge.py` → OBI applet TCP socket (default `localhost:2224`) | WebSocket + Web Worker |
| Display | 8- or 16-bit frames drawn as WebGL2 textures | WebGL2 |

## Running it

1. Start the OBI applet (Glasgow) with its TCP endpoint enabled, as usual for OBI. Only the headless applet is needed, not the OBI GUI.
2. Run:
   ```
   python webui/bridge.py
   ```
   It needs only the Python standard library. Options: `--port 8438`, `--obi-host`, `--obi-port 2224`.
3. Open the page in Chrome or Edge, either way:
   - **http://localhost:8438** (served by the bridge). Recommended: the browser remembers the serial-port permission, so the page reconnects to the control box by itself.
   - `index.html` opened straight from disk. This also works, using plain scripts and a worker built in-page, and imaging reaches the bridge at `ws://localhost:8438`. The browser may ask for the serial port again after each reload.
4. Click **Control box** in the top bar and pick the Teensy. After the first time, the page reconnects to it automatically, including after an unplug and replug.

The bridge relays bytes and does nothing else. The control-box functions work without it; only imaging needs it.

## Operator page

- **Top bar:** vacuum, beam and chamber-mode status chips, the running sequence, link indicators, clock, and a link to the Developer tools.
- **Image area:**
  - Live / Freeze, scan speed (dwell time), live resolution.
  - Photo capture: resolution and dwell; saves a 16-bit TIFF with all parameters in the TIFF description, readable by ImageJ / Fiji.
- **Detector column to the right of the image** (below it in a narrow window):
  - histogram of the raw OBI values over the full 16-bit range, with two draggable lines: left = black, right = white (drag between them to move both). They set the live display and are applied to saved TIFFs (the levels are recorded in the TIFF description);
  - PMT voltage (LEO-32's "brightness": PM HV channel 1 on the EHT set), slider and number box;
  - SE collector voltage, slider and number box;
  - probe current in pA (logarithmic slider). Optibeam is always on, so the condensers follow it; the Optibeam mode (Resolution / Depth / Auto) and the aperture fitted (30 / 50 µm) are in the Beam card.
- **Focus** (detector column, below the probe current): the working distance in mm, 2–100 mm. The box sets the objective for that WD, so moving it shows directly how the WD changes. Coarse: slider or number box. Fine: drag the spring-return handle below them; the WD follows the drag slowly (5 µm per pixel at 100× and below, finer at higher magnification; "Fine focus" in the preferences) and holds while you hold still. On release the handle springs back to the centre and the WD stays, so the next drag continues from there and it never runs out of travel.
- **Magnification** (below Focus): logarithmic slider (10× – 500 000×), number box and the same spring-return fine handle (0.4 % per pixel of drag).
  - Data bar: HFW, magnification, kV, WD, dwell, pixels, vacuum, frame rate.
- **Mouse on the image:**
  - wheel: focus (steps the WD; finer at higher magnification, "Focus / notch" in the preferences);
  - **Ctrl**+wheel: magnification;
  - **Alt** / **Shift**+wheel: stigmator X / Y;
  - double-click: move the stage to centre that point.
- **Side panels:**
  - Vacuum: pump, vent, HV / VP with target pressure.
  - Beam: beam on/off; EHT with presets, emission and filament (sliders), each with its target and, on the right, what is being sent to the supply now (the link has no read-back; it lags the target while ramping); Optibeam mode, aperture.
  - Image: stigmator XY pad (drag anywhere: the dot follows the drag, X right / Y up; "Fine" scales the movement down 10×; "Centre" = 2048 / 2048), focus wobble (amount and speed appear while it is on); rotation, tilt correction and beam shift under "Scan geometry".
  - Stage: positions, jog pad with step size, joystick sensitivity, go-to, initialise.

Every interlock lives on the control box. The page only asks for things, and shows the box's reason when a request is refused. Vent and VP changes ask for confirmation.

## Developer section

Open it with **Developer** in the top bar. Warnings and faults from the box also pop up as notifications; every event is in the traffic log there.

| Tab | Content |
|---|---|
| Settings | All runtime settings of the control box. Filter, edit (sent at once, stored in flash a few seconds later), reset to default, save now |
| Link traffic | Live trace of the EHT / stage-vacuum / VP links, events and USB commands, with filter, pause and save. Raw link commands (need `dbg.raw 1`; they bypass interlocks) |
| Console | Any control-box protocol command, with history (↑ / ↓) |
| OBI / imaging | Bridge and applet state, frame rate, data rate, resyncs; per-browser imaging parameters (dwell unit, live bit depth, HFW at 1×, wheel step sizes, centring direction); demo image source; OBI ExternalCtrl |
| Status JSON | The raw status object from the box |

Page preferences are kept in the browser (`localStorage`). Machine settings live in the control box.

## Files

| File | Content |
|---|---|
| `bridge.py` | static file server + WebSocket ↔ TCP relay (standard library only) |
| `index.html`, `css/app.css` | layout and styling |
| `js/app.js` | page logic: status rendering, controls, imaging, developer tools |
| (all scripts) | plain scripts, not ES modules, so the page also runs from `file://` |
| `js/teensy.js` | Web Serial client for the control box (command ids, replies, telemetry, auto-reconnect) |
| `js/obi-worker.js` | Web Worker (started from a Blob of `obiWorkerMain`): OBI binary protocol (Synchronize / RasterRegion / RasterPixelRun / Flush), frame parsing with sync-cookie checks, demo source |
| `js/viewer.js` | WebGL2 display (8-bit and 16-bit textures, black / white levels applied in the shader) |
| `js/tiff.js` | 8/16-bit TIFF writer |
| `tools/mock_obi.py` | stand-in OBI TCP server for testing without a Glasgow (`--pace 0` = as fast as possible) |

## Tested (2026-11-14, without the microscope)

- Page → worker → bridge → `mock_obi.py` → frames. 512² 8-bit and 1024² 16-bit, zero resyncs.
- Unpaced throughput: **~75 fps of 1024×1024 16-bit (~150 MB/s)** through the bridge, worker and WebGL display. That is several times what the Glasgow's USB 2.0 link delivers, so neither the browser nor the bridge limits the frame rate.
- Status rendering, using a status line from the real control box.
- Not yet tested: Web Serial with the real box in Chrome (the built-in preview browser has no serial chooser), and the real OBI applet.

## Assumptions to check on the real OBI

- **Dwell unit 125 ns per count:** from the OBI source docstring; adjustable in Developer → OBI.
- **Sync markers in 8-bit mode:** assumed to be 4 bytes (`FF FF` + 16-bit cookie), as in 16-bit mode. If 8-bit live view shows resyncs, switch live to 16-bit in Developer → OBI.
- **Field mapping:** the frame is centred in the 14-bit DAC field with square pixels.
- **HFW at 1×:** set to 110 mm (from the original software). Calibrate it against a grid and update "HFW at 1×", because the OBI's external-scan amplitude may differ from the internal one.
- **Double-click centring direction:** depends on how the stage axes map to the image; flip it with the sign settings.
