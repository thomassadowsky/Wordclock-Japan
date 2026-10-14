# webui.py - Einstellungen per Browser (ampule, Port 8080)
#
# Port 80 belegt der CircuitPython Web Workflow, deshalb 8080 wie bei der deutschen Uhr.
# Der Server laeuft nicht-blockierend: poll() wird aus der Hauptschleife aufgerufen.
#
#   GET  /                 Weboberflaeche (index.html aus dem Flash)
#   GET  /api/config       gespeicherte Einstellungen
#   POST /api/config?k=v   Einstellungen aendern + dauerhaft speichern
#   POST /api/preview?color=r,g,b&brightness=n   Farbe live zeigen (nicht gespeichert)
#   POST /api/preview?end=1                       Vorschau beenden
#   POST /api/defaults     auf Standardwerte zuruecksetzen
#   GET  /api/state        Live-Zustand (Satz, Romaji, Deutsch, Sprechtext, leuchtende Felder,
#                          Tag/Nacht, Lux, Ansage-Intervall)
#   GET  /api/info         Systeminformationen
#   POST /api/ntp          NTP-Abgleich jetzt
#   POST /api/reboot       Neustart
#
# Werte werden als Query-String uebertragen (nicht im Body): ampule liest den Body
# nur, wenn er im selben TCP-Paket wie die Header ankommt.

import json
import ampule
import config

PORT = 8080
_app = None

_JSON = {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"}
_HTML = {"Content-Type": "text/html; charset=utf-8"}


def _unquote(s):
    s = s.replace("+", " ")
    if "%" not in s:
        return s
    out = bytearray()
    b = s.encode("utf-8")
    i = 0
    while i < len(b):
        if b[i] == 0x25 and i + 2 < len(b):
            try:
                out.append(int(bytes(b[i + 1:i + 3]).decode(), 16))
                i += 3
                continue
            except ValueError:
                pass
        out.append(b[i])
        i += 1
    return out.decode("utf-8")


def _params(request):
    return {_unquote(k): _unquote(v) for k, v in request.params.items()}


def _json(obj, code=200):
    return (code, dict(_JSON), json.dumps(obj).encode("utf-8"))


# ------------------------------------------------------------------ Routen
@ampule.route("/")
def index(request):
    try:
        with open("/index.html", "rb") as f:
            return (200, dict(_HTML), f.read())
    except OSError:
        return (500, dict(_HTML), b"index.html fehlt auf dem Board")


@ampule.route("/api/config")
def get_config(request):
    return _json(_app.cfg)


@ampule.route("/api/config", method="POST")
def set_config(request):
    changed, errors = config.apply(_app.cfg, _params(request))
    if errors:
        return _json({"ok": False, "errors": errors, "config": _app.cfg}, 400)
    msg = "keine Aenderung"
    ok = True
    _app.end_preview()
    if changed:
        ok, msg = config.save(_app.cfg)
        _app.on_config_changed(changed)
    return _json({"ok": ok, "changed": changed, "saved": msg, "config": _app.cfg})


@ampule.route("/api/preview", method="POST")
def preview(request):
    p = _params(request)
    if p.get("end"):
        _app.end_preview()
        return _json({"ok": True})
    try:
        color = config.VALIDATORS["day_color"](p.get("color", ""))
        pct = config.VALIDATORS["day_brightness"](p.get("brightness", ""))
    except Exception as e:
        return _json({"ok": False, "error": str(e)}, 400)
    _app.set_preview(color, pct)
    return _json({"ok": True})


@ampule.route("/api/defaults", method="POST")
def set_defaults(request):
    d = dict(config.DEFAULTS)
    d["day_color"] = list(d["day_color"])
    d["night_color"] = list(d["night_color"])
    changed, _ = config.apply(_app.cfg, d)
    ok, msg = config.save(_app.cfg)
    _app.on_config_changed(changed)
    return _json({"ok": ok, "changed": changed, "saved": msg, "config": _app.cfg})


@ampule.route("/api/state")
def get_state(request):
    return _json(_app.state())


@ampule.route("/api/info")
def get_info(request):
    return _json(_app.info())


@ampule.route("/api/ntp", method="POST")
def ntp_now(request):
    _app.request_ntp()
    return _json({"ok": True})


@ampule.route("/api/reboot", method="POST")
def reboot(request):
    _app.request_reboot()
    return _json({"ok": True})


# ------------------------------------------------------------------ Server
class _Server:
    """Wrapper: gibt angenommenen Verbindungen ein Timeout, damit ein Browser,
    der eine Verbindung oeffnet und nichts sendet, die Uhr nicht anhaelt."""

    def __init__(self, sock):
        self.sock = sock

    def accept(self):
        client, addr = self.sock.accept()
        client.settimeout(1)
        return client, addr


class WebUI:
    def __init__(self, app):
        global _app
        _app = app
        self.server = None

    def start(self, pool):
        self.stop()
        sock = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
        try:
            sock.setsockopt(pool.SOL_SOCKET, pool.SO_REUSEADDR, 1)
        except Exception:
            pass
        sock.bind(("0.0.0.0", PORT))
        sock.listen(2)
        sock.setblocking(False)
        self.server = _Server(sock)
        print("Webserver: http://%s:%d" % (_app.ip(), PORT))

    def stop(self):
        if self.server:
            try:
                self.server.sock.close()
            except Exception:
                pass
        self.server = None

    def poll(self):
        """Bearbeitet hoechstens eine Anfrage. False = Server defekt, neu starten."""
        if not self.server:
            return False
        try:
            ampule.listen(self.server)
            return True
        except OSError as e:
            print("Webserver-Fehler:", e)
            self.stop()
            return False
