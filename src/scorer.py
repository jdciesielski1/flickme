"""
Hybrid scorer.
Scores each candidate against the user profile using 5 signals,
then returns the top-N ranked results with full metadata.

Performance optimisations:
- Credits are fetched in parallel using a thread pool (max_workers=10)
- Credits fetch is skipped entirely when no actors/directors are in the profile
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from src.tmdb_client import TMDBClient
from src.profile_builder import UserProfile

# Scoring weights -- must sum to 1.0
WEIGHTS = {
    "content_similarity": 0.30,   # genre/tag overlap with seed movies
    "actor_match":        0.25,   # how many preferred actors are in the cast
    "director_match":     0.20,   # whether a preferred director directed it
    "genre_alignment":    0.15,   # alignment with explicitly requested genres
    "quality_signal":     0.10,   # TMDB vote average (normalized)
}


def _genre_overlap_score(candidate_genre_ids, seed_genre_ids):
    """Jaccard similarity between candidate genres and aggregated seed genres."""
    if not seed_genre_ids or not candidate_genre_ids:
        return 0.0
    a = set(candidate_genre_ids)
    b = set(seed_genre_ids)
    return len(a & b) / len(a | b)


def _genre_alignment_score(candidate_genre_ids, requested_genre_ids):
    """How well the candidate matches the explicitly requested genres."""
    if not requested_genre_ids:
        return 0.5
    matches = sum(1 for g in requested_genre_ids if g in candidate_genre_ids)
    return matches / len(requested_genre_ids)


def _quality_score(vote_average, vote_count):
    """Bayesian-ish quality score. Penalizes low vote counts."""
    if vote_count < 10:
        return 0.0
    raw = vote_average / 10.0
    confidence = min(vote_count / 500, 1.0)
    return raw * confidence + raw * (1 - confidence) * 0.5


class HybridScorer:
    def __init__(self, tmdb: TMDBClient):
        self.tmdb = tmdb

    def score_and_rank(self, candidates, profile, top_n=10, genre_mode="soft_boost"):
        """
        Score each candidate and return the top_n with full metadata.

        Credits are fetched in parallel (10 concurrent requests) and only
        when actor or director signals are present in the profile.
        """
        seed_genre_ids = profile.all_genre_ids_from_seeds
        needs_credits = bool(profile.actor_ids or profile.director_ids)

        def score_one(movie):
            candidate_genre_ids = movie.get("genre_ids", [])

            # Hard filter: skip if none of the requested genres match
            if genre_mode == "hard_filter" and profile.genre_ids:
                if not any(g in candidate_genre_ids for g in profile.genre_ids):
                    return None

            cast_ids = set()
            crew_director_ids = set()
            poster_url = self.tmdb.get_movie_poster_url(movie.get("poster_path"))

            # Only hit the credits endpoint when we have actor/director signals
            if needs_credits:
                try:
                    details = self.tmdb.get_movie_details(movie["id"])
                    credits = details.get("credits", {})
                    cast_ids = {c["id"] for c in credits.get("cast", [])[:20]}
                    crew_director_ids = {
                        c["id"] for c in credits.get("crew", [])
                        if c.get("job") == "Director"
                    }
                    poster_url = self.tmdb.get_movie_poster_url(
                        details.get("poster_path")
                    ) or poster_url
                except Exception:
                    pass

            content_sim   = _genre_overlap_score(candidate_genre_ids, seed_genre_ids)
            actor_matches = [aid for aid in profile.actor_ids if aid in cast_ids]
            actor_score   = min(len(actor_matches) / max(len(profile.actor_ids), 1), 1.0)
            dir_matches   = [did for did in profile.director_ids if did in crew_director_ids]
            dir_score     = 1.0 if dir_matches else 0.0
            genre_align   = _genre_alignment_score(candidate_genre_ids, profile.genre_ids)
            quality       = _quality_score(movie.get("vote_average", 0), movie.get("vote_count", 0))

            final_score = (
                WEIGHTS["content_similarity"] * content_sim +
                WEIGHTS["actor_match"]        * actor_score +
                WEIGHTS["director_match"]     * dir_score +
                WEIGHTS["genre_alignment"]    * genre_align +
                WEIGHTS["quality_signal"]     * quality
            )

            return {
                "tmdb_id":    movie["id"],
                "title":      movie.get("title", "Unknown"),
                "year":       (movie.get("release_date") or "")[:4],
                "overview":   movie.get("overview", ""),
                "poster_url": poster_url,
                "vote_average": movie.get("vote_average", 0),
                "vote_count":   movie.get("vote_count", 0),
                "genre_ids":    candidate_genre_ids,
                "score":        round(final_score, 4),
                "score_breakdown": {
                    "content_similarity": round(content_sim, 3),
                    "actor_match":        round(actor_score, 3),
                    "director_match":     round(dir_score, 3),
                    "genre_alignment":    round(genre_align, 3),
                    "quality_signal":     round(quality, 3),
                },
                "matched_actors":    actor_matches,
                "matched_directors": dir_matches,
            }

        # Fetch credits for all candidates in parallel
        scored = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(score_one, movie): movie for movie in candidates}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result is not None:
                        scored.append(result)
                except Exception:
                    pass

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_n]
