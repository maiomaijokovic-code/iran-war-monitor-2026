const REFRESH_INTERVAL_MINUTES = 10;

const newsFeed = document.getElementById("news-feed");
const lastUpdated = document.getElementById("last-updated");
const storiesCount = document.getElementById("stories-count");
const nextRefresh = document.getElementById("next-refresh");
const cycleMinutes = document.getElementById("cycle-minutes");
const manualRefresh = document.getElementById("manual-refresh");
const refreshStatus = document.getElementById("refresh-status");
const trackerCursor = document.getElementById("tracker-cursor");
const isTouchDevice = window.matchMedia("(hover: none), (pointer: coarse)").matches;
const GITHUB_OWNER = "maiomaijokovic-code";
const GITHUB_REPO = "iran-war-monitor-2026";
const GITHUB_WORKFLOW_FILE = "deploy-pages.yml";
const GITHUB_REF = "main";
const TOKEN_STORAGE_KEY = "iwm_github_actions_token";

const cursorState = {
  currentX: window.innerWidth / 2,
  currentY: window.innerHeight / 2,
  targetX: window.innerWidth / 2,
  targetY: window.innerHeight / 2
};

let latestGeneratedAt = null;

function formatDisplayTime(value) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value || "--";
  }

  return new Intl.DateTimeFormat("it-IT", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function cleanTitleForDisplay(title = "", source = "", url = "") {
  const separators = [" - ", " – ", " — ", " | "];
  const sourceLower = source.toLowerCase();
  let host = "";

  try {
    host = new URL(url).hostname.replace(/^www\./, "").toLowerCase();
  } catch (error) {
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
    if (tail.includes(".") || (sourceLower && tail.includes(sourceLower)) || (host && tail.includes(host))) {
      return parts.slice(0, -1).join(separator).trim();
    }
  }

  return title.trim();
}

function fallbackCommentary(story) {
  const text = `${story.title_it || story.title || ""} ${story.summary_it || story.summary || ""}`.toLowerCase();

  if (text.includes("hormuz") || text.includes("maritt") || text.includes("tanker")) {
    return "Il nodo principale è marittimo. Se il rischio su rotte e transiti cresce, può aumentare rapidamente la pressione regionale.";
  }
  if (text.includes("colloqui") || text.includes("negoz") || text.includes("accord")) {
    return "Emerge una finestra diplomatica, ma resta fragile. Il punto chiave è capire se alle parole seguono segnali operativi coerenti.";
  }
  if (text.includes("attacco") || text.includes("missil") || text.includes("drone") || text.includes("bombard")) {
    return "Indicazione di escalation tattica. Va monitorata la probabilità di risposta a catena nelle prossime 24-48 ore.";
  }
  return "Il quadro resta instabile e ad alta volatilità. Conta soprattutto la continuità degli eventi nel brevissimo periodo.";
}

function renderStories(stories) {
  if (!stories.length) {
    newsFeed.innerHTML = `
      <div class="feed-empty">
        Nessuna notizia disponibile nel file dati locale. Esegui lo script di aggiornamento.
      </div>
    `;
    return;
  }

  newsFeed.innerHTML = stories
    .map(
      (story, index) => `
        <article class="feed-item">
          <div class="feed-index">${String(index + 1).padStart(2, "0")}</div>
          <div class="feed-time">${formatDisplayTime(story.time)}</div>
          <div class="feed-body">
            <p class="feed-source">${story.source}</p>
            <a class="feed-link" href="${story.url}" target="_blank" rel="noreferrer">
              ${cleanTitleForDisplay(story.title_it || story.title || "", story.source || "", story.url || "")}
            </a>
            <p class="feed-note">${story.comment_it || fallbackCommentary(story)}</p>
          </div>
        </article>
      `
    )
    .join("");
}

function renderLoadingState() {
  newsFeed.innerHTML = `
    <div class="feed-loading">
      Caricamento stream locale in corso.
    </div>
  `;
}

function renderErrorState() {
  newsFeed.innerHTML = `
    <div class="feed-error">
      Impossibile leggere il file dati locale. Avvia prima il generatore delle notizie.
    </div>
  `;
}

function updateCountdown() {
  const now = new Date();
  const minutes = now.getMinutes();
  const remainder = minutes % REFRESH_INTERVAL_MINUTES;
  const minutesUntilRefresh = remainder === 0 ? REFRESH_INTERVAL_MINUTES : REFRESH_INTERVAL_MINUTES - remainder;
  nextRefresh.textContent = `tra ${minutesUntilRefresh} minuti`;
}

function updateMeta(payload) {
  latestGeneratedAt = payload.generated_at || null;
  lastUpdated.textContent = payload.generated_at ? formatDisplayTime(payload.generated_at) : "--";
  storiesCount.textContent = String((payload.stories || []).length);
  if (cycleMinutes) {
    cycleMinutes.textContent = `${REFRESH_INTERVAL_MINUTES} min`;
  }
  updateCountdown();
}

async function loadStories() {
  renderLoadingState();

  if (window.OFFLINE_NEWS_PAYLOAD) {
    renderStories(window.OFFLINE_NEWS_PAYLOAD.stories || []);
    updateMeta(window.OFFLINE_NEWS_PAYLOAD);
    return;
  }

  try {
    const response = await fetch(`data/news.json?v=${Date.now()}`, { cache: "no-store" });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    renderStories(payload.stories || []);
    updateMeta(payload);
  } catch (error) {
    renderErrorState();
    updateMeta({ stories: [], generated_at: null });
  }
}

function setRefreshStatus(message) {
  if (!refreshStatus) {
    return;
  }

  refreshStatus.textContent = message || "";
}

function getActionsToken() {
  return window.localStorage.getItem(TOKEN_STORAGE_KEY) || "";
}

function askAndStoreToken() {
  const token = window.prompt(
    "Inserisci un GitHub token (scope Actions write) per avviare subito l'aggiornamento. Lascia vuoto per solo refresh locale.",
    getActionsToken()
  );

  if (!token) {
    return "";
  }

  const cleanToken = token.trim();
  if (!cleanToken) {
    return "";
  }

  window.localStorage.setItem(TOKEN_STORAGE_KEY, cleanToken);
  return cleanToken;
}

async function triggerRemoteUpdate(token) {
  if (!token) {
    return false;
  }

  const endpoint = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${GITHUB_WORKFLOW_FILE}/dispatches`;
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ ref: GITHUB_REF })
  });

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }

    throw new Error(`Dispatch failed (${response.status})`);
  }

  return true;
}

async function pollForNewPublication(previousGeneratedAt, attempts = 18) {
  for (let i = 0; i < attempts; i += 1) {
    await new Promise((resolve) => setTimeout(resolve, 10000));
    await loadStories();

    if (latestGeneratedAt && latestGeneratedAt !== previousGeneratedAt) {
      return true;
    }
  }

  return false;
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

manualRefresh.addEventListener("click", async () => {
  const previousGeneratedAt = latestGeneratedAt;
  const tokenFromClick = getActionsToken() || askAndStoreToken();
  manualRefresh.disabled = true;

  try {
    setRefreshStatus("Aggiornamento locale in corso...");
    await loadStories();

    const workflowTriggered = await triggerRemoteUpdate(tokenFromClick).catch(() => false);
    if (!workflowTriggered) {
      setRefreshStatus("Refresh locale completato. Per aggiornare prima dei 10 minuti, inserisci un token GitHub Actions.");
      return;
    }

    setRefreshStatus("Workflow avviato. Attendo nuove notizie (circa 1-3 minuti)...");
    const hasNewPublication = await pollForNewPublication(previousGeneratedAt);

    if (hasNewPublication) {
      setRefreshStatus("Nuove notizie pubblicate e caricate.");
      return;
    }

    setRefreshStatus("Workflow avviato, ma il nuovo pacchetto non è ancora online. Riprova tra poco.");
  } catch (error) {
    setRefreshStatus("Errore durante l'aggiornamento immediato. Verifica token GitHub o riprova.");
  } finally {
    manualRefresh.disabled = false;
  }
});

if (!isTouchDevice && trackerCursor) {
  window.addEventListener("mousemove", (event) => {
    cursorState.targetX = event.clientX;
    cursorState.targetY = event.clientY;
    trackerCursor.classList.add("is-visible");
  });

  window.addEventListener("mouseleave", () => {
    trackerCursor.classList.remove("is-visible");
  });
}

loadStories();
if (!isTouchDevice) {
  animateCursor();
}
setInterval(updateCountdown, 60 * 1000);
setInterval(loadStories, REFRESH_INTERVAL_MINUTES * 60 * 1000);
