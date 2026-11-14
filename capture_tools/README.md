# LEO 438VP serial-link capture tools

Receive-only logging of the microscope's low-speed serial links with a Teensy 3.2.

| Link | Where | Expected format (from the LEO software) |
|---|---|---|
| EHT | IP board UART A ⇄ EHT unit (fiber) | 9600 8N1, ASCII, `.`-prefixed single-letter commands, CR/LF |
| Stage / Vacuum | IP board UART B ⇄ STGVAC comms CPU (fiber) | 9600 8N1, ASCII dot-commands `.Sx`, `.Vx`, `.Cx`, `.Tx`, `.Qx`, CR/LF |
| VP ("Orsay") | PC COM2 ⇄ VP controller (RS-232 copper) | 9600 8N1, ASCII `RE`, `ST n,v`, `TO n`, `HP a,b,c`, `MC a,b` |

## Files

- `teensy_serial_logger/teensy_serial_logger.ino`: Teensy 3.2 firmware
- `capture_serial.py`: records the Teensy output to `captures/<date>_<tag>.log`
- `decode_serial_log.py`: turns a capture into a message timeline (and CSV)

## Build and flash

Arduino IDE with Teensyduino: Board **Teensy 3.2 / 3.1**, USB Type **Serial**, CPU speed 72 MHz (default is fine). Upload.

From the command line (the IDE's bundled CLI):

```
arduino-cli compile --fqbn teensy:avr:teensy31:usb=serial,speed=72 teensy_serial_logger
```

Builds cleanly with Teensyduino 1.62 (v2: 35 KB flash, 40 KB RAM). `snprintf` is avoided on purpose, because it fails to link for Teensy 3.x with this toolchain.

## Wiring

| Channel | Teensy RX pin | Typical use |
|---|---|---|
| ch1 | **0** (Serial1 RX) | direction A, e.g. IP → subsystem |
| ch2 | **9** (Serial2 RX) | direction B, e.g. subsystem → IP |
| ch3 | **7** (Serial3 RX) | e.g. COM2 TXD (PC → VP controller), inverted |
| ch4 | **2** (software UART) | e.g. COM2 RXD (VP controller → PC), inverted. 8N1 only; decoded from pin-change interrupts (firmware v2) |

- **Connect only the RX pins and GND.** The firmware releases the TX pins (1, 10, 8) after configuring each UART, so the Teensy never drives a tapped line.
- **Common ground** between the tap and the Teensy is required.
- **Logic levels:** Teensy 3.2 digital pins are 5 V tolerant, so 3.3 V or 5 V TTL from the fiber tap is fine. The RX pins have weak internal pull-ups, which suits open-collector outputs such as the HFBR-25xx receivers.
- **RS-232 (VP link on COM2):** use a series resistor + clamp diodes (as built: signal reads inverted, so set `I 3 1` / `I 4 1`) or a MAX3232 module (non-inverted). Never wire it directly.
- *(original note)* **RS-232 must NOT be wired directly.** Its ±5–12 V levels will damage the Teensy. Use an RS-232-to-TTL receiver such as a MAX3232 module (powered from the Teensy's 3.3 V). Feed its TTL outputs to the RX pins. Tap the PC's TXD (DB9 pin 3) and RXD (DB9 pin 2), with signal ground on pin 5.
- **Polarity:** an idle UART line is high. Fiber receivers often invert. Run the probe (below) with the microscope idle. If a channel idles low, enable inversion with `--cmd "I 1 1"` (channel 1) and so on.

## Capturing

```
python capture_serial.py --list
python capture_serial.py COM7 --probe
python capture_serial.py COM7 --tag stgvac_vent --label1 "IP->STGVAC" --label2 "STGVAC->IP" --note "vent from HV, stage at exchange"
```

Optional logger commands go in `--cmd`, e.g. `--cmd "B 1 9600" --cmd "I 2 1"`. The logger also accepts these commands directly from any serial terminal:

```
?  help                 S  config + counters        P  polarity probe
X  ch4 self-test         R <pin>  move ch4 (diagnostic)
B <ch> <baud>           F <ch> 8N1|8E1|8O1|7E1|7O1|8N2
I <ch> 0|1  invert RX   E <ch> 0|1  enable           Z  zero clock
```

While recording, the script prints byte counts and the latest text on each channel once per second. Garbled text (`<F8><80>…`) usually means wrong polarity or baud rate.

### Suggested capture sessions (one subsystem at a time)

Start each capture, then perform one action through the LEO UI, wait for things to settle, and stop. One action per file, with a descriptive `--tag` and `--note`.

- **Stage/Vac:** SEM software start-up (init + stage init), stage idle polling, single X move, single Z move, rotate, vent, pump, airlock if fitted, VP/HV switch.
- **EHT:** start-up, EHT on, filament ramp, beam on/off, change kV, change filament current, EHT off, scintillator/collector changes.
- **VP (COM2):** go to VP, change target pressure, go to HV, the VP control panel opening.

## File format

```
# HOST start=2026-11-12T10:15:00 port=COM7      <- added by capture_serial.py
# LABEL ch1=IP->STGVAC
# CFG ch1 rx_pin=0 en=1 baud=9600 fmt=8N1 invert=0 bytes=0
1 18233021 2E                                    <- channel, microseconds, byte (hex)
1 18234063 53
# HB t_us=19000000 n1=… n2=… n3=… dropped=0      <- once per second from the logger
# HOSTTIME 2026-11-12T10:15:19.004              <- wall clock at that heartbeat
```

Timestamps come from the Teensy's microsecond clock. A byte is stamped when the UART finishes receiving it, i.e. at its stop bit, within a few microseconds; ordering between channels is reliable. `dropped` stays 0 unless the PC stops reading for several seconds.

## Decoding

```
python decode_serial_log.py captures/20261112_101500_stgvac_vent.log --vocab
python decode_serial_log.py captures/…log --csv vent.csv --hex
```

Output is one row per message, all channels interleaved in time:

```
    0.000000  IP->STGVAC                  .SS X 0<CR><LF>
    0.013378  STGVAC->IP                  .SS 1234<CR><LF>
```
