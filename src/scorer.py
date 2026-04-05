"""
Hybrid scorer.
Scores each candidate against the user profile using 5 signals,
then returns the top-N ranked results with full metadata.
"""

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


def _genre_overlap_score(candidate_genre_ids: list[int], seed_genre_ids: list[int]) -> float:
    """Jaccard similarity between candidate genres and aggregated seed genres."""
    if not seed_genre_ids or not candidate_genre_ids:
        return 0.0
    a = set(candidate_genre_ids)
    b = set(seed_genre_ids)
    return len(a & b) / len(a | b)


def _genre_alignment_score(candidate_genre_ids: list[int], requested_genre_ids: list[int]) -> float:
    """How well the candidate matches the explicitly requested genres."""
    if not requested_genre_ids:
        return 0.5  # neutral if no genre requested
    matches = sum(1 for g in requested_genre_ids if g in candidate_genre_ids)
    return matches / len(requested_genre_ids)


def _quality_score(vote_average: float, vote_count: int) -> float:
    """Bayesian-ish quality score. Penalizes low vote counts."""
    if vote_count < 10:
        return 0.0
    # Normalize to 0-1, apply vote count confidence
    raw = vote_average / 10.0
    confidence = min(vote_count / 500, 1.0)
    return raw * confidence + raw * (1 - confidence) * 0.5


class HybridScorer:
    def __init__(self, tmdb: TMDBClient):
        self.tmdb = tmdb

    def score_and_rank(
        self,
        candidates: list[dict],
        profile: UserProfile,
        top_n: int = 10,
        genre_mode: str = "soft_boost",
    ) -> list[dict]:
        """
        Score each candidate and return the top_n with full metadata.
        genre_mode="hard_filter" drops non-matching genre candidates entirely.
        genre_mode="soft_boost" keeps all but boosts matching ones.
        """
        seed_genre_ids = profile.all_genre_ids_from_seeds
        scored = []

        for movie in candidates:
            candidate_genre_ids = movie.get("genre_ids", [])

            # Hard filter: skip if none of the requested genres match
            if genre_mode == "hard_filter" and profile.genre_ids:
                if not any(g in candidate_genre_ids for g in profile.genre_ids):
                    continue

            # Fetch credits to check actor/director match
            cast_ids = set()
            crew_director_ids = set()
            poster_url = None

            try:
                details = self.tmdb.get_movie_details(movie["id"])
                credits = details.get("credits", {})
                cast_ids = {c["id"] for c in credits.get("cast", [])[:20]}
                crew_director_ids = {
                    c["id"] for c in credits.get("crew", [])
                    if c.get("job") == "Director"
                }
                poster_url = self.tmdb.get_movie_poster_url(details.get("poster_path"))
            except Exception:
                poster_url = self.tmdb.get_movie_poster_url(movie.get("poster_path"))

            # Compute each signal
            content_sim = _genre_overlap_score(candidate_genre_ids, seed_genre_ids)

            actor_matches = [aid for aid in profile.actor_ids if aid in cast_ids]
            actor_score = min(len(actor_matches) / max(len(profile.actor_ids), 1), 1.0)

            director_matches = [did for did in profile.director_ids if did in crew_director_ids]
            director_score = 1.0 if director_matches else 0.0

            genre_align = _genre_alignment_score(candidate_genre_ids, profile.genre_ids)

            quality = _quality_score(
                movie.get("vote_average", 0),
                movie.get("vote_count", 0),
            )

            final_score = (
                WEIGHTS["content_similarity"] * content_sim +
                WEIGHTS["actor_match"]        * actor_score +
                WEIGHTS["director_match"]     * director_score +
                WEIGHTS["genre_alignment"]    * genre_align +
                WEIGHTS["quality_signal"]     * quality
            )

            scored.append({
                "tmdb_id": movie["id"],
                "title": movie.get("title", "Unknown"),
                "year": (movie.get("release_date") or "")[:4],
                "overview": movie.get("overview", ""),
                "poster_url": poster_url,
                "vote_average": movie.get("vote_average", 0),
                "vote_count": movie.get("vote_count", 0),
                "genre_ids": candidate_genre_ids,
                "score": round(final_score, 4),
                "score_breakdown": {
                    "content_similarity": round(content_sim, 3),
                    "actor_match": round(actor_score, 3),
                    "director_match": round(director_score, 3),
                    "genre_alignment": round(genre_align, 3),
                    "quality_signal": round(quality, 3),
                },
                "matched_actors": actor_matches,
                "matched_directors": director_matches,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_n]
