#!/usr/bin/env bash
# Installs Background Genesis into the local application menu (Plasma/KDE).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_FILE="$REPO_DIR/qutec_sfondi_gui.py"
ENTRY_NAME="background-genesis.desktop"
TARGET_DIR="$HOME/.local/share/applications"
TARGET="$TARGET_DIR/$ENTRY_NAME"

command -v python3 >/dev/null || { echo "Errore: python3 non trovato." >&2; exit 1; }
[[ -f "$APP_FILE" ]] || { echo "Errore: $APP_FILE non trovato." >&2; exit 1; }
python3 -c "import PIL, PySide6" 2>/dev/null || {
    echo "Dipendenze mancanti. Installa con:"
    echo "  python3 -m venv .venv && source .venv/bin/activate && pip install Pillow PySide6"
    exit 1
}

mkdir -p "$TARGET_DIR"
sed -e "s|^Exec=.*|Exec=python3 $APP_FILE %f|" \
    -e "s|^Path=.*|Path=$REPO_DIR|" \
    "$REPO_DIR/background-genesis.desktop" > "$TARGET"

if command -v desktop-file-validate >/dev/null; then
    desktop-file-validate "$TARGET"
fi
if command -v kbuildsycoca6 >/dev/null; then
    kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
elif command -v update-desktop-database >/dev/null; then
    update-desktop-database "$TARGET_DIR" 2>/dev/null || true
fi

echo "Background Genesis aggiunta al menu applicazioni ($TARGET)."
echo "Cercala nel lanciatore con: Background Genesis"
