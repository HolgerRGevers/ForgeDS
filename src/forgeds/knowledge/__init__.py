"""ForgeDS Knowledge Base — relational documentation graph.

Scrapes Zoho/Deluge documentation, parses it into structured knowledge
tokens, builds a weighted relational graph, and uses HRC to verify
internal consistency and discover documentation gaps.

Architecture:
    - **RB** (Reality Database) — permanent source of truth (``reality.db``)
    - **HB** (Holographic Database) — ephemeral projections (``holographic.db``)
    - **Librarian** (C + Python fallback) — sole authority for token
      lifecycle: creation, destruction, weight adjustment.

Public API for external programs::

    from forgeds.knowledge import KnowledgeBase, HologramToken

    kb = KnowledgeBase("knowledge/reality.db")
    kb.init()                                # scrape + parse + build
    kb.ingest("App.ds")                      # tokenize a .ds app
    result = kb.check("app:App")             # reality check (creates HB tokens)
    for h in result.holograms:               # inspect hologram tokens
        print(h.severity_label, h.message)
    kb.confirm_analysis()                    # purge HB (Librarian destroys)
"""

from forgeds.knowledge._types import (
    ContentType,
    KnowledgeToken,
    Relation,
    RelationType,
    RELATION_WEIGHTS,
)
from forgeds.knowledge.api import (
    HologramToken,
    KnowledgeBase,
    RealityCheck,
)
from forgeds.knowledge.librarian_io import (
    LIB_HB,
    LIB_RB,
    LibrarianError,
    LibrarianHandle,
    open_librarian,
)

__all__ = [
    # Public API (primary interface for external programs)
    "KnowledgeBase",
    "HologramToken",
    "RealityCheck",
    # Librarian (token lifecycle authority)
    "LibrarianHandle",
    "LibrarianError",
    "open_librarian",
    "LIB_RB",
    "LIB_HB",
    # Core types
    "ContentType",
    "KnowledgeToken",
    "Relation",
    "RelationType",
    "RELATION_WEIGHTS",
]
