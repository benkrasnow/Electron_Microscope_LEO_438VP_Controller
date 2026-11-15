// Uncompressed single-strip grayscale TIFF (8 or 16 bit, little-endian) with the acquisition
// parameters in ImageDescription, readable by ImageJ / Fiji and most image tools.

function encodeTiff(w, h, bits, pixels, description) {
  const desc = new TextEncoder().encode(description + "\0");
  const bpp = bits / 8, imgBytes = w * h * bpp;
  const tags = [
    [256, 4, 1, w], [257, 4, 1, h], [258, 3, 1, bits], [259, 3, 1, 1], [262, 3, 1, 1],
    [270, 2, desc.length, 0 /* offset patched */], [273, 4, 1, 0 /* patched */], [277, 3, 1, 1],
    [278, 4, 1, h], [279, 4, 1, imgBytes], [284, 3, 1, 1],
  ];
  const ifdSize = 2 + tags.length * 12 + 4;
  const descOff = 8 + ifdSize, imgOff = descOff + desc.length + (desc.length & 1);
  const buf = new ArrayBuffer(imgOff + imgBytes);
  const dv = new DataView(buf), u8 = new Uint8Array(buf);
  u8.set([0x49, 0x49, 42, 0]);
  dv.setUint32(4, 8, true);
  dv.setUint16(8, tags.length, true);
  tags.forEach(([tag, type, count, value], i) => {
    const o = 10 + i * 12;
    if (tag === 270) value = descOff;
    if (tag === 273) value = imgOff;
    dv.setUint16(o, tag, true); dv.setUint16(o + 2, type, true); dv.setUint32(o + 4, count, true);
    if (type === 3) dv.setUint16(o + 8, value, true); else dv.setUint32(o + 8, value, true);
  });
  dv.setUint32(10 + tags.length * 12, 0, true);
  u8.set(desc, descOff);
  if (bits === 16) {
    const src = new Uint16Array(pixels);
    for (let i = 0; i < src.length; i++) dv.setUint16(imgOff + i * 2, src[i], true);
  } else u8.set(new Uint8Array(pixels), imgOff);
  return new Blob([buf], { type: "image/tiff" });
}
