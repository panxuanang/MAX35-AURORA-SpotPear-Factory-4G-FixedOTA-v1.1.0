#!/usr/bin/env python3
from pathlib import Path
import re
import sys

FIXED_OTA = "http://124.221.112.55:8002/xiaozhi/ota/"

if len(sys.argv) != 2:
    raise SystemExit("usage: configure_factory_sdkconfig.py <factory-root>")
root = Path(sys.argv[1]).resolve()
sdk = root / "sdkconfig"
symbol_file = root / ".aurora_factory_board_symbol"
required_file = root / ".aurora_factory_required_symbols"
if not sdk.exists():
    raise SystemExit("sdkconfig does not exist; run idf.py set-target esp32s3 first")
if not symbol_file.exists():
    raise SystemExit("factory board symbol metadata missing; run patch_spotpear_factory.py first")
board_symbol = symbol_file.read_text().strip()
required_symbols = ([x.strip() for x in required_file.read_text().splitlines() if x.strip()]
                    if required_file.exists() else [board_symbol])
text = sdk.read_text(encoding="utf-8", errors="ignore")


def set_value(name: str, value: str) -> None:
    global text
    # Remove both enabled/value and '# ... is not set' forms, then append one
    # authoritative setting. Kconfig will normalize it on reconfigure.
    pat1 = re.compile(rf"(?m)^CONFIG_{re.escape(name)}=.*\n?")
    pat2 = re.compile(rf"(?m)^# CONFIG_{re.escape(name)} is not set\n?")
    text = pat1.sub("", text)
    text = pat2.sub("", text)
    text += f"CONFIG_{name}={value}\n"


def set_bool(name: str, enabled: bool) -> None:
    global text
    pat1 = re.compile(rf"(?m)^CONFIG_{re.escape(name)}=.*\n?")
    pat2 = re.compile(rf"(?m)^# CONFIG_{re.escape(name)} is not set\n?")
    text = pat1.sub("", text)
    text = pat2.sub("", text)
    text += (f"CONFIG_{name}=y\n" if enabled else f"# CONFIG_{name} is not set\n")

# The board choice is the only required factory-specific selection. Clear any
# already-selected BOARD_TYPE_* from the generated default config first.
selected = re.findall(r"(?m)^CONFIG_(BOARD_TYPE_[A-Za-z0-9_]+)=y$", text)
for name in selected:
    set_bool(name, False)
for name in required_symbols:
    set_bool(name, True)

# Fixed product backend/discovery endpoint.
set_value("OTA_URL", f'"{FIXED_OTA}"')

# Hardware SKU documented by SpotPear for the 4G finished unit: rear GC0308,
# YUV422, 90-degree camera rotation. These are the same menuconfig choices a
# human would select in the factory source. Unknown options are harmless and
# are normalized away by kconfig; preflight only enforces options that exist.
for name, enabled in [
    ("CAMERA_GC0308", True),
    ("CAMERA_OV2640", False),
    ("CAMERA_OV5640", False),
    ("ESP_VIDEO_ENABLE_DVP_VIDEO_DEVICE", True),
    ("CAMERA_GC0308_DVP_YUV422_YUYV_640X480_16FPS", True),
    ("CAMERA_GC0308_DVP_DEFAULT_FMT_YUV422_YUYV_640X480_16FPS", True),
    ("XIAOZHI_ENABLE_ROTATE_CAMERA_IMAGE", True),
    ("XIAOZHI_CAMERA_IMAGE_ROTATION_ANGLE_90", True),
    ("XIAOZHI_CAMERA_IMAGE_ROTATION_ANGLE_270", False),
    ("LV_FONT_MONTSERRAT_48", True),
    ("ESPTOOLPY_FLASHSIZE_16MB", True),
]:
    set_bool(name, enabled)
set_value("ESPTOOLPY_FLASHSIZE", '"16MB"')

sdk.write_text(text, encoding="utf-8")
print("[config] selected factory board options: " + ", ".join(f"CONFIG_{x}=y" for x in required_symbols))
print(f"[config] fixed OTA/backend: {FIXED_OTA}")
print("[config] requested rear GC0308 + YUV422 + 90-degree rotation")
