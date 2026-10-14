#!/bin/bash
# deploy.sh - laedt neue und geaenderte Dateien per WLAN auf den Feather (Web Workflow)
#
#   ./deploy.sh            alle geaenderten/neuen Dateien hochladen
#   ./deploy.sh -n         nur anzeigen, was hochgeladen wuerde (Probelauf)
#   ./deploy.sh -f         alles hochladen, ohne Vergleich
#   ./deploy.sh -l         zusaetzlich Bibliotheken per circup installieren/aktualisieren
#   ./deploy.sh datei ...  nur diese Dateien (ebenfalls mit Vergleich, -f erzwingt)
#
# Verglichen wird der Inhalt: jede Datei wird vom Board geladen und mit der lokalen
# verglichen. Das stimmt auch nach einem Board-Reset oder Upload von einem anderen Rechner.
# code.py wird zuletzt hochgeladen, damit der Neustart alle neuen Module schon vorfindet.
#
# Host/Passwort lassen sich ueberschreiben: WC_HOST=... WC_PW=... ./deploy.sh
#
# Der Web Workflow (Port 80) wird von CircuitPython nur nebenbei bedient, waehrend
# code.py laeuft. Er antwortet deshalb manchmal langsam, besonders wenn die
# Weboberflaeche (Port 8080) im Browser offen ist. Daher grosszuegige Timeouts + Wiederholungen.

HOST=${WC_HOST:-192.168.178.103}  # sample value. replace with your ip address
PW=${WC_PW:-nippon}               # sample value. replace with your password for ssh

# Was aufs Board gehoert: alle .py/.html/.json hier im Ordner, ausser diesen
EXCLUDE="wordclock_sim.py deploy.sh"
# Bibliotheken fuer -l
LIBS="neopixel adafruit_ntp adafruit_veml7700 adafruit_bh1750"

cd "$(dirname "$0")" || exit 1

# curl mit Wiederholungen (auch bei Timeout)
CURL=(curl -sS -f --connect-timeout 5 --retry 3 --retry-delay 1 --retry-all-errors)

dry=0; force=0; libs=0
while getopts "nfl" opt; do
  case $opt in
    n) dry=1 ;;
    f) force=1 ;;
    l) libs=1 ;;
    *) sed -n '3,9p' "$0"; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

# Board erreichbar?
if ! "${CURL[@]}" -m 15 -u ":$PW" -o /dev/null "http://$HOST/cp/version.json"; then
  echo "✗ Board $HOST antwortet nicht (WLAN an? IP richtig? Passwort?)" >&2
  echo "  Tipp: Weboberfläche (:8080) im Browser schließen und nochmal versuchen." >&2
  exit 1
fi

# Dateiliste
if [ $# -gt 0 ]; then
  files=("$@")
else
  files=()
  for f in *.py *.html *.json; do
    [ -f "$f" ] || continue
    case " $EXCLUDE " in *" $f "*) continue ;; esac
    files+=("$f")
  done
fi

# code.py ans Ende
ordered=()
has_code=0
for f in "${files[@]}"; do
  if [ "$(basename "$f")" = "code.py" ]; then has_code=1; else ordered+=("$f"); fi
done
[ $has_code = 1 ] && ordered+=("code.py")

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT

todo=()
for f in "${ordered[@]}"; do
  if [ ! -f "$f" ]; then
    echo "✗ $f gibt es lokal nicht" >&2
    exit 1
  fi
  name=$(basename "$f")
  if [ $force = 1 ]; then
    todo+=("$f")
  elif ! curl -s -f --connect-timeout 5 -m 20 -u ":$PW" -o "$tmp" "http://$HOST/fs/$name"; then
    echo "  neu        $name"
    todo+=("$f")
  elif ! cmp -s "$f" "$tmp"; then
    echo "  geändert   $name"
    todo+=("$f")
  fi
done

if [ ${#todo[@]} = 0 ]; then
  echo "✓ Board ist aktuell (${#ordered[@]} Dateien geprüft)"
elif [ $dry = 1 ]; then
  echo "Probelauf: ${#todo[@]} Datei(en) würden hochgeladen"
else
  fail=0
  for f in "${todo[@]}"; do
    if "${CURL[@]}" -m 60 -u ":$PW" -T "$f" "http://$HOST/fs/$(basename "$f")"; then
      echo "✓ $(basename "$f")"
    else
      echo "✗ $(basename "$f")" >&2
      fail=1
    fi
  done
  [ $fail = 1 ] && exit 1
fi

if [ $libs = 1 ]; then
  if [ $dry = 1 ]; then
    echo "Probelauf: circup install $LIBS"
  else
    CIRCUP=.venv/bin/circup
    [ -x "$CIRCUP" ] || CIRCUP=circup
    "$CIRCUP" --host "$HOST" --password "$PW" install $LIBS
  fi
fi
