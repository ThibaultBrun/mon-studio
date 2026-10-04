#!/bin/bash
# Installe le raccourci de Mon Studio pour l'utilisateur courant.
# Dépendances (une fois, en administrateur) :
#   sudo apt install python3-pyqt6 libfluidsynth3 fluid-soundfont-gm ffmpeg
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
ICON="$HOME/.local/share/icons/mon-studio.svg"
mkdir -p "$HOME/.local/share/applications" "$HOME/.local/share/icons"
cp "$DIR/mon-studio.svg" "$ICON"
sed -e "s#@DIR@#$DIR#" -e "s#@ICON@#$ICON#" "$DIR/mon-studio.desktop.in" > "$HOME/.local/share/applications/mon-studio.desktop"
DESKTOP=$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")
if [ -d "$DESKTOP" ]; then
    cp "$HOME/.local/share/applications/mon-studio.desktop" "$DESKTOP/"
    chmod +x "$DESKTOP/mon-studio.desktop"
fi
echo "Mon Studio est installé : cherche « Mon Studio » dans le menu ou sur le bureau."
