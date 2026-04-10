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
            if len(subtitle) >= 40:
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
            if len(subtitle) >= 40:
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
    story["subtitle"] = subtitle or story["summary"]
    story["subtitle_it"] = translate_to_italian(story["subtitle"]) if story["subtitle"] else story["summary_it"]
    story["comment_it"] = story["subtitle_it"]
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
