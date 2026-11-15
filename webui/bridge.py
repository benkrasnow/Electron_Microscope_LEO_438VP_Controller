"""LEO 438VP web UI bridge.

Serves the page in this folder at http://localhost:8438/ and relays a WebSocket at /obi to the
Open Beam Interface applet's TCP endpoint (glasgow ... obi, default localhost:2224). Browsers cannot
open raw TCP sockets; this is the only thing the bridge does besides serving files.

Standard library only (Python 3.8+):  python bridge.py [--port 8438] [--obi-host localhost] [--obi-port 2224]

WebSocket /obi:
  binary messages   = raw OBI command / data bytes, relayed unchanged in both directions
  text, bridge->page: {"type":"status","obi":"connected"|"down","msg":...}
  text, page->bridge: {"cmd":"connect"}  (retry the TCP connection)
"""
import argparse
import asyncio
import base64
import hashlib
import json
import mimetypes
import os
import struct
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml",
        ".png": "image/png", ".ico": "image/x-icon", ".webmanifest": "application/manifest+json"}


class WebSocket:
    """Minimal RFC 6455 server side: unfragmented sends, reassembly of fragmented receives."""

    def __init__(self, reader, writer):
        self.r, self.w = reader, writer
        self.closed = False

    async def send(self, data, text=False):
        if self.closed:
            return
        payload = data.encode() if text else data
        n = len(payload)
        hdr = bytes([0x81 if text else 0x82])
        if n < 126:
            hdr += bytes([n])
        elif n < 65536:
            hdr += bytes([126]) + struct.pack(">H", n)
        else:
            hdr += bytes([127]) + struct.pack(">Q", n)
        self.w.write(hdr + payload)
        await self.w.drain()

    async def recv(self):
        """Returns (is_text, payload) or None when closed."""
        buf, kind = b"", None
        while True:
            h = await self.r.readexactly(2)
            fin, op = h[0] & 0x80, h[0] & 0x0F
            n = h[1] & 0x7F
            if n == 126:
                n = struct.unpack(">H", await self.r.readexactly(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", await self.r.readexactly(8))[0]
            mask = await self.r.readexactly(4) if h[1] & 0x80 else None
            data = await self.r.readexactly(n)
            if mask:
                data = bytes(b ^ mask[i & 3] for i, b in enumerate(data)) if n < 64 else _unmask(data, mask)
            if op == 0x8:
                self.closed = True
                return None
            if op == 0x9:
                self.w.write(bytes([0x8A, len(data)]) + data)
                await self.w.drain()
                continue
            if op == 0xA:
                continue
            if op in (1, 2):
                kind = op
            buf += data
            if fin:
                return kind == 1, buf


def _unmask(data, mask):
    # XOR with the repeated 4-byte mask, done on big integers for speed.
    n = len(data)
    m = (mask * (n // 4 + 1))[:n]
    return (int.from_bytes(data, "big") ^ int.from_bytes(m, "big")).to_bytes(n, "big")


async def obi_session(ws, host, port):
    tcp = None

    async def status(state, msg=""):
        await ws.send(json.dumps({"type": "status", "obi": state, "msg": msg}), text=True)

    async def connect():
        nonlocal tcp
        try:
            r, w = await asyncio.wait_for(asyncio.open_connection(host, port), 3)
            tcp = (r, w)
            await status("connected", f"{host}:{port}")
            asyncio.ensure_future(pump_tcp(r))
        except Exception as e:  # noqa: BLE001 - report any connection failure to the page
            tcp = None
            await status("down", f"{host}:{port}: {e}")

    async def pump_tcp(r):
        nonlocal tcp
        try:
            while True:
                chunk = await r.read(1 << 18)
                if not chunk:
                    break
                await ws.send(chunk)
        except Exception:  # noqa: BLE001
            pass
        tcp = None
        if not ws.closed:
            await status("down", "OBI closed the connection")

    await connect()
    while True:
        m = await ws.recv()
        if m is None:
            break
        is_text, data = m
        if is_text:
            try:
                cmd = json.loads(data).get("cmd")
            except ValueError:
                cmd = None
            if cmd == "connect" and tcp is None:
                await connect()
        elif tcp is not None:
            tcp[1].write(data)
            await tcp[1].drain()
    if tcp is not None:
        tcp[1].close()


async def handle(reader, writer, args):
    try:
        head = await reader.readuntil(b"\r\n\r\n")
    except Exception:  # noqa: BLE001
        writer.close()
        return
    lines = head.decode("latin-1").split("\r\n")
    try:
        method, path, _ = lines[0].split(" ", 2)
    except ValueError:
        writer.close()
        return
    hdrs = {}
    for ln in lines[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            hdrs[k.strip().lower()] = v.strip()
    path = path.split("?", 1)[0]

    if path == "/obi" and hdrs.get("upgrade", "").lower() == "websocket":
        key = hdrs.get("sec-websocket-key", "")
        acc = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {acc}\r\n\r\n").encode())
        await writer.drain()
        ws = WebSocket(reader, writer)
        try:
            await obi_session(ws, args.obi_host, args.obi_port)
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        writer.close()
        return

    if method != "GET":
        writer.write(b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n")
    else:
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.realpath(os.path.join(ROOT, rel))
        if not full.startswith(ROOT + os.sep) or not os.path.isfile(full) or os.path.basename(full) == "bridge.py":
            writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
        else:
            with open(full, "rb") as f:
                body = f.read()
            ctype = MIME.get(os.path.splitext(full)[1], mimetypes.guess_type(full)[0] or "application/octet-stream")
            writer.write((f"HTTP/1.1 200 OK\r\nContent-Type: {ctype}\r\nContent-Length: {len(body)}\r\n"
                          "Cache-Control: no-cache\r\nConnection: close\r\n\r\n").encode() + body)
    await writer.drain()
    writer.close()


async def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=8438, help="HTTP port for the page (default 8438)")
    ap.add_argument("--obi-host", default="localhost", help="OBI applet TCP host")
    ap.add_argument("--obi-port", type=int, default=2224, help="OBI applet TCP port (default 2224)")
    args = ap.parse_args()
    server = await asyncio.start_server(lambda r, w: handle(r, w, args), "127.0.0.1", args.port)
    print(f"LEO 438VP UI: http://localhost:{args.port}/   (OBI relay -> {args.obi_host}:{args.obi_port})")
    sys.stdout.flush()
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
