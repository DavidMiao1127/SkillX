"""Clustering module for skill deduplication and merging."""

from .embedding import EmbeddingService
from .dbscan import DBSCANClustering
from .merger import SkillMerger

__all__ = [
    "EmbeddingService",
    "DBSCANClustering",
    "SkillMerger",
]
