# Mon Studio sur Windows

## Installation automatique (recommandé)

1. Installe **Python 3** depuis <https://www.python.org/downloads/> → **coche « Add Python to PATH »**.
2. Télécharge/clone ce dossier sur le PC.
3. Clic droit sur **`install_windows.ps1`** → **« Exécuter avec PowerShell »**.
   - S'il refuse (politique d'exécution), ouvre PowerShell et lance :
     `powershell -ExecutionPolicy Bypass -File install_windows.ps1`

Le script installe tout **en local** dans le dossier (rien qui touche le système) :
venv + PyQt6, les DLL **FluidSynth** (`bin\`), la **banque de sons** (`soundfonts\`),
**ffmpeg** (`bin\`), et crée un raccourci **« Mon Studio »** sur le Bureau.

Ensuite : double-clic sur **Mon Studio** 🎵

## Ce qui a été adapté pour Windows
- Chargement de **FluidSynth** : `libfluidsynth-3.dll` (au lieu de `libfluidsynth.so.3`), cherché dans `bin\`.
- **Driver audio** : `wasapi` (puis `dsound`) au lieu de `pulseaudio`. Forçable avec la variable `MONSTUDIO_AUDIO_DRIVER`.
- **Banque de sons** : cherchée d'abord dans `soundfonts\` à côté de l'appli, puis `%APPDATA%\MonStudio\`.
- **ffmpeg** : utilisé depuis `bin\` si présent, sinon le PATH.
- **Sauvegardes** : `%APPDATA%\MonStudio\` ; les créations vont dans le dossier **Musique**.

## Installation manuelle (si le script échoue)
1. `py -3 -m venv .venv` puis `.\.venv\Scripts\python -m pip install PyQt6`
2. FluidSynth : récupère la release **win10-x64** sur <https://github.com/FluidSynth/fluidsynth/releases>, copie les `*.dll` du dossier `bin\` de l'archive dans un dossier **`bin\`** ici.
3. Banque de sons : télécharge <https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2> dans **`soundfonts\`**.
4. ffmpeg : récupère <https://www.gyan.dev/ffmpeg/builds/> (essentials), mets `ffmpeg.exe` dans **`bin\`**.
5. Lance : `.\.venv\Scripts\pythonw.exe mon_studio.py`

## Souci de son ?
Teste un autre driver : dans PowerShell, `($env:MONSTUDIO_AUDIO_DRIVER="dsound")` puis relance.
