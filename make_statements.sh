#!/usr/bin/env bash
# make_statements.sh — one-command rebuild of the example "tuned" statement PDFs.
#
#   ./make_statements.sh
#
# Regenerates the statement HTML (build_statements.py), then renders each page to
# PDF with headless Chrome. Chrome does not self-exit after --print-to-pdf in this
# environment, so we launch it in the background, wait for the PDF to finish
# writing, then stop ONLY that headless instance (matched by its unique temp
# profile — your normal Chrome browser is never touched).
set -u
cd "$(dirname "$0")"

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
[ -x "$CHROME" ] || { echo "Chrome not found at: $CHROME  (override with \$CHROME)"; exit 1; }

echo "1/2  Generating statement HTML…"
python3 build_statements.py || { echo "HTML generation failed"; exit 1; }

echo "2/2  Rendering PDFs (headless Chrome)…"

render() {
  local html="$1" pdf="$2" prof size prev tries
  rm -f "$pdf"
  prof="$(mktemp -d "${TMPDIR:-/tmp}/cr.XXXXXX")"
  "$CHROME" --headless --disable-gpu --no-sandbox --no-first-run \
    --disable-background-networking --disable-sync --disable-extensions \
    --disable-component-update --no-pdf-header-footer \
    --user-data-dir="$prof" \
    --print-to-pdf="$pdf" "file://$PWD/$html" >/dev/null 2>&1 &
  local pid=$!

  # Wait until the PDF exists and its size stops growing (write complete).
  prev="-1"
  for tries in $(seq 1 40); do
    sleep 0.5
    [ -f "$pdf" ] || continue
    size="$(stat -f%z "$pdf" 2>/dev/null || echo 0)"
    [ "$size" -gt 1000 ] && [ "$size" = "$prev" ] && break
    prev="$size"
  done

  # Stop only this headless instance (its unique profile path won't match your browser).
  kill "$pid" 2>/dev/null
  pkill -9 -f "$prof" 2>/dev/null
  wait "$pid" 2>/dev/null
  rm -rf "$prof"

  if [ -f "$pdf" ] && [ "$(stat -f%z "$pdf" 2>/dev/null || echo 0)" -gt 1000 ]; then
    echo "   ✓ $pdf  ($(stat -f%z "$pdf") bytes)"
  else
    echo "   ✗ $pdf  FAILED"; return 1
  fi
}

rc=0
render "_statements_html/A_uob.html"           "Example_Statement_A_uob.pdf"           || rc=1
render "_statements_html/B_banque_privee.html" "Example_Statement_B_banque_privee.pdf" || rc=1
render "_statements_html/C_alpine_trust.html"  "Example_Statement_C_alpine_trust.pdf"  || rc=1

[ "$rc" = 0 ] && echo "Done — 3 statement PDFs rebuilt." || echo "Finished with errors."
exit "$rc"
