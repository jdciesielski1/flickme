"""
Explainer.
Calls the Anthropic API to generate a personalized "why you'll like this"
blurb for each top recommendation.
"""

import anthropic
from src.profile_builder import UserProfile


SYSTEM_PROMPT = """You are a knowledgeable film critic helping someone discover movies they'll love.
Given a user's taste profile and a recommended movie, write a concise, enthusiastic 2-3 sentence
explanation of why this specific movie matches their tastes. Be specific -- reference the films,
actors, or directors they mentioned when relevant. Sound like a passionate film buff, not a
recommendation algorithm. Never start with "This film" or "This movie". Vary your openers."""


def _build_prompt(movie: dict, profile: UserProfile, genre_map: dict) -> str:
    seed_titles = [m.title for m in profile.seed_movies]
    actor_names = [p.name for p in profile.actors]
    director_names = [p.name for p in profile.directors]
    genre_names = profile.genre_names

    matched_actor_names = []
    for actor in profile.actors:
        if actor.tmdb_id in movie.get("matched_actors", []):
            matched_actor_names.append(actor.name)

    matched_director_names = []
    for director in profile.directors:
        if director.tmdb_id in movie.get("matched_directors", []):
            matched_director_names.append(director.name)

    candidate_genre_names = [
        genre_map.get(gid, str(gid))
        for gid in movie.get("genre_ids", [])
    ]

    lines = [
        f"Movie to explain: {movie['title']} ({movie['year']})",
        f"Overview: {movie['overview'][:300]}",
        f"Genres: {', '.join(candidate_genre_names)}",
        f"Vote average: {movie['vote_average']}/10",
        "",
        "User's taste profile:",
    ]
    if seed_titles:
        lines.append(f"  Loved films: {', '.join(seed_titles)}")
    if actor_names:
        lines.append(f"  Favorite actors: {', '.join(actor_names)}")
    if director_names:
        lines.append(f"  Favorite directors: {', '.join(director_names)}")
    if genre_names:
        lines.append(f"  Looking for: {', '.join(genre_names)}")
    if matched_actor_names:
        lines.append(f"  This film features: {', '.join(matched_actor_names)}")
    if matched_director_names:
        lines.append(f"  Directed by: {', '.join(matched_director_names)}")

    return "\n".join(lines)


class Explainer:
    def __init__(self, anthropic_api_key: str):
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)

    def explain(self, movie: dict, profile: UserProfile, genre_map: dict) -> str:
        """Generate a personalized explanation for one recommendation."""
        prompt = _build_prompt(movie, profile, genre_map)
        try:
            message = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=200,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text.strip()
        except Exception as e:
            return f"A strong match based on your taste in {', '.join(profile.genre_names or ['cinema'])}."

    def explain_batch(
        self, movies: list[dict], profile: UserProfile, genre_map: dict
    ) -> list[dict]:
        """Add explanation field to each movie dict."""
        enriched = []
        for movie in movies:
            explanation = self.explain(movie, profile, genre_map)
            enriched.append({**movie, "explanation": explanation})
        return enriched
