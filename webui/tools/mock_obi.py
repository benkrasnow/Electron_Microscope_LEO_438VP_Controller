"""Stand-in for the OBI applet's TCP endpoint, for testing the page and bridge without a Glasgow.

Speaks the OBI command stream (Synchronize, RasterRegion, RasterPixelRun, Flush, ...) and returns
synthetic pixels plus FF FF <cookie> sync markers, paced to roughly the requested dwell time.
    python tools/mock_obi.py [--port 2224]
"""
import argparse
import asyncio
import math
import random
import struct

LEN = {0x0: 3, 0x1: 1, 0x2: 1, 0x3: 1, 0x4: 1, 0x5: 1, 0x6: 3, 0x9: 3, 0xA: 13, 0xB: 3, 0xC: 5, 0xD: 3, 0xE: 7, 0xF: 5}


_cache = {}
PACE_NS = 125          # simulated time per dwell count (--pace 0: as fast as possible)


def pattern(w, h, mode):
    """Synthetic frame as wire bytes, built once per size and mode."""
    key = (w, h, mode)
    if key not in _cache:
        px = []
        for y in range(h):
            for x in range(w):
                v = 0.5 + 0.3 * math.sin(x * 0.05) * math.cos(y * 0.04) + random.uniform(-0.08, 0.08)
                px.append(max(0, min(16383, int(v * 16383))))
        if mode == 0:
            _cache[key] = struct.pack(f">{len(px)}H", *[p << 2 for p in px])
        elif mode == 1:
            _cache[key] = bytes(p >> 6 for p in px)
        else:
            _cache[key] = b""
    return _cache[key]


async def session(reader, writer):
    buf = b""
    mode = 0                      # 0 = 16-bit, 1 = 8-bit, 2 = none
    region = (0, 512, 8192, 0, 512, 8192)
    pos = 0
    frame = 0
    print("client connected")
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            buf += data
            out = bytearray()
            while buf:
                kind = buf[0] >> 4
                n = LEN.get(kind)
                if n is None:
                    buf = buf[1:]
                    continue
                if len(buf) < n:
                    break
                c, buf = buf[:n], buf[n:]
                if kind == 0x0:
                    mode = (c[0] >> 1) & 3
                    out += b"\xff\xff" + c[1:3]
                elif kind == 0xA:
                    region = struct.unpack(">6H", c[1:])
                    pos = 0
                    frame += 1
                elif kind == 0xC:
                    length, dwell = struct.unpack(">HH", c[1:])
                    count = length + 1
                    img = pattern(region[1], region[4], mode)
                    bpp = 2 if mode == 0 else (1 if mode == 1 else 0)
                    shift = (frame * 7 % region[1]) * bpp            # drift the pattern sideways
                    start = (pos * bpp + shift) % max(len(img), 1)
                    need = count * bpp
                    while need > 0 and img:                         # copy with wrap-around
                        k = min(need, len(img) - start)
                        out += memoryview(img)[start:start + k]
                        need -= k
                        start = 0
                    pos += count
                    await asyncio.sleep(count * max(dwell, 1) * PACE_NS * 1e-9)
            if out:
                writer.write(bytes(out))
                await writer.drain()
    except ConnectionError:
        pass
    print("client disconnected")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=2224)
    ap.add_argument("--pace", type=float, default=125, help="ns per dwell count (0 = no pacing)")
    a = ap.parse_args()
    global PACE_NS
    PACE_NS = a.pace
    srv = await asyncio.start_server(session, "127.0.0.1", a.port)
    print(f"mock OBI on localhost:{a.port}")
    async with srv:
        await srv.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
