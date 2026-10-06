"""Mon Studio : le mode défi, des petites leçons progressives façon Ableton Learning Music.

Deux sortes de défis :
- « reproduire » : on écoute un modèle et on le recopie dans la grille ;
- « créer » : on suit une consigne libre (par exemple « une mélodie qui finit sur la note de base »).
"""
import copy
import json
from pathlib import Path

import musique as m

# Hors du dossier du code (qui peut être en lecture seule, par exemple dans /opt)
PROGRESS_FILE = Path.home() / ".local/share/mon-studio-donnees/defis.json"
A_MINOR = 0      # indice de « La mineur » dans musique.KEYS
EVERY_2 = list(range(0, 16, 2))


# --- Construction des espaces de travail ---
def renamed(pattern, name):
    pattern = copy.deepcopy(pattern)
    pattern["name"] = name
    return pattern


def empty_like(lane, model):
    return m.new_pattern(lane, "Ton motif", model["bars"] if model else 1)


def workspace(defi):
    """Le morceau de travail du défi : le motif de l'enfant (A) et les motifs d'accompagnement, placés sur 8 mesures."""
    project = m.new_project()
    project.update(name=f"Défi {defi['titre']}", tempo=defi.get("tempo", 90), key=defi.get("key", A_MINOR))
    for lane, instrument in defi.get("instruments", {}).items():
        project["lanes"][lane]["instrument"] = instrument
    if defi.get("workspace"):
        return defi["workspace"](project)
    lane = defi["lane"]
    start = defi.get("depart") or empty_like(lane, defi.get("modele"))
    project["lanes"][lane]["patterns"] = [renamed(start, "A · Ton motif")]
    for other, pattern in defi.get("contexte", {}).items():
        project["lanes"][other]["patterns"] = [renamed(pattern, "A · Accompagnement")]
    for other in m.LANES:
        patterns = project["lanes"][other]["patterns"]
        if patterns:
            for bar in range(0, 8, patterns[0]["bars"]):
                m.place(project, other, 0, bar)
    return project


def loop_events(project, patterns):
    """Notes pour écouter des motifs ensemble en boucle (les accords guident la basse). Renvoie (notes, pas)."""
    preview = copy.deepcopy(project)
    bars = max(p["bars"] for p in patterns.values())
    for lane in m.LANES:
        lane_data = preview["lanes"][lane]
        lane_data["song"] = [None] * m.SONG_BARS
        lane_data["solo"] = False
        if lane in patterns:
            lane_data["patterns"] = [patterns[lane]]
            lane_data["muted"] = False
            for bar in range(0, bars, patterns[lane]["bars"]):
                m.place(preview, lane, 0, bar)
    return m.compile_song(preview), bars * m.STEPS_PER_BAR


def kid_pattern(project, lane):
    patterns = project["lanes"][lane]["patterns"]
    return patterns[0] if patterns else None


def listen_mine(defi, project):
    """Ce que l'enfant a fait, avec l'accompagnement du défi."""
    if defi.get("ecoute_morceau"):
        return m.compile_song(project), m.SONG_BARS * m.STEPS_PER_BAR
    patterns = {lane: p for lane, p in defi.get("contexte", {}).items()}
    mine = kid_pattern(project, defi["lane"])
    if mine:
        patterns[defi["lane"]] = mine
    return loop_events(project, patterns)


def listen_model(defi, project):
    if defi.get("exemple_morceau"):
        example = defi["exemple_morceau"]()
        return m.compile_song(example), m.SONG_BARS * m.STEPS_PER_BAR
    model = defi.get("modele") or defi.get("exemple")
    patterns = dict(defi.get("contexte", {}))
    patterns[defi["lane"]] = model
    return loop_events(project, patterns)


# --- Vérifications ---
def plural(n, word):
    return f"{n} {word}{'s' if n > 1 else ''}"


def row_name(lane, row, key):
    if lane == "batterie":
        return m.DRUM_ROWS[row][0]
    if lane == "basse":
        return f"Note {row + 1}"
    return m.note_name(key, m.scale_note(key, row, 60)) + (" ↑" if row >= 7 else "")


def compare(lane, model, mine, key):
    """(différences en phrases pour un enfant, nombre de cases fausses)."""
    if mine is None:
        return ["Il n'y a pas encore de motif « Ton motif »."], 99
    problems, distance = [], 0
    if lane == "accords":
        for bar in range(model["bars"]):
            want = model["chords"][bar * 4:(bar + 1) * 4]
            have = (mine["chords"] + [None] * 16)[bar * 4:(bar + 1) * 4]
            if want != have:
                distance += sum(1 for w, h in zip(want, have) if w != h)
                names = sorted({m.chord_name(key, d) for d in want if d is not None})
                problems.append(f"Mesure {bar + 1} : il faut l'accord {' / '.join(names)} sur les 4 cases.")
        return problems, distance
    want = {tuple(c) for c in model["cells"]}
    have = {tuple(c) for c in mine["cells"]}
    rows = sorted({r for r, _ in want | have}, reverse=True)
    for row in rows:
        missing = len({c for c in want - have if c[0] == row})
        extra = len({c for c in have - want if c[0] == row})
        word = "coup" if lane == "batterie" else "case"
        name = row_name(lane, row, key)
        distance += missing + extra
        if missing:
            problems.append(f"Il manque {plural(missing, word)} sur « {name} ».")
        if extra:
            problems.append(f"Il y a {plural(extra, word)} en trop sur « {name} ».")
    return problems, distance


def verdict(problems, distance=99):
    if not problems:
        return True, "🎉 Bravo ! C'est exactement ça !"
    start = "Presque ! " if distance <= 2 else "Pas encore… "
    return False, start + " ".join(problems[:3])


def check_copy(defi, project):
    return verdict(*compare(defi["lane"], defi["modele"], kid_pattern(project, defi["lane"]), m.KEYS[project["key"]]))


def check_own_chords(defi, project):
    pattern = kid_pattern(project, "accords")
    chords = pattern["chords"] if pattern else []
    problems = []
    if len(chords) < 16:
        problems.append("Ta suite doit faire 4 mesures (choisis « 4 mesures » dans Longueur).")
    elif None in chords:
        problems.append(f"Il reste {plural(chords.count(None), 'case')} vide{'s' if chords.count(None) > 1 else ''} : remplis tous les temps.")
    else:
        if chords[0] != 0:
            problems.append("Commence par l'accord de la maison : La m.")
        if chords[-1] != 0:
            problems.append("Termine aussi par La m, pour que ça sonne fini.")
        if len(set(chords)) < 3:
            problems.append("Utilise au moins 3 accords différents.")
    return verdict(problems)


def runs_of(pattern):
    return m.runs(pattern["cells"], pattern["bars"] * m.STEPS_PER_BAR) if pattern else []


def check_own_melody(defi, project):
    notes = runs_of(kid_pattern(project, "melodie"))
    problems = []
    if len(notes) < 5:
        problems.append(f"Ta mélodie a {plural(len(notes), 'note')} : il en faut au moins 5.")
    else:
        last = max(notes, key=lambda n: n[1])
        if last[0] % 7 != 0:
            problems.append("Ta dernière note doit être un La (la note de base de la gamme) : ça donne l'impression que c'est fini.")
        if len({n[0] for n in notes}) < 3:
            problems.append("Utilise au moins 3 notes différentes.")
    return verdict(problems)


def check_first_song(defi, project):
    problems = []
    used = {lane: sum(1 for c in project["lanes"][lane]["song"] if c) for lane in m.LANES}
    if used["batterie"] < 8:
        problems.append(f"Mets la batterie sur au moins 8 mesures (il y en a {used['batterie']}).")
    for lane, name in (("basse", "la basse"), ("accords", "les accords"), ("melodie", "la mélodie")):
        if used[lane] < 2:
            problems.append(f"Place aussi {name} sur au moins 2 mesures.")
    return verdict(problems)


def first_song_workspace(project):
    picks = {"batterie": ["Boom bap", "Roulement"], "basse": ["Funk"], "accords": ["Épique (1-6-3-7)"], "melodie": ["Petite boucle"]}
    for lane, names in picks.items():
        project["lanes"][lane]["patterns"] = [renamed(m.template(lane, n), f"{l} · {n}") for l, n in zip("AB", names)]
    project["lanes"]["accords"]["instrument"] = 1
    project["lanes"]["melodie"]["instrument"] = 3
    return project


EPIC = m.template("accords", "Épique (1-6-3-7)")

DEFIS = [
    {"id": "coeur", "titre": "Le battement de cœur", "lane": "batterie", "type": "reproduire",
     "texte": "La grosse caisse, c'est le cœur du morceau : boum, boum, boum, boum.\n\n"
              "Pose un coup de grosse caisse sur chaque temps. Les temps, ce sont les débuts des groupes de 4 cases "
              "(les cases 1, 5, 9 et 13).",
     "indice": "Ligne du bas « Grosse caisse » : 4 coups, un au début de chaque groupe de 4 cases.",
     "modele": m.drum("Modèle", grosse=[0, 4, 8, 12])},
    {"id": "backbeat", "titre": "Boum… tchac !", "lane": "batterie", "type": "reproduire",
     "texte": "Dans la pop et le hip-hop, la caisse claire tape sur le 2e et le 4e temps : c'est le « tchac ».\n\n"
              "Écoute le modèle : grosse caisse sur les temps 1 et 3, caisse claire sur les temps 2 et 4.",
     "indice": "Grosse caisse : cases 1 et 9. Caisse claire : cases 5 et 13.",
     "modele": m.drum("Modèle", grosse=[0, 8], caisse=[4, 12])},
    {"id": "charleston", "titre": "Le charleston qui avance", "lane": "batterie", "type": "reproduire",
     "texte": "Le charleston donne l'impression que le rythme avance, comme une horloge.\n\n"
              "Le boum-tchac est déjà là : ajoute le charleston une case sur deux.",
     "indice": "Ligne « Charleston » : cases 1, 3, 5, 7, 9, 11, 13 et 15 (8 coups).",
     "depart": m.drum("Départ", grosse=[0, 8], caisse=[4, 12]),
     "modele": m.drum("Modèle", grosse=[0, 8], caisse=[4, 12], charleston=EVERY_2)},
    {"id": "boombap", "titre": "Le boom bap", "lane": "batterie", "type": "reproduire", "tempo": 88,
     "texte": "Le boom bap, c'est le rythme du hip-hop des années 90.\n\n"
              "Écoute bien le modèle et recopie-le. Attention : la grosse caisse ne tombe pas toujours sur les temps !",
     "indice": "Grosse caisse : cases 1, 8 et 11. Caisse claire : 5 et 13. Charleston : une case sur deux.",
     "modele": m.template("batterie", "Boom bap")},
    {"id": "electro", "titre": "Danse électro", "lane": "batterie", "type": "reproduire", "tempo": 124,
     "instruments": {"batterie": 4},
     "texte": "En électro, la grosse caisse tape sur tous les temps : c'est le « four on the floor ».\n\n"
              "Recopie le modèle : grosse caisse, clap, et deux sortes de charleston.",
     "indice": "Grosse caisse sur chaque temps, clap sur 5 et 13, charleston ouvert entre les temps (3, 7, 11, 15), "
               "charleston fermé sur toutes les cases paires (2, 4, 6…).",
     "modele": m.template("batterie", "Électro 4/4")},
    {"id": "suite", "titre": "Ta première suite d'accords", "lane": "accords", "type": "reproduire",
     "instruments": {"accords": 0},
     "texte": "Un accord, ce sont plusieurs notes jouées ensemble. Une suite d'accords donne l'ambiance du morceau.\n\n"
              "Pose La m, puis Fa, puis Do, puis Sol : un accord par mesure.",
     "indice": "Mesure 1 : les 4 cases sur « La m ». Mesure 2 : « Fa ». Mesure 3 : « Do ». Mesure 4 : « Sol ».",
     "modele": EPIC},
    {"id": "mes_accords", "titre": "Invente ta suite", "lane": "accords", "type": "créer",
     "instruments": {"accords": 0},
     "texte": "À toi d'inventer ! Fais une suite de 4 mesures :\n"
              "• qui commence et finit par La m (l'accord « maison »),\n"
              "• avec au moins 3 accords différents,\n"
              "• et un accord sur chaque temps.",
     "indice": "Essaie La m, Ré m, Mi m, La m… ou La m, Do, Sol, La m. Écoute l'exemple pour t'inspirer.",
     "depart": m.new_pattern("accords", "Départ", 4),
     "exemple": m.template("accords", "Émotion (6-4-1-5)"),
     "check": check_own_chords},
    {"id": "basse", "titre": "La basse suit les accords", "lane": "basse", "type": "reproduire",
     "texte": "La basse joue la note de base de chaque accord. Ici, elle le fait toute seule !\n\n"
              "Pose « Note 1 » sur chaque temps, puis écoute ta version : la basse change avec les accords.",
     "indice": "Ligne « Note 1 (base) », tout en bas : cases 1, 5, 9 et 13.",
     "contexte": {"accords": EPIC},
     "modele": m.tone("basse", "Modèle", [(0, s, 1) for s in (0, 4, 8, 12)])},
    {"id": "disco", "titre": "La basse disco", "lane": "basse", "type": "reproduire", "tempo": 112,
     "texte": "La basse disco saute entre la note grave et la même note plus aiguë : l'octave.\n\n"
              "Écoute le modèle et recopie-le.",
     "indice": "« Note 1 » sur 1, 5, 9, 13 et « Note 8 (octave) » sur 3, 7, 11, 15.",
     "contexte": {"accords": EPIC, "batterie": m.template("batterie", "Pop rock")},
     "modele": m.template("basse", "Octaves disco")},
    {"id": "gamme", "titre": "Monte l'escalier", "lane": "melodie", "type": "reproduire",
     "instruments": {"melodie": 2},
     "texte": "Une gamme, c'est un escalier de notes qui vont bien ensemble.\n\n"
              "Monte la gamme de La : une marche toutes les 2 cases, de La jusqu'au La du dessus.",
     "indice": "Une note de 2 cases sur chaque ligne, du bas (La) vers le haut (La ↑), en avançant de 2 cases à chaque fois.",
     "modele": m.template("melodie", "Montée")},
    {"id": "ma_melodie", "titre": "Ta mélodie", "lane": "melodie", "type": "créer",
     "instruments": {"melodie": 3},
     "texte": "À toi ! Invente une mélodie sur les accords :\n"
              "• au moins 5 notes,\n"
              "• au moins 3 notes différentes,\n"
              "• et la dernière note sur un La, pour que ça sonne fini.",
     "indice": "Toutes les notes de la grille vont avec les accords : tu ne peux pas jouer faux. Finis sur la ligne « La ».",
     "contexte": {"accords": EPIC},
     "exemple": m.template("melodie", "Petite boucle"),
     "check": check_own_melody},
    {"id": "morceau", "titre": "Ton premier morceau", "lane": "batterie", "type": "créer", "tempo": 88,
     "texte": "Tous les motifs sont prêts en bas : il faut construire le morceau !\n\n"
              "Clique sur un motif, puis dans la ligne de temps pour le placer :\n"
              "• la batterie sur au moins 8 mesures,\n"
              "• la basse, les accords et la mélodie sur au moins 2 mesures chacun.\n\n"
              "Astuce : commence doucement, puis ajoute les instruments un par un.",
     "indice": "Clique sur « 🎸 Basse » à gauche pour voir ses motifs, choisis-en un, puis clique dans sa ligne.",
     "workspace": first_song_workspace, "ecoute_morceau": True,
     "exemple_morceau": m.STYLES["Hip-hop chill"],
     "check": check_first_song},
]


def check(defi, project):
    return (defi.get("check") or check_copy)(defi, project)


# --- Progression ---
def load_progress():
    try:
        return set(json.loads(PROGRESS_FILE.read_text()))
    except (OSError, ValueError):
        return set()


def save_success(defi_id):
    done = load_progress() | {defi_id}
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    m.write_atomic(PROGRESS_FILE, json.dumps(sorted(done)))
    return done
