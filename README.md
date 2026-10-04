# Mon Studio

Une appli de bureau toute simple pour composer un morceau, pensée pour les enfants, dans l'esprit d'[Ableton Learning Music](https://learningmusic.ableton.com/fr/).

![Mon Studio](docs/capture.png)

## Le principe

- **4 lignes** : 🥁 Batterie, 🎸 Basse, 🎹 Accords, 🎵 Mélodie.
- Chaque ligne a ses **motifs** (A, B, C…), qu'on édite sur une grille en bas de la fenêtre.
- En haut, une **ligne de temps** de 16 mesures : pour chaque ligne et chaque mesure, on choisit quel motif joue.

## Fait pour ne pas jouer faux

- La **mélodie** ne propose que les notes de la gamme choisie.
- Les **accords** se choisissent parmi ceux de la gamme (La m, Do, Fa, Sol…), joués tenus, rythmés ou en arpège.
- La **basse suit les accords** : « Note 1 » est toujours la base de l'accord du moment, donc n'importe quelle basse va avec n'importe quelle suite d'accords.
- Plusieurs cases à la suite font une note tenue ; chaque clic fait entendre la note.

![Accords](docs/accords.png)

## Pour démarrer vite

- **✨ Motifs prêts** : boom bap, pop rock, électro, funk, reggaeton, trap, roulements… ; suites d'accords pop, épique, émotion, jazz… ; basses et mélodies.
- **🎁 Morceaux prêts** : Hip-hop chill, Pop joyeuse, Électro, Reggaeton.
- **🔁 Écouter ce motif** fait tourner le motif en boucle pendant qu'on le modifie.

## Et après

- **💾 Enregistrer / 📂 Ouvrir** : les morceaux sont gardés en JSON dans `Musique/Mes créations/Projets`.
- **🎧 Exporter** : le morceau devient un MP3 « Mes créations - titre » dans `Musique/Mes créations`, prêt à être mixé dans [Mixxx](https://mixxx.org).

## Installation (Ubuntu / Debian)

```bash
sudo apt install python3-pyqt6 libfluidsynth3 fluid-soundfont-gm ffmpeg
git clone https://github.com/ThibaultBrun/mon-studio.git
cd mon-studio
./install.sh
```

## Sous le capot

- `musique.py` : gammes, accords, motifs, modèles prêts, conversion du morceau en notes.
- `moteur.py` : FluidSynth via ctypes ; lecture en direct avec le séquenceur de FluidSynth (notes programmées 200 ms à l'avance), rendu WAV pour l'export.
- `mon_studio.py` : l'interface PyQt6.

Les sons viennent de la banque General MIDI FluidR3.
