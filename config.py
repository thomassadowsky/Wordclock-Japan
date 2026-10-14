# config.py - dauerhafte Einstellungen der japanischen Wordclock
#
# Gespeichert wird als JSON im NVM des ESP32 (microcontroller.nvm, 8 KB).
# Vorteil gegenueber einer Datei: das Dateisystem bleibt fuer den Web Workflow
# beschreibbar, deploy.sh / circup funktionieren weiter ohne boot.py-Umbau.
# Fallback (falls kein NVM vorhanden): /wordclock_config.json
#
# Format im NVM:  b"WCJ1" + Laenge (2 Byte, big endian) + JSON (UTF-8)

import json

try:
    import microcontroller
    _nvm = microcontroller.nvm
except Exception:          # CPython / Simulator
    _nvm = None

MAGIC = b"WCJ1"
FILE = "/wordclock_config.json"

DEFAULTS = {
    "ntp_server": "fritz.box",
    "ntp_interval_h": 6,          # Stunden zwischen zwei NTP-Abgleichen
    "light_sensor": False,        # Tag/Nacht-Umschaltung ueber Lichtsensor
    "lux_night": 5.0,             # unter diesem Wert -> Nacht
    "lux_day": 15.0,              # ueber diesem Wert -> Tag (Hysterese)
    "day_color": [0, 200, 180],   # tuerkis wie die deutsche Uhr
    "day_brightness": 25,         # Prozent
    "night_color": [0, 200, 180],
    "night_brightness": 3,
    "demo": False,
    "test": False,
    "voice_interval": 0,          # Sprachausgabe im Browser: 0 aus, 1/15/60 Minuten
}


# ------------------------------------------------------------------ Pruefung
def _bool(v):
    if isinstance(v, bool):
        return v
    v = str(v).strip().lower()
    if v in ("1", "true", "on", "yes", "ja"):
        return True
    if v in ("0", "false", "off", "no", "nein", ""):
        return False
    raise ValueError("an/aus erwartet")


def _color(v):
    if isinstance(v, (list, tuple)):
        parts = list(v)
    else:
        v = str(v).strip()
        if v.startswith("#") and len(v) == 7:
            return [int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16)]
        parts = v.split(",")
    if len(parts) != 3:
        raise ValueError("R,G,B erwartet")
    out = [int(p) for p in parts]
    for x in out:
        if not 0 <= x <= 255:
            raise ValueError("RGB-Werte 0..255")
    return out


def _range(lo, hi, conv):
    def f(v):
        x = conv(v)
        if not lo <= x <= hi:
            raise ValueError("Wert %s..%s" % (lo, hi))
        return x
    return f


def _choice(conv, allowed):
    def f(v):
        x = conv(v)
        if x not in allowed:
            raise ValueError("erlaubt: %s" % ", ".join(str(a) for a in allowed))
        return x
    return f


def _host(v):
    v = str(v).strip()
    if not v or len(v) > 64:
        raise ValueError("Hostname fehlt oder zu lang")
    for ch in v:
        if not (ch.isalpha() or ch.isdigit() or ch in ".-_:"):
            raise ValueError("ungueltiges Zeichen im Hostnamen")
    return v


VALIDATORS = {
    "ntp_server": _host,
    "ntp_interval_h": _range(1, 168, int),
    "light_sensor": _bool,
    "lux_night": _range(0, 100000, float),
    "lux_day": _range(0, 100000, float),
    "day_color": _color,
    "day_brightness": _range(0, 100, int),
    "night_color": _color,
    "night_brightness": _range(0, 100, int),
    "demo": _bool,
    "test": _bool,
    "voice_interval": _choice(int, (0, 1, 15, 60)),
}


def apply(cfg, params):
    """Uebernimmt Werte (z. B. aus der URL) in cfg.
    Rueckgabe: (geaenderte Schluessel, Fehler {schluessel: text})."""
    changed, errors = [], {}
    new = dict(cfg)
    for k, v in params.items():
        if k not in VALIDATORS:
            continue
        try:
            x = VALIDATORS[k](v)
        except Exception as e:
            errors[k] = str(e) or "ungueltig"
            continue
        if new.get(k) != x:
            new[k] = x
            changed.append(k)
    if not errors and new["lux_day"] < new["lux_night"]:
        errors["lux_day"] = "Tag-Schwelle muss >= Nacht-Schwelle sein"
    if errors:
        return [], errors
    cfg.update(new)
    return changed, errors


# ------------------------------------------------------------------ Laden / Speichern
def load():
    cfg = dict(DEFAULTS)
    cfg["day_color"] = list(DEFAULTS["day_color"])
    cfg["night_color"] = list(DEFAULTS["night_color"])
    stored = None
    try:
        if _nvm is not None and bytes(_nvm[0:4]) == MAGIC:
            n = int.from_bytes(bytes(_nvm[4:6]), "big")
            stored = json.loads(bytes(_nvm[6:6 + n]).decode("utf-8"))
        elif _nvm is None:
            with open(FILE) as f:
                stored = json.load(f)
    except Exception as e:
        print("Konfiguration nicht lesbar, Standardwerte:", e)
    if stored:
        apply(cfg, {k: v for k, v in stored.items() if k in DEFAULTS})
    return cfg


def save(cfg):
    """Rueckgabe: (ok, Meldung). Schreibt nur, wenn sich etwas geaendert hat (Flash schonen)."""
    data = json.dumps(cfg).encode("utf-8")
    if _nvm is not None:
        blob = MAGIC + len(data).to_bytes(2, "big") + data
        if len(blob) > len(_nvm):
            return False, "NVM zu klein (%d > %d Byte)" % (len(blob), len(_nvm))
        if bytes(_nvm[0:len(blob)]) != blob:
            _nvm[0:len(blob)] = blob
        return True, "NVM (%d Byte)" % len(blob)
    try:
        with open(FILE, "w") as f:
            f.write(data.decode("utf-8"))
        return True, FILE
    except OSError as e:
        return False, "Dateisystem schreibgeschuetzt (%s)" % e


def storage_info():
    if _nvm is not None:
        return "NVM, %d Byte" % len(_nvm)
    return "Datei " + FILE
