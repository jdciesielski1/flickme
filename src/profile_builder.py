"""
Profile builder.
Converts raw user text input into a structured UserProfile
by resolving all names/titles to TMDB IDs.
"""

from dataclasses import dataclass, field
from typing import Optional
from src.tmdb_client import TMDBClient


GENRE_NAME_TO_ID = {
    "action": 28,
    "adventure": 12,
    "animation": 16,
    "comedy": 35,
    "crime": 80,
    "documentary": 99,
    "drama": 18,
    "family": 10751,
    "fantasy": 14,
    "history": 36,
    "horror": 27,
    "music": 10402,
    "mystery": 9648,
    "romance": 10749,
    "science fiction": 878,
    "sci-fi": 878,
    "thriller": 53,
    "war": 10752,
    "western": 37,
}


@dataclass
class ResolvedMovie:
    tmdb_id: int
    title: str
    year: str
    poster_url: Optional[str]
    genre_ids: list[int]
    overview: str
    vote_average: float


@dataclass
class ResolvedPerson:
    tmdb_id: int
    name: str
    role: str  # "actor" or "director"


@dataclass
class UserProfile:
    seed_movies: list[ResolvedMovie] = field(default_factory=list)
    actors: list[ResolvedPerson] = field(default_factory=list)
    directors: list[ResolvedPerson] = field(default_factory=list)
    genre_ids: list[int] = field(default_factory=list)
    genre_names: list[str] = field(default_factory=list)
    genre_mode: str = "soft_boost"  # "hard_filter" or "soft_boost"
    unresolved: list[str] = field(default_factory=list)  # things we couldn't find

    @property
    def all_genre_ids_from_seeds(self) -> list[int]:
        """Aggregate genre IDs from all seed movies."""
        ids = []
        for m in self.seed_movies:
            ids.extend(m.genre_ids)
        return list(set(ids))

    @property
    def seed_movie_ids(self) -> list[int]:
        return [m.tmdb_id for m in self.seed_movies]

    @property
    def actor_ids(self) -> list[int]:
        return [p.tmdb_id for p in self.actors]

    @property
    def director_ids(self) -> list[int]:
        return [p.tmdb_id for p in self.directors]

    def to_summary(self) -> dict:
        return {
            "seed_movies": [
                {"id": m.tmdb_id, "title": m.title, "year": m.year, "poster_url": m.poster_url}
                for m in self.seed_movies
            ],
            "actors": [{"id": p.tmdb_id, "name": p.name} for p in self.actors],
            "directors": [{"id": p.tmdb_id, "name": p.name} for p in self.directors],
            "genres": self.genre_names,
            "genre_ids": self.genre_ids,
            "genre_mode": self.genre_mode,
            "unresolved": self.unresolved,
        }


class ProfileBuilder:
    def __init__(self, tmdb: TMDBClient):
        self.tmdb = tmdb

    def build(
        self,
        movie_titles: list[str],
        actor_names: list[str],
        director_names: list[str],
        genre_inputs: list[str],
        genre_mode: str = "soft_boost",
    ) -> UserProfile:
        profile = UserProfile(genre_mode=genre_mode)

        # Resolve movies
        for title in (movie_titles or [])[:5]:
            title = title.strip()
            if not title:
                continue
            result = self.tmdb.resolve_movie(title)
            if result:
                profile.seed_movies.append(ResolvedMovie(
                    tmdb_id=result["tmdb_id"],
                    title=result["title"],
                    year=result["year"],
                    poster_url=result["poster_url"],
                    genre_ids=result["genre_ids"],
                    overview=result["overview"],
                    vote_average=result["vote_average"],
                ))
            else:
                profile.unresolved.append(f"Movie: '{title}'")

        # Resolve actors
        for name in (actor_names or [])[:5]:
            name = name.strip()
            if not name:
                continue
            result = self.tmdb.resolve_person(name)
            if result:
                profile.actors.append(ResolvedPerson(
                    tmdb_id=result["tmdb_id"],
                    name=result["name"],
                    role="actor",
                ))
            else:
                profile.unresolved.append(f"Actor: '{name}'")

        # Resolve directors
        for name in (director_names or [])[:5]:
            name = name.strip()
            if not name:
                continue
            result = self.tmdb.resolve_person(name)
            if result:
                profile.directors.append(ResolvedPerson(
                    tmdb_id=result["tmdb_id"],
                    name=result["name"],
                    role="director",
                ))
            else:
                profile.unresolved.append(f"Director: '{name}'")

        # Resolve genres
        for g in (genre_inputs or []):
            g_clean = g.strip().lower()
            genre_id = GENRE_NAME_TO_ID.get(g_clean)
            if genre_id and genre_id not in profile.genre_ids:
                profile.genre_ids.append(genre_id)
                profile.genre_names.append(g.strip().title())

        return profile
