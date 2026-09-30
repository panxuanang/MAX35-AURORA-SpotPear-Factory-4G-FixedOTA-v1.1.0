#!/usr/bin/env python3
from pathlib import Path
import re
import sys

FIXED_OTA = "http://124.221.112.55:8002/xiaozhi/ota/"
if len(sys.argv) != 2:
    raise SystemExit("usage: preflight_factory.py <factory-root>")
root = Path(sys.argv[1]).resolve()
board_symbol = (root / ".aurora_factory_board_symbol").read_text().strip()
required_file = root / ".aurora_factory_required_symbols"
required_symbols = ([x.strip() for x in required_file.read_text().splitlines() if x.strip()]
                    if required_file.exists() else [board_symbol])
board_rel = (root / ".aurora_factory_board_path").read_text().strip()
ota_rel = (root / ".aurora_factory_ota_file").read_text().strip()
sdk = (root / "sdkconfig").read_text(encoding="utf-8", errors="ignore")


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit("PRECHECK FAILED: " + msg)
    print("[OK]", msg)

for sym in required_symbols:
    require(f"CONFIG_{sym}=y" in sdk, f"factory-required board option CONFIG_{sym}=y is selected")
require(f"CONFIG_{board_symbol}=y" in sdk, "documented SpotPear ML307 menuconfig option is selected")
require(f'CONFIG_OTA_URL="{FIXED_OTA}"' in sdk, "fixed OTA/backend URL is present in final sdkconfig")
board = root / board_rel
require(board.is_dir(), "factory MAX35 board directory is still present")
board_blob = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in board.rglob("*") if p.is_file() and p.suffix.lower() in {".c", ".cc", ".cpp", ".h", ".hpp"})
require("AuroraFactoryMax35Display" in board_blob, "only the factory board display construction/base is redirected to AURORA")
require("sp-esp32-s3-lcd-3.5" in board_rel, "factory MAX35 hardware folder is used directly (no current-78 transplant)")
cmake = (root / "main" / "CMakeLists.txt").read_text(encoding="utf-8", errors="ignore")
for src in (
    "display/aurora_factory_max35/aurora_factory_max35_display.cc",
    "display/aurora_factory_max35/ui_home.cc",
    "display/aurora_factory_max35/ui_chat.cc",
):
    require(src in cmake, f"CMake includes {src}")
ui = root / "main" / "display" / "aurora_factory_max35"
chat = (ui / "ui_chat.cc").read_text(encoding="utf-8", errors="ignore")
require("LV_LABEL_LONG_WRAP" in chat, "assistant text is configured for full automatic wrapping")
require("ChatUiStartReadableScroll" in chat and "SetAnimDuration" in chat, "over-height answers use slow readable scrolling")
disp = (ui / "aurora_factory_max35_display.cc").read_text(encoding="utf-8", errors="ignore")
require('std::strcmp(role, "user")' in disp and "ShowPageInternal(Page::Chat)" in disp, "user speech automatically switches to the dedicated chat page")
require("ScheduleReturnHome" in disp, "chat page stays long enough to finish scrolling before returning home")
require("const bool listening" in disp and "正在聆听" in disp, "listening state automatically enters the dedicated chat page before ASR text")
require("const bool idle" in disp and "scroll_finish_us_" in disp, "return home waits for factory idle status and long-scroll completion")
ota = (root / ota_rel).read_text(encoding="utf-8", errors="ignore")
m = re.search(r"std::string\s+Ota::GetCheckVersionUrl\s*\(\s*\).*?\{(.*?)\}", ota, re.S)
require(bool(m) and "return CONFIG_OTA_URL;" in m.group(1), "runtime OTA lookup ignores stale NVS override")

# Only enforce camera options when that option exists in this factory fork's
# normalized sdkconfig. The exact 4G board selection itself remains mandatory.
if "CONFIG_CAMERA_GC0308" in sdk or "# CONFIG_CAMERA_GC0308" in sdk:
    require("CONFIG_CAMERA_GC0308=y" in sdk, "GC0308 is selected")
if "CONFIG_XIAOZHI_CAMERA_IMAGE_ROTATION_ANGLE_90" in sdk or "# CONFIG_XIAOZHI_CAMERA_IMAGE_ROTATION_ANGLE_90" in sdk:
    require("CONFIG_XIAOZHI_CAMERA_IMAGE_ROTATION_ANGLE_90=y" in sdk, "rear camera rotation is 90 degrees")
require("CONFIG_XIAOZHI_CAMERA_IMAGE_ROTATION_ANGLE_270=y" not in sdk, "front-camera 270-degree rotation is not enabled")
print("[done] factory-baseline AURORA 4G preflight passed")
