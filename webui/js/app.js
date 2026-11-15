(() => {
// LEO 438VP operator page: control box over Web Serial, OBI imaging through the bridge (worker),
// WebGL display, and the developer tools.

const $ = (id) => document.getElementById(id);
const box = new Teensy();
const viewer = new Viewer($("canvas"));
// The worker is built from in-page code (obi-worker.js defines obiWorkerMain), so it also runs
// when the page is opened straight from disk, where file-based workers are blocked.
const worker = new Worker(URL.createObjectURL(new Blob([`(${obiWorkerMain.toString()})();`], { type: "text/javascript" })));
let st = null;                 // last status from the box
let lastFrame = null;          // {w,h,bits,data}
let live = false, capturing = false, resumeLive = false;
let obiState = { bridge: false, obi: false, demo: false };

// ---------------------------------------------------------------- preferences (this browser)
const PREF_DEFAULTS = { res: "512x512", speed: "500", photo: "2048x1536", photoDwell: "4000", histLo: 0, histHi: 1,
  dwellUnit: 125, bits: 8, hfw1: 110, focusStep: 2, stigStep: 8, ctrX: 1, ctrY: 1, extCtrl: false, demo: false, scanExt: true, jog: "0.1" };
const prefs = Object.assign({}, PREF_DEFAULTS, (() => { try { return JSON.parse(localStorage.getItem("leo.prefs") || "{}"); } catch { return {}; } })());
const savePrefs = () => { try { localStorage.setItem("leo.prefs", JSON.stringify(prefs)); } catch {} };

// ---------------------------------------------------------------- small helpers
function toast(msg, info = false) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast show" + (info ? " info" : "");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (t.className = "toast"), 4000);
}
async function send(cmd, quiet = false) {
  try { return await box.cmd(cmd); }
  catch (e) { if (!quiet) toast(e.message); throw e; }
}
const sendQ = (cmd) => send(cmd).catch(() => {});

// Coalesce fast-changing controls (sliders, wheel): latest value goes out at most every 60 ms.
const coalesce = {};
function sendLatest(key, cmd) {
  const c = coalesce[key] || (coalesce[key] = { busy: false, next: null });
  c.next = cmd;
  if (c.busy) return;
  const run = async () => {
    if (!c.next) { c.busy = false; return; }
    const x = c.next; c.next = null; c.busy = true;
    await box.cmd(x).catch((e) => toast(e.message));
    setTimeout(run, 60);
  };
  run();
}

// Inputs the operator is editing are not overwritten by telemetry for a moment.
const editing = new Map();
function touch(el) { editing.set(el, performance.now()); }
function setVal(el, v, digits) {
  if (!el || v === undefined || v === null) return;
  if (document.activeElement === el || performance.now() - (editing.get(el) || 0) < 2500) return;
  el.value = digits === undefined ? v : Number(v).toFixed(digits);
}
function stateClass(el, cls, text) { el.className = "state " + cls; el.textContent = text; }
function chip(el, cls) { el.classList.remove("ok", "warn", "bad"); if (cls) el.classList.add(cls); }
function fmtTorr(t) {
  if (t === null || t === undefined) return "–";
  const e = Math.floor(Math.log10(t)), m = t / 10 ** e;
  return `${m.toFixed(1)}e${e} Torr`;
}
function fmtLen(mm) {
  if (mm >= 1) return `${+mm.toPrecision(3)} mm`;
  if (mm >= 1e-3) return `${+(mm * 1e3).toPrecision(3)} µm`;
  return `${+(mm * 1e6).toPrecision(3)} nm`;
}
function fmtMag(m) { return m >= 1000 ? `${+(m / 1000).toPrecision(3)} kx` : `${Math.round(m)} x`; }
async function confirmDlg(title, text, okText = "Confirm") {
  $("dlgTitle").textContent = title; $("dlgText").textContent = text; $("dlgOk").textContent = okText;
  $("dlg").showModal();
  return new Promise((res) => $("dlg").addEventListener("close", () => res($("dlg").returnValue === "ok"), { once: true }));
}

// ---------------------------------------------------------------- control box connection
$("btnBox").onclick = async () => {
  if (!box.supported) { toast("This browser has no Web Serial: use Chrome or Edge"); return; }
  if (box.connected) { if (await confirmDlg("Disconnect the control box?", "The microscope keeps running; only this page stops watching it.", "Disconnect")) box.close(); return; }
  try { await box.choose(); } catch (e) { if (e.name !== "NotFoundError") toast(e.message); }
};
box.addEventListener("link", (e) => {
  chip($("btnBox"), e.detail.connected ? "ok" : "bad");
  $("lastEvent").textContent = e.detail.connected ? "Control box connected" : "Control box not connected";
  if (e.detail.connected) onBoxConnected();
  else { st = null; render(); }
});
async function onBoxConnected() {
  try {
    const g = await box.cmd("get stg.joy_gain");
    $("slJoy").value = Math.log2(g.value);
    for (const [id, name] of [["inShX", "op.shift_x"], ["inShY", "op.shift_y"]]) $(id).value = (await box.cmd(`get ${name}`)).value;
  } catch {}
  if (!$("dev").hidden) loadSettings();
}
box.addEventListener("status", (e) => { st = e.detail; render(); if (!$("dev").hidden && devTab === "status") $("statusJson").textContent = JSON.stringify(st, null, 2); });
box.addEventListener("event", (e) => {
  const m = e.detail;
  $("lastEvent").textContent = `${new Date((m.rtc || 0) * 1000 || Date.now()).toLocaleTimeString()}  ${m.src}: ${m.msg}`;
  $("eventbar").className = "eventbar " + (m.lvl === "fault" ? "fault" : m.lvl === "warn" ? "warn" : "");
  if (m.lvl === "fault") toast(m.msg);
  if ($("trEvents").checked) trafficLine(`[${m.lvl}] ${m.src}: ${m.msg}`, m.lvl === "info" || m.lvl === "debug" ? "ev" : m.lvl);
});
box.addEventListener("trace", (e) => { const m = e.detail; trafficLine(`${m.l.padEnd(3)} ${m.d} ${m.s}`, m.l); });
box.addEventListener("sent", (e) => { if ($("trUsb").checked) trafficLine(`usb > ${e.detail.text}`, "usb"); });
box.addEventListener("reply", (e) => { if ($("trUsb").checked) trafficLine(`usb < ${JSON.stringify(e.detail.reply)}`, "rep"); });

// ---------------------------------------------------------------- status rendering
function render() {
  const on = !!st;
  for (const b of document.querySelectorAll(".sidebar button, .sidebar input, .sidebar select, .detbar input")) if (b.id !== "btnStopAll") b.disabled = !on;
  if (!st) {
    for (const id of ["chipVacTxt", "chipBeamTxt", "chipModeTxt"]) $(id).textContent = "–";
    for (const id of ["chipVac", "chipBeam"]) chip($(id), null);
    $("activity").textContent = box.connected ? "" : "Connect the control box (button at the top right)";
    return;
  }
  const { vac, vp, eht, stg, eo, sys } = st;

  // App bar
  const vsys = vacSystemState(st);
  const vacTxt = vsys.text;
  $("chipVacTxt").textContent = vacTxt;
  chip($("chipVac"), vsys.cls === "ok" ? "ok" : vsys.cls === "bad" ? "bad" : "warn");
  const beamTxt = { on: `On · ${(+eht.kv).toFixed(1)} kV`, off: "Off", cooling: "Off · cooling", starting: "Starting", stopping: "Stopping", eht_off: "EHT off · fil. lit" }[eht.beam] || eht.beam;
  $("chipBeamTxt").textContent = beamTxt;
  chip($("chipBeam"), eht.beam === "on" ? "ok" : eht.beam === "off" ? null : "warn");
  const inVp = vp.link && vp.st >= 7 && vp.st <= 11;
  $("chipModeTxt").textContent = !vp.link ? "VP ?" : inVp ? `VP ${Math.round(vp.pa)} Pa` : "High vacuum";
  $("activity").textContent = sys.act || eht.act || "";

  // Vacuum card
  stateClass($("vacState"), !vac.link ? "bad" : inVp ? "warn" : "", !vac.link ? "No link" : inVp ? "VP mode" : vac.st === "NSP" ? "At air" : "HV mode");
  $("vacSys").className = "vacsys " + vsys.cls + (vsys.busy ? " busy" : "");
  $("vacSysTxt").textContent = vsys.text;
  $("vacSysSub").textContent = vsys.sub;
  // Column: Penning (stage/vacuum controller). Chamber: Pirani on the VP controller, shown at all times.
  $("vacPress").textContent = !vac.link ? "–" : vac.torr !== null ? fmtTorr(vac.torr) : vac.st === "NSP" ? "Atmosphere" : "gauge off";
  $("vacPressSub").textContent = vac.link ? `Penning · raw ${vac.raw}` : "Penning · no link";
  $("vpPress").textContent = !vp.link ? "–" : fmtPa(vp.pa, vp.gauge);
  $("vpPressSub").textContent = vp.link ? `Pirani · ${vp.gauge} counts` : "Pirani · no link";
  $("btnPump").disabled = !(vac.link && vac.st === "NSP" && sys.op === "none");
  $("btnVent").disabled = !(vac.link && vac.st !== "NSP" && vac.st !== "WVT" && (sys.op === "none" || sys.op === "pump"));
  for (const b of $("segVp").children) {
    b.classList.toggle("on", (b.dataset.vp === "vp") === inVp);
    b.disabled = !vp.hs || !vac.ready || sys.op !== "none";
  }
  setVal($("inVpPa"), vp.tgt);

  // Beam card
  const bb = $("btnBeam");
  const busy = eht.beam === "starting" || eht.beam === "stopping";
  bb.textContent = eht.beam === "on" ? "Beam off" : eht.beam === "starting" ? "Starting…  (click to stop)" : eht.beam === "stopping" ? "Stopping…" : "Beam on";
  bb.className = "beam" + (eht.beam === "on" ? " off" : "") + (busy ? " busy" : "");
  bb.disabled = eht.beam === "stopping";
  $("beamProg").classList.toggle("on", busy || (sys.op !== "none" && sys.op !== "pump"));
  stateClass($("beamState"), eht.beam === "on" ? "ok" : !eht.link ? "bad" : eht.beam === "off" ? "" : "warn",
    !eht.link ? "No link" : eht.beam === "cooling" ? `Cooling ${Math.ceil(eht.cool)} s` : beamTxt);
  setVal($("inKv"), eht.kvset, 1);
  setVal($("inEmis"), eht.emis);
  setVal($("inFil"), eht.filset);
  setVal($("inColl"), eht.coll);
  $("filNow").textContent = eht.beam !== "off" && eht.beam !== "cooling" ? `now ${eht.fil} mA` : "";
  for (const b of $("kvPresets").children) b.classList.toggle("on", +b.dataset.kv === +eht.kvset);

  // Image card
  stateClass($("eoState"), eo.link ? "ok" : "warn", eo.link ? `${eo.mode} scan` : "EO link ?");
  setVal($("inMag"), Math.round(eo.mag));
  setVal($("slFocus"), Math.round(eo.focus)); $("oFocus").textContent = Math.round(eo.focus);
  setVal($("slStigX"), eo.stigx); $("oStigX").textContent = eo.stigx;
  setVal($("slStigY"), eo.stigy); $("oStigY").textContent = eo.stigy;
  setVal($("slPmt"), eht.pm1); setVal($("inPmt"), eht.pm1);
  $("btnWobble").classList.toggle("on", eo.wob > 0);
  setVal($("inRot"), eo.rot); setVal($("inWd"), eo.wd); setVal($("inTilt"), eo.tilt);

  // Stage card
  for (let a = 0; a < 5; a++) $("ax" + a).textContent = stg.valid && stg.pos[a] !== null ? stg.pos[a].toFixed(a < 3 ? 3 : 2) : "–";
  stateClass($("stgState"), !vac.link ? "bad" : stg.homing ? "warn" : stg.homed ? (stg.lim ? "warn" : "ok") : "warn",
    !vac.link ? "No link" : stg.homing ? "Initialising" : !stg.homed ? "Not initialised" : stg.lim ? "On limit" : stg.mv ? "Moving" : "Ready");

  updateDatabar();
  if (obiState.demo) worker.postMessage({ type: "config", cfg: liveCfg() });
}

// One plain-language state for the whole vacuum system: stage/vacuum controller state,
// VP controller state and the running sequence combined.
function vacSystemState(s) {
  const { vac, vp, sys } = s;
  const vpName = vp.link ? `VP controller: ${vp.name} (${vp.st})` : "VP controller: no link";
  const R = (text, cls, sub = vpName, busy = false) => ({ text, cls, sub, busy });
  if (!vac.link) return R("No link", "bad", "Stage/vacuum controller not answering");
  if (!vac.cfg) return R("Starting up", "warn", "Configuring the stage/vacuum controller", true);
  // A sequence that is still taking the beam off / cooling the filament comes first.
  const act = sys.act || "";
  if (sys.op === "vent" && vac.st !== "WVT" && vac.st !== "NSP") return R("Preparing to vent", "warn", act, true);
  if (sys.op === "vp_enter" && !(vp.st >= 7)) return R("Preparing for VP", "warn", act, true);
  if (sys.op === "vp_exit" && !(vp.st >= 10 || vp.st === 4)) return R("Preparing for HV", "warn", act, true);
  if (sys.op === "vp_target" && vp.st === 9) return R("Changing VP pressure", "warn", act, true);
  switch (vac.st) {
    case "WVT": return R("Venting", "warn", "Vent valve open", true);
    case "NSP": return R("Vented (idle)", "", "Chamber at air");
    case "WTUS": return R("Pumping", "warn", "Waiting for turbo speed", true);
    case "WP": return R("Pumping", "warn", "Waiting for the Penning gauge", true);
    case "SP": return R("Pumping", "warn", "Penning reading, not yet ready", true);
    case "SPE": return R("Gauge error", "bad", "Penning gauge error");
  }
  if (vac.st !== "SPVR") return R(vac.txt, "warn");
  if (!vp.link) return R("HV ready", "ok", vpName);
  switch (vp.st) {
    case 7: case 8: return R("Going to VP", "warn", `${vpName} · target ${vp.tgt} Pa`, true);
    case 9: return R("VP ready", "ok", `${vpName} · target ${vp.tgt} Pa`);
    case 10: case 11: case 4: return R("Going to HV", "warn", vpName, true);
    case 0: return R("HV ready", "warn", "VP controller in POWER_UP: handshaking");
    default: return R("HV ready", "ok", vpName);
  }
}

// Chamber pressure from the Pirani: ~0 Pa below its range (high vacuum), capped at the top of the table at air.
function fmtPa(pa, counts) {
  if (counts >= 1880) return "Atmosphere";
  if (pa < 1) return "< 1 Pa";
  return pa < 10 ? `${pa.toFixed(1)} Pa` : `${Math.round(pa)} Pa`;
}

function hfwMm() { return (st ? prefs.hfw1 / st.eo.mag : NaN); }
function updateDatabar() {
  const hfw = hfwMm();
  $("dbHfw").textContent = isFinite(hfw) ? fmtLen(hfw) : "–";
  $("dbMag").textContent = st ? fmtMag(st.eo.mag) : "–";
  $("dbKv").textContent = st ? `${(+st.eht.kvset).toFixed(1)} kV` : "–";
  $("dbWd").textContent = st ? `${st.eo.wd} mm` : "–";
  $("dbVac").textContent = st ? (st.vp.link && st.vp.st >= 7 && st.vp.st <= 11 ? `VP ${Math.round(st.vp.pa)} Pa` : st.vac.torr ? fmtTorr(st.vac.torr) : st.vac.txt) : "–";
  $("dbDwell").textContent = `${(+prefs.speed / 1000).toPrecision(2)} µs`;
  $("dbPix").textContent = lastFrame ? `${lastFrame.w}×${lastFrame.h}` : prefs.res.replace("x", "×");
  $("dbDate").textContent = new Date().toLocaleDateString();
  drawScalebar();
}

function drawScalebar() {
  const sb = $("scalebar");
  const hfw = hfwMm();
  if (!lastFrame || !isFinite(hfw)) { sb.style.display = "none"; return; }
  const r = viewer.imageRect();
  const target = hfw * 0.2, p = 10 ** Math.floor(Math.log10(target));
  const nice = [1, 2, 5].map(k => k * p).filter(v => v <= target).pop() || p;
  sb.style.display = "flex";
  sb.querySelector(".bar").style.width = `${(nice / hfw) * r.w}px`;
  sb.querySelector("span").textContent = fmtLen(nice);
  sb.style.left = `${r.x + 16}px`;
  sb.style.top = `${r.y + r.h - 40}px`;
}
addEventListener("resize", drawScalebar);
setInterval(() => { $("clock").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }, 1000);

// ---------------------------------------------------------------- operator controls
$("btnPump").onclick = () => sendQ("pump");
$("btnVent").onclick = async () => {
  if (await confirmDlg("Vent the chamber?", "The beam goes off and the filament cools first, the stage lowers Z, then the chamber vents.", "Vent")) sendQ("vent");
};
for (const b of $("segVp").children) b.onclick = async () => {
  const wantVp = b.dataset.vp === "vp";
  const inVp = st && st.vp.st >= 7 && st.vp.st <= 11;
  if (wantVp === inVp) return;
  if (wantVp) {
    const pa = +$("inVpPa").value || st.vp.tgt;
    if (await confirmDlg("Enter variable pressure?", `Target ${pa} Pa. The beam goes off and the filament cools first.`, "Enter VP")) sendQ(`vp enter ${pa}`);
  } else if (await confirmDlg("Return to high vacuum?", "The beam goes off and the filament cools first.", "High vacuum")) sendQ("vp exit");
};
$("inVpPa").onchange = (e) => { touch(e.target); sendQ(`vp target ${e.target.value}`); };
$("btnBeam").onclick = () => {
  if (!st) return;
  const b = st.eht.beam;
  sendQ(b === "on" || b === "starting" || b === "eht_off" ? "beam off" : "beam on");
};
const numCmd = { inKv: "kv", inEmis: "emis", inFil: "fil", inColl: "coll", inMag: "mag", inRot: "rot", inWd: "wd", inTilt: "tilt" };
for (const [id, cmd] of Object.entries(numCmd)) $(id).onchange = (e) => { touch(e.target); sendQ(`${cmd} ${e.target.value}`); };
for (const b of document.querySelectorAll(".num .step")) b.onclick = () => {
  const inp = $(b.dataset.for);
  const v = b.dataset.mul ? +inp.value * +b.dataset.mul : +inp.value + +b.dataset.step * (+inp.step || 1);
  inp.value = +Math.min(+inp.max, Math.max(+inp.min, v)).toFixed(3);
  inp.dispatchEvent(new Event("change"));
};
for (const b of $("kvPresets").children) b.onclick = () => { $("inKv").value = b.dataset.kv; touch($("inKv")); sendQ(`kv ${b.dataset.kv}`); };
const shift = () => { touch($("inShX")); touch($("inShY")); sendQ(`shift ${$("inShX").value || 0} ${$("inShY").value || 0}`); };
$("inShX").onchange = shift; $("inShY").onchange = shift;

function sliderTo(id, out, fn) {
  $(id).oninput = (e) => { touch(e.target); $(out).textContent = e.target.value; fn(e.target.value); };
}
sliderTo("slFocus", "oFocus", (v) => sendLatest("focus", `focus ${v}`));
sliderTo("slStigX", "oStigX", () => sendLatest("stig", `stig ${$("slStigX").value} ${$("slStigY").value}`));
sliderTo("slStigY", "oStigY", () => sendLatest("stig", `stig ${$("slStigX").value} ${$("slStigY").value}`));
// PMT voltage ("brightness" in LEO-32): PM HV channel 1 on the EHT set (.1 command), via the box's "bright".
$("slPmt").oninput = (e) => { touch(e.target); touch($("inPmt")); $("inPmt").value = e.target.value; sendLatest("bright", `bright ${e.target.value}`); };
$("inPmt").onchange = (e) => { touch(e.target); touch($("slPmt")); $("slPmt").value = e.target.value; sendQ(`bright ${e.target.value}`); };
$("btnWobble").onclick = () => sendQ(`wobble ${st && st.eo.wob > 0 ? 0 : 50}`);
$("btnStigReset").onclick = () => sendQ("stig 2048 2048");

// Stage
$("selJog").value = prefs.jog;
$("selJog").onchange = (e) => { prefs.jog = e.target.value; savePrefs(); };
for (const b of document.querySelectorAll("[data-jog]")) b.onclick = () => {
  const [dx, dy] = b.dataset.jog.split(",").map(Number), s = +$("selJog").value;
  sendQ(`stage move ${dx * s} ${dy * s}`);
};
$("btnStageStop").onclick = () => sendQ("stage stop");
$("btnHome").onclick = async () => { if (await confirmDlg("Initialise the stage?", "Each axis drives to its home switch (Z first), then to the start position.", "Initialise")) sendQ("stage home"); };
$("btnGoto").onclick = () => {
  const v = ["gX", "gY", "gZ", "gT", "gR"].map(id => $(id).value.trim() === "" ? "-" : $(id).value);
  sendQ(`stage goto ${v.join(" ")}`);
};
$("slJoy").oninput = (e) => sendLatest("joy", `set stg.joy_gain ${(2 ** +e.target.value).toFixed(3)}`);

// STOP: button and Escape
const stopAll = () => { sendQ("safe"); toast("STOP: beam off, stage stopped, sequences aborted", true); };
$("btnStopAll").onclick = stopAll;
addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("dlg").open) stopAll();
});

// ---------------------------------------------------------------- imaging
const parseRes = (s) => s.split("x").map(Number);
function liveCfg() {
  const [w, h] = parseRes(prefs.res);
  return { w, h, bits: +prefs.bits, dwellNs: +prefs.speed, dwellUnitNs: +prefs.dwellUnit, extCtrl: prefs.extCtrl,
           mag: st ? st.eo.mag : 100, focus: st ? st.eo.focus : 2234 };
}
$("selRes").value = prefs.res; $("selSpeed").value = prefs.speed; $("selPhoto").value = prefs.photo; $("selPhotoDwell").value = prefs.photoDwell;
for (const [id, key] of [["selRes", "res"], ["selSpeed", "speed"], ["selPhoto", "photo"], ["selPhotoDwell", "photoDwell"]])
  $(id).onchange = (e) => { prefs[key] = e.target.value; savePrefs(); worker.postMessage({ type: "config", cfg: liveCfg() }); updateDatabar(); };

async function startLive() {
  if (prefs.scanExt && st && st.eo.mode !== "external") await send("scan ext").catch(() => {});
  live = true;
  worker.postMessage({ type: "start", cfg: liveCfg() });
  updateScanButtons();
}
function stopLive() { live = false; worker.postMessage({ type: "stop" }); updateScanButtons(); }
function updateScanButtons() {
  $("btnLive").classList.toggle("on", live); $("btnFreeze").classList.toggle("on", !live);
  $("emptyMsg").innerHTML = obiState.demo ? "Demo image source: press <b>Live</b>." :
    !obiState.bridge ? "Start <code>python webui/bridge.py</code> (it relays the OBI data to this page)." :
    !obiState.obi ? "Bridge running; waiting for the OBI applet (TCP 2224)." : "Press <b>Live</b> to start scanning.";
}
$("btnLive").onclick = startLive;
$("btnFreeze").onclick = stopLive;
$("btnCapture").onclick = () => {
  if (capturing) return;
  const [w, h] = parseRes(prefs.photo);
  capturing = true; resumeLive = live;
  if (live) stopLive();
  $("btnCapture").textContent = "◉ Capturing…";
  worker.postMessage({ type: "single", cfg: { w, h, bits: 16, dwellNs: +prefs.photoDwell, dwellUnitNs: +prefs.dwellUnit, mag: st ? st.eo.mag : 100, focus: st ? st.eo.focus : 2234 } });
};

// ---------------------------------------------------------------- histogram and black / white levels
// Raw detector values over the full 16-bit range (8-bit frames are placed at value * 256).
// The two lines are the black and white levels, as fractions of full scale; they set the
// display window and are applied to saved images.
const hist = { lo: +prefs.histLo, hi: +prefs.histHi, bins: new Float32Array(256), drag: null };
const HIST_MIN_GAP = 1 / 256;

function computeHist(f) {
  const a = f.bits === 16 ? new Uint16Array(f.data) : new Uint8Array(f.data);
  const shift = f.bits === 16 ? 8 : 0, b = new Uint32Array(256);
  const stride = Math.max(1, Math.floor(a.length / 262144));
  for (let i = 0; i < a.length; i += stride) b[a[i] >> shift]++;
  let max = 1;
  for (let i = 0; i < 256; i++) if (b[i] > max) max = b[i];
  for (let i = 0; i < 256; i++) hist.bins[i] = Math.sqrt(b[i] / max);   // sqrt keeps small peaks visible
}

function drawHist() {
  const c = $("hist"), dpr = devicePixelRatio || 1;
  const W = Math.round(c.clientWidth * dpr), H = Math.round(c.clientHeight * dpr);
  if (!W || !H) return;
  if (c.width !== W || c.height !== H) { c.width = W; c.height = H; }
  const g = c.getContext("2d");
  g.clearRect(0, 0, W, H);
  const x0 = hist.lo * W, x1 = hist.hi * W;
  g.fillStyle = "rgba(56, 189, 248, 0.13)";
  g.fillRect(x0, 0, x1 - x0, H);
  g.fillStyle = "#8592a3";
  const bw = W / 256;
  for (let i = 0; i < 256; i++) {
    const h = hist.bins[i] * (H - 4);
    if (h > 0) g.fillRect(i * bw, H - h, Math.max(1, bw - 0.5 * dpr), h);
  }
  g.fillStyle = "#38bdf8";
  for (const x of [x0, x1]) g.fillRect(Math.round(x - dpr), 0, 2 * dpr, H);
  g.beginPath();                                       // grab handles at the top of each line
  for (const x of [x0, x1]) { g.moveTo(x - 5 * dpr, 0); g.lineTo(x + 5 * dpr, 0); g.lineTo(x, 7 * dpr); }
  g.fill();
}

function applyLevels(save) {
  viewer.setWindow(hist.lo, hist.hi);
  drawHist();
  if (save) { prefs.histLo = hist.lo; prefs.histHi = hist.hi; savePrefs(); }
}

{
  const c = $("hist");
  const frac = (e) => { const r = c.getBoundingClientRect(); return Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)); };
  const near = (e) => {
    const r = c.getBoundingClientRect(), px = e.clientX - r.left;
    const d0 = Math.abs(px - hist.lo * r.width), d1 = Math.abs(px - hist.hi * r.width);
    if (Math.min(d0, d1) <= 7) return d0 <= d1 ? "lo" : "hi";
    const f = frac(e);
    return f > hist.lo && f < hist.hi ? "both" : null;
  };
  c.addEventListener("pointermove", (e) => {
    if (!hist.drag) { const n = near(e); c.style.cursor = n === "both" ? "grab" : n ? "ew-resize" : "default"; return; }
    const f = frac(e);
    if (hist.drag.what === "lo") hist.lo = Math.min(f, hist.hi - HIST_MIN_GAP);
    else if (hist.drag.what === "hi") hist.hi = Math.max(f, hist.lo + HIST_MIN_GAP);
    else {
      const w = hist.drag.hi - hist.drag.lo;
      const lo = Math.min(1 - w, Math.max(0, hist.drag.lo + f - hist.drag.f));
      hist.lo = lo; hist.hi = lo + w;
    }
    applyLevels(false);
  });
  c.addEventListener("pointerdown", (e) => {
    const what = near(e);
    if (!what) return;
    hist.drag = { what, f: frac(e), lo: hist.lo, hi: hist.hi };
    c.setPointerCapture(e.pointerId);
    if (what === "both") c.style.cursor = "grabbing";
  });
  const end = () => { if (hist.drag) { hist.drag = null; applyLevels(true); } };
  c.addEventListener("pointerup", end);
  c.addEventListener("pointercancel", end);
  new ResizeObserver(drawHist).observe(c);
}
applyLevels(false);

// Black / white levels applied to the pixel data of a saved image (same mapping as the display).
function levelled(data, bits) {
  const max = bits === 16 ? 65535 : 255;
  const src = bits === 16 ? new Uint16Array(data) : new Uint8Array(data);
  const out = bits === 16 ? new Uint16Array(src.length) : new Uint8Array(src.length);
  const lo = hist.lo * max, k = max / Math.max((hist.hi - hist.lo) * max, 1e-9);
  for (let i = 0; i < src.length; i++) { const v = (src[i] - lo) * k; out[i] = v <= 0 ? 0 : v >= max ? max : v + 0.5; }
  return out.buffer;
}

let fpsCount = 0;
worker.onmessage = async (ev) => {
  const m = ev.data;
  if (m.type === "frame") {
    lastFrame = { w: m.w, h: m.h, bits: m.bits, data: m.data };
    viewer.setFrame(m.w, m.h, m.bits, m.data);
    computeHist(lastFrame);
    drawHist();
    $("empty").style.display = "none";
    fpsCount++;
    $("obiLast").textContent = `${m.w}×${m.h}, ${m.bits} bit, ${m.ms.toFixed(0)} ms`;
    updateDatabar();
    if (m.single) await saveCapture(m);
  } else if (m.type === "single-failed") {
    capturing = false; $("btnCapture").textContent = "◉ Capture"; toast("Capture failed: OBI connection lost");
  } else if (m.type === "status") {
    obiState = { bridge: m.bridge, obi: m.obi, demo: !!m.demo || prefs.demo };
    chip($("lnkObi"), obiState.demo ? "warn" : m.obi ? "ok" : m.bridge ? "warn" : "bad");
    $("lnkObi").lastChild.textContent = obiState.demo ? "OBI (demo)" : "OBI";
    $("obiBridge").textContent = obiState.demo ? "demo source" : m.bridge ? "connected" : "not running";
    $("obiApplet").textContent = obiState.demo ? "–" : m.obi ? `connected ${m.msg || ""}` : (m.msg || "not connected");
    updateScanButtons();
  } else if (m.type === "stats") {
    $("obiFps").textContent = m.fps.toFixed(1); $("obiRate").textContent = `${m.mbps.toFixed(1)} MB/s`; $("obiResync").textContent = m.resyncs;
    $("dbFps").textContent = live ? `${m.fps.toFixed(1)} fps` : "frozen";
  } else if (m.type === "log") {
    trafficLine(`obi ${m.msg}`, m.lvl === "warn" ? "warn" : "ev");
  }
};

async function saveCapture(m) {
  capturing = false;
  $("btnCapture").textContent = "◉ Capture";
  const t = new Date();
  const meta = {
    instrument: "LEO 438VP", date: t.toISOString(), width: m.w, height: m.h, bits: m.bits,
    dwell_ns: m.meta.dwellNs, hfw_mm: hfwMm(), pixel_nm: (hfwMm() / m.w) * 1e6,
    kv: st?.eht.kvset, emission_ua: st?.eht.emis, mag: st?.eo.mag, wd_mm: st?.eo.wd, rotation_deg: st?.eo.rot,
    focus: st?.eo.focus, stig: [st?.eo.stigx, st?.eo.stigy], pmt_voltage: st?.eht.pm1,
    vacuum: st?.vac.st, pressure_torr: st?.vac.torr, vp_pa: st && st.vp.st >= 7 && st.vp.st <= 11 ? st.vp.pa : null,
    stage_mm_deg: st?.stg.pos, collector_v: st?.eht.coll, demo: !!m.demo,
    black_level_16bit: Math.round(hist.lo * 65535), white_level_16bit: Math.round(hist.hi * 65535),
  };
  const desc = Object.entries(meta).map(([k, v]) => `${k}=${Array.isArray(v) ? v.join(",") : v}`).join("\n");
  const blob = encodeTiff(m.w, m.h, m.bits, levelled(m.data, m.bits), desc);
  const name = `LEO_${t.toISOString().slice(0, 19).replace(/[:T]/g, "-")}_${fmtMag(st ? st.eo.mag : 0).replace(" ", "")}.tif`;
  try {
    if (window.showSaveFilePicker) {
      const h = await showSaveFilePicker({ suggestedName: name, types: [{ description: "TIFF image", accept: { "image/tiff": [".tif"] } }] });
      const w = await h.createWritable(); await w.write(blob); await w.close();
    } else {
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    }
    toast(`Saved ${name}`, true);
  } catch (e) { if (e.name !== "AbortError") toast(e.message); }
  if (resumeLive) startLive();
}

// Mouse on the image: wheel = focus, Ctrl = magnification, Alt / Shift = stigmator X / Y; double-click = centre.
$("viewport").addEventListener("wheel", (e) => {
  if (!st) return;
  e.preventDefault();
  const n = e.deltaY < 0 ? 1 : -1;
  if (e.ctrlKey) {
    const mag = Math.round(st.eo.mag * (n > 0 ? 1.15 : 1 / 1.15));
    st.eo.mag = mag; setVal($("inMag"), mag); sendLatest("mag", `mag ${mag}`); updateDatabar();
  } else if (e.altKey || e.shiftKey) {
    const k = e.altKey ? "stigx" : "stigy";
    st.eo[k] = Math.max(0, Math.min(4095, st.eo[k] + n * +prefs.stigStep));
    sendLatest("stig", `stig ${st.eo.stigx} ${st.eo.stigy}`);
  } else {
    // Coarser steps at low magnification, one count at high magnification.
    const step = Math.max(1, Math.round(+prefs.focusStep * Math.sqrt(100 / Math.max(st.eo.mag, 1))));
    st.eo.focus = Math.max(0, Math.min(4095, st.eo.focus + n * step));
    $("oFocus").textContent = Math.round(st.eo.focus);
    sendLatest("focus", `focus ${Math.round(st.eo.focus)}`);
  }
}, { passive: false });
$("viewport").addEventListener("dblclick", (e) => {
  if (!st || !lastFrame) return;
  const r = viewer.imageRect(), b = $("canvas").getBoundingClientRect();
  const fx = (e.clientX - b.left - r.x) / r.w - 0.5, fy = (e.clientY - b.top - r.y) / r.h - 0.5;
  if (Math.abs(fx) > 0.5 || Math.abs(fy) > 0.5) return;
  const hfw = hfwMm(), dx = fx * hfw * +prefs.ctrX, dy = fy * hfw * (lastFrame.h / lastFrame.w) * +prefs.ctrY;
  const ch = $("crosshair");
  ch.style.display = "block"; ch.style.left = `${e.clientX - b.left - 11}px`; ch.style.top = `${e.clientY - b.top - 11}px`;
  setTimeout(() => (ch.style.display = "none"), 800);
  sendQ(`stage move ${dx.toFixed(4)} ${(-dy).toFixed(4)}`);
});

// ---------------------------------------------------------------- developer section
let devTab = "settings";
$("btnDevJump").onclick = () => { $("dev").hidden = false; $("dev").scrollIntoView({ behavior: "smooth" }); if (devTab === "settings" && !settings.length) loadSettings(); };
$("btnDevClose").onclick = () => { $("dev").hidden = true; scrollTo({ top: 0, behavior: "smooth" }); };
$("eventbar").onclick = () => { $("btnDevJump").onclick(); selectTab("traffic"); };
function selectTab(t) {
  devTab = t;
  for (const b of $("devTabs").children) b.classList.toggle("on", b.dataset.tab === t);
  for (const d of document.querySelectorAll(".dev .tab")) d.hidden = d.dataset.tab !== t;
  if (t === "settings" && !settings.length) loadSettings();
  if (t === "status") $("statusJson").textContent = st ? JSON.stringify(st, null, 2) : "Not connected";
}
for (const b of $("devTabs").children) b.onclick = () => selectTab(b.dataset.tab);

// Settings table
let settings = [];
async function loadSettings() {
  if (!box.connected) { $("setCount").textContent = "Connect the control box to load its settings."; return; }
  $("setCount").textContent = "Loading…";
  try {
    const r = await box.cmd("list");
    settings = r.items || [];
    const groups = [...new Set(settings.map(s => s.name.split(".")[0]))];
    $("setGroup").innerHTML = `<option value="">All groups</option>` + groups.map(g => `<option>${g}</option>`).join("");
    drawSettings();
  } catch (e) { $("setCount").textContent = "Could not load: " + e.message; }
}
function fmtNum(v) { return typeof v === "number" ? +v.toPrecision(7) : v; }
function drawSettings() {
  const f = $("setFilter").value.trim().toLowerCase(), g = $("setGroup").value, ch = $("setChanged").checked;
  const rows = settings.filter(s => (!g || s.name.startsWith(g + ".")) && (!f || s.name.toLowerCase().includes(f) || s.desc.toLowerCase().includes(f)) && (!ch || s.value !== s.def));
  const tb = $("setTable").tBodies[0];
  tb.innerHTML = "";
  let lastG = null;
  for (const s of rows) {
    const grp = s.name.split(".")[0];
    if (grp !== lastG) { lastG = grp; const tr = tb.insertRow(); tr.className = "group"; const td = tr.insertCell(); td.colSpan = 7; td.textContent = grp; }
    const tr = tb.insertRow();
    tr.className = s.value !== s.def ? "changed" : "";
    const ro = s.flags & 2;
    tr.innerHTML = `<td></td><td><input type="number" step="any"></td><td class="def"></td><td class="rng"></td><td class="def"></td><td class="desc"></td><td><button class="ghost">Default</button></td>`;
    tr.cells[0].textContent = s.name;
    const inp = tr.cells[1].firstChild;
    inp.value = fmtNum(s.value); inp.disabled = !!ro;
    tr.cells[2].textContent = fmtNum(s.def);
    tr.cells[3].textContent = `${fmtNum(s.min)} … ${fmtNum(s.max)}`;
    tr.cells[4].textContent = s.unit;
    tr.cells[5].textContent = s.desc + (s.flags & 1 ? " (operating value)" : "") + (ro ? " (read only)" : "");
    const btn = tr.cells[6].firstChild; btn.disabled = !!ro;
    const apply = async (cmd) => {
      try {
        await box.cmd(cmd);
        const g2 = await box.cmd(`get ${s.name}`);
        s.value = g2.value; inp.value = fmtNum(g2.value);
        tr.className = (s.value !== s.def ? "changed " : "") + "okflash";
        setTimeout(() => tr.classList.remove("okflash"), 800);
      } catch (e) { tr.classList.add("err"); toast(`${s.name}: ${e.message}`); inp.value = fmtNum(s.value); setTimeout(() => tr.classList.remove("err"), 1500); }
    };
    inp.onchange = () => apply(`set ${s.name} ${inp.value}`);
    btn.onclick = () => apply(`default ${s.name}`);
  }
  $("setCount").textContent = `${rows.length} of ${settings.length} shown.`;
}
$("setFilter").oninput = drawSettings; $("setGroup").onchange = drawSettings; $("setChanged").onchange = drawSettings;
$("btnSetReload").onclick = loadSettings;
$("btnSetSave").onclick = async () => { try { await box.cmd("save"); toast("Settings saved to flash", true); } catch (e) { toast(e.message); } };

// Traffic and console
const MAX_LINES = 3000;
function addLine(el, text, cls) {
  if (el === $("traffic") && $("trPause").checked) return;
  const f = $("trFilter").value.toLowerCase();
  if (el === $("traffic") && f && !text.toLowerCase().includes(f)) return;
  const stick = el.scrollTop + el.clientHeight >= el.scrollHeight - 20;
  const d = document.createElement("div");
  d.className = cls || "";
  d.innerHTML = `<span class="t">${new Date().toLocaleTimeString([], { hour12: false })}.${String(Date.now() % 1000).padStart(3, "0")}</span> `;
  d.append(text);
  el.append(d);
  while (el.childElementCount > MAX_LINES) el.firstChild.remove();
  if (stick) el.scrollTop = el.scrollHeight;
}
const trafficLine = (t, c) => addLine($("traffic"), t, c);
async function applyTrace() {
  const on = [...document.querySelectorAll("[data-trace]")].filter(c => c.checked).map(c => c.dataset.trace);
  try { await box.cmd("trace off"); for (const l of on) await box.cmd(`trace ${l}`); } catch (e) { toast(e.message); }
}
for (const c of document.querySelectorAll("[data-trace]")) c.onchange = applyTrace;
$("btnTrClear").onclick = () => ($("traffic").innerHTML = "");
$("btnTrSave").onclick = () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([$("traffic").innerText], { type: "text/plain" }));
  a.download = `leo_traffic_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.txt`;
  a.click();
};
$("btnRawSend").onclick = async () => {
  const t = $("rawText").value.trim();
  if (!t) return;
  try { await box.cmd(`raw ${$("rawLink").value} ${t}`); } catch (e) { toast(e.message); }
};
$("rawText").onkeydown = (e) => { if (e.key === "Enter") $("btnRawSend").onclick(); };
const conHist = [];
let conPos = 0;
async function conSend() {
  const t = $("conIn").value.trim();
  if (!t) return;
  conHist.push(t); conPos = conHist.length; $("conIn").value = "";
  addLine($("console"), "> " + t, "usb");
  try { const r = await box.cmd(t, 15000); addLine($("console"), JSON.stringify(r.items ? { ...r, items: `${r.items.length} settings` } : r), "rep"); }
  catch (e) { addLine($("console"), "! " + e.message, "fault"); }
}
$("btnConSend").onclick = conSend;
$("conIn").onkeydown = (e) => {
  if (e.key === "Enter") conSend();
  if (e.key === "ArrowUp" && conPos > 0) $("conIn").value = conHist[--conPos];
  if (e.key === "ArrowDown") $("conIn").value = conPos < conHist.length - 1 ? conHist[++conPos] : (conPos = conHist.length, "");
};

// OBI parameters
const bindPref = (id, key, num = true, ev = "change") => {
  const el = $(id);
  if (el.type === "checkbox") el.checked = !!prefs[key]; else el.value = prefs[key];
  el.addEventListener(ev, () => {
    prefs[key] = el.type === "checkbox" ? el.checked : num ? +el.value : el.value;
    savePrefs();
    worker.postMessage({ type: "config", cfg: liveCfg() });
    updateDatabar();
  });
};
bindPref("pDwellUnit", "dwellUnit"); bindPref("pBits", "bits"); bindPref("pHfw1", "hfw1"); bindPref("pFocusStep", "focusStep");
bindPref("pStigStep", "stigStep"); bindPref("pCtrX", "ctrX"); bindPref("pCtrY", "ctrY"); bindPref("pExtCtrl", "extCtrl");
bindPref("pScanExt", "scanExt"); bindPref("pDemo", "demo");
$("pDemo").addEventListener("change", () => worker.postMessage({ type: "demo", on: prefs.demo }));
$("pExtCtrl").addEventListener("change", () => worker.postMessage({ type: "ext", on: prefs.extCtrl }));
$("btnObiReconnect").onclick = () => worker.postMessage({ type: "connect", url: obiUrl });
$("btnObiAbort").onclick = () => { stopLive(); worker.postMessage({ type: "abort" }); };

// ---------------------------------------------------------------- start
window.leo = { box, viewer, worker, prefs };   // for the browser console
// Served by the bridge: same host. Opened from disk: the bridge on its default port.
const obiUrl = location.protocol.startsWith("http") ? `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/obi` : "ws://localhost:8438/obi";
worker.postMessage({ type: "connect", url: obiUrl });
if (prefs.demo) worker.postMessage({ type: "demo", on: true });
updateScanButtons();
render();
if (!box.supported) { $("lastEvent").textContent = "This browser has no Web Serial: open the page in Chrome or Edge"; chip($("btnBox"), "bad"); }
else box.autoConnect().then((ok) => { if (!ok) chip($("btnBox"), "bad"); });
})();
