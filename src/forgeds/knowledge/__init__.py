"""ForgeDS Knowledge Base — relational documentation graph.

Scrapes Zoho/Deluge documentation, parses it into structured knowledge
tokens, builds a weighted relational graph, and uses HRC to verify
internal consistency and discover documentation gaps.
"""

from forgeds.knowledge._types import (
    ContentType,
    KnowledgeToken,
    Relation,
    RelationType,
    RELATION_WEIGHTS,
    compute_token_sha,
)

__all__ = [
    "ContentType",
    "KnowledgeToken",
    "Relation",
    "RelationType",
    "RELATION_WEIGHTS",
    "compute_token_sha",
]
