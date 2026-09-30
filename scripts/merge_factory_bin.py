#!/usr/bin/env python3
from pathlib import Path
import json
import subprocess
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: merge_factory_bin.py <factory-root>")
root = Path(sys.argv[1]).resolve()
build = root / "build"
args_file = build / "flasher_args.json"
if not args_file.exists():
    raise SystemExit(f"missing {args_file}")
data = json.loads(args_file.read_text(encoding="utf-8"))
flash_files = data.get("flash_files") or {}
if not flash_files:
    raise SystemExit("flasher_args.json has no flash_files")
settings = data.get("flash_settings") or {}
out = build / "merged-binary.bin"
cmd = [sys.executable, "-m", "esptool", "--chip", "esp32s3", "merge_bin", "-o", str(out)]
mode = settings.get("flash_mode")
freq = settings.get("flash_freq")
size = settings.get("flash_size")
if mode:
    cmd += ["--flash_mode", str(mode)]
if freq:
    cmd += ["--flash_freq", str(freq)]
if size:
    cmd += ["--flash_size", str(size)]
for offset, rel in sorted(flash_files.items(), key=lambda kv: int(kv[0], 0)):
    p = Path(rel)
    if not p.is_absolute():
        p = build / p
    if not p.exists():
        # Some IDF versions store paths relative to project root instead.
        p2 = root / rel
        if p2.exists():
            p = p2
    if not p.exists():
        raise SystemExit(f"flash image missing for {offset}: {rel}")
    cmd += [offset, str(p)]
print("[merge]", " ".join(cmd))
subprocess.run(cmd, check=True)
print("[merge] created", out)
