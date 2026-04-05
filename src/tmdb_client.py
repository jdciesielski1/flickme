"""
TMDB API client.
Handles entity resolution (text -> IDs) and movie discovery.
"""

import os
import requests
from functools import lru_cache
from typing import Optional

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


class TMDBClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.params = {"api_key": api_key}

    def _get(self, path: str, **params) -> dict:
        resp = self.session.get(f"{TMDB_BASE}{path}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------ #
    # Entity resolution
    # ------------------------------------------------------------------ #

    def resolve_movie(self, title: str) -> Optional[dict]:
        """Resolve a movie title to TMDB metadata. Returns best match or None."""
        data = self._get("/search/movie", query=title, include_adult=False)
        results = data.get("results", [])
        if not results:
            return None
        # Return the most popular match
        best = max(results, key=lambda m: m.get("popularity", 0))
        return {
            "tmdb_id": best["id"],
            "title": best["title"],
            "year": (best.get("release_date") or "")[:4],
            "poster_path": best.get("poster_path"),
            "poster_url": f"{TMDB_IMAGE_BASE}{best['poster_path']}" if best.get("poster_path") else None,
            "genre_ids": best.get("genre_ids", []),
            "overview": best.get("overview", ""),
            "vote_average": best.get("vote_average", 0),
            "popularity": best.get("popularity", 0),
        }

    def resolve_person(self, name: str) -> Optional[dict]:
        """Resolve an actor or director name to TMDB person ID."""
        data = self._get("/search/person", query=name)
        results = data.get("results", [])
        if not results:
            return None
        best = max(results, key=lambda p: p.get("popularity", 0))
        return {
            "tmdb_id": best["id"],
            "name": best["name"],
            "known_for_department": best.get("known_for_department", ""),
            "profile_path": best.get("profile_path"),
        }

    def get_movie_details(self, tmdb_id: int) -> dict:
        """Fetch full movie details including credits and keywords."""
        return self._get(
            f"/movie/{tmdb_id}",
            append_to_response="credits,keywords"
        )

    def get_person_credits(self, person_id: int) -> dict:
        """Get all movie credits for a person."""
        return self._get(f"/person/{person_id}/movie_credits")

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    def discover_movies(
        self,
        with_cast: Optional[list[int]] = None,
        with_crew: Optional[list[int]] = None,
        with_genres: Optional[list[int]] = None,
        without_genres: Optional[list[int]] = None,
        min_vote_count: int = 50,
        min_vote_average: float = 5.0,
        page: int = 1,
        sort_by: str = "popularity.desc",
    ) -> list[dict]:
        """
        Use TMDB /discover/movie to find candidates.
        with_cast and with_crew use OR logic within each param (any match counts).
        """
        params = {
            "sort_by": sort_by,
            "vote_count.gte": min_vote_count,
            "vote_average.gte": min_vote_average,
            "page": page,
        }
        if with_cast:
            params["with_cast"] = ",".join(str(i) for i in with_cast)
        if with_crew:
            params["with_crew"] = ",".join(str(i) for i in with_crew)
        if with_genres:
            params["with_genres"] = ",".join(str(i) for i in with_genres)
        if without_genres:
            params["without_genres"] = ",".join(str(i) for i in without_genres)

        data = self._get("/discover/movie", **params)
        return data.get("results", [])

    def get_similar_movies(self, tmdb_id: int, page: int = 1) -> list[dict]:
        """Get TMDB's own similar movie list for a given film."""
        data = self._get(f"/movie/{tmdb_id}/similar", page=page)
        return data.get("results", [])

    def get_recommendations(self, tmdb_id: int, page: int = 1) -> list[dict]:
        """Get TMDB's recommendation list for a given film."""
        data = self._get(f"/movie/{tmdb_id}/recommendations", page=page)
        return data.get("results", [])

    def get_genres(self) -> dict[int, str]:
        """Return a mapping of genre_id -> genre_name."""
        data = self._get("/genre/movie/list")
        return {g["id"]: g["name"] for g in data.get("genres", [])}

    def get_movie_poster_url(self, poster_path: Optional[str]) -> Optional[str]:
        if not poster_path:
            return None
        return f"{TMDB_IMAGE_BASE}{poster_path}"
