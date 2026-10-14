# wordclock_core.py - Kernlogik der japanischen Wordclock
#
# Reine Logik ohne Abhaengigkeiten: laeuft unveraendert unter CPython (Mac)
# und spaeter unter MicroPython/CircuitPython auf dem ESP32.
#
#   phrase(h, m, wd, cfg)      -> Satzteile [(Kanji, Romaji, Deutsch), ...]
#   german(h, m, wd, cfg)      -> deutsche Uebersetzung als ganzer Satz
#   speech(h, m, wd, cfg)      -> Text fuer die Sprachausgabe (Browser, ja-JP)
#   find_positions(text)       -> Rasterpositionen (0..63) der Zeichen
#   led_index(pos, variant)    -> LED-Nummer auf dem Streifen (Serpentine, Einspeisung unten links)

LAYOUT = (
    "今は月火水木金土",
    "日曜日の午前後零",
    "一二三四五六七八",
    "九十一二時半二三",
    "四五十一二三四五",
    "六七八九分ちょう",
    "どです。おはよう",
    "ございまやすみ！",
)
# Version 3 (Rueckmeldung 03.10.): 今は statt 今日は auch mit Wochentag
# (今は木曜日の午前十時半です), 零 fuer Mitternacht, 。 vor dem Gruss,
# keine Fuellzeichen mehr - alle 64 Felder werden genutzt.
# Gruesse am Ende: 。おはようございます！ / 。おやすみ！ (す wird geteilt).

# Textstil - alles umschaltbar, damit wir ausprobieren koennen, was gut aussieht
DEFAULTS = {
    "hour_mode": "ampm",  # "ampm"      今は午後十一時五十五分です
                          # "tageszeit" 今は夜の十一時五十五分です
                          # "24h"       今は二十三時五十五分です
                          # "plain"     今は十一時五十五分です
    "zero_hour": "mixed", # 12h-Modi: "mixed" = Mitternacht 零時, Mittag 十二時
                          #           "12" = beides 十二時, "0" = beides 零時
    "prefix": True,       # 今は ("jetzt ist") am Anfang (bei weekday immer)
    "desu": True,         # です am Ende
    "half": True,         # :30 als 半 statt 三十分
    "exact": False,       # :00 mit ちょうど ("genau")
    "weekday": False,     # 今は○曜日の... ("jetzt ist Donnerstag, ...")
    "greeting": False,    # 。おはようございます！ (5-9 Uhr) / 。おやすみ！ (22-1 Uhr) am Ende
}

# Tageszeiten fuer hour_mode "tageszeit": (von, bis_exklusiv, Kanji, Romaji, Deutsch)
TAGESZEIT = (
    (0, 4, "夜中", "yonaka", "nachts"),
    (4, 11, "朝", "asa", "morgens"),
    (11, 16, "昼", "hiru", "mittags"),
    (16, 19, "夕方", "yūgata", "am späten Nachmittag"),
    (19, 24, "夜", "yoru", "abends"),
)

_DIG = "〇一二三四五六七八九"
_WD = "月火水木金土日"                       # 0 = Montag (wie time.localtime)
_WD_R = ("getsu", "ka", "sui", "moku", "kin'", "do", "nichi")
_WD_DE = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
_R = ("", "ichi", "ni", "san", "yon", "go", "roku", "nana", "hachi", "kyū")
_HOUR_R = {0: "rei", 4: "yo", 7: "shichi", 9: "ku", 14: "jūyo", 17: "jūshichi", 19: "jūku"}
_FUN_R = ("juppun", "ippun", "nifun", "sanpun", "yonpun", "gofun",
          "roppun", "nanafun", "happun", "kyūfun")


def kanji_num(n):
    """0..59 als Kanji-Zahl: 0 零, 10 十, 11 十一, 25 二十五."""
    if n == 0:
        return "零"
    t, o = divmod(n, 10)
    s = ""
    if t:
        s += ("" if t == 1 else _DIG[t]) + "十"
    if o:
        s += _DIG[o]
    return s


def _r_tens(t):
    return "" if t == 0 else ("jū" if t == 1 else _R[t] + "jū")


def romaji_hour(h):
    base = _HOUR_R.get(h)
    if base is None:
        base = _r_tens(h // 10) + _R[h % 10]
    return base + "-ji"


def romaji_min(m):
    t, o = divmod(m, 10)
    if o == 0:
        return ("" if t == 1 else _R[t]) + "juppun"
    return _r_tens(t) + _FUN_R[o]


def _hour12(h, c):
    hh = h % 12
    if hh == 0 and (c["zero_hour"] == "12" or (c["zero_hour"] == "mixed" and h == 12)):
        hh = 12
    return hh


def phrase(h, m, wd=0, cfg=None):
    """Satz fuer h:m (24h) als Liste von (Kanji, Romaji, Deutsch)."""
    c = dict(DEFAULTS)
    if cfg:
        c.update(cfg)
    p = []
    if c["weekday"] or c["prefix"]:
        p.append(("今は", "ima wa", "jetzt ist"))
    if c["weekday"]:
        p.append((_WD[wd] + "曜日の", _WD_R[wd] + "yōbi no", _WD_DE[wd]))

    mode = c["hour_mode"]
    if mode == "24h":
        hh = h
    else:
        hh = _hour12(h, c)
        if mode == "ampm":
            p.append(("午前", "gozen", "vormittags") if h < 12 else ("午後", "gogo", "nachmittags"))
        elif mode == "tageszeit":
            for a, b, k, r, de in TAGESZEIT:
                if a <= h < b:
                    p.append((k + "の", r + " no", de))
                    break
    p.append((kanji_num(hh) + "時", romaji_hour(hh), "%d Uhr" % hh))

    if m == 0:
        if c["exact"]:
            p.append(("ちょうど", "chōdo", "genau"))
    elif m == 30 and c["half"]:
        p.append(("半", "han", "halb (30)"))
    else:
        p.append((kanji_num(m) + "分", romaji_min(m), "%d Min." % m))

    if c["desu"]:
        p.append(("です", "desu", "(ist)"))
    if c["greeting"]:
        if 5 <= h < 10:
            p.append(("。おはようございます！", "ohayō gozaimasu!", "Guten Morgen!"))
        elif h >= 22 or h < 2:
            p.append(("。おやすみ！", "oyasumi!", "Gute Nacht!"))
    return p


def text(h, m, wd=0, cfg=None):
    return "".join(t[0] for t in phrase(h, m, wd, cfg))


def _de_daypart(h, c):
    mode = c["hour_mode"]
    if mode == "ampm":
        if h < 12:
            return "nachts" if h < 5 else "vormittags"
        return "mittags" if h < 14 else ("nachmittags" if h < 18 else "abends")
    if mode == "tageszeit":
        for a, b, k, r, de in TAGESZEIT:
            if a <= h < b:
                return de
    return ""


def german(h, m, wd=0, cfg=None):
    """Deutsche Uebersetzung des Satzes, z. B. 'Jetzt ist es 3:25 Uhr nachmittags.'"""
    c = dict(DEFAULTS)
    if cfg:
        c.update(cfg)
    if c["hour_mode"] == "24h":
        hh = h
    else:
        hh = _hour12(h, c)
    if m == 0:
        t = ("genau %d Uhr" if c["exact"] else "%d Uhr") % hh
    elif m == 30 and c["half"]:
        nxt = hh + 1
        if c["hour_mode"] != "24h" and nxt > 12:
            nxt -= 12
        t = "halb %d" % (nxt % 24 if c["hour_mode"] == "24h" else nxt)
    else:
        t = "%d:%02d Uhr" % (hh, m)
    dp = _de_daypart(h, c)
    if dp:
        t += " " + dp
    if c["weekday"]:
        s = "Jetzt ist %s, %s." % (_WD_DE[wd], t)
    elif c["prefix"]:
        s = "Jetzt ist es %s." % t
    else:
        s = t[0].upper() + t[1:] + "."
    if c["greeting"]:
        if 5 <= h < 10:
            s += " Guten Morgen!"
        elif h >= 22 or h < 2:
            s += " Gute Nacht!"
    return s


def speech(h, m, wd=0, cfg=None):
    """Text fuer die Sprachausgabe: Satzteile mit kurzen Pausen.
    今日は wird als きょうは geschrieben, damit es nicht wie こんにちは gelesen wird."""
    parts = [t[0] for t in phrase(h, m, wd, cfg)]
    return " ".join("きょうは" if p == "今日は" else p for p in parts)


def find_positions(txt, layout=LAYOUT):
    """Sucht die Zeichen der Reihe nach im Raster (Leserichtung).
    Rueckgabe: (Positionsliste, None) oder (None, fehlendes Zeichen)."""
    flat = "".join(layout)
    pos = []
    i = 0
    for ch in txt:
        j = flat.find(ch, i)
        if j < 0:
            return None, ch
        pos.append(j)
        i = j + 1
    return pos, None


def led_index(pos, cols=8, variant="A", start="unten", rows=8):
    """Rasterposition -> LED-Nummer. Serpentine.
    start="unten": Einspeisung unten links (von vorne gesehen), erste Zeile
    von links nach rechts, darueber zurueck usw. start="oben": oben links.
    Mit "_rechts" (z. B. "unten_rechts"): Einspeisung rechts, also jede Zeile gespiegelt.
    A: 30 LEDs/m, eine LED pro Feld. B: 60 LEDs/m, jede zweite LED."""
    r, c = divmod(pos, cols)
    if start.endswith("_rechts"):
        c = cols - 1 - c
        start = start[:-7]
    rr = rows - 1 - r if start == "unten" else r
    cc = c if rr % 2 == 0 else cols - 1 - c
    if variant == "A":
        return rr * cols + cc
    return rr * (2 * cols - 1) + 2 * cc
