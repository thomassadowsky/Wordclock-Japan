#!/bin/bash
# Lädt die übergebenen Dateien auf den Feather (Web Workflow)
HOST=192.168.178.103
PW=nippon
for f in "$@"; do
  curl -sS -f -u ":$PW" -T "$f" "http://$HOST/fs/$(basename "$f")" && echo "✓ $f"
done
