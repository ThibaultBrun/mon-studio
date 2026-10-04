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

## 🏆 Le mode défi

Comme les leçons d'Ableton Learning Music, 12 petits défis progressifs : batterie (battement de cœur, backbeat, charleston, boom bap, électro), accords, basse, mélodie, puis un premier morceau complet.

- **🎧 Écoute et recopie** : on écoute le modèle (avec l'accompagnement quand il le faut) et on le reproduit dans la grille.
- **🎨 À toi de créer** : une consigne libre, par exemple « une suite qui commence et finit par La m » ou « une mélodie qui finit sur la note de base ».
- **✅ Vérifie !** donne un retour précis (« Il manque 2 coups sur Grosse caisse », « Mesure 3 : il faut l'accord Do »), **💡 Un indice** aide quand on bloque.
- La progression est gardée, et le morceau en cours est mis de côté puis retrouvé en quittant les défis.

![Défis](docs/defis.png)

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
- `defis.py` : les défis, leurs vérifications et la progression.
- `mon_studio.py` : l'interface PyQt6.

Les sons viennent de la banque [GeneralUser GS](https://github.com/mrbumpy409/GeneralUser-GS) (téléchargée par `install.sh`), avec la banque FluidR3 en secours.

## Licence

MIT, voir [LICENSE](LICENSE). Les banques de sons ont leur propre licence : GeneralUser GS (libre d'utilisation, y compris dans des logiciels) et FluidR3 GM (MIT).
