# FlickMe

A cinematic movie recommendation engine. Give it films you love, actors you follow,
directors you admire, and a genre mood — it finds what you're missing.

## Features

- Autocomplete for movie titles, actor names, and director names
- 5-signal hybrid scoring: content similarity, actor match, director match, genre alignment, quality
- Personalized "why you'll like this" explanations powered by Claude
- "I've seen this" button on each result to refine recommendations iteratively

## Stack

- **Backend**: Flask + Python
- **Movie data**: TMDB API (free, no gating)
- **Explanations**: Anthropic Claude API
- **Frontend**: Vanilla HTML/CSS/JS — no build step

## Setup

### 1. Get API keys

- **TMDB**: Create a free account at https://www.themoviedb.org/signup, then go to
  Settings → API and request a Developer key (approved instantly).
- **Anthropic**: Get a key at https://console.anthropic.com/

### 2. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/flickme.git
cd flickme
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Open .env and fill in your two API keys
```

### 4. Run

```bash
python -m flask --app app run --debug
```

Open http://localhost:5000

## Architecture

```
User inputs (movies, actors, directors, genre)
    ↓
TMDB entity resolver  →  resolves names/titles to TMDB IDs
    ↓
User preference vector  →  structured profile object
    ↓
Candidate generator  →  ~150 candidates via TMDB discover + similar
    ↓
Hybrid scorer  →  weighted: content + actor + director + genre + quality
    ↓
LLM explainer  →  personalized "why you'll like this" via Claude
    ↓
Results
```

## Project structure

```
flickme/
├── app.py                      # Flask routes + autocomplete endpoints
├── src/
│   ├── tmdb_client.py          # TMDB API wrapper
│   ├── profile_builder.py      # Converts user input to structured profile
│   ├── candidate_generator.py  # Fetches candidate movies from TMDB
│   ├── scorer.py               # 5-signal hybrid scorer
│   ├── explainer.py            # Claude API explanations
│   └── recommender.py          # Pipeline orchestrator
├── templates/
│   └── index.html              # Single-page UI
├── static/
│   ├── css/main.css
│   └── js/main.js              # Tag inputs, autocomplete, results rendering
├── .env.example
├── .gitignore
└── requirements.txt
```

## Scoring weights

Defined in `src/scorer.py`. Adjust to taste:

| Signal | Default | Description |
|---|---|---|
| Content similarity | 0.30 | Genre Jaccard overlap with seed movies |
| Actor match | 0.25 | Fraction of preferred actors in the cast |
| Director match | 0.20 | Whether a preferred director made it |
| Genre alignment | 0.15 | Match with explicitly requested genres |
| Quality signal | 0.10 | TMDB vote average x vote-count confidence |

## Attribution

This product uses the TMDB API but is not endorsed or certified by TMDB.
