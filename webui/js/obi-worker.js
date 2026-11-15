// OBI acquisition worker: WebSocket to the bridge (/obi), OBI binary protocol, frame assembly.
// Runs off the main thread so a busy UI never stalls the data stream.
//
// Per frame we send:  Sync(cookieA, mode)  RasterRegion  RasterPixelRun x k  Sync(cookieB, mode)  Flush
// and expect back:    FF FF cookieA        <w*h pixels, 1 or 2 bytes, big-endian>  FF FF cookieB
// (protocol: nanographs/Open-Beam-Interface software/obi/commands). Two frames are kept in flight.

const CMD = { SYNC: 0x00, ABORT: 0x10, FLUSH: 0x20, EXT: 0x30, BEAM: 0x40, REGION: 0xA0, RUN: 0xC0 };
const MODE16 = 0, MODE8 = 1;

let ws = null, wsUrl = null, obiUp = false, reconnectTimer = null;
let running = false, cfg = null, cookie = 2, demo = false, demoTimer = null;
let pending = [];          // frame requests in flight, in order
let single = null;         // one-shot capture request waiting to be queued
let rx = new Uint8Array(1 << 22), rxLen = 0;
let stats = { frames: 0, bytes: 0, t0: performance.now(), resyncs: 0 };

const post = (m, t) => postMessage(m, t || []);
const log = (msg, lvl = "info") => post({ type: "log", lvl, msg });

function nextCookie() { cookie = (cookie + 2) & 0xFFFE; if (cookie === 0 || cookie === 0xFFFE) cookie = 2; return cookie; }

// ---------------------------------------------------------------- connection
function connect() {
  clearTimeout(reconnectTimer);
  if (demo || !wsUrl) return;
  try { ws = new WebSocket(wsUrl); } catch (e) { scheduleReconnect(); return; }
  ws.binaryType = "arraybuffer";
  ws.onopen = () => post({ type: "status", bridge: true, obi: obiUp });
  ws.onclose = () => { ws = null; obiUp = false; failPending(); post({ type: "status", bridge: false, obi: false }); scheduleReconnect(); };
  ws.onerror = () => {};
  ws.onmessage = (ev) => {
    if (typeof ev.data === "string") {
      const m = JSON.parse(ev.data);
      if (m.type === "status") {
        const was = obiUp;
        obiUp = m.obi === "connected";
        post({ type: "status", bridge: true, obi: obiUp, msg: m.msg });
        if (obiUp && !was) { rxLen = 0; pending = []; if (cfg && cfg.extCtrl) sendBytes([CMD.BEAM | 1, CMD.EXT | 1]); pump(); }
        if (!obiUp) { failPending(); setTimeout(() => ws && ws.readyState === 1 && ws.send(JSON.stringify({ cmd: "connect" })), 3000); }
      }
      return;
    }
    receive(new Uint8Array(ev.data));
  };
}
function scheduleReconnect() { clearTimeout(reconnectTimer); reconnectTimer = setTimeout(connect, 2000); }
function failPending() { if (pending.some(p => p.single)) post({ type: "single-failed" }); pending = []; rxLen = 0; }
function sendBytes(arr) { if (ws && ws.readyState === 1 && obiUp) ws.send(arr instanceof Uint8Array ? arr : new Uint8Array(arr)); }

// ---------------------------------------------------------------- commands
function frameRequest(c, isSingle) {
  const w = c.w, h = c.h, n = w * h, bpp = c.bits === 16 ? 2 : 1, mode = c.bits === 16 ? MODE16 : MODE8;
  // Square pixels: the longer side spans the full 14-bit DAC range, the shorter side is centred.
  const span = Math.max(w, h);
  const step = Math.min(65535, Math.floor((16384 / span) * 256));      // fixed point 8.8
  const xs = Math.round((16384 - (w * step) / 256) / 2), ys = Math.round((16384 - (h * step) / 256) / 2);
  const dwell = Math.max(0, Math.min(65535, Math.round(c.dwellNs / c.dwellUnitNs)));
  const runs = Math.ceil(n / 65536);
  const buf = new Uint8Array(3 + 13 + runs * 5 + 3 + 1);
  const dv = new DataView(buf.buffer);
  const ca = nextCookie(), cb = nextCookie();
  let o = 0;
  buf[o++] = CMD.SYNC | 1 | (mode << 1); dv.setUint16(o, ca); o += 2;
  buf[o++] = CMD.REGION;
  for (const v of [xs, w, step, ys, h, step]) { dv.setUint16(o, v); o += 2; }
  for (let left = n; left > 0; left -= 65536) {
    const len = Math.min(65536, left);
    buf[o++] = CMD.RUN; dv.setUint16(o, len - 1); o += 2; dv.setUint16(o, dwell); o += 2;
  }
  buf[o++] = CMD.SYNC | 1 | (mode << 1); dv.setUint16(o, cb); o += 2;
  buf[o++] = CMD.FLUSH;
  return { bytes: buf, w, h, bpp, n, ca, cb, phase: 0, got: 0, data: new Uint8Array(n * bpp), single: isSingle, t0: performance.now(), cfg: c };
}

function pump() {
  if (demo || !obiUp) return;
  if (single && pending.length < 2) { const r = frameRequest(single, true); single = null; pending.push(r); sendBytes(r.bytes); }
  while (running && cfg && pending.length < 2) { const r = frameRequest(cfg, false); pending.push(r); sendBytes(r.bytes); }
}

// ---------------------------------------------------------------- receive and parse
function receive(chunk) {
  stats.bytes += chunk.length;
  if (rxLen + chunk.length > rx.length) { const g = new Uint8Array(Math.max(rx.length * 2, rxLen + chunk.length)); g.set(rx.subarray(0, rxLen)); rx = g; }
  rx.set(chunk, rxLen); rxLen += chunk.length;
  let p = 0;
  while (pending.length) {
    const f = pending[0];
    if (f.phase === 0 || f.phase === 2) {
      const want = f.phase === 0 ? f.ca : f.cb;
      if (rxLen - p < 4) break;
      if (rx[p] === 0xFF && rx[p + 1] === 0xFF && rx[p + 2] === (want >> 8) && rx[p + 3] === (want & 0xFF)) {
        p += 4;
        if (f.phase === 0) f.phase = 1; else { pending.shift(); deliver(f); }
        continue;
      }
      // Out of step: look for the marker further on.
      let k = -1;
      for (let i = p + 1; i + 3 < rxLen; i++) if (rx[i] === 0xFF && rx[i + 1] === 0xFF && rx[i + 2] === (want >> 8) && rx[i + 3] === (want & 0xFF)) { k = i; break; }
      stats.resyncs++;
      if (k < 0) { p = Math.max(p, rxLen - 3); break; }
      if (f.phase === 2) { pending.shift(); log("frame dropped (out of step)", "warn"); p = k + 4; continue; }
      p = k;
      continue;
    }
    // phase 1: pixel bytes
    const need = f.data.length - f.got, take = Math.min(need, rxLen - p);
    f.data.set(rx.subarray(p, p + take), f.got); f.got += take; p += take;
    if (f.got < f.data.length) break;
    f.phase = 2;
  }
  if (p > 0) { rx.copyWithin(0, p, rxLen); rxLen -= p; }
  pump();
}

function deliver(f) {
  let out;
  if (f.bpp === 2) {                       // big-endian 16-bit -> native Uint16 (ADC code << 2)
    out = new Uint16Array(f.n);
    const d = f.data;
    for (let i = 0, j = 0; i < f.n; i++, j += 2) out[i] = (d[j] << 8) | d[j + 1];
  } else out = f.data;
  stats.frames++;
  post({ type: "frame", w: f.w, h: f.h, bits: f.bpp * 8, single: f.single, ms: performance.now() - f.t0, data: out.buffer, meta: f.cfg }, [out.buffer]);
}

// ---------------------------------------------------------------- demo source (no OBI needed)
let demoPhase = 0;
function demoFrame(c, isSingle) {
  const w = c.w, h = c.h, bits = c.bits;
  const out = bits === 16 ? new Uint16Array(w * h) : new Uint8Array(w * h);
  const blur = Math.min(1, Math.abs((c.focus ?? 2234) - 2234) / 60);       // defocus softens edges
  const scale = 1 / Math.max(1, c.mag / 100) ** 0.5;
  demoPhase += 0.02;
  const max = bits === 16 ? 65532 : 255;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const u = (x / w - 0.5) * scale * 12 + demoPhase * 0.05, v = (y / h - 0.5) * scale * 12;
      let s = 0.5 + 0.25 * Math.sin(u * 3.1) * Math.cos(v * 2.7) + 0.2 * Math.sin((u * u + v * v) * 1.3);
      const edge = Math.sin(u * 7) * Math.sin(v * 7) > 0.3 ? 0.25 * (1 - blur) : 0;
      s = s + edge + (Math.random() - 0.5) * 0.12;
      out[y * w + x] = Math.max(0, Math.min(max, s * max * 0.85));
    }
  }
  stats.frames++; stats.bytes += out.byteLength;
  post({ type: "frame", w, h, bits, single: isSingle, ms: 0, data: out.buffer, meta: c, demo: true }, [out.buffer]);
}
function demoLoop() {
  clearTimeout(demoTimer);
  if (!demo) return;
  const c = single || cfg;
  if (single) { const s = single; single = null; demoFrame(s, true); }
  else if (running && cfg) demoFrame(cfg, false);
  const frameMs = c ? Math.max(33, (c.w * c.h * c.dwellNs) / 1e6) : 100;
  demoTimer = setTimeout(demoLoop, frameMs);
}

// ---------------------------------------------------------------- stats
setInterval(() => {
  const t = performance.now(), dt = (t - stats.t0) / 1000;
  post({ type: "stats", fps: stats.frames / dt, mbps: stats.bytes / dt / 1e6, resyncs: stats.resyncs, inflight: pending.length });
  stats.frames = 0; stats.bytes = 0; stats.t0 = t;
}, 1000);

// ---------------------------------------------------------------- messages from the page
onmessage = (ev) => {
  const m = ev.data;
  switch (m.type) {
    case "connect": wsUrl = m.url; connect(); break;
    case "config": cfg = m.cfg; break;
    case "start": cfg = m.cfg; running = true; if (demo) demoLoop(); else pump(); break;
    case "stop": running = false; break;
    case "single": single = m.cfg; if (demo) demoLoop(); else pump(); break;
    case "abort": running = false; single = null; sendBytes([CMD.ABORT, CMD.FLUSH]); pending = []; rxLen = 0; break;
    case "ext": sendBytes([CMD.EXT | (m.on ? 1 : 0)]); break;
    case "demo":
      demo = m.on;
      if (demo) { if (ws) ws.close(); post({ type: "status", bridge: false, obi: false, demo: true }); demoLoop(); }
      else { clearTimeout(demoTimer); post({ type: "status", bridge: false, obi: false, demo: false }); connect(); }
      break;
  }
};
