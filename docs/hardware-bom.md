# Hardware bill of materials – 今は Wordclock

Everything needed to build one Japanese word clock (285 × 285 mm, 8 × 8 grid, about 40 mm deep). Part numbers refer to Adafruit where an Adafruit board is used; equivalent parts work as long as the dimensions and hole spacings match.

## Electronics

| Qty | Part | Notes |
|---|---|---|
| 1 | **Adafruit Feather ESP32 V2** | Controller, runs CircuitPython 10.x. Mounted on 4 M2.5 domes (hole spacing 45.72 × 17.78 mm). Built-in NeoPixel is used as status LED. |
| 64 | **WS2812B LEDs, 30 LEDs/m, 10 mm wide strip** (variant A) | 8 pieces of 8 LEDs, cut at the grid edge – about 2.2 m of strip. Pitch 33.33 mm matches the grid. |
| – | *alternative:* WS2812B, 60 LEDs/m (variant B) | 8 pieces of 15 LEDs, every second LED used (120 LEDs). Set `LED_VARIANT = "B"` in `code.py`. |
| 1 | **Adafruit VEML7700** light sensor, STEMMA QT (25.4 × 17.8 mm) | Optional, for automatic day/night brightness. A BH1750 on STEMMA QT also works; both are detected automatically. |
| 1 | STEMMA QT / Qwiic cable (JST SH 4-pin), approx. 100–200 mm | Feather ↔ light sensor |
| 1 | **Adafruit USB-C breakout** (product 4090, 20.4 × 14.2 mm) | Taps VBUS/GND to power the LED strips. Mounted on 2 M2.5 domes (hole spacing 15.24 mm). |
| 1 | **USB-C Y-cable** (1 socket in, 2 plugs out) | Socket sits in the holder in the bottom rim (housing max. 14 × 8 × 26 mm). Output 1 → Feather, output 2 → USB-C breakout. |
| 1 | **5 V power supply, 3–4 A, USB-C** | LED brightness is capped in firmware (`MAX_BRIGHTNESS = 60 %`). |
| 1 | Electrolytic capacitor, e.g. 1000 µF / 6.3 V or higher | Across 5 V/GND directly before the first LED. |
| 1 | Resistor 330–470 Ω *(recommended)* | In series with the data line, close to the first LED. |
| 1 | Level shifter 74AHCT125 *(optional)* | Only if the LEDs flicker or the first LED does not react – see [troubleshooting.md](troubleshooting.md). |
| – | Hookup wire (e.g. 22–24 AWG silicone), 3 colors | Row-to-row connections on the back (5 V, GND, data), feed line from the Feather (data on pin `D33`) and from the USB-C breakout. |
| – | Heat-shrink tubing, cable ties (max. 4 mm wide) | 7 cable-tie eyelets are built into the back. |

**Wiring:** the strips run in a serpentine pattern, one strip per row. The feed goes into the bottom row – on the built clock at the **bottom right as seen from the front** (`LED_START = "unten_rechts"`). The cables at the strip ends go through the 16 feed-through slots to the back, where the rows are connected. The ESP32 drives the data line at 3.3 V; with a short feed line this works with the WS2812B without a level shifter. If it does not, see "LEDs flicker" in [troubleshooting.md](troubleshooting.md).

## 3D-printed parts

Print files are in [`3d-print-files/3mf`](../3d-print-files/3mf) (already oriented for printing) and [`3d-print-files/stl`](../3d-print-files/stl); the CAD scripts are in [`cad/`](../cad). Settings and tips: [printing.md](printing.md). Designed for a Prusa CORE One L (300 × 300 mm bed).

| Qty | Part | File | Material / notes |
|---|---|---|---|
| 1 | Front panel (2.8 mm) | `wordclock_jp_front` | PLA, 1.8 mm black + 1.0 mm white as diffuser; color change (M600) at 1.8 mm is included in the 3MF. Printed face-down, satin sheet. |
| 1 | Light grid (23 mm) | `wordclock_jp_raster` | PLA black. Separates the 64 cells. |
| 1 | Base with electronics tray | `wordclock_jp_boden` | PLA black. LED channels at the front, open tray with domes, socket holder, light notch and keyhole hangers at the back. |
| 1 | Light-sensor adapter *(only for bases printed before 15.10.2026)* | `wordclock_jp_luxadapter_2mm` or `_4mm` | Moves the sensor away from the rim; the current base no longer needs it. |
| 1 | Desk stand *(optional)* | `wordclock_jp_staender_winkel` or `_gerade` | For a 90° USB-C angled plug or a straight plug. |

Filament: roughly 0.8–1 kg PLA in total (black), plus a small amount of white for the diffuser layer.

## Screws and mounting

| Qty | Part | Use |
|---|---|---|
| 4 | M3 × 12 | From the front through the front panel into the corner posts of the grid |
| 10 | M3 × 12 countersunk | From the back through the base into the grid (4 corners, 6 nodes) |
| 4 | M2.5 × 6 self-tapping | Feather ESP32 V2 |
| 2 | M2.5 × 6 self-tapping | USB-C breakout |
| 2 | M2.5 self-tapping (× 6 with the current base; with the adapter: × 4 for `_2mm`, × 5–8 for `_4mm`) | Light sensor |
| 2 | Wall screws + dowels, head ≤ 8.5 mm, shank ≤ 4.2 mm | Keyhole hangers, screw spacing 133.3 mm |
| – | Double-sided tape or the strips' own adhesive | LED strips in the channels of the base |
| – | Rubber feet *(optional)* | Under the desk stand |
| – | Superglue *(only with the adapter)* | Fixes the adapter on the sensor domes |

## Tools

Soldering iron and solder, wire stripper, side cutters, screwdriver for M2.5/M3, 3D printer with a 300 × 300 mm bed, a computer with Chrome (for flashing CircuitPython) and Python 3 (for `deploy.sh` / circup).
