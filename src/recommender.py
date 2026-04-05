"""
Recommender orchestrator.
Wires all modules together into a single recommend() call.
"""

from src.tmdb_client import TMDBClient
from src.profile_builder import ProfileBuilder, UserProfile
from src.candidate_generator import CandidateGenerator
from src.scorer import HybridScorer
from src.explainer import Explainer


class Recommender:
    def __init__(self, tmdb_api_key: str, anthropic_api_key: str):
        self.tmdb = TMDBClient(tmdb_api_key)
        self.profile_builder = ProfileBuilder(self.tmdb)
        self.candidate_generator = CandidateGenerator(self.tmdb)
        self.scorer = HybridScorer(self.tmdb)
        self.explainer = Explainer(anthropic_api_key)
        self._genre_map = None

    def _get_genre_map(self) -> dict:
        if self._genre_map is None:
            self._genre_map = self.tmdb.get_genres()
        return self._genre_map

    def recommend(
        self,
        movie_titles: list[str],
        actor_names: list[str],
        director_names: list[str],
        genre_inputs: list[str],
        genre_mode: str = "soft_boost",
        top_n: int = 10,
    ) -> dict:
        """
        Full recommendation pipeline.
        Returns a dict with profile summary, recommendations, and any warnings.
        """
        genre_map = self._get_genre_map()

        # Step 1: Build user profile
        profile = self.profile_builder.build(
            movie_titles=movie_titles,
            actor_names=actor_names,
            director_names=director_names,
            genre_inputs=genre_inputs,
            genre_mode=genre_mode,
        )

        # Require at least one resolved input
        if not profile.seed_movies and not profile.actors and not profile.directors and not profile.genre_ids:
            return {
                "error": "Could not resolve any of your inputs. Please check for typos.",
                "unresolved": profile.unresolved,
            }

        # Step 2: Generate candidates
        candidates = self.candidate_generator.generate(profile)

        if not candidates:
            return {
                "error": "No candidates found. Try different inputs or a broader genre.",
                "profile": profile.to_summary(),
            }

        # Step 3: Score and rank
        ranked = self.scorer.score_and_rank(
            candidates=candidates,
            profile=profile,
            top_n=top_n,
            genre_mode=genre_mode,
        )

        # Add genre names to each result
        for movie in ranked:
            movie["genre_names"] = [
                genre_map.get(gid, "") for gid in movie["genre_ids"]
            ]

        # Step 4: Generate explanations
        results = self.explainer.explain_batch(ranked, profile, genre_map)

        return {
            "profile": profile.to_summary(),
            "recommendations": results,
            "unresolved": profile.unresolved,
            "candidate_count": len(candidates),
        }
