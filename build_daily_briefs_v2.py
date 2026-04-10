from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
NEWS_FILE = ROOT / "data" / "news.json"
KNOWLEDGE_DIR = ROOT / "knowledge" / "manual-ir-v2"
CHUNKS_FILE = KNOWLEDGE_DIR / "chunks.json"
OUTPUT_FILE = ROOT / "data" / "daily-v2" / "briefs.json"
try:
    LOCAL_TZ = ZoneInfo("Europe/Rome")
except Exception:
    LOCAL_TZ = timezone(timedelta(hours=2), name="Europe/Rome")
CRISIS_START_DAY = "2026-02-28"

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "their", "about", "sono", "della", "delle",
    "dello", "degli", "dalla", "dalle", "dallo", "sulla", "sulle", "sullo", "dopo", "dell", "nella", "nelle",
    "negli", "sugli", "dati", "come", "piu", "più", "anche", "dentro", "iran", "guerra", "war", "news", "reuters",
    "jazeera", "council", "foreign", "relations", "csis", "center", "strategic", "studies", "house", "chatham",
    "brookings", "iiss", "ifri", "swp", "paper", "journal", "issue"
}

FRAMEWORDS = {
    "deterrence": {"deterrence", "deterr", "escalation", "strike", "raid", "threat", "security dilemma", "spiral"},
    "commitment": {"ceasefire", "truce", "negotiation", "commitment", "credibility", "ultimatum", "bargaining"},
    "geoeconomics": {"oil", "energy", "sanctions", "interdependence", "shipping", "hormuz", "trade", "market"},
    "order": {"regional", "order", "alliance", "partners", "revisionism", "power", "hegemony"},
    "humanitarian": {"civilian", "humanitarian", "casualties", "displacement", "hospital", "evacuation"},
}

FRAME_LABELS = {
    "deterrence": "deterrenza e segnalazione coercitiva",
    "commitment": "credibilità degli impegni e diplomazia coercitiva",
    "geoeconomics": "leva geoeconomica e vulnerabilità strategiche",
    "order": "ordine regionale e riallineamento degli attori",
    "humanitarian": "costi umani e vincoli politico-strategici",
}

FRAME_READING = {
    "deterrence": (
        "La chiave interpretativa più utile è quella della deterrenza: minacce, posture e segnali di forza "
        "servono a spostare il calcolo dell'avversario, ma possono anche accelerare la spirale di insicurezza."
    ),
    "commitment": (
        "La giornata va letta soprattutto sul piano della credibilità degli impegni: aperture negoziali, tregue e "
        "ultimatum contano solo se riducono davvero l'incentivo a colpire o a rinviare il costo politico delle scelte."
    ),
    "geoeconomics": (
        "La lettura più convincente è geoeconomica: energia, sanzioni, rotte e prezzi non restano sullo sfondo, ma "
        "diventano strumenti di pressione che redistribuiscono costi e margini di manovra."
    ),
    "order": (
        "Qui pesa soprattutto la dimensione di ordine regionale: alleati, mediatori e potenze esterne ricalibrano "
        "coperture politiche, ambiguità strategiche e forme di allineamento."
    ),
    "humanitarian": (
        "La giornata va letta anche come problema politico-strategico: i costi umani restringono la libertà d'azione, "
        "cambiano il tono diplomatico e possono alterare il consenso."
    ),
}

FRAME_WATCH = {
    "deterrence": "Conviene monitorare se il segnale resta dimostrativo o se apre una soglia nuova di ritorsione e contro-ritorsione.",
    "commitment": "Conviene monitorare tempi, garanzie, verifiche e soprattutto l'eventuale scarto tra linguaggio diplomatico e condotta operativa.",
    "geoeconomics": "Conviene monitorare prezzi, rotte, premi assicurativi, sanzioni e aggiustamenti dei partner più esposti ai costi della crisi.",
    "order": "Conviene monitorare se gli attori regionali restano nelle dichiarazioni o spostano davvero risorse, coperture politiche e iniziative di mediazione.",
    "humanitarian": "Conviene monitorare se l'impatto sui civili modifica la pressione diplomatica, il consenso interno o la legittimità delle operazioni.",
}

ACTOR_DEFS = {
    "Stati Uniti": {"usa", "us", "washington", "trump", "americano", "americani", "statunitense", "statunitensi"},
    "Iran": {"iran", "iraniano", "iraniani", "teheran", "tehran", "khamenei", "pasdaran"},
    "Israele": {"israele", "israel", "israeliano", "israeliani", "idf", "netanyahu"},
    "Russia": {"russia", "mosca", "moscow", "putin"},
    "Cina": {"cina", "china", "pechino", "beijing"},
    "Stati del Golfo": {"gulf", "golfo", "saudita", "sauditi", "emirati", "qatar", "oman"},
    "Europa": {"europa", "europe", "ue", "bruxelles", "francia", "germania", "uk", "regno unito"},
}

THEME_DEFS = {
    "pressione militare": {"strike", "raid", "drone", "missile", "bombard", "attacco", "attacchi", "minaccia", "threat"},
    "rotte e choke points": {"hormuz", "shipping", "strait", "tanker", "cargo", "rotte", "maritt", "vessel"},
    "energia e sanzioni": {"oil", "energy", "energia", "sanzioni", "sanctions", "prezzi", "mercati", "export"},
    "negoziato e tregua": {"negozi", "negoziati", "colloqui", "ceasefire", "truce", "tregua", "mediazione", "ultimatum"},
    "ordine regionale": {"regional", "regionale", "alliance", "partner", "gulf", "golfo", "russia", "cina", "europa"},
    "costi civili": {"civilian", "casualties", "sfoll", "morti", "feriti", "osped", "humanitarian", "evacuation"},
}

MOJIBAKE_REPLACEMENTS = {
    "â€™": "'",
    "Ã¢â‚¬â„¢": "'",
    "â€œ": '"',
    "â€": '"',
    "â€“": "-",
    "â€”": "-",
    "Ã¨": "è",
    "Ã ": "à",
    "Ã¹": "ù",
    "Ã¬": "ì",
    "Ã²": "ò",
    "Ã©": "é",
    "Â·": "·",
}


def repair_mojibake(text: str) -> str:
    cleaned = text or ""
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        cleaned = cleaned.replace(bad, good)
    return cleaned


def normalize(text: str) -> str:
    text = repair_mojibake(text).lower()
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    return [word for word in normalize(text).split() if len(word) > 3 and word not in STOPWORDS]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def display_text(text: str) -> str:
    return re.sub(r"\s+", " ", repair_mojibake(text or "")).strip()


def list_phrase(items: list[str]) -> str:
    cleaned = [display_text(item) for item in items if display_text(item)]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} e {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])} e {cleaned[-1]}"


def clean_title(title: str) -> str:
    cleaned = display_text(title)
    separators = [" - ", " | ", " – ", " — "]
    for separator in separators:
        if separator in cleaned:
            parts = [part.strip() for part in cleaned.split(separator) if part.strip()]
            if len(parts) > 1:
                tail = parts[-1].lower()
                if "." in tail or any(source in tail for source in {
                    "reuters", "al jazeera", "council on foreign relations", "csis", "instituto", "institute",
                    "international institute for strategic studies", "centro di studi strategici"
                }):
                    cleaned = separator.join(parts[:-1]).strip()
                    break
    cleaned = re.sub(
        r"\s+(Reuters|Al Jazeera|Council on Foreign Relations|Consiglio per le Relazioni Estere|CSIS(?:\s*\|.*)?|The International Institute for Strategic Studies.*|L’Istituto internazionale per gli studi strategici.*)$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned


def strip_source_tail(text: str) -> str:
    cleaned = display_text(text)
    tails = [
        "Reuters",
        "Al Jazeera",
        "Council on Foreign Relations",
        "CSIS",
        "The International Institute for Strategic Studies",
    ]
    for tail in tails:
        if cleaned.endswith(tail):
            cleaned = cleaned[: -len(tail)].strip(" -|")
    cleaned = re.sub(r"\b(di|by)\s+(Reuters|Al Jazeera)\s*$", "", cleaned, flags=re.IGNORECASE).strip(" -|")
    cleaned = re.sub(
        r"\s+(CSIS(?:\s*\|.*)?|Council on Foreign Relations|Consiglio per le relazioni estere|The International Institute for Strategic Studies.*|L’Istituto internazionale per gli studi strategici.*)$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" -|")
    cleaned = re.sub(r"\b(di|su|con|per|da|a)\s*$", "", cleaned, flags=re.IGNORECASE).strip(" -|")
    return cleaned.strip()


def story_blob(stories: list[dict]) -> str:
    return " ".join(
        display_text(
            " ".join(
                filter(
                    None,
                    [
                        story.get("title_it"),
                        story.get("summary_it"),
                        story.get("comment_it"),
                        story.get("title"),
                        story.get("summary"),
                    ],
                )
            )
        )
        for story in stories
    )


def group_stories_by_day(stories: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for story in stories:
        time_value = story.get("time", "")
        if not time_value:
            continue
        day_key = time_value[:10]
        if day_key < CRISIS_START_DAY:
            continue
        buckets[day_key].append(story)

    groups = [{"day": day, "stories": sorted(items, key=lambda s: s.get("time", ""), reverse=True)} for day, items in buckets.items()]
    groups.sort(key=lambda item: item["day"], reverse=True)
    return groups


def top_keywords(stories: list[dict], limit: int = 10) -> list[str]:
    counter = Counter()
    for story in stories:
        text = " ".join(
            filter(
                None,
                [
                    story.get("title_it"),
                    story.get("summary_it"),
                    story.get("comment_it"),
                    story.get("title"),
                    story.get("summary"),
                ],
            )
        )
        counter.update(tokenize(text))
    return [word for word, _ in counter.most_common(limit)]


def retrieval_keywords(stories: list[dict], frame: str) -> list[str]:
    keywords = top_keywords(stories, limit=12)
    frame_words = list(FRAMEWORDS.get(frame, set()))
    return list(dict.fromkeys(keywords + frame_words))


def frame_scores(text: str) -> dict[str, int]:
    norm = normalize(text)
    scores: dict[str, int] = {}
    for frame, words in FRAMEWORDS.items():
        scores[frame] = sum(1 for word in words if word in norm)
    return scores


def dominant_frame(stories: list[dict]) -> str:
    scores = Counter()
    for story in stories:
        text = " ".join(
            filter(
                None,
                [
                    story.get("title_it"),
                    story.get("summary_it"),
                    story.get("comment_it"),
                    story.get("title"),
                    story.get("summary"),
                ],
            )
        )
        scores.update(frame_scores(text))
    return scores.most_common(1)[0][0] if scores else "order"


def detect_ranked_items(stories: list[dict], definitions: dict[str, set[str]], limit: int = 4) -> list[str]:
    counter = Counter()
    text = normalize(story_blob(stories))
    for label, words in definitions.items():
        hits = sum(1 for word in words if word in text)
        if hits:
            counter[label] = hits
    return [label for label, _ in counter.most_common(limit)]


def select_key_stories(stories: list[dict], limit: int = 3) -> list[dict]:
    selected = []
    for story in stories[:limit]:
        selected.append(
            {
                "time": (story.get("time", "")[11:16] or "--:--"),
                "source": display_text(story.get("source", "")),
                "title": clean_title(story.get("title_it") or story.get("title") or ""),
                "summary": strip_source_tail(story.get("summary_it") or story.get("summary") or ""),
            }
        )
    return selected


def trim_sentence(text: str) -> str:
    cleaned = strip_source_tail(text)
    if not cleaned:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    first = parts[0].strip() if parts else cleaned
    if len(parts) > 1 and len(first) < 24:
        first = f"{first} {parts[1].strip()}".strip()
    return first.rstrip(". ")


def story_clause(story: dict, *, fallback_to_title: bool = True) -> str:
    summary = trim_sentence(story.get("summary", ""))
    title = clean_title(story.get("title", ""))
    weak_endings = {"di", "su", "con", "per", "da", "a"}
    summary_ending = summary.split()[-1].lower() if summary.split() else ""
    use_summary = bool(summary) and len(summary) >= 36 and summary_ending not in weak_endings
    candidate = summary if use_summary else (title if fallback_to_title else "")
    candidate = display_text(candidate).strip()
    if not candidate:
        return ""

    lowered = candidate[0].lower() + candidate[1:] if len(candidate) > 1 else candidate.lower()
    return lowered


def build_frame_opening(frame: str, day: str, theme_phrase: str, actor_phrase: str, signal_phrase: str, story_count: int) -> str:
    if frame == "deterrence":
        text = (
            f"Il cuore della giornata del {day} sta nel modo in cui segnali coercitivi e margini negoziali vengono fatti convivere nello stesso ciclo di crisi. "
            f"I temi che pesano di più sono {theme_phrase}, mentre {actor_phrase} restano gli attori che definiscono il livello di rischio percepito."
        )
    elif frame == "geoeconomics":
        text = (
            f"La giornata del {day} segnala uno slittamento dal solo piano militare a quello dei costi strategici. "
            f"Il baricentro passa per {theme_phrase}, con {actor_phrase} al centro delle decisioni che redistribuiscono oneri, vulnerabilità e leve di pressione."
        )
    elif frame == "commitment":
        text = (
            f"La giornata del {day} ruota soprattutto attorno alla tenuta degli impegni dichiarati. "
            f"In primo piano ci sono {theme_phrase}, mentre {actor_phrase} restano i soggetti da cui dipende la credibilità delle aperture o delle minacce."
        )
    elif frame == "order":
        text = (
            f"La giornata del {day} vale soprattutto per il suo effetto di riallineamento. "
            f"I temi più presenti sono {theme_phrase}, e {actor_phrase} mostrano come la crisi stia ridisegnando il quadro regionale oltre il singolo episodio."
        )
    else:
        text = (
            f"La giornata del {day} concentra l'attenzione su {theme_phrase}. "
            f"Il flusso delle notizie mostra che {actor_phrase} restano i soggetti che orientano il significato politico della sequenza."
        )

    if signal_phrase:
        text += f" I segnali più visibili ruotano attorno a {signal_phrase}."
    if story_count == 1:
        text += " Il numero ridotto di notizie rende ancora più leggibile il punto di pressione prevalente."
    return text


def build_implication(frame: str, themes: list[str], actors: list[str], source_names: list[str]) -> str:
    actor_phrase = list_phrase(actors[:2]) or "gli attori principali"
    theme_phrase = list_phrase(themes[:2]) or "il nucleo centrale della crisi"
    source_phrase = list_phrase(source_names[:2]) if source_names else ""

    if frame == "deterrence":
        text = (
            f"Il punto politico più delicato è che {theme_phrase} non vengono gestiti come fasi separate: pressione e pausa tattica si sovrappongono. "
            f"Questo costringe {actor_phrase} a misurare non solo la forza del segnale, ma anche il rischio di essere letti come incoerenti o poco credibili."
        )
    elif frame == "geoeconomics":
        text = (
            f"La giornata chiarisce che {theme_phrase} stanno entrando nel conflitto come leve strategiche vere e proprie. "
            f"Per {actor_phrase} il problema non è soltanto reagire all'evento, ma assorbire costi e vulnerabilità che possono accumularsi anche senza una nuova offensiva."
        )
    elif frame == "commitment":
        text = (
            f"Il nodo politico è la distanza tra dichiarazioni e garanzie effettive. "
            f"Per {actor_phrase} la questione non è solo aprire un canale, ma convincere l'altra parte che il rinvio dell'escalation non sarà usato per migliorare le proprie posizioni."
        )
    elif frame == "order":
        text = (
            f"La posta in gioco non riguarda solo l'episodio del giorno, ma il modo in cui la crisi rialloca posizioni e margini di mediazione. "
            f"Per {actor_phrase} questo significa decidere se restare sul piano dichiarativo oppure trasformare il posizionamento politico in iniziativa concreta."
        )
    else:
        text = (
            f"La giornata conferma che {theme_phrase} stanno incidendo anche sul terreno politico più ampio. "
            f"Per {actor_phrase} diventa quindi importante contenere l'episodio immediato senza perdere controllo della traiettoria generale."
        )

    if source_phrase:
        text += f" Le fonti che pesano di più nella giornata sono {source_phrase}, e questo aiuta a capire quale lato della crisi sta ricevendo maggiore attenzione."
    return text


def build_storyline(key_stories: list[dict]) -> str:
    if not key_stories:
        return "Il flusso della giornata non offre ancora abbastanza elementi per una ricostruzione puntuale."

    if len(key_stories) == 1:
        story = key_stories[0]
        clause = story_clause(story)
        return (
            f"Sul piano dei fatti, il punto più visibile della giornata è che {clause}. "
            f"Questo episodio concentra quasi da solo il significato operativo della sequenza."
        )

    opening = key_stories[0]
    second = key_stories[1]
    opening_clause = story_clause(opening)
    second_clause = story_clause(second)
    pieces = [f"Sul piano dei fatti, la giornata si apre con il fatto che {opening_clause}"]
    if second_clause:
        pieces.append(f"a cui si aggiunge che {second_clause}")
    if len(key_stories) > 2:
        third_clause = story_clause(key_stories[2])
        if third_clause:
            pieces.append(f"mentre {third_clause}")
    return f"{', '.join(pieces)}."


def build_source_angle(key_stories: list[dict]) -> str:
    if not key_stories:
        return "Le fonti del giorno non consentono ancora di distinguere un angolo di lettura prevalente."

    source_map: dict[str, list[str]] = defaultdict(list)
    for story in key_stories:
        if story["source"] and story["title"]:
            source_map[story["source"]].append(story["title"])

    chunks = []
    for source, titles in list(source_map.items())[:3]:
        chunks.append(f"{source} insiste soprattutto su {titles[0].lower()}")

    if not chunks:
        return "Le fonti convergono soprattutto sulla stessa sequenza di segnali politici e operativi."

    return "Tra le fonti emerge una ripartizione abbastanza chiara: " + "; ".join(chunks) + "."


def retrieve_chunks(keywords: list[str], chunks: list[dict], limit: int = 4) -> list[dict]:
    scored = []
    keyword_set = set(keywords)

    for chunk in chunks:
        chunk_words = set(tokenize(chunk.get("text", "")))
        overlap = len(keyword_set & chunk_words)
        if overlap:
            scored.append((overlap, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:limit]]


def day_label(day: str) -> str:
    return datetime.fromisoformat(day).strftime("%Y-%m-%d")


def classify_day_status(day: str, newest_day: str | None, local_today: str) -> tuple[str, str]:
    if day == local_today:
        return (
            "live",
            "Brief provvisorio: il giorno in corso resta aperto e si aggiorna a ogni ciclo di raccolta."
        )

    if newest_day and day == newest_day and newest_day < local_today:
        return (
            "latest_closed",
            "Ultimo dossier disponibile: non essendoci ancora notizie per oggi, questo resta il giorno più recente già chiuso."
        )

    return (
        "final",
        "Brief chiuso: la giornata non si aggiorna più e resta come archivio stabile della sequenza."
    )


def finalization_note(status: str) -> str:
    if status == "live":
        return "Se arrivano nuove notizie il brief si aggiorna ogni 10 minuti; dopo le 00:05 ora italiana viene consolidato in versione finale."
    if status == "latest_closed":
        return "Questo blocco è già consolidato. Il prossimo brief si aprirà appena arriveranno notizie nel nuovo giorno operativo."
    return "Giornata già consolidata dopo la chiusura notturna del ciclo di aggiornamento."


def continuity_sentence(previous_group: dict | None, themes: list[str], continuity: list[str], discontinuity: list[str]) -> str:
    if not previous_group:
        return "Essendo il primo blocco della sequenza recente, questa giornata funziona come base iniziale del quadro evolutivo."

    previous_day = previous_group["day"]
    if themes and continuity:
        return (
            f"Rispetto al {previous_day}, la continuità si vede soprattutto nella persistenza di "
            f"{list_phrase(themes[:2])}; cambia però il modo in cui questi temi entrano nel ciclo di crisi."
        )

    if discontinuity:
        return (
            f"Rispetto al {previous_day}, il baricentro della giornata si sposta verso "
            f"{list_phrase(discontinuity[:2])}, segnalando una variazione nel ritmo o nella scala della pressione."
        )

    return f"Rispetto al {previous_day}, la giornata resta dentro lo stesso quadro generale ma con una distribuzione diversa dei segnali più rilevanti."


def build_analytical_summary(
    day_group: dict,
    previous_group: dict | None,
    frame: str,
    actors: list[str],
    themes: list[str],
    continuity: list[str],
    discontinuity: list[str],
    key_stories: list[dict],
    source_names: list[str],
) -> dict[str, str]:
    actor_phrase = list_phrase(actors[:3]) or "gli attori già più esposti nella crisi"
    theme_phrase = list_phrase(themes[:3]) or FRAME_LABELS.get(frame, "il quadro strategico del giorno")
    signal_phrase = list_phrase(discontinuity[:2] or continuity[:2])
    overview = build_frame_opening(frame, day_group["day"], theme_phrase, actor_phrase, signal_phrase, len(day_group["stories"]))

    storyline = build_storyline(key_stories)
    source_angle = build_source_angle(key_stories)
    implication = build_implication(frame, themes, actors, source_names)
    strategic_reading = FRAME_READING.get(
        frame,
        "La chiave interpretativa più utile è seguire come i segnali del giorno cambiano il calcolo del rischio senza produrre ancora una svolta conclusiva.",
    )
    trajectory = continuity_sentence(previous_group, themes, continuity, discontinuity)
    watchpoint = FRAME_WATCH.get(
        frame,
        "Conviene monitorare se i segnali del giorno vengono assorbiti oppure si sommano fino a cambiare la fase della crisi.",
    )
    return {
        "overview": overview,
        "storyline": storyline,
        "source_angle": source_angle,
        "implication": implication,
        "strategic_reading": strategic_reading,
        "trajectory": trajectory,
        "watchpoint": watchpoint,
    }


def build_brief(day_group: dict, previous_group: dict | None, chunks: list[dict], newest_day: str | None, local_today: str) -> dict:
    stories = day_group["stories"]
    frame = dominant_frame(stories)
    keywords = top_keywords(stories)
    retrieved = retrieve_chunks(retrieval_keywords(stories, frame), chunks)
    retrieved_titles = [display_text(chunk["title"]) for chunk in retrieved]
    actors = detect_ranked_items(stories, ACTOR_DEFS, limit=4)
    themes = detect_ranked_items(stories, THEME_DEFS, limit=4)
    key_stories = select_key_stories(stories, limit=3)
    source_names = [display_text(story.get("source", "")) for story in stories if story.get("source")]
    source_names = list(dict.fromkeys(source_names))

    previous_keywords = top_keywords(previous_group["stories"]) if previous_group else []
    continuity = [word for word in keywords if word in previous_keywords][:4]
    discontinuity = [word for word in keywords if word not in previous_keywords][:4]
    status, status_note = classify_day_status(day_group["day"], newest_day, local_today)
    analytical_summary = build_analytical_summary(
        day_group,
        previous_group,
        frame,
        actors,
        themes,
        continuity,
        discontinuity,
        key_stories,
        source_names,
    )

    return {
        "day": day_group["day"],
        "label": day_label(day_group["day"]),
        "story_count": len(stories),
        "status": status,
        "status_note": status_note,
        "finalization_note": finalization_note(status),
        "dominant_frame": frame,
        "dominant_theme_label": FRAME_LABELS.get(frame, frame),
        "top_keywords": keywords,
        "continuity_markers": continuity,
        "discontinuity_markers": discontinuity,
        "actors_in_focus": actors,
        "themes_in_focus": themes,
        "manual_lens": FRAME_LABELS.get(frame, frame),
        "key_stories": key_stories,
        "analytical_summary": analytical_summary,
        "sources": source_names,
        "retrieved_context_titles": list(dict.fromkeys(retrieved_titles)),
        "retrieved_context": [
            {
                "chunk_id": chunk["chunk_id"],
                "title": display_text(chunk["title"]),
                "text": display_text(chunk["text"][:700]),
            }
            for chunk in retrieved
        ],
        "commentator_prompt_package": {
            "instruction": (
                "Scrivi una sintesi giornaliera in italiano chiaro, analitico ma leggibile. "
                "Spiega cosa conta nella giornata, quale meccanismo strategico o geoeconomico aiuta a leggerla, "
                "che cosa cambia rispetto ai giorni precedenti e che cosa conviene monitorare dopo. "
                "Non citare il materiale di supporto e non usare formule meta-discorsive."
            ),
            "dominant_frame": frame,
            "keywords": keywords,
            "continuity_markers": continuity,
            "discontinuity_markers": discontinuity,
            "retrieved_context_titles": list(dict.fromkeys(retrieved_titles)),
        },
    }


def main() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = load_json(NEWS_FILE)
    chunks = load_json(CHUNKS_FILE) if CHUNKS_FILE.exists() else []
    day_groups = group_stories_by_day(payload.get("stories", []))
    local_now = datetime.now(LOCAL_TZ)
    local_today = local_now.date().isoformat()
    newest_day = day_groups[0]["day"] if day_groups else None

    briefs = []
    for index, day_group in enumerate(day_groups):
        previous_group = day_groups[index + 1] if index + 1 < len(day_groups) else None
        briefs.append(build_brief(day_group, previous_group, chunks, newest_day, local_today))

    OUTPUT_FILE.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "generated_at_local": local_now.isoformat(),
                "refresh_interval_minutes": 10,
                "daily_close_time_local": "00:05",
                "coverage_start_day": CRISIS_START_DAY,
                "briefs": briefs,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Daily v2 briefs: {len(briefs)}")


if __name__ == "__main__":
    main()
