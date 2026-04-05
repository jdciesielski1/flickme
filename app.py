"""
Flask web app for FlickMe.
"""

import os
from flask import Flask, render_template, request, jsonify
from src.recommender import Recommender

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Initialize once at startup
recommender = Recommender(
    tmdb_api_key=os.environ.get("TMDB_API_KEY", ""),
    anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
)


def _parse_list(value: str) -> list[str]:
    """Split a comma-separated string into a cleaned list."""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/recommend", methods=["POST"])
def api_recommend():
    data = request.get_json(force=True)

    movies = data.get("movies", [])
    actors = data.get("actors", [])
    directors = data.get("directors", [])
    genres = data.get("genres", [])
    genre_mode = data.get("genre_mode", "soft_boost")
    top_n = min(int(data.get("top_n", 10)), 20)

    # Require at least one input
    if not any([movies, actors, directors, genres]):
        return jsonify({"error": "Please provide at least one movie, actor, director, or genre."}), 400

    try:
        result = recommender.recommend(
            movie_titles=movies[:5],
            actor_names=actors[:5],
            director_names=directors[:5],
            genre_inputs=genres[:3],
            genre_mode=genre_mode,
            top_n=top_n,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Something went wrong: {str(e)}"}), 500


@app.route("/api/autocomplete/movie", methods=["GET"])
def autocomplete_movie():
    """Return movie suggestions for a partial title query."""
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify({"results": []})
    try:
        tmdb = recommender.tmdb
        data = tmdb._get("/search/movie", query=query, include_adult=False, page=1)
        results = data.get("results", [])[:6]
        suggestions = [
            {
                "title": m["title"],
                "year": (m.get("release_date") or "")[:4],
                "poster_url": f"https://image.tmdb.org/t/p/w92{m['poster_path']}" if m.get("poster_path") else None,
            }
            for m in results
        ]
        return jsonify({"results": suggestions})
    except Exception as e:
        return jsonify({"results": [], "error": str(e)})


@app.route("/api/autocomplete/person", methods=["GET"])
def autocomplete_person():
    """Return person suggestions for a partial name query."""
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify({"results": []})
    try:
        tmdb = recommender.tmdb
        data = tmdb._get("/search/person", query=query, page=1)
        results = data.get("results", [])[:6]
        suggestions = [
            {
                "name": p["name"],
                "role": p.get("known_for_department", ""),
                "known_for": ", ".join(
                    kf.get("title") or kf.get("name", "")
                    for kf in p.get("known_for", [])[:2]
                ),
            }
            for p in results
        ]
        return jsonify({"results": suggestions})
    except Exception as e:
        return jsonify({"results": [], "error": str(e)})


@app.route("/api/genres", methods=["GET"])
def api_genres():
    """Return the list of available genres."""
    from src.profile_builder import GENRE_NAME_TO_ID
    genres = sorted(GENRE_NAME_TO_ID.keys())
    return jsonify({"genres": [g.title() for g in genres]})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
