# Third-party notices

This project includes or uses the following third-party components. Their licenses apply to those components only; everything else in this repository is licensed as described in the [readme](readme.md#license).

## Included in this repository

### ampule

- File: [`ampule.py`](ampule.py)
- Source: https://github.com/deckerego/ampule
- License: MIT

```
MIT License

Copyright (c) 2021 John Ellis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Noto Sans CJK JP (character shapes in the front panel)

- Used in: [`cad/`](cad) scripts, and as outlines in the front panel models ([`3d-print-files/`](3d-print-files), `cad/wordclock_jp_front.svg`)
- Source: https://github.com/notofonts/noto-cjk
- License: SIL Open Font License 1.1 – https://openfontlicense.org
- The font file itself is **not** included in this repository; the CAD scripts expect it to be installed on the system.

## Used but not included

These are installed separately on the board (`./deploy.sh -l` / circup) or on the computer and are not part of this repository:

| Component | Used for | License |
|---|---|---|
| CircuitPython | runtime on the Feather ESP32 V2 | MIT |
| Adafruit CircuitPython libraries: `neopixel`, `adafruit_ntp`, `adafruit_veml7700`, `adafruit_bh1750` | LEDs, NTP, light sensors | MIT |
| manifold3d, trimesh, fontTools, NumPy | CAD scripts in `cad/` | Apache 2.0 / MIT / MIT / BSD |
