#!/usr/bin/env python3
"""Mon Studio : composer un morceau avec 4 lignes (batterie, basse, accords, mélodie) et des motifs à placer
sur une ligne de temps. Pensé pour un enfant : gros boutons, notes toujours dans la gamme, modèles prêts."""
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import time as clock
from pathlib import Path

from PyQt6.QtCore import QEvent, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout,
                             QInputDialog, QLabel, QLineEdit, QListWidget, QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox,
                             QVBoxLayout, QWidget)

import defis
import moteur
import musique as m

def music_dir():
    """Dossier Musique de l'utilisateur, quelle que soit la langue/plateforme."""
    if sys.platform.startswith("win") or sys.platform == "darwin":
        # Windows/macOS : dossier « Music » standard
        for name in ("Music", "Musique"):
            p = Path.home() / name
            if p.exists():
                return p
        return Path.home() / "Music"
    try:
        path = subprocess.run(["xdg-user-dir", "MUSIC"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        path = ""
    return Path(path) if path and Path(path) != Path.home() else Path.home() / "Musique"


def data_dir():
    """Dossier des données de l'appli (sauvegardes auto, défis) selon l'OS."""
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "MonStudio"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MonStudio"
    return Path.home() / ".local/share/mon-studio-donnees"


def ffmpeg_bin():
    """ffmpeg bundlé (bin/ à côté de l'appli) sinon celui du PATH."""
    import shutil
    exe = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
    local = Path(__file__).resolve().parent / "bin" / exe
    if local.exists():
        return str(local)
    return shutil.which("ffmpeg") or "ffmpeg"


CREATIONS = music_dir() / "Mes créations"
DATA = data_dir()
FFMPEG = ffmpeg_bin()
AUTOSAVE = DATA / "sauvegarde-auto.json"
UNDO_LIMIT = 80
UNDO_GROUP_SECONDS = 0.6  # les clics rapprochés (glisser dans la grille) s'annulent d'un coup
PROJECTS = CREATIONS / "Projets"
LOOKAHEAD_MS = 200
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LATENCY_MS = 40  # délai de la carte son, pour caler les notes enregistrées au clavier
# Jeu au clavier : touches repérées par leur position (codes XKB), pour marcher en AZERTY comme en QWERTY
HOME_ROW = list(range(38, 48))   # rangée du milieu : Q S D F G H J K L M (AZERTY)
TOP_ROW = list(range(24, 34))    # rangée du dessus : A Z E R T Y U I O P (AZERTY)
HOME_LETTERS, TOP_LETTERS = "QSDFGHJKLM", "AZERTYUIOP"
MAX_KEY_ROWS = {"batterie": len(m.DRUM_ROWS), "basse": m.BASS_ROWS, "accords": 7, "melodie": m.MELODY_ROWS}


def key_slot(event):
    """('milieu' | 'haut', position 0-9) de la touche, ou None."""
    code = event.nativeScanCode()
    if code in HOME_ROW:
        return "milieu", HOME_ROW.index(code)
    if code in TOP_ROW:
        return "haut", TOP_ROW.index(code)
    letter = event.text().upper()  # secours si le code n'est pas disponible
    if letter and letter in HOME_LETTERS:
        return "milieu", HOME_LETTERS.index(letter)
    if letter and letter in TOP_LETTERS:
        return "haut", TOP_LETTERS.index(letter)
    return None


def slot_row(lane, slot):
    """Ligne de la grille jouée par une touche (0 = en bas), ou None."""
    row_kind, index = slot
    row = index if row_kind == "milieu" else (7 + index if lane == "melodie" else None)
    return row if row is not None and row < MAX_KEY_ROWS[lane] else None


def row_key(lane, row):
    """Lettre de la touche qui joue cette ligne (pour l'afficher dans la grille)."""
    if row < len(HOME_LETTERS) and row < MAX_KEY_ROWS[lane]:
        return HOME_LETTERS[row]
    if lane == "melodie" and 0 <= row - 7 < len(TOP_LETTERS):
        return TOP_LETTERS[row - 7]
    return ""

STYLE = """
QWidget { font-size: 15px; }
QPushButton { font-size: 15px; font-weight: bold; padding: 8px 14px; border-radius: 12px;
              background: #4a90e2; color: white; border: none; }
QPushButton:hover { background: #357abd; }
QPushButton:checked { background: #1a3d66; }
QPushButton#play { background: #43a047; font-size: 20px; min-width: 130px; }
QPushButton#play:checked { background: #e53935; }
QPushButton#light { background: #eef4fc; color: #1a3d66; border: 2px solid #4a90e2; }
QPushButton#light:hover { background: #d6e6fa; }
QPushButton#mute { background: #ddd; color: #333; padding: 4px 8px; }
QPushButton#mute:checked { background: #e53935; color: white; }
QPushButton#chip { background: white; color: #1a1a1a; border: 2px solid #bbb; padding: 6px 12px; }
QPushButton#chip:checked { border: 3px solid #1a3d66; background: #fff8d6; }
QLabel#title { font-size: 22px; font-weight: bold; color: #4a90e2; }
QLabel#lane { font-size: 17px; font-weight: bold; }
QLabel#help { color: #555; font-size: 14px; }
QComboBox, QSpinBox { font-size: 15px; padding: 4px 8px; }
QFrame#defis { background: #fff8d6; border: 2px solid #f0c040; border-radius: 16px; }
QFrame#defis QLabel { background: transparent; color: #1a1a1a; }
QLabel#defi_title { font-size: 20px; font-weight: bold; color: #1a3d66; }
QLabel#defi_text { font-size: 15px; color: #222; }
QLabel#feedback { font-size: 17px; font-weight: bold; padding: 8px; border-radius: 10px; }
QPushButton#check { background: #43a047; font-size: 18px; }
QPushButton#next { background: #ff9800; font-size: 17px; }
QListWidget { font-size: 15px; border-radius: 10px; }
"""


def lane_color(lane, index=0):
    """Couleur d'un motif : la couleur de la ligne, plus ou moins claire selon la lettre."""
    color = QColor(m.LANE_INFO[lane][2])
    return color.lighter(100 + (index % 4) * 18)


def short_name(pattern):
    return pattern["name"].split(" · ")[0]


def apply_light_theme(app):
    """Toujours le même thème clair et coloré, même si le bureau est en thème sombre
    (sinon du texte blanc par défaut se retrouve sur nos fonds clairs)."""
    app.setStyle("Fusion")
    app.setPalette(app.style().standardPalette())


# --- Ligne de temps (une rangée par instrument) ---
class TimelineRow(QWidget):
    clicked = pyqtSignal(str, int, bool)  # ligne, mesure, clic droit

    def __init__(self, studio, lane):
        super().__init__()
        self.studio, self.lane = studio, lane
        self.setMinimumHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.last_bar = None

    def bar_at(self, x):
        return max(0, min(m.SONG_BARS - 1, int(x / (self.width() / m.SONG_BARS))))

    def mousePressEvent(self, event):
        self.last_bar = self.bar_at(event.position().x())
        self.clicked.emit(self.lane, self.last_bar, event.button() == Qt.MouseButton.RightButton)

    def mouseMoveEvent(self, event):  # glisser pour peindre plusieurs mesures
        bar = self.bar_at(event.position().x())
        if bar != self.last_bar and event.buttons() & Qt.MouseButton.LeftButton:
            self.last_bar = bar
            self.studio.paint_bar(self.lane, bar)

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        lane_data = self.studio.project["lanes"][self.lane]
        w = self.width() / m.SONG_BARS
        selected = self.lane == self.studio.lane
        painter.fillRect(self.rect(), QColor("#fffbe8" if selected else "#f4f4f4"))
        for bar in range(m.SONG_BARS):
            painter.setPen(QPen(QColor("#ccc"), 1))
            painter.drawLine(int(bar * w), 0, int(bar * w), self.height())
            cell = lane_data["song"][bar]
            if not cell or cell[0] >= len(lane_data["patterns"]):
                continue
            pattern = lane_data["patterns"][cell[0]]
            rect = QRectF(bar * w + 2, 6, w - 4, self.height() - 12)
            painter.setBrush(lane_color(self.lane, cell[0]).darker(130 if lane_data["muted"] else 100))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 8, 8)
            if cell[1] == 0:  # nom du motif sur sa première mesure
                painter.setPen(QColor("white"))
                painter.setFont(QFont(self.font().family(), 13, QFont.Weight.Bold))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, short_name(pattern))
        self.studio.draw_playhead(painter, self.width(), self.height())


class BarNumbers(QWidget):
    clicked = pyqtSignal(int)

    def __init__(self, studio):
        super().__init__()
        self.studio = studio
        self.setFixedHeight(26)

    def mousePressEvent(self, event):
        self.clicked.emit(int(event.position().x() / (self.width() / m.SONG_BARS)))

    def paintEvent(self, _):
        painter = QPainter(self)
        w = self.width() / m.SONG_BARS
        painter.setPen(QColor("#666"))
        for bar in range(m.SONG_BARS):
            painter.drawText(QRectF(bar * w, 0, w, self.height()), Qt.AlignmentFlag.AlignCenter, str(bar + 1))
        self.studio.draw_playhead(painter, self.width(), self.height())


# --- Éditeur de motif (grille) ---
class GridEditor(QWidget):
    LABEL_W = 170

    def __init__(self, studio):
        super().__init__()
        self.studio = studio
        self.drag_value = None

    def layout_info(self):
        lane, pattern = self.studio.lane, self.studio.current_pattern()
        if lane == "accords":
            columns, rows = m.BEATS_PER_BAR * pattern["bars"], 7
        else:
            columns = m.STEPS_PER_BAR * pattern["bars"]
            rows = {"batterie": len(m.DRUM_ROWS), "basse": m.BASS_ROWS, "melodie": m.MELODY_ROWS}[lane]
        return columns, rows

    def row_labels(self):
        lane, key = self.studio.lane, m.KEYS[self.studio.project["key"]]
        if lane == "batterie":
            return [name for name, _, _ in reversed(m.DRUM_ROWS)]
        if lane == "accords":
            return [m.chord_name(key, d) for d in range(6, -1, -1)]
        if lane == "basse":
            return [f"Note {r + 1}" + (" (base)" if r == 0 else " (octave)" if r == 7 else "") for r in range(m.BASS_ROWS - 1, -1, -1)]
        base = 60 if key[1] < 5 else 48
        return [m.note_name(key, m.scale_note(key, r, base)) + ("  ↑" if r >= 7 else "") for r in range(m.MELODY_ROWS - 1, -1, -1)]

    def sizeHint(self):
        if not self.studio.current_pattern():
            return QSize(600, 200)
        columns, rows = self.layout_info()
        col_w = 64 if self.studio.lane == "accords" else 34
        return QSize(self.LABEL_W + columns * col_w + 2, rows * self.row_height() + 2)

    def row_height(self):
        return 26 if self.studio.lane == "melodie" else 34

    def cell_at(self, pos):
        columns, rows = self.layout_info()
        col_w = (self.width() - self.LABEL_W) / columns
        col, row_from_top = int((pos.x() - self.LABEL_W) / col_w), int(pos.y() / self.row_height())
        if pos.x() < self.LABEL_W or not (0 <= col < columns and 0 <= row_from_top < rows):
            return None
        return rows - 1 - row_from_top, col

    def mousePressEvent(self, event):
        cell = self.cell_at(event.position())
        if not cell:
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.drag_value = None
            self.studio.cycle_accent(*cell)
        else:
            self.drag_value = self.studio.toggle_cell(*cell)

    def mouseMoveEvent(self, event):
        cell = self.cell_at(event.position())
        if cell and event.buttons() & Qt.MouseButton.LeftButton and self.drag_value is not None:
            self.studio.toggle_cell(*cell, self.drag_value)

    def paintEvent(self, _):
        pattern = self.studio.current_pattern()
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("white"))
        if not pattern:
            painter.setPen(QColor("#888"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Choisis un motif tout prêt avec « ✨ Motifs prêts », ou crée-en un avec « ➕ Nouveau ».")
            return
        lane = self.studio.lane
        columns, rows = self.layout_info()
        rh = self.row_height()
        col_w = (self.width() - self.LABEL_W) / columns
        color = lane_color(lane, self.studio.selected[lane])
        labels = self.row_labels()
        held = self.studio.held_rows()
        for r in range(rows):
            y = r * rh
            row = rows - 1 - r
            background = "#ffd54f" if row in held else ("#f0f0f0" if r % 2 else "#e6e6e6")
            painter.fillRect(QRectF(0, y, self.LABEL_W, rh), QColor(background))
            key = row_key(lane, row)
            painter.setPen(QColor("#4a90e2"))
            painter.setFont(QFont(self.font().family(), 10, QFont.Weight.Bold))
            painter.drawText(QRectF(8, y, 22, rh), Qt.AlignmentFlag.AlignVCenter, key)
            painter.setPen(QColor("#333"))
            painter.setFont(self.font())
            painter.drawText(QRectF(30, y, self.LABEL_W - 32, rh), Qt.AlignmentFlag.AlignVCenter, labels[r])
        if lane == "accords":
            lit = {(6 - d, beat) for beat, d in enumerate(pattern["chords"]) if d is not None}
        else:
            lit = {(rows - 1 - r, s) for r, s in pattern["cells"]}
        per_beat = 1 if lane == "accords" else 4
        for c in range(columns):
            x = self.LABEL_W + c * col_w
            for r in range(rows):
                rect = QRectF(x + 1, r * rh + 1, col_w - 2, rh - 2)
                if (r, c) in lit:
                    accent = None if lane == "accords" else m.accent_of(pattern, rows - 1 - r, c)
                    fill = color.darker(140) if accent == "fort" else color.lighter(155) if accent == "doux" else color
                    painter.fillRect(rect, fill)
                    if accent:
                        painter.setPen(QColor("white" if accent == "fort" else "#555"))
                        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "▲" if accent == "fort" else "▽")
                else:
                    shade = "#fafafa" if (c // per_beat) % 2 == 0 else "#efefef"
                    painter.fillRect(rect, QColor(shade))
            bar_line = c % (m.BEATS_PER_BAR if lane == "accords" else m.STEPS_PER_BAR) == 0
            painter.setPen(QPen(QColor("#555" if bar_line else "#ccc"), 2 if bar_line else 1))
            painter.drawLine(int(x), 0, int(x), rows * rh)
        # tête de lecture dans le motif
        step = self.studio.pattern_play_step()
        if step is not None:
            x = self.LABEL_W + (step / (4 if lane == "accords" else 1)) * col_w
            painter.setPen(QPen(QColor("#e53935"), 3))
            painter.drawLine(int(x), 0, int(x), rows * rh)


# --- Panneau des défis ---
class DefiPanel(QFrame):
    def __init__(self, studio):
        super().__init__()
        self.studio = studio
        self.index = None
        self.setObjectName("defis")
        self.setFixedWidth(430)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("🏆 Défis")
        title.setObjectName("title")
        header.addWidget(title)
        self.progress = QLabel()
        header.addWidget(self.progress, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(header)
        self.list = QListWidget()
        self.list.setFixedHeight(270)  # les 12 défis sans défiler
        self.list.currentRowChanged.connect(lambda row: row >= 0 and row != self.index and studio.start_defi(row))
        layout.addWidget(self.list)
        self.title = QLabel()
        self.title.setObjectName("defi_title")
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.text = QLabel()
        self.text.setObjectName("defi_text")
        self.text.setWordWrap(True)
        layout.addWidget(self.text)
        self.model_btn = QPushButton()
        self.model_btn.clicked.connect(lambda: studio.listen_defi("modele"))
        self.mine_btn = QPushButton("▶ Écouter ma version")
        self.mine_btn.setObjectName("light")
        self.mine_btn.clicked.connect(lambda: studio.listen_defi("moi"))
        self.check_btn = QPushButton("✅ J'ai fini, vérifie !")
        self.check_btn.setObjectName("check")
        self.check_btn.clicked.connect(studio.check_defi)
        self.hint_btn = QPushButton("💡 Un indice")
        self.hint_btn.setObjectName("light")
        self.hint_btn.clicked.connect(self.show_hint)
        for button in (self.model_btn, self.mine_btn, self.check_btn, self.hint_btn):
            layout.addWidget(button)
        self.feedback = QLabel()
        self.feedback.setObjectName("feedback")
        self.feedback.setWordWrap(True)
        self.feedback.setMinimumHeight(90)
        self.feedback.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.feedback.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        layout.addWidget(self.feedback)
        self.next_btn = QPushButton("➡ Défi suivant")
        self.next_btn.setObjectName("next")
        self.next_btn.clicked.connect(lambda: studio.start_defi(self.index + 1))
        layout.addWidget(self.next_btn)
        layout.addStretch()
        quit_btn = QPushButton("🚪 Quitter les défis")
        quit_btn.setObjectName("light")
        quit_btn.clicked.connect(studio.quit_defis)
        layout.addWidget(quit_btn)

    def refresh_list(self):
        done = defis.load_progress()
        self.list.blockSignals(True)
        self.list.clear()
        for i, defi in enumerate(defis.DEFIS):
            self.list.addItem(f"{'✅' if defi['id'] in done else '⬜'}  {i + 1}. {defi['titre']}")
        if self.index is not None:
            self.list.setCurrentRow(self.index)
        self.list.blockSignals(False)
        self.progress.setText(f"⭐ {len(done & {d['id'] for d in defis.DEFIS})} / {len(defis.DEFIS)} réussis")

    def show_defi(self, index):
        self.index = index
        defi = defis.DEFIS[index]
        kind = "🎧 Écoute et recopie" if defi["type"] == "reproduire" else "🎨 À toi de créer"
        self.title.setText(f"{index + 1}. {defi['titre']}")
        self.text.setText(f"{kind}\n\n{defi['texte']}")
        self.model_btn.setText("🎧 Écouter le modèle" if defi["type"] == "reproduire" else "🎧 Écouter un exemple")
        self.set_feedback("", None)
        self.next_btn.setVisible(False)
        self.refresh_list()

    def show_hint(self):
        self.set_feedback("💡 " + defis.DEFIS[self.index]["indice"], "hint")

    def set_feedback(self, text, state):
        colors = {True: "#c8f0c8", False: "#ffe0cc", "hint": "#ddeeff", None: "transparent"}
        self.feedback.setText(text)
        self.feedback.setStyleSheet(f"background: {colors[state]}; color: #1a1a1a;")


# --- Fenêtre principale ---
class Studio(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎛 Mon Studio")
        self.setStyleSheet(STYLE)
        self.resize(1500, 920)
        self.engine = moteur.Engine()
        self.project = self.restore_autosave() or m.STYLES["Hip-hop chill"]()
        self.undo_stack, self.redo_stack = [], []
        self.snapshot = json.dumps(self.project)
        self.last_change = 0.0
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(self.autosave)
        self.lane = "batterie"
        self.selected = {lane: 0 if self.project["lanes"][lane]["patterns"] else None for lane in m.LANES}
        self.playing = None      # None, "song" ou "pattern"
        self.events = {}
        self.loop_steps = 0
        self.dirty = True
        self.start_tick = 0
        self.next_step = 0
        self.first_step = 0
        self.save_path = None
        self.custom_source = None
        self.custom_name = None
        self.before_defis = None   # morceau mis de côté pendant les défis
        self.held = {}             # touches enfoncées : slot -> (canal, notes, ligne, début en pas)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(28, 18, 28, 18)  # de l'air autour de la fenêtre
        outer.setSpacing(24)
        root = QVBoxLayout()
        root.setSpacing(12)
        outer.addLayout(root, 1)
        root.addLayout(self.build_top_bar())
        self.help = QLabel()
        self.help.setObjectName("help")
        self.help.setWordWrap(True)
        root.addWidget(self.help)
        root.addLayout(self.build_timeline())
        root.addLayout(self.build_editor_bar())
        self.grid = GridEditor(self)
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidget(self.grid)
        self.grid_scroll.setWidgetResizable(True)  # la grille remplit la largeur, et défile si elle est plus grande
        root.addWidget(self.grid_scroll, 1)
        self.defi_panel = DefiPanel(self)
        self.defi_panel.hide()
        outer.addWidget(self.defi_panel)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(20)
        QApplication.instance().installEventFilter(self)  # le clavier joue de la musique
        self.apply_instruments()
        self.refresh_all()

    # ---------- construction ----------
    def build_top_bar(self):
        bar = QHBoxLayout()
        title = QLabel("🎛 Mon Studio")
        title.setObjectName("title")
        bar.addWidget(title)
        self.play_btn = QPushButton("▶ Lecture")
        self.play_btn.setObjectName("play")
        self.play_btn.setCheckable(True)
        self.play_btn.clicked.connect(lambda: self.toggle_play("song"))
        bar.addWidget(self.play_btn)
        bar.addWidget(QLabel("Tempo"))
        self.tempo = QSpinBox()
        self.tempo.setRange(60, 180)
        self.tempo.setSuffix(" BPM")
        self.tempo.valueChanged.connect(self.set_tempo)
        bar.addWidget(self.tempo)
        bar.addWidget(QLabel("Gamme"))
        self.key = QComboBox()
        self.key.addItems([k[0] for k in m.KEYS])
        self.key.currentIndexChanged.connect(self.set_key)
        bar.addWidget(self.key)
        self.swing_label = QLabel()
        self.swing_label.setMinimumWidth(95)
        bar.addWidget(self.swing_label)
        self.swing = QSlider(Qt.Orientation.Horizontal)
        self.swing.setRange(0, m.MAX_SWING)
        self.swing.setFixedWidth(110)
        self.swing.setToolTip("Le swing fait « balancer » le rythme, comme en hip-hop ou en jazz")
        self.swing.valueChanged.connect(self.set_swing)
        bar.addWidget(self.swing)
        self.human_label = QLabel()
        self.human_label.setMinimumWidth(105)
        bar.addWidget(self.human_label)
        self.human = QSlider(Qt.Orientation.Horizontal)
        self.human.setRange(0, 100)
        self.human.setFixedWidth(110)
        self.human.setToolTip("Petites imperfections de force et de placement, comme un vrai musicien. "
                              "À 0, tout est pile sur la grille (effet robot).")
        self.human.valueChanged.connect(self.set_human)
        bar.addWidget(self.human)
        self.undo_btn = QPushButton("↩")
        self.undo_btn.setToolTip("Annuler (Ctrl+Z)")
        self.undo_btn.clicked.connect(self.undo)
        self.redo_btn = QPushButton("↪")
        self.redo_btn.setToolTip("Rétablir (Ctrl+Y)")
        self.redo_btn.clicked.connect(self.redo)
        for button in (self.undo_btn, self.redo_btn):
            button.setObjectName("light")
            button.setFixedWidth(52)
            bar.addWidget(button)
        bar.addStretch()
        rows = QVBoxLayout()  # 1re ligne : jouer et régler ; 2e ligne : défis, morceaux et fichiers
        rows.addLayout(bar)
        bar = QHBoxLayout()
        rows.addLayout(bar)
        self.defis_btn = QPushButton("🏆 Défis")
        self.defis_btn.setObjectName("next")
        self.defis_btn.setCheckable(True)
        self.defis_btn.clicked.connect(self.toggle_defis)
        bar.addWidget(self.defis_btn)
        styles = QPushButton("🎁 Morceaux prêts")
        styles.setObjectName("light")
        menu = QMenu(styles)
        for name in m.STYLES:
            menu.addAction(name, lambda n=name: self.load_style(n))
        styles.setMenu(menu)
        bar.addWidget(styles)
        bar.addStretch()
        for text, slot in [("🆕 Nouveau", self.new_song), ("📂 Ouvrir", self.open_song), ("💾 Sauvegarder", self.save_song)]:
            button = QPushButton(text)
            button.setObjectName("light")
            button.clicked.connect(slot)
            bar.addWidget(button)
        export = QPushButton("🎧 Exporter vers Mixxx")
        export.clicked.connect(self.export_song)
        bar.addWidget(export)
        return rows

    def build_timeline(self):
        grid = QVBoxLayout()
        numbers_row = QHBoxLayout()
        spacer = QWidget()
        spacer.setFixedWidth(450)
        numbers_row.addWidget(spacer)
        self.numbers = BarNumbers(self)
        self.numbers.clicked.connect(self.play_from_bar)
        numbers_row.addWidget(self.numbers, 1)
        grid.addLayout(numbers_row)
        self.rows, self.instrument_boxes, self.mute_buttons, self.volume_sliders, self.lane_labels = {}, {}, {}, {}, {}
        for lane in m.LANES:
            row = QHBoxLayout()
            header = QWidget()
            header.setFixedWidth(450)
            h = QHBoxLayout(header)
            h.setContentsMargins(0, 0, 0, 0)
            label = QPushButton(m.LANE_INFO[lane][0])
            label.setObjectName("chip")
            label.setCheckable(True)
            label.setFixedWidth(130)
            label.clicked.connect(lambda _, l=lane: self.select_lane(l))
            self.lane_labels[lane] = label
            h.addWidget(label)
            box = QComboBox()
            box.addItems([instrument[0] for instrument in m.INSTRUMENTS[lane]])
            box.currentIndexChanged.connect(lambda i, l=lane: self.set_instrument(l, i))
            box.setMinimumWidth(215)  # « Vraie batterie pop / rock » en entier
            self.instrument_boxes[lane] = box
            h.addWidget(box, 1)
            mute = QPushButton("🔇")
            mute.setObjectName("mute")
            mute.setCheckable(True)
            mute.setToolTip("Couper cette ligne")
            mute.clicked.connect(lambda checked, l=lane: self.set_muted(l, checked))
            self.mute_buttons[lane] = mute
            h.addWidget(mute)
            volume = QSlider(Qt.Orientation.Horizontal)
            volume.setRange(0, 127)
            volume.setFixedWidth(60)
            volume.setToolTip("Volume")
            volume.valueChanged.connect(lambda v, l=lane: self.set_volume(l, v))
            self.volume_sliders[lane] = volume
            h.addWidget(volume)
            row.addWidget(header)
            timeline_row = TimelineRow(self, lane)
            timeline_row.clicked.connect(self.timeline_clicked)
            self.rows[lane] = timeline_row
            row.addWidget(timeline_row, 1)
            grid.addLayout(row)
        return grid

    def build_editor_bar(self):
        bar = QHBoxLayout()
        self.editor_title = QLabel()
        self.editor_title.setObjectName("lane")
        bar.addWidget(self.editor_title)
        self.chips_widget = QWidget()
        self.chips_box = QHBoxLayout(self.chips_widget)
        self.chips_box.setContentsMargins(0, 0, 0, 0)
        chips_scroll = QScrollArea()
        chips_scroll.setWidget(self.chips_widget)
        chips_scroll.setWidgetResizable(True)
        chips_scroll.setFrameShape(QFrame.Shape.NoFrame)
        chips_scroll.setFixedHeight(60)
        chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        bar.addWidget(chips_scroll, 1)
        rows = QVBoxLayout()
        rows.addLayout(bar)
        bar = QHBoxLayout()
        rows.addLayout(bar)
        new = QPushButton("➕ Nouveau")
        new.clicked.connect(self.new_pattern)
        bar.addWidget(new)
        self.templates_btn = QPushButton("✨ Motifs prêts")
        bar.addWidget(self.templates_btn)
        dup = QPushButton("📋 Copier")
        dup.setObjectName("light")
        dup.clicked.connect(self.duplicate_pattern)
        bar.addWidget(dup)
        delete = QPushButton("🗑")
        delete.setObjectName("light")
        delete.setToolTip("Supprimer ce motif")
        delete.clicked.connect(self.delete_pattern)
        bar.addWidget(delete)
        bar.addStretch()
        bar.addWidget(QLabel("Longueur"))
        self.length = QComboBox()
        self.length.addItems([f"{n} mesure" + ("s" if n > 1 else "") for n in m.LENGTHS])
        self.length.activated.connect(self.set_length)
        bar.addWidget(self.length)
        self.chord_style_label = QLabel("Jeu")
        bar.addWidget(self.chord_style_label)
        self.chord_style = QComboBox()
        self.chord_style.addItems(m.CHORD_STYLES.values())
        self.chord_style.activated.connect(self.set_chord_style)
        bar.addWidget(self.chord_style)
        self.record_btn = QPushButton("⏺ Enregistrer")
        self.record_btn.setCheckable(True)
        self.record_btn.setToolTip("Joue avec le clavier : tes notes s'inscrivent dans le motif")
        self.record_btn.setStyleSheet("QPushButton:checked { background: #e53935; }")
        self.record_btn.clicked.connect(self.toggle_record)
        bar.addWidget(self.record_btn)
        self.loop_btn = QPushButton("🔁 Écouter ce motif")
        self.loop_btn.setCheckable(True)
        self.loop_btn.clicked.connect(lambda: self.toggle_play("pattern"))
        bar.addWidget(self.loop_btn)
        return rows

    # ---------- affichage ----------
    def refresh_all(self):
        for widget in (self.tempo, self.key, self.swing, self.human):
            widget.blockSignals(True)
        self.tempo.setValue(self.project["tempo"])
        self.key.setCurrentIndex(self.project["key"])
        self.swing.setValue(self.project.get("swing", 0))
        self.human.setValue(self.project.get("humain", m.DEFAULT_HUMAN))
        for widget in (self.tempo, self.key, self.swing, self.human):
            widget.blockSignals(False)
        self.human_label.setText(f"Humain {self.project.get('humain', m.DEFAULT_HUMAN)} %")
        self.swing_label.setText(f"Swing {self.project.get('swing', 0)} %")
        self.update_undo_buttons()
        for lane in m.LANES:
            data = self.project["lanes"][lane]
            for widget, setter, value in [(self.instrument_boxes[lane], "setCurrentIndex", data["instrument"]),
                                          (self.mute_buttons[lane], "setChecked", data["muted"]),
                                          (self.volume_sliders[lane], "setValue", data["volume"])]:
                widget.blockSignals(True)
                getattr(widget, setter)(value)
                widget.blockSignals(False)
        self.refresh_editor()

    def refresh_editor(self):
        lane = self.lane
        for l, label in self.lane_labels.items():
            label.setChecked(l == lane)
        self.editor_title.setText(f"{m.LANE_INFO[lane][0]} :")
        while self.chips_box.count():
            widget = self.chips_box.takeAt(0).widget()
            if widget:
                widget.setParent(None)  # disparaît tout de suite de l'écran
                widget.deleteLater()
        for i, pattern in enumerate(self.project["lanes"][lane]["patterns"]):
            chip = QPushButton(pattern["name"])
            chip.setObjectName("chip")
            chip.setCheckable(True)
            chip.setChecked(i == self.selected[lane])
            chip.setStyleSheet(f"QPushButton {{ border-left: 10px solid {lane_color(lane, i).name()}; }}")
            chip.clicked.connect(lambda _, i=i: self.select_pattern(i))
            self.chips_box.addWidget(chip)
        self.chips_box.addStretch()
        menu = QMenu(self.templates_btn)
        for t in m.TEMPLATES[lane]:
            menu.addAction(t["name"], lambda n=t["name"]: self.add_template(n))
        self.templates_btn.setMenu(menu)
        pattern = self.current_pattern()
        self.length.setEnabled(pattern is not None)
        if pattern:
            self.length.setCurrentIndex(m.LENGTHS.index(pattern["bars"]))
        is_chords = lane == "accords"
        self.chord_style.setVisible(is_chords)
        self.chord_style_label.setVisible(is_chords)
        if is_chords and pattern:
            self.chord_style.setCurrentIndex(list(m.CHORD_STYLES).index(pattern["style"]))
        tips = {
            "batterie": "Clique dans la grille pour poser un coup de batterie, clic droit pour un coup fort ▲ ou doux ▽.",
            "basse": "La basse suit les accords tout seule : « Note 1 » est toujours la base de l'accord. Plusieurs cases à la suite = une note tenue.",
            "accords": "Choisis un accord par temps. Toutes ces notes vont ensemble dans la gamme !",
            "melodie": "Toutes les notes de la grille sont dans la gamme : impossible de jouer faux ! Plusieurs cases à la suite = une note tenue.",
        }
        self.help.setText(f"💡 {tips[lane]}   ⌨ Joue avec les touches {'Q S D F G H J K L M (et A Z E R T Y U I O P plus aigu)' if lane == 'melodie' else 'Q S D F G H J K L'[:2 * MAX_KEY_ROWS[lane] - 1]}, "
                          f"⏺ Enregistrer pour les ajouter au motif, espace pour lancer la lecture.\nPour construire le morceau : choisis un motif, puis clique dans la ligne "
                          "de temps pour le placer (clic droit pour l'enlever).")
        self.fit_grid()
        self.update_views()

    def fit_grid(self):
        self.grid.setMinimumSize(self.grid.sizeHint())

    def update_views(self):
        for row in self.rows.values():
            row.update()
        self.numbers.update()
        self.grid.update()

    def draw_playhead(self, painter, width, height):
        if self.playing != "song":
            return
        step = self.current_step()
        x = width * step / (m.SONG_BARS * m.STEPS_PER_BAR)
        painter.setPen(QPen(QColor("#e53935"), 3))
        painter.drawLine(int(x), 0, int(x), height)

    # ---------- motifs ----------
    def lane_data(self, lane=None):
        return self.project["lanes"][lane or self.lane]

    def current_pattern(self):
        index = self.selected[self.lane]
        patterns = self.lane_data()["patterns"]
        return patterns[index] if index is not None and index < len(patterns) else None

    def next_letter(self):
        used = {short_name(p) for p in self.lane_data()["patterns"]}
        return next(letter for letter in LETTERS if letter not in used)

    def add_pattern(self, pattern):
        patterns = self.lane_data()["patterns"]
        patterns.append(pattern)
        self.selected[self.lane] = len(patterns) - 1
        self.changed()
        self.refresh_editor()

    def new_pattern(self):
        bars = 4 if self.lane == "accords" else 1
        self.add_pattern(m.new_pattern(self.lane, self.next_letter(), bars))

    def add_template(self, name):
        pattern = m.template(self.lane, name)
        pattern["name"] = f"{self.next_letter()} · {name}"
        self.add_pattern(pattern)

    def duplicate_pattern(self):
        pattern = self.current_pattern()
        if pattern:
            clone = copy.deepcopy(pattern)
            clone["name"] = self.next_letter() + (" · " + pattern["name"].split(" · ")[1] if " · " in pattern["name"] else "")
            self.add_pattern(clone)

    def delete_pattern(self):
        index = self.selected[self.lane]
        if index is None:
            return
        data = self.lane_data()
        data["patterns"].pop(index)
        data["song"] = [None if c and c[0] == index else ([c[0] - 1, c[1]] if c and c[0] > index else c) for c in data["song"]]
        self.selected[self.lane] = (min(index, len(data["patterns"]) - 1) if data["patterns"] else None)
        self.changed()
        self.refresh_editor()

    def select_pattern(self, index):
        self.selected[self.lane] = index
        self.refresh_editor()

    def select_lane(self, lane):
        self.lane = lane
        if self.playing == "pattern":
            self.stop()
        self.refresh_editor()

    def set_length(self, index):
        pattern = self.current_pattern()
        if not pattern:
            return
        bars = m.LENGTHS[index]
        pattern["bars"] = bars
        if self.lane == "accords":
            chords = pattern["chords"][:bars * m.BEATS_PER_BAR]
            pattern["chords"] = chords + [None] * (bars * m.BEATS_PER_BAR - len(chords))
        else:
            pattern["cells"] = [c for c in pattern["cells"] if c[1] < bars * m.STEPS_PER_BAR]
        # replace chaque utilisation du motif dans le morceau avec sa nouvelle longueur
        data, idx = self.lane_data(), self.selected[self.lane]
        starts = [b for b, c in enumerate(data["song"]) if c and c[0] == idx and c[1] == 0]
        data["song"] = [None if c and c[0] == idx else c for c in data["song"]]
        for bar in starts:
            m.place(self.project, self.lane, idx, bar)
        self.changed()
        self.refresh_editor()

    def set_chord_style(self, index):
        pattern = self.current_pattern()
        if pattern:
            pattern["style"] = list(m.CHORD_STYLES)[index]
            self.changed()

    def toggle_cell(self, row, col, value=None):
        """Allume ou éteint une case. value : forcer (glisser) ; renvoie l'état appliqué."""
        pattern = self.current_pattern()
        if self.lane == "accords":
            degree = row
            new = (None if pattern["chords"][col] == degree else degree) if value is None else (degree if value else None)
            pattern["chords"][col] = new
            if new is not None:
                key = m.KEYS[self.project["key"]]
                for note in m.chord_voicing(key, degree):
                    self.engine.preview(1, note, 90, 500)
            result = new is not None
        else:
            cell = [row, col]
            on = cell in pattern["cells"]
            result = (not on) if value is None else value
            if result and not on:
                pattern["cells"].append(cell)
                self.preview_cell(row)
            elif not result and on:
                pattern["cells"].remove(cell)
                pattern.get("accents", {}).pop(f"{row}:{col}", None)
        self.changed()
        self.update_views()
        return result

    def cycle_accent(self, row, col):
        """Clic droit sur une case allumée : normal -> fort -> doux -> normal."""
        pattern = self.current_pattern()
        if self.lane == "accords" or [row, col] not in pattern["cells"]:
            return
        accents = pattern.setdefault("accents", {})
        key = f"{row}:{col}"
        following = {None: "fort", "fort": "doux", "doux": None}[accents.get(key)]
        if following:
            accents[key] = following
        else:
            accents.pop(key, None)
        self.preview_cell(row, m.accented(100, following))
        self.changed()
        self.update_views()

    def preview_cell(self, row, velocity=None):
        key = m.KEYS[self.project["key"]]
        if self.lane == "batterie":
            _, note, base = m.DRUM_ROWS[row]
            self.engine.preview(9, note, velocity or base, 200)
        elif self.lane == "basse":
            self.engine.preview(0, m.scale_note(key, row, 36), velocity or 105, 300)
        else:
            self.engine.preview(2, m.scale_note(key, row, 60 if key[1] < 5 else 48), velocity or 100, 300)

    # ---------- ligne de temps ----------
    def timeline_clicked(self, lane, bar, right):
        if lane != self.lane:
            self.lane = lane
            self.refresh_editor()
        data = self.lane_data(lane)
        cell = data["song"][bar]
        index = self.selected[lane]
        if right or (cell and index is not None and cell[0] == index and cell[1] == 0) or index is None:
            self.clear_instance(lane, bar)
        else:
            m.place(self.project, lane, index, bar)
        self.changed()
        self.update_views()

    def paint_bar(self, lane, bar):
        index = self.selected[lane]
        if index is not None:
            m.place(self.project, lane, index, bar)
            self.changed()
            self.update_views()

    def clear_instance(self, lane, bar):
        data = self.lane_data(lane)
        cell = data["song"][bar]
        if not cell:
            return
        start = bar - cell[1]
        for i in range(data["patterns"][cell[0]]["bars"]):
            if 0 <= start + i < m.SONG_BARS and data["song"][start + i] == [cell[0], i]:
                data["song"][start + i] = None

    # ---------- réglages ----------
    def set_tempo(self, value):
        position = self.current_step_float() if self.playing else 0
        self.project["tempo"] = value
        if self.playing:  # garde la position actuelle avec le nouveau tempo
            now = self.engine.now()
            self.engine.stop()
            self.start_tick = now - position * self.step_ms()
            self.next_step = int(position) + 1
        self.changed()

    def set_key(self, index):
        self.project["key"] = index
        self.changed()
        self.refresh_editor()

    def set_instrument(self, lane, index):
        self.lane_data(lane)["instrument"] = index
        self.apply_instruments()
        self.changed()

    def set_volume(self, lane, value):
        self.lane_data(lane)["volume"] = value
        self.apply_instruments()
        self.changed()

    def set_human(self, value):
        self.project["humain"] = value
        self.human_label.setText(f"Humain {value} %")
        self.changed()

    def set_swing(self, value):
        self.project["swing"] = value
        self.swing_label.setText(f"Swing {value} %")
        self.changed()

    def set_muted(self, lane, muted):
        self.lane_data(lane)["muted"] = muted
        self.changed()
        self.update_views()

    def channels(self):
        result = {}
        for lane in m.LANES:
            data = self.lane_data(lane)
            instruments = m.INSTRUMENTS[lane]
            _, bank, program, soundfont, gain_db = instruments[min(data["instrument"], len(instruments) - 1)]
            volume = max(1, min(127, round(data["volume"] * 10 ** (gain_db / 40))))  # le volume MIDI suit 40·log10
            result[m.LANE_INFO[lane][1]] = (bank, program, volume, soundfont, m.LANE_FX[lane])
        return result

    def apply_instruments(self):
        self.engine.setup(self.channels())

    # ---------- lecture ----------
    def changed(self):
        self.dirty = True
        self.record_history()
        self.autosave_timer.start(1500)

    def record_history(self):
        """Garde l'état d'avant chaque action, pour pouvoir l'annuler."""
        current = json.dumps(self.project)
        if current == self.snapshot:
            return
        now = clock.monotonic()
        if now - self.last_change > UNDO_GROUP_SECONDS:
            self.undo_stack = (self.undo_stack + [self.snapshot])[-UNDO_LIMIT:]
            self.redo_stack.clear()
        self.snapshot, self.last_change = current, now
        self.update_undo_buttons()

    def update_undo_buttons(self):
        if hasattr(self, "undo_btn"):
            self.undo_btn.setEnabled(bool(self.undo_stack))
            self.redo_btn.setEnabled(bool(self.redo_stack))

    def restore_state(self, state):
        self.project = json.loads(state)
        self.snapshot, self.last_change = state, 0.0
        for lane in m.LANES:
            count = len(self.project["lanes"][lane]["patterns"])
            index = self.selected.get(lane)
            self.selected[lane] = None if not count else min(index or 0, count - 1)
        self.dirty = True
        self.apply_instruments()
        self.refresh_all()
        self.autosave_timer.start(1500)

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(json.dumps(self.project))
            self.restore_state(self.undo_stack.pop())

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(json.dumps(self.project))
            self.restore_state(self.redo_stack.pop())

    def restore_autosave(self):
        if not AUTOSAVE.exists():
            return None
        try:
            return m.load(AUTOSAVE)
        except (OSError, ValueError):
            # Sauvegarde abîmée : on la met de côté (pour papa) au lieu de l'écraser, et on prévient
            broken = AUTOSAVE.with_name(f"sauvegarde-abimee-{clock.strftime('%Y%m%d-%H%M%S')}.json")
            try:
                AUTOSAVE.replace(broken)
            except OSError:
                pass
            QTimer.singleShot(500, lambda: QMessageBox.warning(
                self, "Mon Studio", "😕 Je n'ai pas réussi à relire ton dernier morceau.\n"
                "Je l'ai mis de côté : demande à papa, il pourra peut-être le récupérer."))
            return None

    def autosave(self):
        """Sauvegarde automatique du morceau (pas des exercices des défis)."""
        project = self.before_defis[0] if self.before_defis else self.project
        DATA.mkdir(parents=True, exist_ok=True)
        m.save(project, AUTOSAVE)

    def step_ms(self):
        return 60000 / self.project["tempo"] / 4

    def current_step_float(self):
        return max(0.0, (self.engine.now() - self.start_tick) / self.step_ms())

    def current_step(self):
        return int(self.current_step_float()) % max(1, self.loop_steps)

    def pattern_play_step(self):
        """Position de lecture dans le motif affiché (en pas), ou None."""
        if self.playing == "pattern":
            return self.current_step()
        if self.playing == "custom" and self.current_pattern():
            return self.current_step() % (self.current_pattern()["bars"] * m.STEPS_PER_BAR)
        if self.playing == "song":
            step = self.current_step()
            cell = self.lane_data()["song"][step // m.STEPS_PER_BAR]
            if cell and cell[0] == self.selected[self.lane]:
                return cell[1] * m.STEPS_PER_BAR + step % m.STEPS_PER_BAR
        return None

    def compile(self):
        if self.playing == "custom":
            self.events, self.loop_steps = self.custom_source()
        elif self.playing == "pattern":
            pattern = self.current_pattern()
            self.events = m.compile_pattern(self.project, self.lane, pattern) if pattern else {}
            self.loop_steps = (pattern["bars"] if pattern else 1) * m.STEPS_PER_BAR
        else:
            self.events = m.compile_song(self.project)
            self.loop_steps = m.SONG_BARS * m.STEPS_PER_BAR
        self.dirty = False

    def toggle_play(self, mode, from_step=0, source=None, name=None):
        was = (self.playing, self.custom_name)
        self.stop()
        if was == (mode, name) and from_step == 0:
            return
        self.custom_source, self.custom_name = source, name
        if mode == "pattern" and not self.current_pattern():
            return
        self.playing = mode
        self.compile()
        self.start_tick = self.engine.now() + 60 - from_step * self.step_ms()
        self.next_step = from_step
        self.play_btn.setChecked(mode == "song")
        self.play_btn.setText("⏹ Stop" if mode == "song" else "▶ Lecture")
        self.loop_btn.setChecked(mode == "pattern")

    def play_from_bar(self, bar):
        self.toggle_play("song", bar * m.STEPS_PER_BAR)

    def stop(self):
        self.playing = None
        self.custom_name = None
        if hasattr(self, "record_btn"):
            self.record_btn.setChecked(False)
        self.engine.stop()
        self.play_btn.setChecked(False)
        self.play_btn.setText("▶ Lecture")
        self.loop_btn.setChecked(False)
        self.update_views()

    def tick(self):
        if not self.playing:
            return
        if self.dirty:
            self.compile()
        now = self.engine.now()
        step_ms = self.step_ms()
        while self.start_tick + self.next_step * step_ms < now + LOOKAHEAD_MS:
            time = self.start_tick + self.next_step * step_ms
            delay = m.swing_offset(self.next_step, self.project.get("swing", 0), step_ms)
            human = self.project.get("humain", m.DEFAULT_HUMAN)
            for channel, note, velocity, length in self.events.get(self.next_step % self.loop_steps, []):
                self.engine.note_at(max(self.engine.now(), time + delay + moteur.jitter_ms(human)), channel, note,
                                    moteur.humanize(velocity, human), length * step_ms * 0.95)
            self.next_step += 1
        self.update_views()

    # ---------- jeu au clavier ----------
    def eventFilter(self, obj, event):
        if event.type() not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease) or not self.isActiveWindow():
            return False
        if isinstance(QApplication.focusWidget(), (QLineEdit, QAbstractSpinBox)):
            return False  # on laisse taper dans les cases de texte et le tempo
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.type() == QEvent.Type.KeyPress:
                shift = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                actions = {Qt.Key.Key_Z: self.redo if shift else self.undo, Qt.Key.Key_Y: self.redo, Qt.Key.Key_S: self.save_song}
                if event.key() in actions:
                    actions[event.key()]()
                    return True
            return False
        if event.isAutoRepeat():
            return True
        pressed = event.type() == QEvent.Type.KeyPress
        if event.key() == Qt.Key.Key_Space:
            if pressed:
                self.toggle_play("song")
            return True
        slot = key_slot(event)
        if slot is None:
            return False
        if pressed:
            self.key_down(slot)
        else:
            self.key_up(slot)
        return True

    def play_position(self):
        """Position de lecture en pas (non arrondie), corrigée du délai de la carte son."""
        return (self.engine.now() - LATENCY_MS - self.start_tick) / self.step_ms()

    def chord_now(self):
        if self.playing == "song":
            step = self.current_step()
            return m.chord_at(self.project, step // m.STEPS_PER_BAR, (step % m.STEPS_PER_BAR) // 4)
        return 0

    def key_down(self, slot):
        lane = self.lane
        row = slot_row(lane, slot)
        if row is None or slot in self.held:
            return
        key = m.KEYS[self.project["key"]]
        channel = m.LANE_INFO[lane][1]
        if lane == "batterie":
            notes, velocity = [m.DRUM_ROWS[row][1]], m.DRUM_ROWS[row][2]
        elif lane == "basse":
            notes, velocity = [m.scale_note(key, self.chord_now() + row, 36)], 105
        elif lane == "accords":
            notes, velocity = m.chord_voicing(key, row), 85
        else:
            notes, velocity = [m.scale_note(key, row, 60 if key[1] < 5 else 48)], 100
        for note in notes:
            self.engine.note_on(channel, note, velocity)
        start = round(self.play_position()) if self.recording() else None
        self.held[slot] = (channel, notes, row, start)
        if start is not None and lane in ("batterie", "accords"):
            self.record_note(row, start, 1)
        self.grid.update()

    def key_up(self, slot):
        if slot not in self.held:
            return
        channel, notes, row, start = self.held.pop(slot)
        for note in notes:
            self.engine.note_off(channel, note)
        if start is not None and self.recording() and self.lane in ("basse", "melodie"):
            self.record_note(row, start, max(1, round(self.play_position()) - start))
        self.grid.update()

    def held_rows(self):
        return {row for _, _, row, _ in self.held.values()}

    def recording(self):
        return self.record_btn.isChecked() and self.playing == "pattern" and self.current_pattern() is not None

    def toggle_record(self, checked):
        if checked and not self.current_pattern():
            self.record_btn.setChecked(False)
            return
        if checked and self.playing != "pattern":
            self.toggle_play("pattern")
            self.record_btn.setChecked(True)

    def record_note(self, row, start, length):
        """Inscrit une note jouée au clavier dans le motif, à la case la plus proche."""
        pattern = self.current_pattern()
        total = pattern["bars"] * m.STEPS_PER_BAR
        if self.lane == "accords":
            pattern["chords"][(start % total) // 4] = row
        else:
            for i in range(min(length, total)):
                cell = [row, (start + i) % total]
                if cell not in pattern["cells"]:
                    pattern["cells"].append(cell)
        self.changed()
        self.update_views()

    # ---------- défis ----------
    def toggle_defis(self, checked):
        if checked:
            done = defis.load_progress()
            first = next((i for i, d in enumerate(defis.DEFIS) if d["id"] not in done), 0)
            self.start_defi(first)
        else:
            self.quit_defis()

    def start_defi(self, index):
        if index >= len(defis.DEFIS):
            self.defi_panel.set_feedback("🏆 Tu as fini tous les défis ! Tu es un vrai producteur !", True)
            return
        if self.before_defis is None:
            self.before_defis = (self.project, self.save_path)
        defi = defis.DEFIS[index]
        self.load_project(defis.workspace(defi))
        self.lane = defi["lane"]
        self.refresh_editor()
        self.defis_btn.setChecked(True)
        self.defi_panel.show()
        self.defi_panel.show_defi(index)

    def current_defi(self):
        return defis.DEFIS[self.defi_panel.index]

    def listen_defi(self, which):
        defi = self.current_defi()
        if which == "modele":
            source = lambda: defis.listen_model(defi, self.project)
        else:
            source = lambda: defis.listen_mine(defi, self.project)
        self.toggle_play("custom", source=source, name=which)

    def check_defi(self):
        defi = self.current_defi()
        ok, message = defis.check(defi, self.project)
        self.defi_panel.set_feedback(message, ok)
        if ok:
            defis.save_success(defi["id"])
            self.defi_panel.next_btn.setVisible(True)
            self.defi_panel.refresh_list()
            self.fanfare()

    def fanfare(self):
        now = self.engine.now()
        for i, note in enumerate((72, 76, 79, 84)):
            self.engine.note_at(now + 40 + i * 110, 2, note, 110, 300 if i < 3 else 700)

    def quit_defis(self):
        self.stop()
        self.defi_panel.hide()
        self.defis_btn.setChecked(False)
        if self.before_defis:
            project, path = self.before_defis
            self.before_defis = None
            self.load_project(project, path)

    # ---------- fichiers ----------
    def confirm_replace(self):
        answer = QMessageBox.question(self, "Mon Studio", "Remplacer le morceau en cours ?\n(Pense à l'enregistrer avant !)")
        return answer == QMessageBox.StandardButton.Yes

    def load_project(self, project, path=None):
        self.stop()
        self.project = project
        self.undo_stack, self.redo_stack = [], []
        self.snapshot, self.last_change = json.dumps(project), 0.0
        self.save_path = path
        self.selected = {lane: 0 if project["lanes"][lane]["patterns"] else None for lane in m.LANES}
        self.dirty = True
        self.autosave_timer.start(1500)
        self.apply_instruments()
        self.refresh_all()

    def load_style(self, name):
        if self.confirm_replace():
            self.load_project(m.STYLES[name]())

    def new_song(self):
        if self.confirm_replace():
            self.load_project(m.new_project())

    def open_song(self):
        PROJECTS.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir un morceau", str(PROJECTS), "Morceaux (*.json)")
        if not path:
            return
        previous, previous_path = self.project, self.save_path
        try:
            self.load_project(m.load(path), Path(path))
        except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
            # Fichier abîmé ou pas un morceau : on garde le morceau en cours
            self.load_project(previous, previous_path)
            QMessageBox.warning(self, "Mon Studio", f"😕 Je n'arrive pas à lire « {Path(path).name} ».\n"
                                                    "Ce fichier est abîmé ou ce n'est pas un morceau de Mon Studio.")

    def ask_name(self, question, mp3=False):
        """Demande le nom du morceau. Si un autre morceau porte déjà ce nom, on demande avant de l'écraser."""
        name, ok = QInputDialog.getText(self, "Mon Studio", question, text=self.project.get("name", "Mon morceau"))
        name = re.sub(r'[/\\:*?"<>|]', " ", name).strip()
        if not ok or not name:
            return None
        if self.name_taken(name, mp3):
            box = QMessageBox(self)
            box.setWindowTitle("Mon Studio")
            box.setText(f"Tu as déjà un morceau qui s'appelle « {name} ».")
            replace = box.addButton("🔁 Le remplacer", QMessageBox.ButtonRole.DestructiveRole)
            keep = box.addButton("➕ Garder les deux", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(keep)
            box.exec()
            if box.clickedButton() is keep:
                base, number = name, 2
                while self.name_taken(f"{base} ({number})", mp3):
                    number += 1
                name = f"{base} ({number})"
            elif box.clickedButton() is not replace:
                return None
        self.project["name"] = name
        return name

    def name_taken(self, name, mp3=False):
        """Un autre morceau (pas celui qu'on est en train d'enregistrer) porte déjà ce nom ?"""
        project = PROJECTS / f"{name}.json"
        if project.exists() and project != self.save_path:
            return True
        return mp3 and (CREATIONS / f"Mes créations - {name}.mp3").exists() and project != self.save_path

    def save_song(self):
        name = self.ask_name("Comment s'appelle ton morceau ?")
        if not name:
            return
        PROJECTS.mkdir(parents=True, exist_ok=True)
        self.save_path = PROJECTS / f"{name}.json"
        m.save(self.project, self.save_path)
        QMessageBox.information(self, "Mon Studio", f"💾 « {name} » est enregistré !")

    def export_song(self):
        name = self.ask_name("Comment s'appelle ton morceau ? Il ira dans Mixxx !", mp3=True)
        if not name:
            return
        self.stop()
        CREATIONS.mkdir(parents=True, exist_ok=True)
        PROJECTS.mkdir(parents=True, exist_ok=True)
        self.save_path = PROJECTS / f"{name}.json"
        m.save(self.project, self.save_path)
        events = m.compile_song(self.project)
        last_bar = max((b for lane in m.LANES for b, c in enumerate(self.lane_data(lane)["song"]) if c), default=0)
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "morceau.wav"
            moteur.render_wav(wav, events, (last_bar + 1) * m.STEPS_PER_BAR, self.project["tempo"], self.channels(),
                              swing=self.project.get("swing", 0), human=self.project.get("humain", m.DEFAULT_HUMAN))
            mp3 = CREATIONS / f"Mes créations - {name}.mp3"
            # « Mastering » léger : compression douce, limiteur, puis volume standard
            mastering = ("acompressor=threshold=-18dB:ratio=2.5:attack=15:release=200:makeup=2,"
                         "alimiter=limit=0.95:level=disabled,loudnorm=I=-14:TP=-1")
            subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(wav), "-af", mastering,
                            "-codec:a", "libmp3lame", "-q:a", "2", "-metadata", "artist=Mes créations",
                            "-metadata", f"title={name}", str(mp3)], check=True)
        QMessageBox.information(self, "Mon Studio", f"🎧 « {name} » est dans tes musiques !\n"
                                                    "Ouvre Mixxx : il est dans le dossier « Mes créations ».")

    def closeEvent(self, event):
        self.autosave()
        self.timer.stop()
        self.engine.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Mon Studio")
    app.setDesktopFileName("mon-studio")
    apply_light_theme(app)
    app.setFont(QFont(app.font().family(), 11))
    window = Studio()
    window.showMaximized()
    sys.exit(app.exec())
