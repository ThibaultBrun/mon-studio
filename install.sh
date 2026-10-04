#!/bin/bash
# Installe le raccourci de Mon Studio pour l'utilisateur courant.
# Dépendances (une fois, en administrateur) :
#   sudo apt install python3-pyqt6 libfluidsynth3 fluid-soundfont-gm avldrums.lv2-soundfont musescore-general-soundfont-lossless ffmpeg
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
# Banque de sons GeneralUser GS (meilleure que FluidR3), si elle n'est pas déjà installée pour tout le système
SF=/usr/share/sounds/sf2/GeneralUser-GS.sf2
if [ ! -f "$SF" ]; then
    mkdir -p "$HOME/.local/share/sounds/sf2"
    curl -fsSL -o "$HOME/.local/share/sounds/sf2/GeneralUser-GS.sf2" \
        https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2
fi
echo "Mon Studio est installé : cherche « Mon Studio » dans le menu ou sur le bureau."
