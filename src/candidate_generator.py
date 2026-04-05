"""
Candidate generator.
Pulls a broad pool of candidate movies from multiple TMDB signals.
No scoring here -- just breadth.
"""

from src.tmdb_client import TMDBClient
from src.profile_builder import UserProfile


class CandidateGenerator:
    def __init__(self, tmdb: TMDBClient):
        self.tmdb = tmdb

    def generate(self, profile: UserProfile, target_count: int = 150) -> list[dict]:
        """
        Generate a broad candidate pool from multiple sources:
        1. TMDB similar/recommended for each seed movie
        2. TMDB discover filtered by actors
        3. TMDB discover filtered by directors
        4. TMDB discover filtered by genre (if provided)

        Returns deduplicated list of raw TMDB movie dicts.
        """
        seen_ids = set(profile.seed_movie_ids)  # exclude seeds from results
        candidates = []

        def add(movies: list[dict]):
            for m in movies:
                mid = m.get("id")
                if mid and mid not in seen_ids:
                    seen_ids.add(mid)
                    candidates.append(m)

        # 1. Similar + recommended for each seed movie
        for movie_id in profile.seed_movie_ids:
            try:
                add(self.tmdb.get_similar_movies(movie_id))
                add(self.tmdb.get_recommendations(movie_id))
            except Exception:
                pass

        # 2. Discover by actors (up to 3 at a time to avoid over-filtering)
        if profile.actor_ids:
            for i in range(0, len(profile.actor_ids), 3):
                batch = profile.actor_ids[i:i+3]
                try:
                    add(self.tmdb.discover_movies(with_cast=batch))
                except Exception:
                    pass

        # 3. Discover by directors
        if profile.director_ids:
            for director_id in profile.director_ids:
                try:
                    add(self.tmdb.discover_movies(with_crew=[director_id]))
                except Exception:
                    pass

        # 4. Discover by genre (soft signal -- just adds genre-specific candidates)
        if profile.genre_ids:
            try:
                add(self.tmdb.discover_movies(
                    with_genres=profile.genre_ids,
                    min_vote_count=100,
                    sort_by="vote_average.desc",
                ))
            except Exception:
                pass

        # If we're still thin, pull top popular movies in requested genre
        if len(candidates) < 50 and profile.genre_ids:
            try:
                add(self.tmdb.discover_movies(
                    with_genres=profile.genre_ids,
                    min_vote_count=200,
                    sort_by="popularity.desc",
                    page=2,
                ))
            except Exception:
                pass

        return candidates[:target_count]
