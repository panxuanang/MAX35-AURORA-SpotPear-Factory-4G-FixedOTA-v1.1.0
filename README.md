# MAX35 AURORA - SpotPear Factory 4G Base

This repository builds the SpotPear MAX35 4G/ML307 firmware from the **SpotPear factory Xiaozhi source line**, then applies only two product changes:

1. AURORA UI for the 3.5-inch 480x320 display.
2. A fixed OTA/backend discovery URL: `http://124.221.112.55:8002/xiaozhi/ota/`.

It deliberately does **not** transplant MAX35 hardware into the newest 78/xiaozhi branch. The factory ML307 networking, audio, camera, touch, power and MCP logic stay in the vendor source.

## Factory baseline

The workflow downloads SpotPear's official `xiaozhi-esp32-3.1.0` Google Drive package and builds it with ESP-IDF 5.5, matching the SpotPear MAX35 documentation.

Official source package used by CI:

`https://drive.google.com/file/d/1WIrLLpS7OxHll7KD5v6kePZM50hAtzlf/view?usp=sharing`

SpotPear's Chinese MAX35 guide documents the 4G menu option as:

`Spotpear ESP32-S3-3.5-LCD-cam-ML307`

The build scripts require that exact menu prompt to exist before compilation. If SpotPear changes the source package and the documented 4G selector is absent, the workflow stops rather than silently compiling a Wi-Fi image.

## Target hardware

- ESP32S3-MAX35 4G finished unit
- ML307 cellular modem
- 3.5-inch ST7796 LCD, 480x320 landscape UI
- Rear camera
- GC0308 / YUV422 / 90-degree rotation requested in build config
- Touch hardware stays enabled exactly as implemented by SpotPear, but AURORA does not require touch
- 16 MB flash

SpotPear notes that the SD card cannot be used while the 4G function is active.

## UI behavior

AURORA is a new visual design; only the long-dialog interaction idea is carried over from the previous STELLAR project.

- Home page: dark AURORA status screen, clock/date, central AI status orb.
- When the device enters listening or ASR produces user text, it automatically switches to the dedicated DIALOG page.
- User text is shown separately at the top.
- Assistant text uses full automatic wrapping rather than truncation.
- If the answer is taller than the visible answer region, it pauses briefly and then scrolls upward slowly until the final line is readable.
- Return to Home waits for an idle/standby status and for long-answer scrolling to finish. A long fallback timer prevents a permanently stuck dialog screen if a vendor build never emits an idle status string.
- The factory camera preview path is preserved. AURORA hides its overlay while a factory preview image is active when that API is present.

## Fixed OTA/backend URL

The firmware is locked to:

`http://124.221.112.55:8002/xiaozhi/ota/`

The workflow sets `CONFIG_OTA_URL` to this value and patches the factory `Ota::GetCheckVersionUrl()` to return `CONFIG_OTA_URL` directly. This prevents an old NVS `wifi/ota_url` value from overriding the configured backend on the 4G unit.

## GitHub build

Upload **all files and folders in this repository** to the root of a new GitHub repository, including `.github/`.

Then open:

`Actions -> Build MAX35 AURORA 4G - SpotPear Factory Base -> Run workflow`

The workflow will:

1. start an ESP-IDF 5.5 container;
2. download the official SpotPear source package;
3. verify the exact factory ML307 menu option;
4. attach AURORA only to the factory display construction;
5. lock the OTA/backend URL;
6. select the factory 4G board and rear-camera settings;
7. build the factory tree;
8. create a merged binary for address `0x0`;
9. upload `MAX35-AURORA-SpotPear-Factory-4G-Firmware` as an Actions artifact.

The firmware artifact contains:

- `MAX35_AURORA_FACTORY_4G_<version>_merged-binary.bin`
- `sdkconfig.final`
- `BUILD_INFO.txt`
- `SHA256SUMS.txt`

## Flashing

For the first test, erase the ESP32-S3 flash completely, then flash the generated merged binary at address `0x0`.

Keep the SpotPear factory 4G BIN available as a recovery image while testing.

## Scope guard

The patch script is intentionally narrow. It changes the factory project only in these places:

- adds the `main/display/aurora_factory_max35/` UI files;
- registers those UI source files in `main/CMakeLists.txt`;
- changes the MAX35 board's `SpiLcdDisplay` construction/base to `AuroraFactoryMax35Display`;
- fixes the OTA URL/default and runtime OTA URL getter;
- selects documented board/camera build options in `sdkconfig`.

It does not replace the factory ML307 implementation, audio service, camera driver, touch driver, MCP tools, protocol code, or power logic.

## If Actions stops before compilation

The early checks are intentional. In particular, the workflow will stop if the downloaded SpotPear package does not contain the exact documented `Spotpear ESP32-S3-3.5-LCD-cam-ML307` menu item or the expected `sp-esp32-s3-lcd-3.5` hardware folder. This is safer than producing a firmware that looks like a 4G build but actually uses the wrong hardware profile.
