# Troubleshooting – 今は Wordclock

Known problems and their fixes, collected while building the clock. See [readme.md](../readme.md) for the software and [hardware-bom.md](hardware-bom.md) for the parts list.

## LEDs

### Every row appears mirrored (left ↔ right)

**Symptom:** the web interface shows the correct sentence, but on the clock the lit characters are in the wrong columns – e.g. 金土 lights up instead of 今は.

**Cause:** the strips were fed from the other side than the firmware expects. When soldering from the back, left and right are easily swapped.

**Fix:** change `LED_START` in `code.py`:

| Feed point (seen from the front) | Setting |
|---|---|
| bottom left | `"unten"` |
| bottom right | `"unten_rechts"` (current build) |
| top left | `"oben"` |
| top right | `"oben_rechts"` |

Rows mirrored → switch left/right. Rows upside down → switch `unten`/`oben`. Afterwards check all 64 LEDs once with the **test mode** in the web interface.

### LEDs flicker, show wrong colors, or the first LED does not react

**Cause:** signal level. The WS2812B run on 5 V and, according to the datasheet, only reliably detect a logic high above about 0.7 × VDD = 3.5 V. The ESP32 drives the data pin (`D33`) at only 3.3 V – slightly below the specification.

In practice this usually works anyway: most LEDs are more tolerant than the datasheet, and every LED regenerates the signal to 5 V for the next one, so only the **first LED** is critical. With a short data line from the Feather to the first LED it works – the current clock runs this way without any level shifting.

It can fail with:

- a long data line between Feather and first LED
- an LED batch with a stricter threshold
- a supply voltage at the strip noticeably above 5 V (e.g. 5.2 V)

Typical symptoms: flickering, random cells lighting up, wrong colors, the first LED (or the whole strip) not reacting.

**Fixes, from simplest to cleanest:**

1. **Shorten the data line** and add a 330–470 Ω series resistor close to the first LED. Make sure GND of the Feather and GND of the strips are connected.
2. **Diode trick:** power only the first LED through a diode (e.g. 1N4001) from 5 V. It then runs at about 4.3 V, its threshold drops to about 3 V, and 3.3 V from the ESP32 is enough. From the second LED onward the signal is a full 5 V again. Costs one cent, but the first LED is slightly dimmer.
3. **Level shifter:** a 74AHCT125 (or 74HCT245) between Feather and first LED, powered from 5 V, converts 3.3 V to 5 V. This is the standard solution; small ready-made boards are available (e.g. from Adafruit). Note: it must be an **HCT/AHCT** type – plain HC types do not accept 3.3 V as high at 5 V supply.

### LEDs dim or change color towards the end of the chain

**Cause:** voltage drop on the thin strip conductors at high brightness.

**Fix:** feed 5 V/GND additionally into the far end (top row), use thicker wires for power, or lower the brightness in the web interface (capped at `MAX_BRIGHTNESS`).

### Do not use pin 12 for the data line

GPIO 12 is a boot-strapping pin on the ESP32. A strip connected there can prevent the board from booting. The data line is on `D33`.

## Light sensor

### Sensor not found

The firmware first scans the STEMMA QT port for a VEML7700 (0x10) or BH1750 (0x23/0x5C). The detected sensor (or the error) is printed on the serial console and shown in the web interface under system info. Check the STEMMA QT cable and that the library is installed (`./deploy.sh -l`).

### Lux value stuck at a fixed value (analog sensor)

With the analog ALS-PT19 the ESP32's ADC cannot resolve anything below about 140 mV (≈ 47 "lux"), so at a wall the reading stayed at 47. That is why the clock uses a VEML7700. Analog sensors must be on an **ADC1** pin (A2, A3, A4) – the ADC2 pins (A0, A1, A5) do not work while Wi-Fi is active.

### Clock switches day/night at the wrong time

Adjust the thresholds "night below" / "day above" in the web interface. The live lux value is shown there. The two thresholds must differ (hysteresis), and switching happens at most every 10 s.

### Sensor board sticks out over the top rim

Bases printed before 15.10.2026 hold the sensor too close to the edge. Use the adapter `wordclock_jp_luxadapter_2mm` (with M2.5 × 4 screws only – longer screws hit the dome and push the adapter off) or `wordclock_jp_luxadapter_4mm` (M2.5 × 5–8). The current base has the domes in the right place.

## Network and upload

### `deploy.sh` reports "Board … antwortet nicht"

- Check that the board is on Wi-Fi (status LED dim green) and the IP is correct (`WC_HOST=…`).
- The Web Workflow on port 80 is only served on the side while `code.py` runs and can be slow. **Close the web interface (port 8080) in the browser** and try again.
- Wrong password → `WC_PW=…` or `CIRCUITPY_WEB_API_PASSWORD` in `settings.toml`.

### No Wi-Fi after flashing

The online installer can leave `settings.toml` empty. Write `CIRCUITPY_WIFI_SSID`, `CIRCUITPY_WIFI_PASSWORD` and `CIRCUITPY_WEB_API_PASSWORD` via the serial REPL. The Feather ESP32 V2 has no CIRCUITPY drive (USB-serial chip CH9102F), so the serial console is the only way in at first:

```bash
screen /dev/cu.wchusbserial* 115200     # Ctrl+C = stop, Ctrl+D = restart code.py
```

If the port is busy, close any browser tab using Web Serial.

### Wrong time

- Check the NTP server in the web interface (default `fritz.box`); "sync NTP now" triggers an immediate sync.
- The web interface stays reachable even without NTP, so a wrong server can always be corrected there.
- The RTC runs on UTC; CET/CEST is computed by the firmware itself.

### circup does not work

Use circup ≥ 3 from the project's `.venv` – an old version 1.2.3 outside the venv does not support the Web Workflow.

## Status LED on the Feather

| Color | Meaning | What to check |
|---|---|---|
| blue (stays) | connecting to Wi-Fi | SSID/password in `settings.toml`, signal strength |
| yellow (stays) | fetching time | NTP server reachable? |
| green (dim) | running | – |
| red | error | serial console for the traceback |
