#!/usr/bin/env python3
"""Patch only UI + fixed OTA into the SpotPear MAX35 factory Xiaozhi source.

This deliberately does NOT transplant the board into current 78 upstream.  The
factory tree keeps its own ML307/network/audio/camera/power/touch implementation.
"""
from pathlib import Path
import argparse
import re
import shutil

PROMPT = "Spotpear ESP32-S3-3.5-LCD-cam-ML307"
BOARD_REL = Path("main/boards/sp-esp32-s3-lcd-3.5")
UI_REL = Path("main/display/aurora_factory_max35")
UI_SOURCES = [
    "display/aurora_factory_max35/aurora_factory_max35_display.cc",
    "display/aurora_factory_max35/ui_home.cc",
    "display/aurora_factory_max35/ui_chat.cc",
]
FIXED_OTA = "http://124.221.112.55:8002/xiaozhi/ota/"
SRC_SUFFIXES = {".h", ".hpp", ".c", ".cc", ".cpp"}


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def write(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")


def find_factory_4g_symbol(root: Path) -> tuple[str, Path]:
    hits = []
    for p in (root / "main").rglob("Kconfig*"):
        if not p.is_file():
            continue
        text = read(p)
        start = 0
        while True:
            i = text.find(PROMPT, start)
            if i < 0:
                break
            prefix = text[:i]
            configs = list(re.finditer(r"(?m)^\s*config\s+([A-Za-z0-9_]+)\s*$", prefix))
            if configs:
                m = configs[-1]
                if i - m.start() < 1600:
                    hits.append((m.group(1), p, i - m.start()))
            start = i + len(PROMPT)
    if not hits:
        raise SystemExit(f"Could not find exact factory Kconfig prompt: {PROMPT}")
    hits.sort(key=lambda x: (x[2], len(str(x[1]))))
    symbol, path, _ = hits[0]
    if len({h[0] for h in hits}) > 1:
        raise SystemExit("Ambiguous ML307 factory board symbols: " + ", ".join(sorted({h[0] for h in hits})))
    print(f"[factory] exact 4G menuconfig symbol: CONFIG_{symbol}=y ({path.relative_to(root)})")
    return symbol, path


def cmake_symbols_for_board_dir(root: Path) -> list[str]:
    """Return CONFIG symbols whose CMake branch maps to the factory MAX35 folder.

    Some SpotPear source snapshots expose the 4G/ML307 selector as the actual
    board choice; others expose it as a secondary option under the normal MAX35
    board.  We support both layouts instead of guessing.
    """
    p = root / "main" / "CMakeLists.txt"
    text = read(p)
    matches = list(re.finditer(
        r"(?m)^\s*(?:if|elseif)\s*\(\s*CONFIG_([A-Za-z0-9_]+)\s*\)\s*$", text
    ))
    found = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.start():end]
        if re.search(r"set\s*\(\s*BOARD_DIR\s+[\"'](?:main/boards/|boards/)?sp-esp32-s3-lcd-3\.5[\"']\s*\)", block):
            found.append(m.group(1))
    # Older forks can use independent if()/endif() blocks where the simple
    # next-if range above may overrun.  Keep only unique symbols, preserving order.
    out = []
    for sym in found:
        if sym not in out:
            out.append(sym)
    return out


def determine_required_board_symbols(root: Path, ml307_symbol: str) -> list[str]:
    mapped = cmake_symbols_for_board_dir(root)
    if mapped:
        print("[factory] CMake symbols mapping to sp-esp32-s3-lcd-3.5:", ", ".join("CONFIG_" + x for x in mapped))
    else:
        print("[factory] no direct CMake symbol mapping found for sp-esp32-s3-lcd-3.5; ML307 selector will be used directly")

    # Best case: the explicit 4G option itself is the board type and maps to the
    # MAX35 folder.  Select only it (important when board types are a Kconfig choice).
    if ml307_symbol in mapped:
        return [ml307_symbol]

    # Otherwise the documented ML307 item is a sub-option.  Select the physical
    # MAX35 board plus that ML307 sub-option. Prefer a SpotPear/MAX35-looking symbol.
    base = None
    for sym in mapped:
        low = sym.lower()
        if "spotpear" in low and any(t in low for t in ("3_5", "3_5_lcd", "lcd_cam", "max35")):
            base = sym
            break
    if base is None and len(mapped) == 1:
        base = mapped[0]
    if base:
        print(f"[factory] ML307 is a sub-option; base board also required: CONFIG_{base}=y")
        return [base, ml307_symbol]

    # If the ML307 symbol itself is clearly a board choice, it is still safe to
    # select it even when the CMake parser did not recognize an unusual layout.
    if ml307_symbol.startswith("BOARD_TYPE_"):
        return [ml307_symbol]
    raise SystemExit(
        "Found the documented ML307 selector, but could not determine the physical MAX35 board selection. "
        "Refusing to guess a Wi-Fi/4G combination."
    )


def copy_ui(product: Path, root: Path) -> Path:
    src = product / "overlay" / UI_REL
    dst = root / UI_REL
    if not src.is_dir():
        raise SystemExit(f"Product UI missing: {src}")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print("[ui] AURORA overlay copied ->", dst.relative_to(root))
    return dst


def generate_compat(root: Path, ui_dst: Path) -> None:
    display = root / "main" / "display"
    header_blob = "\n".join(
        read(p) for p in display.rglob("*.h") if p.is_file() and "aurora_factory_max35" not in str(p)
    )
    has_chat = bool(re.search(r"\bSetChatMessage\s*\(\s*const\s+char\s*\*", header_blob))
    has_status = bool(re.search(r"\bSetStatus\s*\(\s*const\s+char\s*\*", header_blob))
    has_clear = "ClearChatMessages" in header_blob
    has_preview = bool(re.search(
        r"SetPreviewImage\s*\(\s*std::unique_ptr\s*<\s*LvglImage\s*>\s*", header_blob
    ))
    has_guard = "DisplayLockGuard" in header_blob
    if not has_chat:
        raise SystemExit("Factory display headers do not expose SetChatMessage(const char*, ...); cannot attach requested chat UI safely")
    lcd_h = display / "lcd_display.h"
    if not lcd_h.exists() or "SpiLcdDisplay" not in read(lcd_h):
        raise SystemExit("Factory source does not contain SpiLcdDisplay in main/display/lcd_display.h")
    compat = f'''#pragma once
// Auto-generated from the downloaded SpotPear factory display headers.
#define AURORA_FACTORY_HAS_SET_STATUS {1 if has_status else 0}
#define AURORA_FACTORY_HAS_SET_CHAT_MESSAGE {1 if has_chat else 0}
#define AURORA_FACTORY_HAS_CLEAR_CHAT_MESSAGES {1 if has_clear else 0}
#define AURORA_FACTORY_HAS_SET_PREVIEW_IMAGE {1 if has_preview else 0}
#define AURORA_FACTORY_HAS_DISPLAY_LOCK_GUARD {1 if has_guard else 0}
'''
    write(ui_dst / "aurora_factory_compat.h", compat)
    print(f"[compat] status={has_status} chat={has_chat} clear={has_clear} preview={has_preview} lock_guard={has_guard}")


def patch_cmake(root: Path) -> None:
    p = root / "main" / "CMakeLists.txt"
    text = read(p)
    missing = [s for s in UI_SOURCES if s not in text]
    if not missing:
        print("[cmake] UI sources already registered")
        return

    reg = re.search(r"idf_component_register\s*\(", text)
    if not reg:
        raise SystemExit("main/CMakeLists.txt has no idf_component_register()")
    prefix = text[:reg.start()]
    # Most Xiaozhi versions gather sources in a SOURCES variable. Infer the var
    # used by SRCS ${...}; fall back to SOURCES if present.
    tail = text[reg.start():]
    m = re.search(r"\bSRCS\s+\$\{([A-Za-z_][A-Za-z0-9_]*)\}", tail)
    var = m.group(1) if m else ("SOURCES" if re.search(r"\bset\s*\(\s*SOURCES\b", prefix) else None)
    if var:
        block = "\n# AURORA factory-only UI overlay\nlist(APPEND " + var + "\n" + "\n".join(f'    "{s}"' for s in missing) + "\n)\n\n"
        text = text[:reg.start()] + block + text[reg.start():]
    else:
        # Direct SRCS list fallback.
        sr = re.search(r"idf_component_register\s*\(\s*SRCS\s*", text)
        if not sr:
            raise SystemExit("Could not determine source list variable in main/CMakeLists.txt")
        addition = "\n".join(f'        "{s}"' for s in missing) + "\n"
        text = text[:sr.end()] + "\n" + addition + text[sr.end():]
    write(p, text)
    print("[cmake] registered AURORA UI sources")


def patch_board_display(root: Path) -> None:
    board = root / BOARD_REL
    if not board.is_dir():
        raise SystemExit(f"Exact SpotPear factory board folder is missing: {BOARD_REL}")
    include = '#include "display/aurora_factory_max35/aurora_factory_max35_display.h"'
    patched = 0
    touched = 0
    for p in board.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in SRC_SUFFIXES:
            continue
        text = read(p)
        if "SpiLcdDisplay" not in text and "AuroraFactoryMax35Display" not in text:
            continue
        original = text
        if include not in text:
            inc = '#include "display/lcd_display.h"'
            if inc in text:
                text = text.replace(inc, inc + "\n" + include, 1)
            else:
                first = re.search(r"(?m)^#\s*include[^\n]*$", text)
                if first:
                    text = text[:first.end()] + "\n" + include + text[first.end():]
                else:
                    text = include + "\n" + text
        text, n = re.subn(r"new\s+SpiLcdDisplay\s*\(", "new AuroraFactoryMax35Display(", text)
        patched += n
        classes = re.findall(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*public\s+SpiLcdDisplay", text)
        for cls in classes:
            text = re.sub(
                rf"class\s+{re.escape(cls)}\s*:\s*public\s+SpiLcdDisplay",
                f"class {cls} : public AuroraFactoryMax35Display", text, count=1)
            text = text.replace("using SpiLcdDisplay::SpiLcdDisplay;", "using AuroraFactoryMax35Display::AuroraFactoryMax35Display;")
            text = re.sub(r":\s*SpiLcdDisplay\s*\(", ": AuroraFactoryMax35Display(", text)
            text = text.replace("SpiLcdDisplay::SetupUI();", "AuroraFactoryMax35Display::SetupUI();")
            patched += 1
        if text != original:
            write(p, text)
            touched += 1
            print("[board] display-only patch:", p.relative_to(root))
    if patched == 0:
        raise SystemExit("Factory MAX35 board has no SpiLcdDisplay construction/subclass to replace; refusing to touch hardware/network code")
    print(f"[board] attached AURORA display in {touched} file(s); vendor board logic otherwise unchanged")


def function_close(text: str, sig_pos: int) -> tuple[int, int]:
    brace = text.find("{", sig_pos)
    if brace < 0:
        return -1, -1
    depth = 0
    for i in range(brace, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return brace, i
    return -1, -1


def patch_fixed_ota(root: Path) -> Path:
    main = root / "main"
    patterns = [
        re.compile(r"std::string\s+Ota::GetCheckVersionUrl\s*\(\s*\)"),
        re.compile(r"std::string\s+Ota::GetCheckVersionUrl\s*\(\s*\)\s*const"),
    ]
    for p in main.rglob("*.cc"):
        text = read(p)
        for pat in patterns:
            m = pat.search(text)
            if not m:
                continue
            brace, close = function_close(text, m.start())
            if brace < 0:
                continue
            replacement = "{\n    // Product requirement: 4G build has no provisioning UI, so the discovery\n    // endpoint is fixed in firmware and cannot be overridden by stale NVS.\n    return CONFIG_OTA_URL;\n}"
            new = text[:brace] + replacement + text[close + 1:]
            write(p, new)
            print("[ota] fixed GetCheckVersionUrl() -> CONFIG_OTA_URL in", p.relative_to(root))
            return p
    # Older forks may inline the same NVS lookup in a differently named function.
    for p in main.rglob("*.cc"):
        text = read(p)
        if 'GetString("ota_url")' in text and "CONFIG_OTA_URL" in text:
            raise SystemExit(f"Found an OTA NVS override in {p.relative_to(root)} but could not safely identify GetCheckVersionUrl(); source layout changed")
    raise SystemExit("Could not find factory Ota::GetCheckVersionUrl(); refusing to claim OTA is fixed")


def patch_kconfig_ota_default(root: Path) -> None:
    changed = 0
    for p in (root / "main").rglob("Kconfig*"):
        if not p.is_file():
            continue
        text = read(p)
        # Restrict replacement to the OTA_URL config block.
        m = re.search(r"(?ms)^\s*config\s+OTA_URL\s*$.*?(?=^\s*(?:config|choice|menu|endmenu)\b|\Z)", text)
        if not m:
            continue
        block = m.group(0)
        new_block, n = re.subn(r'(?m)^\s*default\s+"[^"]*"\s*$', f'    default "{FIXED_OTA}"', block, count=1)
        if n:
            text = text[:m.start()] + new_block + text[m.end():]
            write(p, text)
            changed += 1
            print("[ota] Kconfig OTA_URL default fixed in", p.relative_to(root))
    if changed == 0:
        print("[ota] OTA_URL Kconfig default block not patched; sdkconfig will still force the fixed URL")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--factory", required=True)
    ap.add_argument("--product", required=True)
    args = ap.parse_args()
    root = Path(args.factory).resolve()
    product = Path(args.product).resolve()
    if not (root / "main" / "CMakeLists.txt").exists():
        raise SystemExit(f"Not a Xiaozhi source root: {root}")
    board = root / BOARD_REL
    if not board.is_dir():
        raise SystemExit(f"Downloaded package does not contain expected SpotPear board: {BOARD_REL}")

    symbol, kconfig = find_factory_4g_symbol(root)
    required_symbols = determine_required_board_symbols(root, symbol)
    ui_dst = copy_ui(product, root)
    generate_compat(root, ui_dst)
    patch_cmake(root)
    patch_board_display(root)
    ota_file = patch_fixed_ota(root)
    patch_kconfig_ota_default(root)

    write(root / ".aurora_factory_board_symbol", symbol + "\n")
    write(root / ".aurora_factory_required_symbols", "\n".join(required_symbols) + "\n")
    write(root / ".aurora_factory_board_path", BOARD_REL.as_posix() + "\n")
    write(root / ".aurora_factory_ota_file", str(ota_file.relative_to(root)) + "\n")
    print("[done] SpotPear factory source preserved; only display UI + fixed OTA were patched")


if __name__ == "__main__":
    main()
