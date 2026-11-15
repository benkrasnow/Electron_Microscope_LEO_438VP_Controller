// WebGL2 image display: 8-bit or 16-bit frames uploaded as textures, display window (black / white
// level) and gamma applied in the fragment shader, aspect-correct fit in the canvas.

const VS = `#version 300 es
in vec2 p; out vec2 uv; uniform vec2 scale;
void main() { uv = vec2(p.x * 0.5 + 0.5, 0.5 - p.y * 0.5); gl_Position = vec4(p * scale, 0.0, 1.0); }`;

const FS8 = `#version 300 es
precision highp float; in vec2 uv; out vec4 o; uniform sampler2D t; uniform float lo, hi, gam;
void main() { float v = texture(t, uv).r; v = clamp((v - lo) / max(hi - lo, 1e-6), 0.0, 1.0); o = vec4(vec3(pow(v, gam)), 1.0); }`;

const FS16 = `#version 300 es
precision highp float; precision highp usampler2D; in vec2 uv; out vec4 o; uniform usampler2D t; uniform float lo, hi, gam;
void main() { float v = float(texture(t, uv).r) / 65535.0; v = clamp((v - lo) / max(hi - lo, 1e-6), 0.0, 1.0); o = vec4(vec3(pow(v, gam)), 1.0); }`;

class Viewer {
  constructor(canvas) {
    this.c = canvas;
    const gl = this.gl = canvas.getContext("webgl2", { antialias: false, preserveDrawingBuffer: true });
    if (!gl) throw new Error("WebGL2 not available");
    this.p8 = this.prog(FS8);
    this.p16 = this.prog(FS16);
    const vb = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, vb);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    this.tex = gl.createTexture();
    this.w = 0; this.h = 0; this.bits = 8;
    this.lo = 0; this.hi = 1; this.gamma = 1;
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    new ResizeObserver(() => this.draw()).observe(canvas);
  }

  prog(fs) {
    const gl = this.gl, p = gl.createProgram();
    for (const [type, src] of [[gl.VERTEX_SHADER, VS], [gl.FRAGMENT_SHADER, fs]]) {
      const s = gl.createShader(type);
      gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      gl.attachShader(p, s);
    }
    gl.bindAttribLocation(p, 0, "p");
    gl.linkProgram(p);
    return p;
  }

  setFrame(w, h, bits, data) {
    const gl = this.gl;
    gl.bindTexture(gl.TEXTURE_2D, this.tex);
    if (bits === 16) {
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.R16UI, w, h, 0, gl.RED_INTEGER, gl.UNSIGNED_SHORT, new Uint16Array(data));
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    } else {
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8, w, h, 0, gl.RED, gl.UNSIGNED_BYTE, new Uint8Array(data));
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    }
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    this.w = w; this.h = h; this.bits = bits;
    this.draw();
  }

  setWindow(lo, hi, gamma = 1) { this.lo = lo; this.hi = hi; this.gamma = gamma; this.draw(); }

  // Image rectangle inside the canvas, in CSS pixels (used for overlays and click mapping).
  imageRect() {
    const cw = this.c.clientWidth, ch = this.c.clientHeight;
    if (!this.w) return { x: 0, y: 0, w: cw, h: ch };
    const s = Math.min(cw / this.w, ch / this.h);
    const w = this.w * s, h = this.h * s;
    return { x: (cw - w) / 2, y: (ch - h) / 2, w, h };
  }

  draw() {
    const gl = this.gl, c = this.c, dpr = devicePixelRatio || 1;
    const W = Math.round(c.clientWidth * dpr), H = Math.round(c.clientHeight * dpr);
    if (c.width !== W || c.height !== H) { c.width = W; c.height = H; }
    gl.viewport(0, 0, W, H);
    gl.clearColor(0, 0, 0, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    if (!this.w) return;
    const p = this.bits === 16 ? this.p16 : this.p8;
    gl.useProgram(p);
    const r = this.imageRect();
    gl.uniform2f(gl.getUniformLocation(p, "scale"), r.w / c.clientWidth, r.h / c.clientHeight);
    gl.uniform1f(gl.getUniformLocation(p, "lo"), this.lo);
    gl.uniform1f(gl.getUniformLocation(p, "hi"), this.hi);
    gl.uniform1f(gl.getUniformLocation(p, "gam"), 1 / this.gamma);
    gl.uniform1i(gl.getUniformLocation(p, "t"), 0);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.tex);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }
}

// Percentile window over a frame (sampled), for auto contrast. Returns normalised [lo, hi].
function autoWindow(data, bits, lowPct = 0.5, highPct = 99.5) {
  const a = bits === 16 ? new Uint16Array(data) : new Uint8Array(data);
  const shift = bits === 16 ? 8 : 0, hist = new Uint32Array(256);
  const stride = Math.max(1, Math.floor(a.length / 200000));
  let n = 0;
  for (let i = 0; i < a.length; i += stride) { hist[a[i] >> shift]++; n++; }
  let acc = 0, lo = 0, hi = 255;
  for (let i = 0; i < 256; i++) { acc += hist[i]; if (acc >= (n * lowPct) / 100) { lo = i; break; } }
  acc = 0;
  for (let i = 255; i >= 0; i--) { acc += hist[i]; if (acc >= (n * (100 - highPct)) / 100) { hi = i; break; } }
  if (hi <= lo) hi = lo + 1;
  return [lo / 255, (hi + 1) / 256];
}
