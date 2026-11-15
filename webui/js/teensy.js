// Web Serial client for the control box (firmware/PROTOCOL.md).
// Commands go out as text lines with a "#id"; every JSON line coming back is dispatched:
// replies resolve the matching promise, "st" / "ev" / "tr" / "set" go to listeners.

const PJRC_VID = 0x16C0;

class Teensy extends EventTarget {
  constructor() {
    super();
    this.port = null;
    this.writer = null;
    this.nextId = 1;
    this.waiting = new Map();
    this.connected = false;
    this.listBuf = null;
  }

  get supported() { return "serial" in navigator; }

  // Reconnect to a port this page was granted before (no chooser needed), and follow plug / unplug.
  async autoConnect() {
    if (!this.supported) return false;
    navigator.serial.addEventListener("connect", (e) => { if (!this.connected) this.open(e.target).catch(() => {}); });
    navigator.serial.addEventListener("disconnect", (e) => { if (e.target === this.port) this.lost("unplugged"); });
    const ports = await navigator.serial.getPorts();
    const p = ports.find(p => p.getInfo().usbVendorId === PJRC_VID) || ports[0];
    if (p) { try { await this.open(p); return true; } catch { /* fall through */ } }
    return false;
  }

  async choose() {
    const p = await navigator.serial.requestPort({ filters: [{ usbVendorId: PJRC_VID }] });
    await this.open(p);
  }

  async open(port) {
    if (this.connected) await this.close();
    await port.open({ baudRate: 115200, bufferSize: 1 << 16 });
    await port.setSignals({ dataTerminalReady: true, requestToSend: true });
    this.port = port;
    this.writer = port.writable.getWriter();
    this.connected = true;
    this.emit("link", { connected: true });
    this.readDone = this.readLoop(port);
    // Set the box's clock from the PC on every connection.
    this.cmd(`time ${Math.floor(Date.now() / 1000)}`).catch(() => {});
  }

  // Release the port completely, so it can be opened again (here or by another program).
  // The streams must be unlocked before port.close() succeeds: stop the reader, wait for the
  // read loop to release its lock, close the writer, then close the port.
  async close(why) {
    const p = this.port;
    this.connected = false;
    this.port = null;
    for (const [, w] of this.waiting) { clearTimeout(w.timer); w.reject(new Error("link closed")); }
    this.waiting.clear();
    this.listBuf = null;
    if (p) {
      try { this.reader && await this.reader.cancel(); } catch {}
      try { await this.readDone; } catch {}
      const w = this.writer;
      this.writer = null;
      if (w) {
        try { await Promise.race([w.close(), new Promise(r => setTimeout(r, 500))]); } catch {}
        try { w.releaseLock(); } catch {}
      }
      try { await p.setSignals({ dataTerminalReady: false, requestToSend: false }); } catch {}
      try { await p.close(); } catch (e) { console.warn("serial close:", e); }
    }
    this.emit("link", { connected: false, why });
  }

  // Device gone (unplugged, read error): clean up the same way.
  lost(why) {
    if (!this.connected) return;
    this.close(why);
  }

  async readLoop(port) {
    const dec = new TextDecoder();
    let pend = "";
    const reader = this.reader = port.readable.getReader();
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        pend += dec.decode(value, { stream: true });
        let i;
        while ((i = pend.indexOf("\n")) >= 0) {
          const line = pend.slice(0, i).trim();
          pend = pend.slice(i + 1);
          if (line && this.port === port) this.handle(line);
        }
      }
    } catch { /* device lost or cancelled */ } finally {
      try { reader.releaseLock(); } catch {}
      if (this.reader === reader) this.reader = null;
    }
    if (this.port === port) this.lost("read ended");
  }

  handle(line) {
    let m;
    try { m = JSON.parse(line); } catch { this.emit("raw", { line }); return; }
    if (m.t === "set" && this.listBuf) { this.listBuf.push(m); return; }
    if ("r" in m && this.waiting.has(m.r)) {
      const w = this.waiting.get(m.r);
      this.waiting.delete(m.r);
      clearTimeout(w.timer);
      if (w.list) { m.items = this.listBuf; this.listBuf = null; }
      m.ok ? w.resolve(m) : w.reject(Object.assign(new Error(m.err || "refused"), { reply: m }));
      this.emit("reply", { cmd: w.cmd, reply: m });
      return;
    }
    if (m.t === "st") this.emit("status", m);
    else if (m.t === "ev") this.emit("event", m);
    else if (m.t === "tr") this.emit("trace", m);
    else if (m.t === "hello") this.emit("hello", m);
    else this.emit("other", m);
  }

  // Send one command line; resolves with the JSON reply, rejects with its "err".
  cmd(text, timeoutMs = 3000) {
    if (!this.connected || !this.writer) return Promise.reject(new Error("control box not connected"));
    const id = this.nextId++;
    const isList = /^list\b/.test(text);
    if (isList) this.listBuf = [];
    const p = new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.waiting.delete(id); reject(new Error("no reply")); }, isList ? 15000 : timeoutMs);
      this.waiting.set(id, { resolve, reject, timer, cmd: text, list: isList });
    });
    this.writer.write(new TextEncoder().encode(`#${id} ${text}\n`)).catch(() => this.lost("write failed"));
    this.emit("sent", { text });
    return p;
  }

  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }
}
