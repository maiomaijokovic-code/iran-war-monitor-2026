from __future__ import annotations

import json
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
    Source("Washington Post", "google_news", "site:washingtonpost.com Iran"),
    Source("The Guardian", "google_news", "site:theguardian.com Iran"),
    Source("BBC", "google_news", "site:bbc.com Iran"),
    Source("Sky News", "google_news", "site:news.sky.com Iran"),
    Source("CNN", "google_news", "site:cnn.com Iran"),
    Source("New York Times", "google_news", "site:nytimes.com Iran"),
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
]


def build_feed_url(source: Source) -> str:
    if source.kind == "rss":
        return source.value

    encoded_query = urllib.parse.quote(f"{source.value} when:14d")
    return f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def summarize(value: str) -> str:
    clean = strip_html(value)
    if not clean:
        return "Apri il link per leggere la notizia completa sulla fonte originale."
    if len(clean) <= MAX_SUMMARY_LENGTH:
        return clean
    return f"{clean[:MAX_SUMMARY_LENGTH].rstrip()}..."


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


def infer_commentary(summary_it: str, title_it: str) -> str:
    text = f"{title_it} {summary_it}".lower()

    if any(word in text for word in ("colloqui", "negozi", "accord", "ceasefire", "sospendere", "tregua")):
        return (
            "Il segnale è soprattutto diplomatico. Se il canale negoziale regge, "
            "la pressione militare può rallentare nel breve, ma resta alta la volatilità politica."
        )
    if any(word in text for word in ("hormuz", "nave", "tanker", "maritt", "stretto", "ais")):
        return (
            "Il focus è marittimo-operativo. Ogni frizione su Hormuz o sulle rotte "
            "commerciali può produrre effetti rapidi su sicurezza regionale e costi energetici."
        )
    if any(word in text for word in ("missil", "drone", "bombard", "raid", "attacco", "strike")):
        return (
            "Il contenuto indica una dinamica di escalation tattica. "
            "Nel breve conta capire se l'evento resta isolato o apre una sequenza di ritorsioni."
        )
    if any(word in text for word in ("civili", "osped", "evacu", "sfoll", "morti", "feriti")):
        return (
            "Il punto centrale è il rischio civile. Se questi segnali aumentano, "
            "cresce anche la probabilità di pressione diplomatica e narrativa internazionale."
        )
    if any(word in text for word in ("sanzion", "tariff", "petrol", "export", "energia", "prezzo")):
        return (
            "La notizia suggerisce un canale di pressione economica oltre a quello militare. "
            "Da monitorare gli effetti su energia, rotte commerciali e tenuta politica regionale."
        )
    return (
        "Il dato rafforza un quadro ancora instabile, con segnali misti tra deterrenza e negoziazione. "
        "La variabile chiave resta la continuità degli eventi nelle prossime 24-48 ore."
    )


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
            return "".join(part[0] for part in data[0] if part and part[0]).strip()
    except Exception:
        return text

    return text


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
        description = strip_html(item.findtext("description", default=""))
        link = strip_html(item.findtext("link", default=""))
        pub_date = item.findtext("pubDate", default="") or item.findtext("published", default="")
        title = cleanup_title(raw_title, source_name, link)

        if not title or not link:
            continue
        if not item_matches_iran(title, description):
            continue

        iso_time, sort_time = parse_datetime(pub_date)
        items.append(
            {
                "source": source_name,
                "title": title,
                "summary": summarize(description),
                "url": link,
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
    story["comment_it"] = infer_commentary(story["summary_it"], story["title_it"])
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
