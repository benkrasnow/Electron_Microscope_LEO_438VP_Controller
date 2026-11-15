"""Regenerate firmware/SETTINGS.md from the X-macro table in leo_control/settings.h.
Run: python tools/gen_settings_doc.py (from the firmware folder)."""
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
src = (root / "leo_control" / "settings.h").read_text()
row = re.compile(r'^X\((\w+),\s*"([^"]+)",\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*"([^"]*)",\s*([^,]+),\s*"([^"]*)"\)', re.M)
groups = {"eht": "EHT / gun supply link", "op": "Operating values (changed by commands, persisted)",
          "state": "Internal persisted state (read only)", "stg": "Stage", "vac": "Vacuum",
          "vp": "VP controller", "eo": "EO board and optics", "scan": "Internal scan",
          "ui": "Display", "btn": "Buttons", "usb": "USB", "sys": "System", "dbg": "Debug"}
rows = row.findall(src)
out = ["# Control box settings", "",
       f"All {len(rows)} runtime settings, generated from `leo_control/settings.h` by `tools/gen_settings_doc.py`. "
       "Read and change them over USB with `get`, `set`, `list`, `default` (see PROTOCOL.md); they are kept in flash.", ""]
last = None
for _id, name, d, mn, mx, unit, flags, desc in rows:
    g = name.split(".")[0]
    if g != last:
        out += ["", f"## {groups.get(g, g)}", "", "| Name | Default | Min | Max | Unit | Description |", "|---|---|---|---|---|---|"]
        last = g
    out.append(f"| `{name}` | {d.strip()} | {mn.strip()} | {mx.strip()} | {unit} | {desc} |")
(root / "SETTINGS.md").write_text("\n".join(out) + "\n")
print(len(rows), "settings")
