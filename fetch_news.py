from __future__ import annotations

import json
import hashlib
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_FILE = DATA_DIR / "news.json"
TIMEOUT_SECONDS = 20
MAX_ITEMS_PER_SOURCE = 3
MAX_SUMMARY_LENGTH = 260
ARTICLE_FETCH_TIMEOUT_SECONDS = 8
CRISIS_START_DAY = "2026-02-28"
MOJIBAKE_MARKERS = (
    "Ã",
    "Â",
    "â€™",
    "â€“",
    "â€”",
    "â€œ",
    "â€",
    "â€˜",
    "â€¦",
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

IRAN_TERMS = (
    "iran",
    "tehran",
    "israel",
    "middle east",
    "gulf",
    "hormuz",
    "natanz",
    "isfahan",
    "conflict",
    "war",
)


@dataclass(frozen=True)
class Source:
    name: str
    kind: str
    value: str


SOURCES: list[Source] = [
    # Italia
    Source("Corriere della Sera", "google_news", "site:corriere.it Iran"),
    Source("la Repubblica", "google_news", "site:repubblica.it Iran"),
    Source("La Stampa", "google_news", "site:lastampa.it Iran"),
    Source("Il Sole 24 Ore", "google_news", "site:ilsole24ore.com Iran"),
    Source("ANSA", "google_news", "site:ansa.it Iran"),
    # Global media
    Source("Reuters", "google_news", "site:reuters.com Iran"),
    Source("Associated Press", "google_news", "site:apnews.com Iran"),
    Source("AFP", "google_news", "site:france24.com AFP Iran"),
    Source("Bloomberg", "google_news", "site:bloomberg.com Iran"),
    Source("Financial Times", "google_news", "site:ft.com Iran"),
    Source("The Economist", "google_news", "site:economist.com Iran"),
    Source("Wall Street Journal", "google_news", "site:wsj.com Iran"),
    Source("The Guardian", "google_news", "site:theguardian.com Iran"),
    Source("BBC", "google_news", "site:bbc.com Iran"),
    Source("Sky News", "google_news", "site:news.sky.com Iran"),
    Source("CNN", "google_news", "site:cnn.com Iran"),
    Source("Al Jazeera", "google_news", "site:aljazeera.com Iran"),
    Source("Middle East Eye", "google_news", "site:middleeasteye.net Iran"),
    Source("The National", "google_news", "site:thenationalnews.com Iran"),
    # China / Asia
    Source("CIIS", "google_news", "site:ciis.org.cn Iran"),
    Source("CICIR", "google_news", "site:cicir.ac.cn Iran"),
    Source("Global Times", "google_news", "site:globaltimes.cn Iran"),
    Source("South China Morning Post", "google_news", "site:scmp.com Iran"),
    # US think tanks
    Source("Council on Foreign Relations", "google_news", "site:cfr.org Iran"),
    Source("CSIS", "google_news", "site:csis.org Iran"),
    Source("Brookings", "google_news", "site:brookings.edu Iran"),
    Source("Carnegie Endowment", "google_news", "site:carnegieendowment.org Iran"),
    Source("Atlantic Council", "google_news", "site:atlanticcouncil.org Iran"),
    Source("RAND", "google_news", "site:rand.org Iran"),
    Source("Stimson Center", "google_news", "site:stimson.org Iran"),
    # UK think tanks
    Source("Chatham House", "google_news", "site:chathamhouse.org Iran"),
    Source("IISS", "google_news", "site:iiss.org Iran"),
    Source("RUSI", "google_news", "site:rusi.org Iran"),
    Source("ODI", "google_news", "site:odi.org Iran"),
    # France / Germany / EU
    Source("Ifri", "google_news", "site:ifri.org Iran"),
    Source("IRIS France", "google_news", "site:iris-france.org Iran"),
    Source("Fondation pour la Recherche Strategique", "google_news", "site:frstrategie.org Iran"),
    Source("SWP Berlin", "google_news", "site:swp-berlin.org Iran"),
    Source("DGAP", "google_news", "site:dgap.org Iran"),
    Source("German Marshall Fund", "google_news", "site:gmfus.org Iran"),
    Source("ECFR", "google_news", "site:ecfr.eu Iran"),
    # Additional requested sources
    Source("The Telegraph", "google_news", "site:telegraph.co.uk Iran"),
    Source("Le Monde", "google_news", "site:lemonde.fr Iran"),
    Source("Institute for the Study of War", "google_news", "site:understandingwar.org Iran middle east"),
    Source("Defense News", "google_news", "site:defensenews.com Iran"),
    Source("Foreign Policy", "google_news", "site:foreignpolicy.com Iran Israel conflict"),
    Source("War on the Rocks", "google_news", "site:warontherocks.com Iran"),
    Source("International Crisis Group", "google_news", "site:crisisgroup.org Iran"),
    Source("Analisi Difesa", "google_news", "site:analisidifesa.it Iran"),
    Source("NPR", "google_news", "site:npr.org Iran"),
    Source("Asharq Al-Awsat", "google_news", "site:english.aawsat.com Iran"),
    Source("Politico", "google_news", "site:politico.com Iran"),
    Source("Al Arabiya English", "google_news", "site:english.alarabiya.net Iran"),
    Source("Arab News", "google_news", "site:arabnews.com Iran"),
    Source("The New Arab", "google_news", "site:newarab.com Iran"),
    Source("Al-Monitor", "google_news", "site:al-monitor.com Iran"),
    Source("IRNA English", "google_news", "site:en.irna.ir Iran"),
    Source("Tasnim News", "google_news", "site:tasnimnews.com/en Iran"),
    Source("Mehr News", "google_news", "site:en.mehrnews.com Iran"),
    Source("Press TV", "google_news", "site:presstv.ir Iran"),
    Source("Iran International", "google_news", "site:iranintl.com Iran"),
    Source("The Times of Israel", "google_news", "site:timesofisrael.com Iran"),
    Source("Haaretz", "google_news", "site:haaretz.com Iran"),
    Source("The Jerusalem Post", "google_news", "site:jpost.com Iran"),
    Source("i24NEWS", "google_news", "site:i24news.tv Iran"),
    Source("Saudi Press Agency", "google_news", "site:spa.gov.sa/en Iran"),
    Source("WAM Emirates News Agency", "google_news", "site:wam.ae/en Iran"),
    Source("Qatar News Agency", "google_news", "site:qna.org.qa/en Iran"),
    Source("Bahrain News Agency", "google_news", "site:bna.bh/en Iran"),
    Source("KUNA", "google_news", "site:kuna.net.kw Iran"),
]


def build_feed_url(source: Source) -> str:
    if source.kind == "rss":
        return source.value

    encoded_query = urllib.parse.quote(f"{source.value} when:14d")
    return f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"


def fetch_text(url: str, timeout: int = TIMEOUT_SECONDS) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def looks_mojibake(text: str) -> bool:
    if not text:
        return False
    return any(marker in text for marker in MOJIBAKE_MARKERS) or "�" in text


def repair_mojibake(text: str) -> str:
    if not text or not looks_mojibake(text):
        return text

    def score(value: str) -> tuple[int, int]:
        marker_hits = sum(value.count(marker) for marker in MOJIBAKE_MARKERS)
        return (marker_hits + value.count("�"), len(value))

    best = text
    seen = {text}
    queue = [text]

    while queue:
        current = queue.pop(0)
        for encoding in ("latin1", "cp1252"):
            try:
                candidate = current.encode(encoding).decode("utf-8")
            except Exception:
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            queue.append(candidate)
            if score(candidate) < score(best):
                best = candidate

    return best


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = unescape(text)
    text = repair_mojibake(text)
    return re.sub(r"\s+", " ", text).strip()


def summarize(value: str) -> str:
    clean = strip_html(value)
    if not clean:
        return "Apri il link per leggere la notizia completa sulla fonte originale."
    if len(clean) <= MAX_SUMMARY_LENGTH:
        return clean
    return f"{clean[:MAX_SUMMARY_LENGTH].rstrip()}..."


def extract_original_url(raw_description: str, fallback_link: str) -> str:
    if raw_description:
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', raw_description, flags=re.IGNORECASE)
        for href in hrefs:
            candidate = unescape(href).strip()
            if not candidate:
                continue
            host = ""
            try:
                host = (urlparse(candidate).hostname or "").lower()
            except Exception:
                host = ""
            if host and "news.google.com" not in host:
                return candidate
    return fallback_link


def build_source_markers(source_name: str, link: str) -> set[str]:
    markers = {source_name.lower().strip()}

    try:
        host = urlparse(link).hostname or ""
    except Exception:
        host = ""

    if host:
        host = host.lower().replace("www.", "")
        markers.add(host)
        root = host.split(".")[0].strip()
        if root:
            markers.add(root)
    return {m for m in markers if m}


def cleanup_title(title: str, source_name: str, link: str) -> str:
    clean = strip_html(title)
    markers = build_source_markers(source_name, link)
    separators = (" - ", " – ", " — ", " | ")

    for separator in separators:
        if separator not in clean:
            continue
        head, tail = clean.rsplit(separator, 1)
        tail_norm = tail.lower().strip()
        if not tail_norm:
            continue
        if "." in tail_norm or any(marker in tail_norm for marker in markers):
            return head.strip()

    return clean.strip()


def pick_variant(seed: str, options: list[str]) -> str:
    if not options:
        return ""
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return options[int(digest[:8], 16) % len(options)]


def detect_actor(text: str) -> str:
    actor_map = [
        (("stati uniti", "usa", "washington", "trump", "pentagono"), "gli Stati Uniti"),
        (("iran", "teheran", "tehran", "pasdaran"), "l'Iran"),
        (("israele", "israel", "netanyahu", "idf"), "Israele"),
        (("cina", "beijing", "pechino"), "la Cina"),
        (("russia", "mosca", "moscow"), "la Russia"),
        (("europa", "ue", "bruxelles", "european union"), "l'Unione Europea"),
        (("houthi", "yemen"), "gli Houthi"),
        (("hezbollah", "libano", "lebanon"), "Hezbollah"),
    ]
    for words, label in actor_map:
        if any(word in text for word in words):
            return label
    return "gli attori coinvolti"


def detect_location(text: str) -> str:
    location_map = [
        (("hormuz", "stretto"), "nello Stretto di Hormuz"),
        (("golfo", "gulf"), "nell'area del Golfo"),
        (("teheran", "tehran"), "attorno a Teheran"),
        (("natanz",), "attorno a Natanz"),
        (("isfahan",), "nell'area di Isfahan"),
        (("libano", "lebanon"), "sul fronte libanese"),
        (("siria", "syria"), "sul fronte siriano"),
        (("iraq", "iraq"), "sul fronte iracheno"),
        (("yemen",), "sul fronte yemenita"),
        (("mar rosso", "red sea"), "nel Mar Rosso"),
    ]
    for words, label in location_map:
        if any(word in text for word in words):
            return label
    return "nel teatro regionale"


def detect_theme(text: str) -> str:
    theme_checks = [
        ("diplomacy", ("colloqui", "negozi", "accord", "tregua", "ceasefire", "mediare", "mediat")),
        ("maritime", ("hormuz", "nave", "tanker", "maritt", "stretto", "ais", "shipping", "cargo")),
        ("military", ("missil", "drone", "bombard", "raid", "attacco", "strike", "intercett")),
        ("civilian", ("civili", "osped", "evacu", "sfoll", "morti", "feriti", "rifugiat")),
        ("economic", ("sanzion", "tariff", "petrol", "export", "energia", "prezzo", "oil")),
    ]
    for theme, words in theme_checks:
        if any(word in text for word in words):
            return theme
    return "strategic"


def extract_first_sentence(text: str) -> str:
    clean = re.sub(r"\s+", " ", strip_html(text)).strip()
    if not clean:
        return ""
    match = re.match(r"(.{20,280}?[.!?])(\s|$)", clean)
    if match:
        return match.group(1).strip()
    return clean[:220].rstrip()


def extract_subtitle(text: str) -> str:
    clean = re.sub(r"\s+", " ", strip_html(text)).strip()
    if not clean:
        return ""
    if len(clean) > 360:
        return clean[:360].rstrip()
    return clean


def is_generic_subtitle(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return True

    generic_markers = (
        "coverage updated",
        "updated coverage",
        "complete coverage",
        "full coverage",
        "aggregated from sources",
        "google news",
        "copertura di notizie aggiornata",
        "copertura aggiornata",
        "copertura completa",
        "aggregata da fonti",
        "aggiornata e completa",
        "leggi l'articolo completo",
        "read the full article",
    )

    return any(marker in lowered for marker in generic_markers)


def normalize_for_comparison(text: str) -> str:
    clean = strip_html(text).lower()
    clean = re.sub(r"[^\w\s]", " ", clean, flags=re.UNICODE)
    return re.sub(r"\s+", " ", clean).strip()


def is_redundant_with_title(candidate: str, title: str) -> bool:
    normalized_candidate = normalize_for_comparison(candidate)
    normalized_title = normalize_for_comparison(title)

    if not normalized_candidate or not normalized_title:
        return False

    if normalized_candidate == normalized_title:
        return True
    if normalized_title in normalized_candidate or normalized_candidate in normalized_title:
        return True

    title_words = {word for word in normalized_title.split() if len(word) > 3}
    candidate_words = {word for word in normalized_candidate.split() if len(word) > 3}
    if not title_words or not candidate_words:
        return False

    overlap = len(title_words & candidate_words) / max(1, len(title_words))
    return overlap >= 0.8


def detect_mechanism(text: str, theme: str) -> str:
    mechanism_map = {
        "maritime": "la leva decisiva riguarda i colli di bottiglia marittimi e la sicurezza delle rotte energetiche",
        "diplomacy": "il nodo reale e' capire se l'apertura negoziale produce impegni credibili e verificabili",
        "military": "il punto centrale e' se l'episodio resta circoscritto o innesca una risposta a catena",
        "civilian": "la questione principale e' l'impatto politico e strategico dei costi umani del conflitto",
        "economic": "la dinamica chiave passa per coercizione economica, prezzi dell'energia e vulnerabilita' degli importatori",
        "strategic": "il punto decisivo e' la tenuta di un equilibrio regionale ancora instabile e negoziato sotto pressione",
    }

    if "sanzion" in text:
        return "la leva usata sembra economico-finanziaria, con effetti che contano piu' nel medio periodo che nell'immediato"
    if "petrol" in text or "oil" in text or "energia" in text:
        return "la variabile decisiva e' energetica: prezzi, scorte e continuita' delle forniture diventano subito un fatto geopolitico"
    if "giappone" in text or "japan" in text or "cina" in text or "india" in text:
        return "il segnale importante e' che le ricadute non restano locali ma coinvolgono subito gli importatori asiatici e le catene di approvvigionamento"
    return mechanism_map.get(theme, mechanism_map["strategic"])


def detect_frame(text: str, theme: str) -> str:
    if any(word in text for word in ("ceasefire", "tregua", "colloqui", "negozi", "mediazione", "mediat", "deadline", "ultimatum")):
        return "commitment"
    if any(word in text for word in ("hormuz", "shipping", "cargo", "tanker", "petrol", "oil", "energia", "sanzion", "export", "tariff")):
        return "geoeconomic"
    if any(word in text for word in ("bombard", "raid", "strike", "drone", "missil", "attacco", "threat", "minaccia", "ultimatum")):
        return "deterrence"
    if any(word in text for word in ("civili", "morti", "feriti", "sfoll", "evacu", "osped", "devastation", "casualt")):
        return "humanitarian"
    if any(word in text for word in ("gulf states", "golfo", "putin", "russia", "cina", "china", "europa", "europe", "pakistan", "giappone", "japan", "korea", "corea")):
        return "order"
    if theme == "economic":
        return "geoeconomic"
    if theme == "diplomacy":
        return "commitment"
    if theme == "military":
        return "deterrence"
    if theme == "civilian":
        return "humanitarian"
    return "regional_balance"


def detect_secondary_actor(text: str) -> str:
    actor_map = [
        (("giappone", "japan"), "il Giappone"),
        (("pakistan", "islamabad"), "il Pakistan"),
        (("gulf states", "stati del golfo", "gulf"), "gli Stati del Golfo"),
        (("putin", "mosca", "russia"), "la Russia"),
        (("cina", "china", "pechino", "beijing"), "la Cina"),
        (("europa", "bruxelles", "ue", "european union"), "l'Unione Europea"),
        (("south korea", "corea del sud", "seoul"), "la Corea del Sud"),
        (("pope", "papa", "vatican", "vaticano"), "il Vaticano"),
    ]
    for words, label in actor_map:
        if any(word in text for word in words):
            return label
    return ""


def with_preposition_da(actor: str) -> str:
    mapping = {
        "gli Stati Uniti": "dagli Stati Uniti",
        "l'Iran": "dall'Iran",
        "Israele": "da Israele",
        "la Cina": "dalla Cina",
        "la Russia": "dalla Russia",
        "l'Unione Europea": "dall'Unione Europea",
        "gli Houthi": "dagli Houthi",
        "Hezbollah": "da Hezbollah",
        "gli attori coinvolti": "dagli attori coinvolti",
    }
    return mapping.get(actor, f"da {actor}")


def build_hook_sentence(text: str, actor: str, location: str, theme: str) -> str:
    secondary_actor = detect_secondary_actor(text)

    if "hormuz" in text and secondary_actor == "il Giappone":
        return "Qui si vede bene come una tensione su Hormuz non resti locale: appena traffico e transiti si inceppano, i grandi importatori asiatici sono costretti a usare scorte o cercare alternative."
    if "gulf states" in text or "stati del golfo" in text:
        return "La notizia segnala che anche i partner regionali stanno ricalibrando le proprie scelte di sicurezza, cioe' come si proteggono senza farsi trascinare direttamente nel conflitto."
    if secondary_actor == "la Russia":
        return "Qui il conflitto non resta regionale: entra anche nel calcolo strategico di Mosca, che valuta costi, opportunita' e spazi di influenza."
    if secondary_actor == "il Vaticano":
        return "Il peso della notizia sta nel fatto che l'escalation produce ormai anche un costo politico e reputazionale fuori dal teatro strettamente militare."
    if theme == "maritime":
        return f"Il fatto centrale e' che la pressione {location} tocca insieme rotte, assicurazioni, approvvigionamenti e tempi della logistica energetica."
    if theme == "diplomacy":
        return f"Il punto immediato e' il tentativo di aprire o mantenere una finestra negoziale {location}, in un contesto in cui i segnali militari restano comunque attivi."
    if theme == "military":
        return f"Il nodo della notizia e' se la mossa compiuta {with_preposition_da(actor)} {location} serva a rafforzare la deterrenza oppure apra una nuova spirale di ritorsioni."
    if theme == "economic":
        return "La notizia mostra che energia, sanzioni, prezzi e accesso alle rotte stanno diventando parte del confronto strategico, non solo del suo contesto."
    if theme == "civilian":
        return "Qui il dato piu' importante e' che i costi civili del conflitto stanno acquistando un peso politico autonomo e possono cambiare i margini di scelta dei governi."
    if secondary_actor:
        return f"Il punto di fondo e' che la notizia coinvolge anche {secondary_actor}, segno che la crisi sta ridistribuendo costi e pressioni ben oltre il suo nucleo originario."
    return f"Il punto di fondo e' che {actor} {location} sta ridefinendo il quadro regionale oltre il singolo episodio raccontato dal titolo."


def build_frame_sentence(text: str, frame: str) -> str:
    frame_map = {
        "commitment": "In termini di relazioni internazionali, qui conta la credibilita' dell'impegno: tregue, aperture e mediazioni reggono solo se ciascuna parte teme meno di essere colpita subito dopo.",
        "geoeconomic": "In chiave IPE, questo e' un caso di interdipendenza usata come leva: rotte, energia, sanzioni e accesso ai mercati diventano strumenti di pressione politica.",
        "deterrence": "Sul piano strategico, il problema e' il dilemma della deterrenza: mostrare forza puo' contenere l'avversario, ma puo' anche spingerlo a reagire per non perdere credibilita'.",
        "humanitarian": "Sul piano politico, i costi umani non restano solo morali: possono restringere la liberta' d'azione dei governi e aumentare pressioni diplomatiche, interne e internazionali.",
        "order": "Sul piano dell'ordine regionale, la notizia segnala che partner, mediatori e grandi potenze stanno ricalibrando posizione, coperture politiche e margini di allineamento.",
        "regional_balance": "Sul piano analitico, il dato da leggere non e' il titolo in se', ma la sequenza: annunci, minacce e mosse parziali cambiano il calcolo del rischio anche senza una svolta immediata.",
    }

    if "hormuz" in text:
        return "In termini strategici, Hormuz pesa perche' concentra passaggi energetici cruciali: basta una minaccia credibile, non necessariamente una chiusura totale, per produrre effetti globali."
    if "sanzion" in text:
        return "In chiave geoeconomica, la coercizione funziona attraverso aspettative e vulnerabilita': non conta solo il danno immediato, ma anche come gli attori anticipano costi e aggiustano le scelte."
    if "colloqui" in text or "negozi" in text or "ceasefire" in text:
        return "La lente utile qui e' quella del commitment problem: anche quando tutti dichiarano di voler ridurre l'escalation, manca spesso la garanzia che l'altro non approfitti della pausa."
    return frame_map.get(frame, frame_map["regional_balance"])


def build_watch_sentence(text: str, frame: str) -> str:
    watch_map = {
        "commitment": "Da seguire: tempi, garanzie, verifiche e soprattutto se ai contatti politici corrispondono segnali operativi coerenti.",
        "geoeconomic": "Da seguire: traffico marittimo, premi assicurativi, prezzi dell'energia, uso delle scorte e reazione degli importatori piu' esposti.",
        "deterrence": "Da seguire: se all'annuncio segue una ritorsione, una pausa, oppure un nuovo ultimatum che alza ancora il costo del passo successivo.",
        "humanitarian": "Da seguire: se l'impatto sui civili modifica consenso interno, pressione diplomatica e tono delle posizioni internazionali.",
        "order": "Da seguire: se gli attori esterni si fermano alle dichiarazioni o spostano davvero risorse, mediazioni e coperture politiche.",
        "regional_balance": "Da seguire: se il segnale resta isolato oppure viene assorbito in una dinamica di escalation piu' ampia nei prossimi passaggi.",
    }

    if "japan" in text or "giappone" in text or "corea del sud" in text or "south korea" in text:
        return "Da seguire: la risposta degli importatori asiatici, perche' quando cambiano scorte, rotte o contratti si capisce subito se la crisi sta diventando sistemica."
    if "pakistan" in text:
        return "Da seguire: se il mediatore riesce davvero a congelare i tempi della crisi oppure se la diplomazia serve solo a guadagnare spazio tattico."
    return watch_map.get(frame, watch_map["regional_balance"])


def build_commentary(story: dict) -> str:
    source_text = (
        f"{story.get('title', '')} {story.get('summary', '')} "
        f"{story.get('title_it', '')} {story.get('summary_it', '')}"
    ).lower()
    title_it = story.get("title_it") or translate_to_italian(story.get("title", ""))
    actor = detect_actor(source_text)
    location = detect_location(source_text)
    theme = detect_theme(source_text)
    frame = detect_frame(source_text, theme)
    hook = build_hook_sentence(source_text, actor, location, theme)
    frame_sentence = build_frame_sentence(source_text, frame)
    watch_sentence = build_watch_sentence(source_text, frame)

    comment = f"{hook} {frame_sentence} {watch_sentence}"

    if is_redundant_with_title(comment, title_it):
        comment = f"{frame_sentence} {watch_sentence}"

    return re.sub(r"\s+", " ", comment).strip()


def subtitle_from_article(url: str) -> str:
    try:
        html = fetch_text(url, timeout=ARTICLE_FETCH_TIMEOUT_SECONDS)
    except Exception:
        return ""

    html = re.sub(r"[\r\n\t]+", " ", html)
    meta_patterns = [
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for pattern in meta_patterns:
        meta_match = re.search(pattern, html, flags=re.IGNORECASE)
        if meta_match:
            subtitle = extract_subtitle(meta_match.group(1))
            if len(subtitle) >= 40 and not is_generic_subtitle(subtitle):
                return subtitle

    subtitle_patterns = [
        r'<p[^>]+class=["\'][^"\']*(?:subtitle|standfirst|deck|subheadline|headline__sub|article-subtitle|article__excerpt|entry-summary|post-excerpt|article__standfirst)[^"\']*["\'][^>]*>(.*?)</p>',
        r'<div[^>]+class=["\'][^"\']*(?:subtitle|standfirst|deck|subheadline|headline__sub|article-subtitle|article__excerpt|entry-summary|post-excerpt|article__standfirst)[^"\']*["\'][^>]*>(.*?)</div>',
        r'<h2[^>]+class=["\'][^"\']*(?:subtitle|standfirst|deck|subheadline|headline__sub|article-subtitle)[^"\']*["\'][^>]*>(.*?)</h2>',
    ]
    for pattern in subtitle_patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            subtitle = extract_subtitle(match.group(1))
            if len(subtitle) >= 40 and not is_generic_subtitle(subtitle):
                return subtitle

    body = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    body = re.sub(r"<style[\s\S]*?</style>", " ", body, flags=re.IGNORECASE)
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", body, flags=re.IGNORECASE | re.DOTALL)

    for para in paragraphs:
        subtitle = extract_subtitle(para)
        if len(subtitle) < 40:
            continue
        lowered = subtitle.lower()
        if any(skip in lowered for skip in ("cookie", "subscribe", "newsletter", "advertis", "consent")):
            continue
        if is_generic_subtitle(subtitle):
            continue
        return subtitle

    return ""


def translate_to_italian(text: str) -> str:
    if not text:
        return ""

    query = urllib.parse.quote(text)
    url = (
        "https://translate.googleapis.com/translate_a/single"
        f"?client=gtx&sl=auto&tl=it&dt=t&q={query}"
    )

    try:
        payload = fetch_text(url)
        data = json.loads(payload)
        if isinstance(data, list) and data and isinstance(data[0], list):
            translated = "".join(part[0] for part in data[0] if part and part[0]).strip()
            return repair_mojibake(translated)
    except Exception:
        return repair_mojibake(text)

    return repair_mojibake(text)


def parse_datetime(value: str) -> tuple[str, float]:
    if not value:
        now = datetime.now(timezone.utc)
        return now.isoformat(), now.timestamp()

    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat(), parsed.timestamp()
    except Exception:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.isoformat(), parsed.timestamp()
        except Exception:
            now = datetime.now(timezone.utc)
            return value, now.timestamp()


def item_matches_iran(title: str, description: str) -> bool:
    haystack = f"{title} {description}".lower()
    return any(term in haystack for term in IRAN_TERMS)


def parse_rss(xml_text: str, source_name: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    items: list[dict] = []

    for item in root.findall(".//item"):
        raw_title = strip_html(item.findtext("title", default=""))
        raw_description = item.findtext("description", default="") or ""
        description = strip_html(raw_description)
        link = strip_html(item.findtext("link", default=""))
        original_link = extract_original_url(raw_description, link)
        pub_date = item.findtext("pubDate", default="") or item.findtext("published", default="")
        title = cleanup_title(raw_title, source_name, original_link)

        if not title or not original_link:
            continue
        if not item_matches_iran(title, description):
            continue

        iso_time, sort_time = parse_datetime(pub_date)
        if iso_time[:10] < CRISIS_START_DAY:
            continue
        items.append(
            {
                "source": source_name,
                "title": title,
                "summary": summarize(description),
                "url": original_link,
                "time": iso_time,
                "sort_time": sort_time,
            }
        )

        if len(items) >= MAX_ITEMS_PER_SOURCE:
            break

    return items


def enrich_story(story: dict) -> dict:
    title_it = translate_to_italian(story["title"])
    summary_it = translate_to_italian(story["summary"])
    cleaned_title_it = cleanup_title(title_it or story["title"], story["source"], story["url"])
    story["title_it"] = cleaned_title_it
    story["summary_it"] = summary_it or story["summary"]
    subtitle = subtitle_from_article(story["url"])
    clean_summary = "" if is_generic_subtitle(story["summary"]) else story["summary"]
    chosen_subtitle = subtitle or clean_summary
    story["subtitle"] = "" if is_redundant_with_title(chosen_subtitle, story["title"]) else chosen_subtitle
    translated_subtitle = translate_to_italian(story["subtitle"]) if story["subtitle"] else ""
    story["subtitle_it"] = "" if is_redundant_with_title(translated_subtitle, cleaned_title_it) else translated_subtitle
    story["comment_it"] = build_commentary(story)
    return story


def fetch_source(source: Source) -> list[dict]:
    xml_text = fetch_text(build_feed_url(source))
    stories = parse_rss(xml_text, source.name)
    return [enrich_story(story) for story in stories]


def collect_stories() -> tuple[list[dict], list[str]]:
    stories: list[dict] = []
    errors: list[str] = []

    for source in SOURCES:
        try:
            source_stories = fetch_source(source)
            if source_stories:
                stories.extend(source_stories)
            else:
                errors.append(f"{source.name}: nessuna notizia rilevante trovata")
        except (urllib.error.URLError, ET.ParseError, TimeoutError, ValueError) as exc:
            errors.append(f"{source.name}: {exc}")

    stories.sort(key=lambda item: item["sort_time"], reverse=True)
    return stories, errors


def build_payload() -> dict:
    generated_at = datetime.now(timezone.utc).isoformat()
    stories, errors = collect_stories()
    for story in stories:
        story.pop("sort_time", None)
    return {
        "generated_at": generated_at,
        "story_count": len(stories),
        "coverage_start_day": CRISIS_START_DAY,
        "sources": [source.name for source in SOURCES],
        "errors": errors,
        "stories": stories,
    }


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Salvato {OUTPUT_FILE} con {payload['story_count']} notizie.")
    if payload["errors"]:
        print("Fonti con problemi:")
        for error in payload["errors"]:
            print(f"- {error}")


if __name__ == "__main__":
    main()
