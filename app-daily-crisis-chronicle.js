const trackerCursor = document.getElementById("tracker-cursor");
const isTouchDevice = window.matchMedia("(hover: none), (pointer: coarse)").matches;

const timelineRoot = document.getElementById("daily-timeline");
const sectionsRoot = document.getElementById("daily-sections");
const evolutionRoot = document.getElementById("daily-evolution");
const periodNode = document.getElementById("daily-period");
const daysCountNode = document.getElementById("daily-days-count");
const storiesCountNode = document.getElementById("daily-stories-count");
const filterNoteNode = document.getElementById("daily-filter-note");
const CRISIS_START_DAY = "2026-02-28";

const cursorState = {
  currentX: window.innerWidth / 2,
  currentY: window.innerHeight / 2,
  targetX: window.innerWidth / 2,
  targetY: window.innerHeight / 2
};

const THEME_DEFS = [
  { id: "diplomacy", label: "negoziato e tregua", words: ["colloqui", "negozi", "negoziati", "ceasefire", "tregua", "mediazione", "ultimatum"] },
  { id: "maritime", label: "rotte e choke points", words: ["hormuz", "maritt", "tanker", "shipping", "strait", "cargo", "vessel", "naval"] },
  { id: "military", label: "pressione militare", words: ["bombard", "drone", "missil", "raid", "attacco", "strike", "threat", "minaccia", "deterr"] },
  { id: "energy", label: "energia e sanzioni", words: ["oil", "petrol", "energia", "export", "sanzion", "price", "scorte", "supply", "mercati"] },
  { id: "regional", label: "ordine regionale", words: ["gulf states", "golfo", "pakistan", "russia", "putin", "cina", "china", "europa", "europe", "japan", "giappone"] },
  { id: "humanitarian", label: "costi civili", words: ["civili", "morti", "feriti", "evacu", "sfoll", "osped", "devastation", "casualt"] }
];

const ACTOR_DEFS = [
  { label: "Stati Uniti", words: ["trump", "usa", "washington", "stati uniti", " us "] },
  { label: "Iran", words: ["iran", "teheran", "tehran"] },
  { label: "Israele", words: ["israele", "israel", "idf", "netanyahu"] },
  { label: "Pakistan", words: ["pakistan", "islamabad"] },
  { label: "Russia", words: ["russia", "mosca", "moscow", "putin"] },
  { label: "Cina", words: ["cina", "china", "pechino", "beijing"] },
  { label: "Stati del Golfo", words: ["gulf states", "stati del golfo", "gulf"] }
];

const MOJIBAKE_REPLACEMENTS = [
  ["ÃƒÂ¨", "è"],
  ["Ãƒ ", "à"],
  ["ÃƒÂ¹", "ù"],
  ["ÃƒÂ¬", "ì"],
  ["ÃƒÂ²", "ò"],
  ["ÃƒÂ©", "é"],
  ["Ã¨", "è"],
  ["Ã ", "à"],
  ["Ã¹", "ù"],
  ["Ã¬", "ì"],
  ["Ã²", "ò"],
  ["Ã©", "é"],
  ["Ã¢â‚¬â„¢", "'"],
  ["â€™", "'"],
  ["Ã¢â‚¬Ëœ", "'"],
  ["Ã¢â‚¬Å“", "\""],
  ["Ã¢â‚¬Â", "\""],
  ["â€œ", "\""],
  ["â€", "\""],
  ["Ã¢â‚¬â€œ", "-"],
  ["Ã¢â‚¬â€", "-"],
  ["â€“", "-"],
  ["â€”", "-"],
  ["Ã‚Â°", "°"],
  ["Ã‚Â«", "«"],
  ["Ã‚Â»", "»"],
  ["Â·", "·"],
  ["â†’", "→"],
  ["Â", ""]
];

function fixMojibake(text = "") {
  let value = text || "";
  MOJIBAKE_REPLACEMENTS.forEach(([bad, good]) => {
    value = value.replaceAll(bad, good);
  });
  return value;
}

function cleanTitleForDisplay(title = "", source = "", url = "") {
  const separators = [" - ", " | ", " – ", " — "];
  const sourceLower = (source || "").toLowerCase();
  let host = "";

  try {
    host = new URL(url).hostname.replace(/^www\./, "").toLowerCase();
  } catch {
    host = "";
  }

  for (const separator of separators) {
    if (!title.includes(separator)) {
      continue;
    }
    const parts = title.split(separator);
    const tail = (parts[parts.length - 1] || "").trim().toLowerCase();
    if (!tail) {
      continue;
    }
    if (tail.includes(".") || tail.includes(sourceLower) || (host && tail.includes(host))) {
      return parts.slice(0, -1).join(separator).trim();
    }
  }

  return title.trim();
}

function normalizeText(story) {
  return fixMojibake(
    `${story.title_it || story.title || ""} ${story.summary_it || story.summary || ""} ${story.comment_it || ""}`.toLowerCase()
  );
}

function parseStoryDate(story) {
  const date = new Date(story.time);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDayLabel(dayKey) {
  const date = new Date(`${dayKey}T12:00:00`);
  return new Intl.DateTimeFormat("it-IT", {
    weekday: "long",
    day: "numeric",
    month: "long"
  }).format(date);
}

function formatShortDay(dayKey) {
  const date = new Date(`${dayKey}T12:00:00`);
  return new Intl.DateTimeFormat("it-IT", {
    day: "2-digit",
    month: "2-digit"
  }).format(date);
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "--";
  }
  return new Intl.DateTimeFormat("it-IT", {
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function normalizeStories(stories) {
  const withDates = stories
    .map((story) => ({ ...story, _date: parseStoryDate(story) }))
    .filter((story) => story._date && story.time.slice(0, 10) >= CRISIS_START_DAY);

  withDates.sort((a, b) => b._date - a._date);
  return { activeStories: withDates, archiveCount: 0 };
}

function countMatches(text, defs) {
  const counts = new Map();
  defs.forEach((def) => {
    const hits = def.words.reduce((total, word) => total + (text.includes(word) ? 1 : 0), 0);
    if (hits > 0) {
      counts.set(def.id || def.label, hits);
    }
  });
  return counts;
}

function getThemeMetaById(id) {
  return THEME_DEFS.find((theme) => theme.id === id) || { id, label: id };
}

function buildThemeCounts(stories) {
  const counts = new Map();
  stories.forEach((story) => {
    const matches = countMatches(normalizeText(story), THEME_DEFS);
    matches.forEach((value, key) => {
      counts.set(key, (counts.get(key) || 0) + value);
    });
  });

  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([id, count]) => ({ ...getThemeMetaById(id), count }));
}

function buildActorCounts(stories) {
  const counts = new Map();
  stories.forEach((story) => {
    const text = normalizeText(story);
    ACTOR_DEFS.forEach((actor) => {
      const hits = actor.words.reduce((total, word) => total + (text.includes(word) ? 1 : 0), 0);
      if (hits > 0) {
        counts.set(actor.label, (counts.get(actor.label) || 0) + hits);
      }
    });
  });

  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([label, count]) => ({ label, count }));
}

function buildFallbackNarrative(group, previousGroup, olderGroups) {
  const themes = buildThemeCounts(group.stories);
  const actors = buildActorCounts(group.stories);
  const dominant = themes[0]?.label || "riallineamento regionale";
  const olderThemeCounts = buildThemeCounts(olderGroups.flatMap((day) => day.stories));
  const persistentTheme = olderThemeCounts[0]?.label || dominant;
  const topActors = actors.slice(0, 3).map((actor) => actor.label);

  const overview = `La giornata del ${formatDayLabel(group.key)} ruota soprattutto attorno a ${dominant}, con un peso visibile di ${topActors.join(", ") || "attori distribuiti"}.`;
  const strategicReading = "La lettura più utile è osservare come segnali militari, diplomatici ed economici cambino insieme il ritmo della crisi.";
  const trajectory = previousGroup
    ? `Rispetto al ${formatDayLabel(previousGroup.key)}, questa giornata resta dentro lo stesso ciclo ma ne riorganizza le priorità operative e politiche.`
    : "Essendo il primo blocco della serie recente, questa giornata funziona come base iniziale del quadro evolutivo.";
  const watchpoint = "Conviene monitorare se i segnali del giorno vengono assorbiti oppure si sommano fino a cambiare la fase della crisi.";

  return {
    themes: themes.map((theme) => theme.label),
    actors: topActors,
    dominantTheme: dominant,
    manualLens: dominant,
    status: "final",
    statusNote: "Brief chiuso: questo blocco non si aggiorna più e resta come archivio stabile della sequenza.",
    finalizationNote: "Giornata già consolidata dopo la chiusura notturna del ciclo di aggiornamento.",
    overview,
    storyline: "Le notizie del giorno restano abbastanza compatte e convergono sullo stesso nucleo operativo della crisi.",
    sourceAngle: "Le fonti tendono a descrivere la stessa sequenza con enfasi diverse, ma senza divergenze sostanziali sul quadro generale.",
    strategicReading,
    trajectory,
    watchpoint,
    persistentTheme
  };
}

function buildBriefMap(briefs) {
  const map = new Map();
  briefs.forEach((brief) => {
    map.set(brief.day, brief);
  });
  return map;
}

function formatList(items = []) {
  const clean = items.map((item) => fixMojibake(String(item || "")).trim()).filter(Boolean);
  if (!clean.length) {
    return "quadro diffuso";
  }
  if (clean.length === 1) {
    return clean[0];
  }
  if (clean.length === 2) {
    return `${clean[0]} e ${clean[1]}`;
  }
  return `${clean.slice(0, -1).join(", ")} e ${clean[clean.length - 1]}`;
}

function getDayAnalysis(group, index, groups, briefMap) {
  const brief = briefMap.get(group.key);
  if (brief) {
    return {
      themes: brief.themes_in_focus || [],
      actors: brief.actors_in_focus || [],
      dominantTheme: fixMojibake(brief.dominant_theme_label || brief.manual_lens || brief.dominant_frame || "quadro misto"),
      manualLens: fixMojibake(brief.manual_lens || brief.dominant_theme_label || "lettura strategica"),
      status: fixMojibake(brief.status || "final"),
      statusNote: fixMojibake(brief.status_note || ""),
      finalizationNote: fixMojibake(brief.finalization_note || ""),
      overview: fixMojibake(brief.analytical_summary?.overview || ""),
      storyline: fixMojibake(brief.analytical_summary?.storyline || ""),
      sourceAngle: fixMojibake(brief.analytical_summary?.source_angle || ""),
      implication: fixMojibake(brief.analytical_summary?.implication || ""),
      strategicReading: fixMojibake(brief.analytical_summary?.strategic_reading || ""),
      trajectory: fixMojibake(brief.analytical_summary?.trajectory || ""),
      watchpoint: fixMojibake(brief.analytical_summary?.watchpoint || ""),
      continuityMarkers: (brief.continuity_markers || []).map((item) => fixMojibake(item)),
      discontinuityMarkers: (brief.discontinuity_markers || []).map((item) => fixMojibake(item)),
      retrievedTitles: (brief.retrieved_context_titles || []).map((item) => fixMojibake(item)),
      keyStories: (brief.key_stories || []).map((story) => ({
        time: fixMojibake(story.time || "--:--"),
        source: fixMojibake(story.source || ""),
        title: fixMojibake(story.title || ""),
        summary: fixMojibake(story.summary || "")
      }))
    };
  }

  return buildFallbackNarrative(group, groups[index + 1] || null, groups.slice(index + 1));
}

function buildEvolution(groups, briefMap, archiveCount) {
  const recentBriefs = groups
    .slice(0, 4)
    .map((group) => briefMap.get(group.key))
    .filter(Boolean);

  if (recentBriefs.length) {
    const themeCounter = new Map();
    const actorCounter = new Map();
    const lensCounter = new Map();

    recentBriefs.forEach((brief) => {
      (brief.themes_in_focus || []).forEach((theme) => {
        themeCounter.set(theme, (themeCounter.get(theme) || 0) + 1);
      });
      (brief.actors_in_focus || []).forEach((actor) => {
        actorCounter.set(actor, (actorCounter.get(actor) || 0) + 1);
      });
      const lens = fixMojibake(brief.manual_lens || brief.dominant_theme_label || brief.dominant_frame || "");
      if (lens) {
        lensCounter.set(lens, (lensCounter.get(lens) || 0) + 1);
      }
    });

    const topThemes = [...themeCounter.entries()].sort((a, b) => b[1] - a[1]).map(([value]) => value).slice(0, 4);
    const topActors = [...actorCounter.entries()].sort((a, b) => b[1] - a[1]).map(([value]) => value).slice(0, 4);
    const topLenses = [...lensCounter.entries()].sort((a, b) => b[1] - a[1]).map(([value]) => value).slice(0, 3);
    const phase = fixMojibake(recentBriefs[0].analytical_summary?.strategic_reading || "Il quadro recente resta fluido.");
    const trajectory = fixMojibake(recentBriefs[0].analytical_summary?.trajectory || "");
    const watch = fixMojibake(recentBriefs[0].analytical_summary?.watchpoint || "");
    const turningPoints = groups
      .slice(0, 4)
      .map((group) => {
        const brief = briefMap.get(group.key);
        const label = fixMojibake(brief?.dominant_theme_label || "quadro misto");
        return `${formatShortDay(group.key)}: ${label}`;
      })
      .join(" · ");

    const items = [
      { label: "Fase corrente", value: phase },
      { label: "Traiettoria", value: trajectory || "La traiettoria resta aperta e va letta giorno per giorno." },
      { label: "Lenti prevalenti", value: formatList(topLenses) },
      { label: "Temi persistenti", value: formatList(topThemes) },
      { label: "Attori ricorrenti", value: formatList(topActors) },
      { label: "Snodi recenti", value: turningPoints || "sequenza in costruzione" },
      { label: "Da monitorare", value: watch || "Segnali operativi, diplomatici ed economici dei prossimi aggiornamenti." }
    ];

    if (archiveCount > 0) {
      items.push({
        label: "Archivio escluso",
        value: `${archiveCount} articoli fuori finestra recente, lasciati fuori per non falsare l'andamento giornaliero.`
      });
    }

    return items;
  }

  const allStories = groups.flatMap((group) => group.stories);
  const themes = buildThemeCounts(allStories);
  const actors = buildActorCounts(allStories);
  return [
    { label: "Fase corrente", value: "Il quadro recente resta fluido." },
    { label: "Temi persistenti", value: themes.slice(0, 4).map((theme) => theme.label).join(", ") || "nessuno" },
    { label: "Attori ricorrenti", value: actors.slice(0, 4).map((actor) => actor.label).join(", ") || "diffusi" }
  ];
}

function renderMeta(groups, totalStories) {
  daysCountNode.textContent = String(groups.length);
  storiesCountNode.textContent = String(totalStories);

  if (groups.length) {
    periodNode.textContent = `${formatShortDay(groups[groups.length - 1].key)} → ${formatShortDay(groups[0].key)}`;
  } else {
    periodNode.textContent = "--";
  }
}

function renderTimeline(groups, briefMap) {
  timelineRoot.innerHTML = groups
    .map((group, index) => {
      const analysis = getDayAnalysis(group, index, groups, briefMap);
      return `
        <a class="timeline-link" href="#day-${group.key}">
          <span class="timeline-date">${formatShortDay(group.key)}</span>
          <span class="timeline-meta">${group.stories.length} notizie · ${analysis.dominantTheme}</span>
        </a>
      `;
    })
    .join("");
}

function renderEvolution(groups, briefMap, archiveCount) {
  const cards = buildEvolution(groups, briefMap, archiveCount)
    .map(
      (item) => `
        <article class="daily-evolution-card">
          <p class="daily-evolution-title">${item.label}</p>
          <p class="daily-evolution-copy">${item.value}</p>
        </article>
      `
    )
    .join("");

  evolutionRoot.innerHTML = cards;
}

function renderDaySections(groups, briefMap) {
  sectionsRoot.innerHTML = groups
    .map((group, index) => {
      const analysis = getDayAnalysis(group, index, groups, briefMap);
      const themeBadges = (analysis.themes || [])
        .slice(0, 4)
        .map((theme) => `<span class="theme-badge">${fixMojibake(theme)}</span>`)
        .join("");

      const continuityText = analysis.continuityMarkers?.length ? formatList(analysis.continuityMarkers) : "sequenza ancora in consolidamento";
      const discontinuityText = analysis.discontinuityMarkers?.length ? formatList(analysis.discontinuityMarkers) : "nessuna rottura netta";
      const topActors = analysis.actors?.length ? formatList(analysis.actors.slice(0, 3)) : "quadro diffuso";
      const statusLabel = analysis.status === "live"
        ? "Brief in aggiornamento"
        : analysis.status === "latest_closed"
          ? "Ultimo giorno chiuso"
          : "Brief chiuso";
      const keyStoryCards = (analysis.keyStories || [])
        .slice(0, 3)
        .map((story) => `
          <div class="day-key-story">
            <span class="day-key-story-time">${story.time}</span>
            <div>
              <p class="day-key-story-source">${story.source}</p>
              <p class="day-key-story-title">${story.title}</p>
            </div>
          </div>
        `)
        .join("");

      const stories = group.stories
        .map((story) => {
          const title = cleanTitleForDisplay(fixMojibake(story.title_it || story.title || ""), story.source || "", story.url || "");
          const comment = fixMojibake(story.comment_it || story.summary_it || story.summary || "");
          return `
            <article class="day-story-card">
              <div class="day-story-time">${formatTime(story.time)}</div>
              <div>
                <p class="day-story-source">${fixMojibake(story.source || "")}</p>
                <h3 class="day-story-title"><a href="${story.url}" target="_blank" rel="noreferrer">${title}</a></h3>
                <p class="day-story-comment">${comment}</p>
              </div>
            </article>
          `;
        })
        .join("");

      return `
        <section id="day-${group.key}" class="day-section">
          <header class="day-header">
            <div>
              <p class="section-label">Dossier del giorno</p>
              <h2 class="day-date">${formatDayLabel(group.key)}</h2>
              <p class="day-count">${group.stories.length} notizie raccolte</p>
            </div>
            <div class="day-header-side">
              <span class="day-status day-status-${analysis.status}">${statusLabel}</span>
              <div class="day-theme-badges">${themeBadges}</div>
            </div>
          </header>

          <article class="day-cycle-card">
            <p class="day-meta-title">Ciclo del dossier</p>
            <p class="day-summary-copy">${analysis.statusNote}</p>
            <p class="day-summary-copy">${analysis.finalizationNote}</p>
          </article>

          <div class="day-summary-grid">
            <article class="day-summary-card">
              <p class="day-summary-title">Sintesi del giorno</p>
              <p class="day-summary-copy">${analysis.overview}</p>
              <p class="day-summary-copy">${analysis.storyline || ""}</p>
              <p class="day-summary-copy">${analysis.sourceAngle || ""}</p>
              <p class="day-summary-copy">${analysis.implication || ""}</p>
              <p class="day-summary-copy">${analysis.strategicReading}</p>
              <p class="day-summary-copy">${analysis.trajectory}</p>
              <p class="day-summary-copy">${analysis.watchpoint}</p>
            </article>

            <article class="day-meta-card">
              <p class="day-meta-title">Lettura evolutiva</p>
              <div class="day-meta-list">
                <div class="day-meta-row">
                  <span class="day-meta-label">Tema dominante</span>
                  <span class="day-meta-value">${analysis.dominantTheme}</span>
                </div>
                <div class="day-meta-row">
                  <span class="day-meta-label">Attori in evidenza</span>
                  <span class="day-meta-value">${topActors}</span>
                </div>
                <div class="day-meta-row">
                  <span class="day-meta-label">Lente analitica</span>
                  <span class="day-meta-value">${analysis.manualLens}</span>
                </div>
                <div class="day-meta-row">
                  <span class="day-meta-label">Continuità</span>
                  <span class="day-meta-value">${continuityText}</span>
                </div>
                <div class="day-meta-row">
                  <span class="day-meta-label">Discontinuità</span>
                  <span class="day-meta-value">${discontinuityText}</span>
                </div>
              </div>
            </article>
          </div>

          ${keyStoryCards ? `
            <article class="day-key-stories-card">
              <p class="day-meta-title">Snodi puntuali della giornata</p>
              <div class="day-key-stories-list">${keyStoryCards}</div>
            </article>
          ` : ""}

          <div class="day-stories">${stories}</div>
        </section>
      `;
    })
    .join("");
}

function renderEmptyState() {
  sectionsRoot.innerHTML = `
    <div class="daily-empty">
      Nessun dato disponibile per costruire il dossier giornaliero della crisi.
    </div>
  `;
}

async function loadDailyChronicle() {
  try {
    const [newsResponse, briefsResponse] = await Promise.all([
      fetch(`data/news.json?v=${Date.now()}`, { cache: "no-store" }),
      fetch(`data/daily-v2/briefs.json?v=${Date.now()}`, { cache: "no-store" })
    ]);

    if (!newsResponse.ok) {
      throw new Error(`HTTP ${newsResponse.status}`);
    }

    const payload = await newsResponse.json();
    const briefsPayload = briefsResponse.ok ? await briefsResponse.json() : { briefs: [] };
    const briefMap = buildBriefMap(briefsPayload.briefs || []);
    const { activeStories, archiveCount } = normalizeStories(payload.stories || []);

    if (!activeStories.length) {
      renderEmptyState();
      return;
    }

    const groupsMap = new Map();
    activeStories.forEach((story) => {
      const key = story.time.slice(0, 10);
      if (!groupsMap.has(key)) {
        groupsMap.set(key, []);
      }
      groupsMap.get(key).push(story);
    });

    const groups = [...groupsMap.entries()]
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([key, stories]) => ({ key, stories }));

    renderMeta(groups, activeStories.length);
    if (briefMap.size && briefsPayload.refresh_interval_minutes && briefsPayload.daily_close_time_local) {
      const coverageStart = briefsPayload.coverage_start_day ? briefsPayload.coverage_start_day.split("-").reverse().join("/") : "28/02/2026";
      filterNoteNode.textContent = `${coverageStart} / ${briefsPayload.refresh_interval_minutes} min / close ${briefsPayload.daily_close_time_local}`;
    } else {
      filterNoteNode.textContent = "dal 28/02/2026";
    }
    renderTimeline(groups, briefMap);
    renderEvolution(groups, briefMap, archiveCount);
    renderDaySections(groups, briefMap);
  } catch {
    renderEmptyState();
  }
}

function animateCursor() {
  if (!trackerCursor) {
    return;
  }

  cursorState.currentX += (cursorState.targetX - cursorState.currentX) * 0.38;
  cursorState.currentY += (cursorState.targetY - cursorState.currentY) * 0.38;
  trackerCursor.style.transform = `translate(${cursorState.currentX}px, ${cursorState.currentY}px)`;
  window.requestAnimationFrame(animateCursor);
}

if (!isTouchDevice && trackerCursor) {
  window.addEventListener("mousemove", (event) => {
    cursorState.targetX = event.clientX;
    cursorState.targetY = event.clientY;
    trackerCursor.classList.add("is-visible");
  });

  window.addEventListener("mouseleave", () => {
    trackerCursor.classList.remove("is-visible");
  });

  animateCursor();
}

loadDailyChronicle();
