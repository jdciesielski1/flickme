/* ── State ── */
const state = {
  movies:    [],
  actors:    [],
  directors: [],
  genres:    [],
};

const GENRES = [
  "Action","Adventure","Animation","Comedy","Crime",
  "Documentary","Drama","Fantasy","History","Horror",
  "Mystery","Romance","Science Fiction","Thriller","War","Western"
];

/* ── DOM refs ── */
const form             = document.getElementById("pref-form");
const submitBtn        = document.getElementById("submit-btn");
const clearBtn         = document.getElementById("clear-btn");
const loadingState     = document.getElementById("loading-state");
const errorState       = document.getElementById("error-state");
const errorMsg         = document.getElementById("error-message");
const resultsSection   = document.getElementById("results-section");
const resultsMeta      = document.getElementById("results-meta");
const cardsGrid        = document.getElementById("cards-grid");
const unresolvedWarn   = document.getElementById("unresolved-warning");
const unresolvedTxt    = document.getElementById("unresolved-text");
const genreGrid        = document.getElementById("genre-grid");
const hardFilterToggle = document.getElementById("hard-filter-toggle");

/* ── Autocomplete ── */
function debounce(fn, ms) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

function setupAutocomplete({ inputId, dropdownId, stateKey, max, endpoint, renderItem, getLabel }) {
  const input    = document.getElementById(inputId);
  const dropdown = document.getElementById(dropdownId);
  let focusedIdx  = -1;
  let lastResults = [];

  function closeDropdown() {
    dropdown.hidden = true;
    focusedIdx  = -1;
    lastResults = [];
  }

  function setFocused(idx) {
    const items = dropdown.querySelectorAll(".ac-item");
    items.forEach(el => el.classList.remove("focused"));
    if (idx >= 0 && idx < items.length) {
      items[idx].classList.add("focused");
      focusedIdx = idx;
    }
  }

  function selectItem(label) {
    if (!label.trim()) return;
    if (state[stateKey].length >= max) { closeDropdown(); return; }
    if (state[stateKey].includes(label)) { closeDropdown(); return; }
    state[stateKey].push(label);
    const tagsDisplay = document.getElementById(stateKey + "-tags");
    addTag(tagsDisplay, label, stateKey);
    input.value = "";
    closeDropdown();
  }

  const fetchSuggestions = debounce(async (query) => {
    if (query.length < 2) { closeDropdown(); return; }
    if (state[stateKey].length >= max) { closeDropdown(); return; }
    try {
      const resp = await fetch("/api/autocomplete/" + endpoint + "?q=" + encodeURIComponent(query));
      const data = await resp.json();
      lastResults = data.results || [];
      if (!lastResults.length) { closeDropdown(); return; }

      dropdown.innerHTML = "";
      focusedIdx = -1;
      lastResults.forEach((item) => {
        const el = document.createElement("div");
        el.className = "ac-item";
        el.innerHTML = renderItem(item);
        el.addEventListener("mousedown", (e) => {
          e.preventDefault();
          selectItem(getLabel(item));
        });
        dropdown.appendChild(el);
      });
      dropdown.hidden = false;
    } catch (e) {
      closeDropdown();
    }
  }, 200);

  input.addEventListener("input", () => fetchSuggestions(input.value.trim()));

  input.addEventListener("keydown", (e) => {
    const items = dropdown.querySelectorAll(".ac-item");

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocused(Math.min(focusedIdx + 1, items.length - 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocused(Math.max(focusedIdx - 1, 0));
      return;
    }
    if (e.key === "Escape") { closeDropdown(); return; }

    if ((e.key === "Enter" || e.key === "Tab") && focusedIdx >= 0 && lastResults[focusedIdx]) {
      e.preventDefault();
      selectItem(getLabel(lastResults[focusedIdx]));
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      const value = input.value.trim();
      if (!value) return;
      selectItem(value);
      return;
    }
    if (e.key === "Backspace" && input.value === "" && state[stateKey].length > 0) {
      const tagsDisplay = document.getElementById(stateKey + "-tags");
      state[stateKey].pop();
      tagsDisplay.removeChild(tagsDisplay.lastChild);
    }
  });

  input.addEventListener("blur", () => setTimeout(closeDropdown, 150));
}

/* ── Autocomplete renderers ── */
function movieItem(m) {
  const poster = m.poster_url
    ? '<img class="ac-poster" src="' + m.poster_url + '" alt="" loading="lazy">'
    : '<div class="ac-poster-placeholder">&#127916;</div>';
  const year = m.year ? " · " + m.year : "";
  return poster + '<div class="ac-info"><div class="ac-name">' + m.title + '</div><div class="ac-meta">' + year + '</div></div>';
}

function personItem(p) {
  const role  = p.role  || "";
  const known = p.known_for ? " · " + p.known_for : "";
  return '<div class="ac-poster-placeholder">&#128100;</div>'
    + '<div class="ac-info">'
    + '<div class="ac-name">' + p.name + '</div>'
    + '<div class="ac-meta">' + role + known + '</div>'
    + '</div>';
}

/* ── Tag system ── */
function addTag(container, value, stateKey) {
  const tag = document.createElement("span");
  tag.className = "tag";
  tag.dataset.value = value;
  tag.textContent = value;

  const removeBtn = document.createElement("button");
  removeBtn.className = "tag-remove";
  removeBtn.innerHTML = "&times;";
  removeBtn.setAttribute("aria-label", "Remove " + value);
  removeBtn.addEventListener("click", () => {
    const idx = state[stateKey].indexOf(value);
    if (idx > -1) state[stateKey].splice(idx, 1);
    container.removeChild(tag);
  });

  tag.appendChild(removeBtn);
  container.appendChild(tag);
}

/* ── Genre chips ── */
function buildGenreGrid() {
  GENRES.forEach(genre => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "genre-chip";
    chip.textContent = genre;
    chip.addEventListener("click", () => {
      const idx = state.genres.indexOf(genre);
      if (idx > -1) {
        state.genres.splice(idx, 1);
        chip.classList.remove("selected");
      } else {
        if (state.genres.length >= 3) return;
        state.genres.push(genre);
        chip.classList.add("selected");
      }
    });
    genreGrid.appendChild(chip);
  });
}

/* ── Clear all ── */
function clearAll() {
  ["movies","actors","directors"].forEach(key => {
    state[key] = [];
    document.getElementById(key + "-tags").innerHTML = "";
    document.getElementById(key + "-input").value = "";
    document.getElementById(key + "-dropdown").hidden = true;
  });
  state.genres = [];
  document.querySelectorAll(".genre-chip.selected").forEach(c => c.classList.remove("selected"));
  hardFilterToggle.checked = false;
  resultsSection.hidden = true;
  errorState.hidden = true;
  cardsGrid.innerHTML = "";
}

/* ── "Seen it" ── */
function addSeenMovie(title) {
  if (state.movies.length >= 5) return false;
  if (state.movies.includes(title)) return false;
  state.movies.push(title);
  const tagsDisplay = document.getElementById("movies-tags");
  addTag(tagsDisplay, title, "movies");
  document.getElementById("pref-form").scrollIntoView({ behavior: "smooth", block: "start" });
  return true;
}

/* ── API call ── */
async function fetchRecommendations() {
  const payload = {
    movies:     state.movies,
    actors:     state.actors,
    directors:  state.directors,
    genres:     state.genres,
    genre_mode: hardFilterToggle.checked ? "hard_filter" : "soft_boost",
    top_n:      10,
  };

  if (!payload.movies.length && !payload.actors.length &&
      !payload.directors.length && !payload.genres.length) {
    showError("Please add at least one film, actor, director, or genre.");
    return;
  }

  setLoading(true);
  try {
    const resp = await fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok || data.error) { showError(data.error || "Something went wrong."); return; }
    renderResults(data);
  } catch (err) {
    showError("Network error. Is the server running?");
  } finally {
    setLoading(false);
  }
}

/* ── UI helpers ── */
function setLoading(on) {
  submitBtn.disabled = on;
  loadingState.hidden = !on;
  errorState.hidden = true;
  if (on) resultsSection.hidden = true;
}

function showError(msg) {
  errorMsg.textContent = msg;
  errorState.hidden = false;
  resultsSection.hidden = true;
}

/* ── Render results ── */
function renderResults(data) {
  const recs = data.recommendations || [];
  if (!recs.length) { showError("No recommendations found. Try adjusting your inputs."); return; }

  resultsMeta.textContent = recs.length + " picks · from " + (data.candidate_count || "many") + " candidates";

  const unresolved = data.unresolved || [];
  if (unresolved.length) {
    unresolvedTxt.textContent = "Couldn't find: " + unresolved.join(", ");
    unresolvedWarn.hidden = false;
  } else {
    unresolvedWarn.hidden = true;
  }

  cardsGrid.innerHTML = "";
  recs.forEach((movie, i) => cardsGrid.appendChild(buildCard(movie, i)));
  resultsSection.hidden = false;
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function buildCard(movie, index) {
  const card = document.createElement("article");
  card.className = "movie-card";
  card.style.animationDelay = (index * 0.06) + "s";

  if (movie.poster_url) {
    const img = document.createElement("img");
    img.className = "card-poster";
    img.src = movie.poster_url;
    img.alt = movie.title;
    img.loading = "lazy";
    card.appendChild(img);
  } else {
    const ph = document.createElement("div");
    ph.className = "card-poster-placeholder";
    ph.textContent = "🎬";
    card.appendChild(ph);
  }

  const body = document.createElement("div");
  body.className = "card-body";

  const title = document.createElement("h3");
  title.className = "card-title";
  title.textContent = movie.title;

  const year = document.createElement("p");
  year.className = "card-year";
  year.textContent = movie.year || "—";

  const genreRow = document.createElement("div");
  genreRow.className = "card-genres";
  (movie.genre_names || []).slice(0, 3).forEach(g => {
    const chip = document.createElement("span");
    chip.className = "card-genre";
    chip.textContent = g;
    genreRow.appendChild(chip);
  });

  const explanation = document.createElement("p");
  explanation.className = "card-explanation";
  explanation.textContent = movie.explanation || "";

  const scoreEl = document.createElement("div");
  scoreEl.className = "card-score";
  const track = document.createElement("div");
  track.className = "score-bar-track";
  const fill = document.createElement("div");
  fill.className = "score-bar-fill";
  const pct = Math.min(Math.round(movie.score * 200), 100);
  setTimeout(() => { fill.style.width = pct + "%"; }, 100 + index * 60);
  track.appendChild(fill);
  const scoreLabel = document.createElement("span");
  scoreLabel.className = "score-label";
  scoreLabel.textContent = movie.vote_average ? movie.vote_average.toFixed(1) + "★" : "";
  scoreEl.append(track, scoreLabel);

  const seenBtn = document.createElement("button");
  seenBtn.className = "seen-it-btn";
  seenBtn.innerHTML = "<span>＋</span> I've seen this — find me something similar";
  seenBtn.addEventListener("click", () => {
    const added = addSeenMovie(movie.title);
    if (added) {
      seenBtn.classList.add("added");
      seenBtn.innerHTML = "<span>✓</span> Added to your seeds";
      seenBtn.disabled = true;
    } else if (state.movies.length >= 5) {
      seenBtn.textContent = "Seeds full (max 5)";
      seenBtn.disabled = true;
    }
  });

  body.append(title, year, genreRow, explanation, scoreEl, seenBtn);
  card.appendChild(body);
  return card;
}

/* ── Init ── */
buildGenreGrid();

setupAutocomplete({
  inputId: "movies-input", dropdownId: "movies-dropdown",
  stateKey: "movies", max: 5, endpoint: "movie",
  renderItem: movieItem, getLabel: (m) => m.title,
});
setupAutocomplete({
  inputId: "actors-input", dropdownId: "actors-dropdown",
  stateKey: "actors", max: 5, endpoint: "person",
  renderItem: personItem, getLabel: (p) => p.name,
});
setupAutocomplete({
  inputId: "directors-input", dropdownId: "directors-dropdown",
  stateKey: "directors", max: 5, endpoint: "person",
  renderItem: personItem, getLabel: (p) => p.name,
});

form.addEventListener("submit", (e) => { e.preventDefault(); fetchRecommendations(); });
clearBtn.addEventListener("click", clearAll);
