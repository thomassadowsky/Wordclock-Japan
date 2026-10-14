#!/usr/bin/env python3
"""Simulator der japanischen Wordclock fuer das Terminal (Mac).

Beispiele:
  python3 wordclock_sim.py                     aktuelle Uhrzeit
  python3 wordclock_sim.py --time 23:55        feste Uhrzeit
  python3 wordclock_sim.py --live              laeuft mit, jede Sekunde neu
  python3 wordclock_sim.py --demo 7            Zeitraffer, 7 Minuten pro Schritt
  python3 wordclock_sim.py --list              alle 1440 Saetze als Liste
  python3 wordclock_sim.py --check             passt der Stil auf das Raster?
  python3 wordclock_sim.py --mode 24h --check  ... z.B. fuer 24h-Format
  python3 wordclock_sim.py --layout mein_raster.txt --mode tageszeit --check
"""
import argparse
import datetime
import sys
import time

import wordclock_core as wc

ON = "\033[1;38;2;64;224;208m"   # tuerkis wie bei der deutschen Uhr
OFF = "\033[38;2;55;55;55m"
RESET = "\033[0m"
TAGE = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


def render(layout, positions, color):
    lit = set(positions)
    cols = len(layout[0])
    lines = []
    for r, row in enumerate(layout):
        cells = []
        for c, ch in enumerate(row):
            on = r * cols + c in lit
            if color:
                cells.append((ON if on else OFF) + ch + RESET)
            else:
                cells.append(ch if on else "・")
        lines.append("   " + " ".join(cells))
    return "\n".join(lines)


def show(h, m, wd, cfg, layout, color):
    parts = wc.phrase(h, m, wd, cfg)
    txt = "".join(t[0] for t in parts)
    pos, bad = wc.find_positions(txt, layout)
    out = ["", "   %02d:%02d  %s" % (h, m, TAGE[wd]), ""]
    if pos is None:
        out.append("   !! Zeichen '%s' nicht (an passender Stelle) im Raster" % bad)
        pos = []
    out.append(render(layout, pos, color))
    out += ["", "   " + " ".join(t[0] for t in parts),
            "   " + " · ".join(t[1] for t in parts),
            "   " + " · ".join(t[2] for t in parts),
            "   → " + wc.german(h, m, wd, cfg), ""]
    return "\n".join(out)


def check(cfg, layout):
    flat = "".join(layout)
    days = range(7) if cfg["weekday"] else [0]
    fails = {}
    needed = set()
    n = 0
    for d in days:
        for h in range(24):
            for m in range(60):
                txt = wc.text(h, m, d, cfg)
                needed.update(txt)
                n += 1
                pos, bad = wc.find_positions(txt, layout)
                if pos is None:
                    fails.setdefault(bad, []).append("%02d:%02d %s" % (h, m, txt))
    absent = sorted(needed - set(flat))
    print("Stil: %s" % cfg)
    print("%d Saetze geprueft, %d nicht darstellbar." %
          (n, sum(len(v) for v in fails.values())))
    if absent:
        print("Zeichen, die im Raster ganz fehlen: " + " ".join(absent))
    for ch, ex in fails.items():
        print("  '%s' fehlt/falsche Reihenfolge: %d x, z.B. %s" % (ch, len(ex), ex[0]))
    unused = [ch for i, ch in enumerate(flat) if ch not in needed]
    print("Im Stil nie benutzte Rasterzeichen: " + " ".join(unused))
    return 0 if not fails else 1


def load_layout(path):
    with open(path, encoding="utf-8") as f:
        rows = [ln.strip().replace(" ", "") for ln in f if ln.strip()]
    if len({len(r) for r in rows}) != 1:
        sys.exit("Layout: alle Zeilen muessen gleich lang sein")
    return tuple(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--time", help="feste Uhrzeit HH:MM")
    ap.add_argument("--day", type=int, help="Wochentag 0=Mo .. 6=So")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--demo", type=int, metavar="MIN", help="Zeitraffer, MIN Minuten pro Schritt")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--layout", help="Rasterdatei (eine Zeile pro Rasterzeile)")
    ap.add_argument("--no-color", action="store_true")
    g = ap.add_argument_group("Textstil")
    g.add_argument("--mode", choices=("ampm", "tageszeit", "24h", "plain"))
    g.add_argument("--zero", choices=("mixed", "12", "0"), help="Stunde 0/12: mixed (0=零, 12=十二), 12 oder 0")
    g.add_argument("--half", action="store_true", help=":30 als 半 (Standard)")
    g.add_argument("--no-half", action="store_true", help=":30 als 三十分 statt 半")
    g.add_argument("--exact", action="store_true", help=":00 mit ちょうど")
    g.add_argument("--with-day", action="store_true", help="今は○曜日の... anzeigen")
    g.add_argument("--greeting", action="store_true", help="。おはようございます！ / 。おやすみ！")
    g.add_argument("--no-prefix", action="store_true", help="ohne 今は")
    g.add_argument("--no-desu", action="store_true", help="ohne です")
    a = ap.parse_args()

    cfg = dict(wc.DEFAULTS)
    if a.mode: cfg["hour_mode"] = a.mode
    if a.zero: cfg["zero_hour"] = a.zero
    if a.half: cfg["half"] = True
    if a.no_half: cfg["half"] = False
    if a.exact: cfg["exact"] = True
    if a.with_day: cfg["weekday"] = True
    if a.greeting: cfg["greeting"] = True
    if a.no_prefix: cfg["prefix"] = False
    if a.no_desu: cfg["desu"] = False
    layout = load_layout(a.layout) if a.layout else wc.LAYOUT
    color = not a.no_color and sys.stdout.isatty()

    if a.check:
        sys.exit(check(cfg, layout))

    now = datetime.datetime.now()
    wd = now.weekday() if a.day is None else a.day

    if a.list:
        for h in range(24):
            for m in range(60):
                p = wc.phrase(h, m, wd, cfg)
                print("%02d:%02d  %s\t%s" % (h, m, "".join(t[0] for t in p),
                                         " ".join(t[1] for t in p)))
        return

    if a.demo:
        t = 0
        try:
            while t < 24 * 60:
                sys.stdout.write("\033[2J\033[H" + show(t // 60, t % 60, wd, cfg, layout, color))
                sys.stdout.flush()
                time.sleep(0.4)
                t += a.demo
        except KeyboardInterrupt:
            pass
        return

    if a.time:
        h, m = (int(x) for x in a.time.split(":"))
        print(show(h, m, wd, cfg, layout, color))
        return

    if a.live:
        last = None
        try:
            while True:
                now = datetime.datetime.now()
                key = (now.hour, now.minute)
                if key != last:
                    sys.stdout.write("\033[2J\033[H" +
                                     show(now.hour, now.minute, now.weekday(), cfg, layout, color))
                    sys.stdout.flush()
                    last = key
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        return

    print(show(now.hour, now.minute, wd, cfg, layout, color))


if __name__ == "__main__":
    main()



