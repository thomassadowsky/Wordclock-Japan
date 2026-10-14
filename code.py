# code.py - Japanische Wordclock, Firmware fuer Adafruit Feather ESP32 V2 (CircuitPython 10.x)
#
# Ablauf: WLAN (aus settings.toml) -> Webserver :8080 -> Zeit per NTP -> jede Minute
# Satz bilden (wordclock_core.py) -> LEDs setzen + Satz, Romaji, deutsche Uebersetzung
# und Raster auf der Konsole ausgeben.
#
# Sprachausgabe (ab 1.3.0): spricht der Browser, solange die Weboberflaeche offen ist
# (Web Speech API, japanische Stimme). Die Uhr liefert nur den Text (/api/state "speak")
# und das gespeicherte Intervall (voice_interval: 0 aus, 1, 15 oder 60 Minuten).
#
# Einstellungen (NTP-Server, Lichtsensor, Farben Tag/Nacht, Demo, Test) werden im
# Browser unter http://<board-ip>:8080 geaendert und im NVM gespeichert (config.py).
# Die Hauptschleife blockiert nicht, damit die Weboberflaeche in jedem Modus erreichbar
# bleibt - auch ohne NTP, z. B. um einen falschen NTP-Server zu korrigieren.
#
# Benoetigte Dateien auf dem Board:
#   /code.py, /wordclock_core.py, /config.py, /webui.py, /index.html, /settings.toml
#   /lib: neopixel, adafruit_ntp, ampule, adafruit_veml7700 bzw. adafruit_bh1750
#         (fuer den analogen ALS-PT19 wird keine Bibliothek gebraucht)
#     circup --host 192.168.178.103 --password <pw> install neopixel adafruit_ntp \
#            adafruit_veml7700 adafruit_bh1750
#     (ampule.py liegt im Projekt und wird mit deploy.sh hochgeladen)
#
# Status-LED auf dem Feather (eingebaute NeoPixel):
#   blau = WLAN verbinden, gelb = Zeit holen, gruen (schwach) = laeuft, rot = Fehler

import gc
import os
import sys
import time
import traceback
import board
import rtc
import wifi
import socketpool
import microcontroller
import neopixel
import adafruit_ntp

import wordclock_core as wc
import config
from webui import WebUI, PORT

FW_VERSION = "1.4.1 (2026-10-09)"

# ---------------------------------------------------------------- Hardware (fest)
LED_PIN = board.D33          # Datenpin zum LED-Streifen: Pin "33" (kein Boot-Strapping-Pin; 12 meiden)
LED_VARIANT = "A"            # "A": 30 LEDs/m (64 LEDs), "B": 60 LEDs/m, jede zweite (120 LEDs)
LED_START = "unten_rechts"   # Einspeisung unten rechts (von vorne gesehen) - so verlötet, 15.10.2026; "unten" = unten links
# Lichtsensor: zuerst wird am STEMMA QT nach VEML7700/BH1750 gesucht; nur wenn dort keiner
# gefunden wird, wird ein ALS-PT19 (analog) an diesem Pin gelesen (None = kein Analogsensor).
# Nur ADC1-Pins verwenden (A2, A3, A4): die ADC2-Pins (A0, A1, A5) gehen bei aktivem WLAN nicht.
LIGHT_ANALOG_PIN = board.A2  # A2 = GPIO34
ALS_MV_PER_LUX = 3.0         # ALS-PT19 mit 10-kOhm-Lastwiderstand: ca. 3 mV pro lux (Naeherung)
MAX_BRIGHTNESS = 60          # Prozent - Obergrenze fuer die Weboberflaeche (Netzteil schonen)
TEST_INTERVAL = 2            # Sekunden an bzw. aus im Test-Modus
DEMO_STEP = 1                # Sekunden pro Uhrzeit im Demo-Modus

# Textstil (siehe DEFAULTS in wordclock_core.py)
TEXT_CFG = {
    "hour_mode": "ampm",
    "weekday": False,
    "greeting": False,
}
# ------------------------------------------------------------------------------

NUM_LEDS = 64 if LED_VARIANT == "A" else 8 * 15
LUX_INTERVAL = 1000          # ms zwischen zwei Messungen
DAYNIGHT_MIN_HOLD = 10000    # ms - fruehestens so oft zwischen Tag und Nacht wechseln


def now_ms():
    return time.monotonic_ns() // 1000000


# ------------------------------------------------------------------ Zeitzone
def _eu_dst_bounds(y):
    """Beginn/Ende der Sommerzeit (MESZ) in UTC-Sekunden fuer Jahr y (gueltig 1900-2099)."""
    mar = 31 - ((5 * y // 4 + 4) % 7)    # letzter Sonntag im Maerz
    oct_ = 31 - ((5 * y // 4 + 1) % 7)   # letzter Sonntag im Oktober
    start = time.mktime((y, 3, mar, 1, 0, 0, 0, 0, -1))
    end = time.mktime((y, 10, oct_, 1, 0, 0, 0, 0, -1))
    return start, end


def local_time(utc=None):
    """RTC laeuft auf UTC; gibt struct_time in Europe/Berlin zurueck."""
    if utc is None:
        utc = time.time()
    start, end = _eu_dst_bounds(time.localtime(utc).tm_year)
    offset = 7200 if start <= utc < end else 3600
    return time.localtime(utc + offset)


def fmt_time(lt):
    return "%04d-%02d-%02d %02d:%02d:%02d" % tuple(lt[:6])


# ------------------------------------------------------------------ Lichtsensor
class LightSensor:
    """VEML7700 (0x10) oder BH1750 (0x23/0x5C) am STEMMA-QT-Anschluss (automatisch erkannt),
    sonst ALS-PT19 analog an LIGHT_ANALOG_PIN."""

    def __init__(self):
        self.dev = None
        self.kind = None
        self.error = None
        self.init()

    def init(self):
        if self.dev is not None and hasattr(self.dev, "deinit"):
            try:
                self.dev.deinit()        # Analogpin wieder freigeben
            except Exception:
                pass
        self.dev, self.kind, self.error = None, None, None
        self.init_i2c()
        if self.kind is None and LIGHT_ANALOG_PIN is not None:
            i2c_error = self.error
            self.init_analog()
            if self.kind is None:
                self.error = "%s; %s" % (i2c_error, self.error)
            return
        if self.kind:
            print("Lichtsensor:", self.kind)
        else:
            print("Lichtsensor:", self.error)

    def init_i2c(self):
        try:
            i2c = board.STEMMA_I2C()
        except Exception as e:
            self.error = "I2C: %s" % e
            return
        try:
            while not i2c.try_lock():
                pass
            addrs = i2c.scan()
            i2c.unlock()
            if 0x10 in addrs:
                import adafruit_veml7700
                self.dev = adafruit_veml7700.VEML7700(i2c)
                self.kind = "VEML7700"
            elif 0x23 in addrs or 0x5C in addrs:
                import adafruit_bh1750
                self.dev = adafruit_bh1750.BH1750(i2c, address=0x23 if 0x23 in addrs else 0x5C)
                self.kind = "BH1750"
            else:
                self.error = "kein Sensor gefunden (I2C: %s)" % [hex(a) for a in addrs]
        except Exception as e:
            self.error = str(e)

    def init_analog(self):
        try:
            import analogio
            self.dev = analogio.AnalogIn(LIGHT_ANALOG_PIN)
            self.kind = "ALS-PT19 (%s)" % str(LIGHT_ANALOG_PIN).split(".")[-1]
            print("Lichtsensor:", self.kind)
        except Exception as e:
            self.dev = None
            self.error = "Analogpin: %s" % e
            print("Lichtsensor:", self.error)

    def read(self):
        if not self.dev:
            return None
        try:
            if self.kind.startswith("ALS"):
                # 8 Messungen mitteln (ADC des ESP32 rauscht), Spannung -> lux
                raw = 0
                for _ in range(8):
                    raw += self.dev.value
                volts = raw / 8 * self.dev.reference_voltage / 65535
                return volts * 1000 / ALS_MV_PER_LUX
            return float(self.dev.lux)
        except Exception as e:
            self.error = "Lesefehler: %s" % e
            return None


# ------------------------------------------------------------------ Anwendung
class App:
    def __init__(self):
        self.cfg = config.load()
        self.boot_ms = now_ms()

        self.status = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.05, auto_write=True)
        self.strip = neopixel.NeoPixel(LED_PIN, NUM_LEDS, brightness=0, auto_write=False)
        self.strip.fill(0)
        self.strip.show()

        self.sensor = LightSensor()
        self.lux = None
        self.lux_avg = None
        self.night = False
        self.daynight_ms = 0
        self.next_lux_ms = 0

        self.pool = None
        self.web = WebUI(self)
        self.next_net_ms = 0

        self.synced = False
        self.last_sync_utc = None
        self.next_ntp_ms = 0
        self.ntp_error = None
        self.ntp_requested = False
        self.reboot_at = None
        self.preview = None        # (farbe, helligkeit) waehrend der Auswahl im Browser
        self.preview_until = 0

        self.mode = None
        self.redraw = True
        self.next_step_ms = 0
        self.demo = [0, 0, 0]      # h, m, wd
        self.test_on = False
        self.shown = None          # (h, m, wd) der Anzeige
        self.pos = []
        self.txt = ""
        self.roman = ""
        self.german = ""
        self.speak = ""

    # -------------------------------------------------------------- Hilfen
    def set_status(self, color):
        self.status[0] = color

    def ip(self):
        try:
            return str(wifi.radio.ipv4_address)
        except Exception:
            return "-"

    def active(self):
        """Aktive Farbe + Helligkeit (Prozent) je nach Tag/Nacht (bzw. Vorschau aus dem Browser)."""
        if self.preview:
            return self.preview
        if self.cfg["light_sensor"] and self.night:
            return self.cfg["night_color"], self.cfg["night_brightness"]
        return self.cfg["day_color"], self.cfg["day_brightness"]

    # -------------------------------------------------------------- Aufrufe aus webui
    def on_config_changed(self, changed):
        self.redraw = True
        if "ntp_server" in changed or "ntp_interval_h" in changed:
            self.ntp_requested = True
        if "light_sensor" in changed:
            if self.cfg["light_sensor"] and not self.sensor.dev:
                self.sensor.init()
            if not self.cfg["light_sensor"]:
                self.night = False
        print("Einstellungen geaendert:", ", ".join(changed))

    def set_preview(self, color, pct):
        """Farbe voruebergehend anzeigen (nicht gespeichert), endet nach 20 s ohne neue Vorschau."""
        self.preview = (color, pct)
        self.preview_until = now_ms() + 20000
        self.redraw = True

    def end_preview(self):
        if self.preview:
            self.preview = None
            self.redraw = True

    def request_ntp(self):
        self.ntp_requested = True

    def request_reboot(self):
        self.reboot_at = now_ms() + 1000      # Antwort noch ausliefern

    # -------------------------------------------------------------- Netzwerk
    def ensure_network(self, t):
        if t < self.next_net_ms:
            return
        if wifi.radio.connected and self.web.server:
            return
        self.next_net_ms = t + 30000
        if not wifi.radio.connected:
            self.web.stop()
            self.set_status((0, 0, 255))
            try:
                wifi.radio.connect(os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD"))
                print("WLAN verbunden:", wifi.radio.ipv4_address)
            except Exception as e:
                print("WLAN-Fehler:", e)
                self.set_status((255, 0, 0))
                return
        if self.pool is None:
            self.pool = socketpool.SocketPool(wifi.radio)
        try:
            self.web.start(self.pool)
            self.set_status((0, 40, 0) if self.synced else (255, 160, 0))
        except Exception as e:
            print("Webserver startet nicht:", e)

    def sync_ntp(self):
        if not wifi.radio.connected or self.pool is None:
            self.ntp_error = "kein WLAN"
            return False
        self.set_status((255, 160, 0))
        server = self.cfg["ntp_server"]
        try:
            ntp = adafruit_ntp.NTP(self.pool, server=server, tz_offset=0, socket_timeout=5)
            rtc.RTC().datetime = ntp.datetime
            self.synced = True
            self.last_sync_utc = time.time()
            self.ntp_error = None
            print("NTP ok (%s): %s (lokal)" % (server, fmt_time(local_time())))
            self.set_status((0, 40, 0))
            return True
        except Exception as e:
            self.ntp_error = "%s: %s" % (server, e)
            print("NTP-Fehler:", self.ntp_error)
            self.set_status((255, 0, 0))
            return False

    def handle_ntp(self, t):
        if not (self.ntp_requested or t >= self.next_ntp_ms):
            return
        self.ntp_requested = False
        if self.sync_ntp():
            self.next_ntp_ms = t + self.cfg["ntp_interval_h"] * 3600000
        else:   # noch nie synchron: schnell erneut, sonst laeuft die RTC weiter
            self.next_ntp_ms = t + (600000 if self.synced else 30000)

    # -------------------------------------------------------------- Lichtsensor
    def update_light(self, t):
        if t < self.next_lux_ms:
            return
        self.next_lux_ms = t + LUX_INTERVAL
        # Immer messen (fuer die Anzeige in der Weboberflaeche), auch wenn die
        # Tag/Nacht-Umschaltung aus ist - so lassen sich die Schwellen vorher einstellen.
        lux = self.sensor.read()
        self.lux = lux
        if lux is None:
            return
        self.lux_avg = lux if self.lux_avg is None else 0.7 * self.lux_avg + 0.3 * lux
        if not self.cfg["light_sensor"]:
            return
        if t - self.daynight_ms < DAYNIGHT_MIN_HOLD:
            return
        if not self.night and self.lux_avg < self.cfg["lux_night"]:
            self.night = True
        elif self.night and self.lux_avg > self.cfg["lux_day"]:
            self.night = False
        else:
            return
        self.daynight_ms = t
        self.redraw = True
        print("Nachtmodus" if self.night else "Tagmodus", "(%.1f lux)" % self.lux_avg)

    # -------------------------------------------------------------- Anzeige
    def render(self, pos):
        color, pct = self.active()
        self.strip.brightness = min(pct, MAX_BRIGHTNESS) / 100
        self.strip.fill(0)
        for p in pos:
            self.strip[wc.led_index(p, variant=LED_VARIANT, start=LED_START)] = tuple(color)
        self.strip.show()
        self.pos = list(pos)
        self.redraw = False

    def show_time(self, h, m, wd):
        self.shown = (h, m, wd)
        txt = wc.text(h, m, wd, TEXT_CFG)
        pos, missing = wc.find_positions(txt)
        self.txt = txt
        self.roman = " ".join(t[1] for t in wc.phrase(h, m, wd, TEXT_CFG))
        self.german = wc.german(h, m, wd, TEXT_CFG)
        self.speak = wc.speech(h, m, wd, TEXT_CFG)
        if pos is None:
            print("%02d:%02d  %s  -> Zeichen fehlt im Raster: %s" % (h, m, txt, missing))
            self.set_status((255, 0, 0))
            self.render([])
            return
        self.render(pos)

        # Konsole: Satz + Raster (leuchtende Zeichen, sonst ・)
        print()
        print("%02d:%02d  %s  (%s)" % (h, m, txt, self.roman))
        print("       " + self.german)
        lit = set(pos)
        for r, row in enumerate(wc.LAYOUT):
            print("  " + "".join(ch if r * 8 + c in lit else "・" for c, ch in enumerate(row)))

    def tick_test(self, t):
        if t >= self.next_step_ms:
            self.next_step_ms = t + TEST_INTERVAL * 1000
            self.test_on = not self.test_on
            self.redraw = True
        if self.redraw:
            self.txt, self.roman, self.shown = "", "TEST", None
            self.german = self.speak = ""
            self.render(range(64) if self.test_on else [])

    def tick_demo(self, t):
        if t >= self.next_step_ms:
            self.next_step_ms = t + DEMO_STEP * 1000
            h, m, wd = self.demo
            m += 7
            if m >= 60:
                m, h = 0, h + 1
                if h >= 24:
                    h, wd = 0, (wd + 1) % 7
            self.demo = [h, m, wd]
            self.show_time(h, m, wd)
        elif self.redraw and self.shown:
            self.show_time(*self.shown)

    def tick_clock(self, t):
        if not self.synced:
            if self.redraw:
                self.txt, self.roman, self.shown = "", "warte auf NTP", None
                self.german = self.speak = ""
                self.render([])
            return
        lt = local_time()
        hm = (lt.tm_hour, lt.tm_min, lt.tm_wday)
        if hm != self.shown or self.redraw:
            self.show_time(*hm)

    def tick(self):
        t = now_ms()
        if self.reboot_at and t >= self.reboot_at:
            self.strip.fill(0)
            self.strip.show()
            microcontroller.reset()

        if self.preview and t >= self.preview_until:
            self.end_preview()
        self.ensure_network(t)
        if self.web.server and not self.web.poll():
            self.next_net_ms = t + 2000          # Server neu starten
        self.handle_ntp(t)
        self.update_light(t)

        mode = "test" if self.cfg["test"] else ("demo" if self.cfg["demo"] else "clock")
        if mode != self.mode:
            print("Modus:", mode)
            self.mode = mode
            self.redraw = True
            self.next_step_ms = 0
            self.shown = None
        if mode == "test":
            self.tick_test(t)
        elif mode == "demo":
            self.tick_demo(t)
        else:
            self.tick_clock(t)

    # -------------------------------------------------------------- Web: Zustand / Info
    def state(self):
        color, pct = self.active()
        clock = fmt_time(local_time()) if self.synced else None
        if self.mode == "test":
            shown = "alle an" if self.test_on else "alle aus"
        elif self.shown:
            shown = "%02d:%02d" % self.shown[:2]
        else:
            shown = None
        return {
            "mode": self.mode,
            "shown": shown,
            "text": self.txt,
            "roman": self.roman,
            "german": self.german,
            "speak": self.speak,
            "voice_interval": self.cfg["voice_interval"],
            "positions": self.pos,
            "layout": "".join(wc.LAYOUT),
            "night": bool(self.cfg["light_sensor"] and self.night),
            "light_sensor": self.cfg["light_sensor"],
            "sensor": self.sensor.kind,
            "sensor_error": self.sensor.error,
            "lux": None if self.lux is None else round(self.lux, 1),
            "lux_avg": None if self.lux_avg is None else round(self.lux_avg, 1),
            "color": color,
            "preview": bool(self.preview),
            "brightness": min(pct, MAX_BRIGHTNESS),
            "synced": self.synced,
            "clock": clock,
        }

    def info(self):
        gc.collect()
        u = os.uname()
        d = {
            "firmware": FW_VERSION,
            "board": board.board_id,
            "machine": u.machine,
            "sysname": u.sysname,
            "release": u.release,
            "version": u.version,
            "implementation": "%s %s" % (sys.implementation.name,
                                         ".".join(str(x) for x in sys.implementation.version[:3])),
            "mem_free": gc.mem_free(),
            "mem_alloc": gc.mem_alloc(),
            "uptime_s": (now_ms() - self.boot_ms) // 1000,
            "config_storage": config.storage_info(),
            "web_port": PORT,
            "leds": {"count": NUM_LEDS, "variant": LED_VARIANT, "pin": str(LED_PIN),
                     "start": LED_START, "max_brightness": MAX_BRIGHTNESS},
        }
        cpu = microcontroller.cpu
        try:
            d["cpu_freq_mhz"] = cpu.frequency // 1000000
        except Exception:
            d["cpu_freq_mhz"] = None
        try:
            d["cpu_temp_c"] = None if cpu.temperature is None else round(cpu.temperature, 1)
        except Exception:
            d["cpu_temp_c"] = None
        try:
            d["reset_reason"] = str(cpu.reset_reason).split(".")[-1]
        except Exception:
            d["reset_reason"] = None
        try:
            s = os.statvfs("/")
            d["flash_total"] = s[0] * s[2]
            d["flash_free"] = s[0] * s[3]
        except Exception:
            d["flash_total"] = d["flash_free"] = None
        r = wifi.radio
        w = {"connected": r.connected, "ip": self.ip(),
             "mac": ":".join("%02x" % b for b in r.mac_address)}
        try:
            w["hostname"] = r.hostname
        except Exception:
            w["hostname"] = None
        ap = r.ap_info if r.connected else None
        if ap:
            w["ssid"], w["rssi"], w["channel"] = ap.ssid, ap.rssi, ap.channel
        d["wifi"] = w
        n = {"server": self.cfg["ntp_server"], "synced": self.synced, "error": self.ntp_error,
             "next_in_s": max(0, (self.next_ntp_ms - now_ms()) // 1000)}
        if self.last_sync_utc:
            n["last_sync"] = fmt_time(local_time(self.last_sync_utc))
        d["ntp"] = n
        return d


# ------------------------------------------------------------------ Start
print("Japanese Word Clock %s\nA clock that displays the time in Japanese words.\nMade by Thomas Sadowsky" % FW_VERSION)
app = App()
print("Einstellungen:", app.cfg)
while True:
    try:
        app.tick()
    except Exception as e:                   # Uhr soll weiterlaufen
        print("Fehler in der Hauptschleife:")
        traceback.print_exception(e)
        gc.collect()
        time.sleep(1)
    time.sleep(0.02)
