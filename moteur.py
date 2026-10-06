"""Mon Studio : le moteur audio (FluidSynth), pour jouer en direct et exporter en WAV."""
import ctypes
import ctypes.util
import os
import sys
import wave

from pathlib import Path

_HERE = Path(__file__).resolve().parent

# Banque de sons : d'abord une banque locale livrée avec l'appli (soundfonts/ à côté du code,
# pratique pour un bundle Windows/macOS), puis les emplacements système Linux, sinon FluidR3.
SOUNDFONTS = [
    _HERE / "soundfonts" / "GeneralUser-GS.sf2",            # bundle (toutes plateformes)
    Path("/usr/share/sounds/sf2/GeneralUser-GS.sf2"),       # Linux (apt)
    Path.home() / ".local/share/sounds/sf2/GeneralUser-GS.sf2",
    Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),           # secours Linux
]
if os.environ.get("APPDATA"):  # Windows : banque installée dans %APPDATA%
    SOUNDFONTS.insert(-1, Path(os.environ["APPDATA"]) / "MonStudio" / "GeneralUser-GS.sf2")
# Sans banque trouvée, on garde le secours (comme avant) pour que l'erreur soit claire
SOUNDFONT = str(next((p for p in SOUNDFONTS if p.exists()), SOUNDFONTS[-1])).encode()
SAMPLE_RATE = 44100


def _load_fluidsynth():
    """Charge la lib FluidSynth selon l'OS (Linux .so.3 / Windows .dll / macOS .dylib)."""
    candidates = []
    if sys.platform.startswith("win"):
        # Permet de livrer les DLL FluidSynth dans un dossier bin/ à côté de l'appli
        for sub in ("bin", "fluidsynth", "."):
            d = _HERE / sub
            if d.is_dir():
                try:
                    os.add_dll_directory(str(d))
                except (OSError, AttributeError):
                    pass
        candidates = ["libfluidsynth-3.dll", "libfluidsynth-2.dll", "fluidsynth.dll", "libfluidsynth.dll"]
    elif sys.platform == "darwin":
        candidates = ["libfluidsynth.3.dylib", "libfluidsynth.dylib"]
    else:
        candidates = ["libfluidsynth.so.3", "libfluidsynth.so.2", "libfluidsynth.so"]
    found = ctypes.util.find_library("fluidsynth")
    if found:
        candidates.append(found)
    last = None
    for name in candidates:
        try:
            return ctypes.CDLL(name)
        except OSError as exc:
            last = exc
    raise OSError(
        "FluidSynth introuvable. Linux : « sudo apt install libfluidsynth3 ». "
        "Windows : installe FluidSynth (ou place libfluidsynth-3.dll à côté de l'appli) et "
        "vérifie qu'il est dans le PATH. Détail : %s" % last
    )


_lib = _load_fluidsynth()
_p = ctypes.c_void_p
for name, restype, argtypes in [
    ("new_fluid_settings", _p, []),
    ("delete_fluid_settings", None, [_p]),
    ("fluid_settings_setstr", ctypes.c_int, [_p, ctypes.c_char_p, ctypes.c_char_p]),
    ("fluid_settings_setnum", ctypes.c_int, [_p, ctypes.c_char_p, ctypes.c_double]),
    ("fluid_settings_setint", ctypes.c_int, [_p, ctypes.c_char_p, ctypes.c_int]),
    ("new_fluid_synth", _p, [_p]),
    ("delete_fluid_synth", None, [_p]),
    ("fluid_synth_sfload", ctypes.c_int, [_p, ctypes.c_char_p, ctypes.c_int]),
    ("fluid_synth_program_select", ctypes.c_int, [_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]),
    ("fluid_synth_cc", ctypes.c_int, [_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]),
    ("fluid_synth_noteon", ctypes.c_int, [_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]),
    ("fluid_synth_noteoff", ctypes.c_int, [_p, ctypes.c_int, ctypes.c_int]),
    ("fluid_synth_all_notes_off", ctypes.c_int, [_p, ctypes.c_int]),
    ("fluid_synth_write_s16", ctypes.c_int, [_p, ctypes.c_int, _p, ctypes.c_int, ctypes.c_int, _p, ctypes.c_int, ctypes.c_int]),
    ("new_fluid_audio_driver", _p, [_p, _p]),
    ("delete_fluid_audio_driver", None, [_p]),
    ("new_fluid_sequencer2", _p, [ctypes.c_int]),
    ("delete_fluid_sequencer", None, [_p]),
    ("fluid_sequencer_register_fluidsynth", ctypes.c_short, [_p, _p]),
    ("fluid_sequencer_get_tick", ctypes.c_uint, [_p]),
    ("fluid_sequencer_send_at", ctypes.c_int, [_p, _p, ctypes.c_uint, ctypes.c_int]),
    ("fluid_sequencer_remove_events", None, [_p, ctypes.c_short, ctypes.c_short, ctypes.c_int]),
    ("new_fluid_event", _p, []),
    ("delete_fluid_event", None, [_p]),
    ("fluid_event_set_source", None, [_p, ctypes.c_short]),
    ("fluid_event_set_dest", None, [_p, ctypes.c_short]),
    ("fluid_event_note", None, [_p, ctypes.c_int, ctypes.c_short, ctypes.c_short, ctypes.c_uint]),
    ("fluid_event_control_change", None, [_p, ctypes.c_int, ctypes.c_short, ctypes.c_int]),
]:
    function = getattr(_lib, name)
    function.restype = restype
    function.argtypes = argtypes
# Pour « l'intro qui s'ouvre » (FluidSynth 2 et plus) ; sans elles, cet effet ne fait simplement rien
for name, restype, argtypes in [
    ("new_fluid_mod", _p, []),
    ("delete_fluid_mod", None, [_p]),
    ("fluid_mod_set_source1", None, [_p, ctypes.c_int, ctypes.c_int]),
    ("fluid_mod_set_source2", None, [_p, ctypes.c_int, ctypes.c_int]),
    ("fluid_mod_set_dest", None, [_p, ctypes.c_int]),
    ("fluid_mod_set_amount", None, [_p, ctypes.c_double]),
    ("fluid_synth_add_default_mod", ctypes.c_int, [_p, _p, ctypes.c_int]),
]:
    function = getattr(_lib, name, None)
    if function is not None:
        function.restype = restype
        function.argtypes = argtypes

EFFECT_CONTROLS = {11: 127, 74: 127}  # expression (pompe) et brillance (intro) : valeurs « effet éteint »
CUTOFF_RANGE = -6000  # en cents : contrôleur 74 à 0 = filtre 5 octaves plus bas, à 127 = son normal


def add_filter_control(synth):
    """Les banques de sons ne réagissent pas toutes au contrôleur 74 (brillance) : on le branche nous-mêmes
    sur le filtre de chaque son. À 127 (la valeur normale), le son ne change pas du tout."""
    if not hasattr(_lib, "fluid_synth_add_default_mod"):
        return
    mod = _lib.new_fluid_mod()
    _lib.fluid_mod_set_source1(mod, 74, 0x10 | 0x01)  # contrôleur 74, sens inversé : 127 -> 0, 0 -> 1
    _lib.fluid_mod_set_source2(mod, 0, 0)            # pas de deuxième source
    _lib.fluid_mod_set_dest(mod, 8)                  # fréquence de coupure du filtre
    _lib.fluid_mod_set_amount(mod, CUTOFF_RANGE)
    _lib.fluid_synth_add_default_mod(synth, mod, 1)  # 1 = ajouter (la banque garde ses propres réglages)
    _lib.delete_fluid_mod(mod)


def _new_synth(realtime):
    settings = _lib.new_fluid_settings()
    _lib.fluid_settings_setnum(settings, b"synth.sample-rate", float(SAMPLE_RATE))
    _lib.fluid_settings_setnum(settings, b"synth.gain", 0.5)
    _lib.fluid_settings_setint(settings, b"synth.reverb.active", 1)
    _lib.fluid_settings_setint(settings, b"synth.chorus.active", 1)
    # Une salle un peu plus grande et plus douce que celle par défaut
    for name, value in [(b"synth.reverb.room-size", 0.62), (b"synth.reverb.damp", 0.4),
                        (b"synth.reverb.width", 0.9), (b"synth.reverb.level", 0.65)]:
        _lib.fluid_settings_setnum(settings, name, value)
    # Ne charge en mémoire que les échantillons des instruments choisis (les grosses banques font des centaines de Mo)
    _lib.fluid_settings_setint(settings, b"synth.dynamic-sample-loading", 1)
    if realtime:
        # Driver audio selon l'OS : Windows = wasapi, macOS = coreaudio, Linux = pulseaudio.
        # Un autre (dsound, alsa…) peut être choisi avec la variable MONSTUDIO_AUDIO_DRIVER.
        default = "wasapi" if sys.platform.startswith("win") else "coreaudio" if sys.platform == "darwin" else "pulseaudio"
        driver = os.environ.get("MONSTUDIO_AUDIO_DRIVER") or default
        _lib.fluid_settings_setstr(settings, b"audio.driver", driver.encode())
        _lib.fluid_settings_setint(settings, b"audio.period-size", 512)
    synth = _lib.new_fluid_synth(settings)
    add_filter_control(synth)
    sfont = _lib.fluid_synth_sfload(synth, SOUNDFONT, 1)
    if sfont < 0:
        raise RuntimeError("Impossible de charger la banque de sons")
    return settings, synth


_loaded = {}  # (synthé, fichier) -> numéro de la banque chargée


def sfont_id(synth, path):
    """Charge une banque de sons supplémentaire (une seule fois par synthé). None si elle n'existe pas."""
    if (synth, path) not in _loaded:
        number = _lib.fluid_synth_sfload(synth, path.encode(), 0) if Path(path).exists() else -1
        _loaded[(synth, path)] = number if number >= 0 else None
    return _loaded[(synth, path)]


def setup_channels(synth, channels):
    """channels : {canal: (banque, programme, volume 0-127, fichier de banque à part ou None, (réverbe, chorus, stéréo))}"""
    for channel, (bank, program, volume, extra, (reverb, chorus, pan)) in channels.items():
        number = sfont_id(synth, extra) if extra else 1
        if number is None:  # banque absente : batterie standard de la banque principale
            number, bank, program = 1, 128, 0
        _lib.fluid_synth_program_select(synth, channel, number, bank, program)
        for control, value in ((7, volume), (91, reverb), (93, chorus), (10, pan)):
            _lib.fluid_synth_cc(synth, channel, control, value)
        reset_effects(synth, [channel])


def reset_effects(synth, channels):
    """Remet la pompe et le filtre au repos (sinon un arrêt au milieu d'un effet laisserait le son étouffé)."""
    for channel in channels:
        for control, value in EFFECT_CONTROLS.items():
            _lib.fluid_synth_cc(synth, channel, control, value)


class Engine:
    """Synthé en direct : les notes sont programmées à l'avance au milliseconde près par le séquenceur."""

    def __init__(self):
        self.settings, self.synth = _new_synth(realtime=True)
        self.driver = _lib.new_fluid_audio_driver(self.settings, self.synth)
        if not self.driver and sys.platform.startswith("linux"):
            # Pas de PulseAudio/PipeWire (système ALSA pur) : on passe directement par ALSA
            _lib.fluid_settings_setstr(self.settings, b"audio.driver", b"alsa")
            self.driver = _lib.new_fluid_audio_driver(self.settings, self.synth)
        self.sequencer = _lib.new_fluid_sequencer2(0)
        self.dest = _lib.fluid_sequencer_register_fluidsynth(self.sequencer, self.synth)

    def setup(self, channels):
        setup_channels(self.synth, channels)

    def now(self):
        return _lib.fluid_sequencer_get_tick(self.sequencer)

    def note_at(self, time_ms, channel, note, velocity, duration_ms):
        event = _lib.new_fluid_event()
        _lib.fluid_event_set_source(event, -1)
        _lib.fluid_event_set_dest(event, self.dest)
        _lib.fluid_event_note(event, channel, note, velocity, max(1, int(duration_ms)))
        _lib.fluid_sequencer_send_at(self.sequencer, event, int(time_ms), 1)
        _lib.delete_fluid_event(event)

    def control_at(self, time_ms, channel, control, value):
        """Réglage d'effet programmé (pompe, filtre), comme une note."""
        event = _lib.new_fluid_event()
        _lib.fluid_event_set_source(event, -1)
        _lib.fluid_event_set_dest(event, self.dest)
        _lib.fluid_event_control_change(event, channel, control, value)
        _lib.fluid_sequencer_send_at(self.sequencer, event, int(time_ms), 1)
        _lib.delete_fluid_event(event)

    def note_on(self, channel, note, velocity=100):
        """Note jouée tout de suite et tenue jusqu'à note_off (jeu au clavier)."""
        _lib.fluid_synth_noteon(self.synth, channel, note, velocity)

    def note_off(self, channel, note):
        _lib.fluid_synth_noteoff(self.synth, channel, note)

    def preview(self, channel, note, velocity=100, duration_ms=300):
        """Joue une note tout de suite (quand on clique une case)."""
        self.note_at(self.now() + 5, channel, note, velocity, duration_ms)

    def stop(self):
        _lib.fluid_sequencer_remove_events(self.sequencer, -1, self.dest, -1)
        _lib.fluid_synth_all_notes_off(self.synth, -1)
        reset_effects(self.synth, range(16))

    def close(self):
        self.stop()
        _lib.delete_fluid_sequencer(self.sequencer)
        _lib.delete_fluid_audio_driver(self.driver)
        for key in [k for k in _loaded if k[0] == self.synth]:
            del _loaded[key]
        _lib.delete_fluid_synth(self.synth)
        _lib.delete_fluid_settings(self.settings)


def render_wav(path, notes, end_ms, channels, tail_seconds=2.5, progress=None, controls=()):
    """Fabrique le fichier WAV du morceau.

    notes : [(début en ms, canal, note, force, durée en ms)], déjà « jouées » (swing, humain) par
    musique.performance, comme en lecture directe. controls : [(moment en ms, canal, contrôleur, valeur)],
    les réglages des effets (pompe, filtre), eux aussi calculés par musique.performance.
    progress(fraction) est appelé pendant le rendu."""
    settings, synth = _new_synth(realtime=False)
    try:
        _render(synth, channels, path, notes, end_ms, tail_seconds, progress, controls)
    finally:  # même si le rendu échoue, on libère le synthé
        for key in [k for k in _loaded if k[0] == synth]:
            del _loaded[key]
        _lib.delete_fluid_synth(synth)
        _lib.delete_fluid_settings(settings)


def _render(synth, channels, path, notes, end_ms, tail_seconds, progress, controls=()):
    setup_channels(synth, channels)
    frames = SAMPLE_RATE / 1000
    timeline = []  # (image, 0 = fin / 1 = réglage / 2 = début, canal, note ou contrôleur, force ou valeur)
    for start_ms, channel, note, velocity, duration_ms in notes:
        start = int(start_ms * frames)
        timeline.append((start, 2, channel, note, velocity))
        timeline.append((start + max(1, int(duration_ms * frames)), 0, channel, note, 0))
    for time_ms, channel, control, value in controls:
        timeline.append((int(time_ms * frames), 1, channel, control, value))
    timeline.sort(key=lambda e: (e[0], e[1]))  # au même instant : les fins, puis les réglages, puis les débuts
    end_frame = int(end_ms * frames + tail_seconds * SAMPLE_RATE)

    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        position = 0

        def write_until(frame):
            nonlocal position
            while position < frame:
                count = min(4096, frame - position)
                buffer = (ctypes.c_int16 * (2 * count))()
                _lib.fluid_synth_write_s16(synth, count, buffer, 0, 2, buffer, 1, 2)
                out.writeframes(bytes(buffer))
                position += count
                if progress and position % (SAMPLE_RATE // 2) < 4096:
                    progress(min(1.0, position / max(1, end_frame)))

        for frame, kind, channel, number, value in timeline:
            write_until(frame)
            if kind == 2:
                _lib.fluid_synth_noteon(synth, channel, number, value)
            elif kind == 1:
                _lib.fluid_synth_cc(synth, channel, number, value)
            else:
                _lib.fluid_synth_noteoff(synth, channel, number)
        write_until(end_frame)
