const REFRESH_INTERVAL_MINUTES = 10;

const newsFeed = document.getElementById("news-feed");
const lastUpdated = document.getElementById("last-updated");
const storiesCount = document.getElementById("stories-count");
const nextRefresh = document.getElementById("next-refresh");
const manualRefresh = document.getElementById("manual-refresh");
const trackerCursor = document.getElementById("tracker-cursor");

const cursorState = {
  currentX: window.innerWidth / 2,
  currentY: window.innerHeight / 2,
  targetX: window.innerWidth / 2,
  targetY: window.innerHeight / 2
};

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
              ${story.title_it || story.title}
            </a>
            <p class="feed-note">${story.summary_it || story.summary || "Apri il link per leggere la notizia completa."}</p>
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
  lastUpdated.textContent = payload.generated_at ? formatDisplayTime(payload.generated_at) : "--";
  storiesCount.textContent = String((payload.stories || []).length);
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

function animateCursor() {
  cursorState.currentX += (cursorState.targetX - cursorState.currentX) * 0.38;
  cursorState.currentY += (cursorState.targetY - cursorState.currentY) * 0.38;
  trackerCursor.style.transform = `translate(${cursorState.currentX}px, ${cursorState.currentY}px)`;
  window.requestAnimationFrame(animateCursor);
}

manualRefresh.addEventListener("click", () => {
  loadStories();
});

window.addEventListener("mousemove", (event) => {
  cursorState.targetX = event.clientX;
  cursorState.targetY = event.clientY;
  trackerCursor.classList.add("is-visible");
});

window.addEventListener("mouseleave", () => {
  trackerCursor.classList.remove("is-visible");
});

loadStories();
animateCursor();
setInterval(updateCountdown, 60 * 1000);
setInterval(loadStories, REFRESH_INTERVAL_MINUTES * 60 * 1000);
