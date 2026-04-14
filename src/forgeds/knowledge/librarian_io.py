"""Python bindings for librarian.c — token lifecycle authority.

The Librarian is the SOLE gatekeeper for token creation, destruction,
and weight mutation across the Reality Database (RB) and the Holographic
Database (HB).

Follows the same ctypes auto-compile pattern as graph_io.py: try gcc,
fallback to cl.exe on Windows, pure-Python fallback if no compiler.

Usage::

    from forgeds.knowledge.librarian_io import open_librarian, LibrarianHandle

    lib = open_librarian("knowledge/reality.db", "knowledge/holographic.db")
    sha = lib.create(LIB_RB, content="...", page_url="...", ...)
    lib.destroy(sha)
    lib.close()
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import logging
import platform
import sqlite3
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Database target constants
LIB_RB = 0  # Reality Database — permanent
LIB_HB = 1  # Holographic Database — ephemeral


# ---------------------------------------------------------------------------
# LibResult ctypes structure
# ---------------------------------------------------------------------------

class _LibResult(ctypes.Structure):
    _fields_ = [
        ("ok", ctypes.c_int),
        ("sha", ctypes.c_char * 65),
        ("error", ctypes.c_char * 256),
    ]


# ---------------------------------------------------------------------------
# Auto-compile C accelerator
# ---------------------------------------------------------------------------

_C_SOURCE = Path(__file__).parent / "librarian.c"
_SO_NAME = "librarian.dll" if platform.system() == "Windows" else "librarian.so"
_SO_PATH = Path(__file__).parent / _SO_NAME
_LIB: ctypes.CDLL | None = None


def _so_is_stale() -> bool:
    if not _SO_PATH.exists() or not _C_SOURCE.exists():
        return True
    # Check all source files
    header = Path(__file__).parent / "librarian.h"
    hashmap = Path(__file__).parent / "sha_hashmap.h"
    newest_src = max(
        _C_SOURCE.stat().st_mtime,
        header.stat().st_mtime if header.exists() else 0,
        hashmap.stat().st_mtime if hashmap.exists() else 0,
    )
    return newest_src > _SO_PATH.stat().st_mtime


def _try_compile() -> bool:
    if not _C_SOURCE.exists():
        return False

    src = str(_C_SOURCE)
    out = str(_SO_PATH)

    logger.info("Compiling Librarian C accelerator: %s -> %s", src, out)

    for compiler in ("gcc", "cc"):
        try:
            result = subprocess.run(
                [compiler, "-O2", "-shared", "-fPIC", "-o", out, src, "-lsqlite3"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and _SO_PATH.exists():
                logger.info("Librarian compiled successfully with %s", compiler)
                return True
            if result.stderr:
                logger.debug("Compile stderr: %s", result.stderr[:500])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["cl.exe", "/LD", "/O2", f"/Fe:{out}", src, "sqlite3.lib"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and _SO_PATH.exists():
                logger.info("Librarian compiled successfully with cl.exe")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    logger.warning("Librarian C compilation failed — using Python fallback")
    return False


def _load_lib() -> ctypes.CDLL | None:
    global _LIB
    if _LIB is not None:
        return _LIB

    if not _SO_PATH.exists() or _so_is_stale():
        if not _try_compile():
            return None

    try:
        _LIB = ctypes.CDLL(str(_SO_PATH))

        # lib_open / lib_close
        _LIB.lib_open.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        _LIB.lib_open.restype = ctypes.c_void_p

        _LIB.lib_close.argtypes = [ctypes.c_void_p]
        _LIB.lib_close.restype = None

        # lib_create
        _LIB.lib_create.argtypes = [
            ctypes.c_void_p, ctypes.c_int,
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int,
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_double,
            ctypes.c_char_p,
        ]
        _LIB.lib_create.restype = _LibResult

        # lib_destroy
        _LIB.lib_destroy.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        _LIB.lib_destroy.restype = _LibResult

        # lib_adjust_weight
        _LIB.lib_adjust_weight.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_double,
        ]
        _LIB.lib_adjust_weight.restype = _LibResult

        # lib_create_edge
        _LIB.lib_create_edge.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p,
            ctypes.c_char_p, ctypes.c_double,
        ]
        _LIB.lib_create_edge.restype = _LibResult

        # lib_export_token — returns malloc'd string, use c_void_p to avoid
        # ctypes auto-converting to bytes (which prevents lib_free_string)
        _LIB.lib_export_token.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        _LIB.lib_export_token.restype = ctypes.c_void_p

        # lib_export_hb
        _LIB.lib_export_hb.argtypes = [ctypes.c_void_p]
        _LIB.lib_export_hb.restype = ctypes.c_void_p

        # lib_free_string — takes the raw c_void_p pointer
        _LIB.lib_free_string.argtypes = [ctypes.c_void_p]
        _LIB.lib_free_string.restype = None

        # lib_purge_hb
        _LIB.lib_purge_hb.argtypes = [ctypes.c_void_p]
        _LIB.lib_purge_hb.restype = ctypes.c_int

        # lib_sha_exists
        _LIB.lib_sha_exists.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        _LIB.lib_sha_exists.restype = ctypes.c_int

        # lib_sha_db
        _LIB.lib_sha_db.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        _LIB.lib_sha_db.restype = ctypes.c_int

        # lib_count
        _LIB.lib_count.argtypes = [ctypes.c_void_p, ctypes.c_int]
        _LIB.lib_count.restype = ctypes.c_int

        # lib_registry_size
        _LIB.lib_registry_size.argtypes = [ctypes.c_void_p]
        _LIB.lib_registry_size.restype = ctypes.c_int

        return _LIB
    except OSError:
        return None


# ---------------------------------------------------------------------------
# LibrarianError
# ---------------------------------------------------------------------------

class LibrarianError(Exception):
    """Raised when the Librarian rejects an operation."""
    pass


# ---------------------------------------------------------------------------
# Pure-Python fallback Librarian
# ---------------------------------------------------------------------------

class _PyLibrarian:
    """Pure-Python Librarian fallback when C compilation is unavailable."""

    def __init__(self, rb_path: str, hb_path: str) -> None:
        self._rb_path = rb_path
        self._hb_path = hb_path
        self._registry: dict[str, int] = {}  # sha -> db_id

        # Open connections
        Path(rb_path).parent.mkdir(parents=True, exist_ok=True)
        Path(hb_path).parent.mkdir(parents=True, exist_ok=True)

        self._rb = sqlite3.connect(rb_path)
        self._hb = sqlite3.connect(hb_path)

        # Pragmas
        for conn in (self._rb, self._hb):
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")

        # Create schemas
        from forgeds.knowledge._types import SCHEMA_DDL
        self._rb.executescript(SCHEMA_DDL)

        # Add weight column to RB if missing
        try:
            self._rb.execute("SELECT weight FROM tokens LIMIT 0")
        except sqlite3.OperationalError:
            self._rb.execute(
                "ALTER TABLE tokens ADD COLUMN weight REAL NOT NULL DEFAULT 1.0"
            )

        self._hb.executescript(
            "CREATE TABLE IF NOT EXISTS tokens ("
            "    token_sha    TEXT PRIMARY KEY,"
            "    content      TEXT NOT NULL,"
            "    content_type TEXT NOT NULL,"
            "    module       TEXT NOT NULL,"
            "    page_url     TEXT NOT NULL,"
            "    page_title   TEXT,"
            "    section      TEXT,"
            "    paragraph    INTEGER,"
            "    created_at   TEXT NOT NULL,"
            "    weight       REAL NOT NULL DEFAULT 1.0"
            ");"
            "CREATE TABLE IF NOT EXISTS edges ("
            "    source_sha TEXT NOT NULL,"
            "    target_sha TEXT NOT NULL,"
            "    rel_type   TEXT NOT NULL,"
            "    weight     REAL NOT NULL DEFAULT 0.5,"
            "    PRIMARY KEY (source_sha, target_sha, rel_type)"
            ");"
        )

        # Load existing SHAs
        for row in self._rb.execute("SELECT token_sha FROM tokens"):
            self._registry[row[0]] = LIB_RB
        for row in self._hb.execute("SELECT token_sha FROM tokens"):
            self._registry[row[0]] = LIB_HB

    @staticmethod
    def _compute_sha(content: str, page_url: str, paragraph_num: int) -> str:
        raw = f"{content}\x00{page_url}\x00{paragraph_num}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def create(
        self, db: int, content: str, page_url: str, paragraph_num: int,
        module: str, content_type: str, weight: float,
        metadata: dict | None = None,
    ) -> str:
        sha = self._compute_sha(content, page_url, paragraph_num)

        if sha in self._registry:
            db_name = "RB" if self._registry[sha] == LIB_RB else "HB"
            raise LibrarianError(
                f"SHA collision: {sha[:16]}... already exists in {db_name}"
            )

        meta = metadata or {}

        if db == LIB_RB:
            self._rb.execute(
                "INSERT INTO tokens "
                "(token_sha, revision, content, content_type, module, page_url, "
                " page_title, section, paragraph, page_updated, created_at, "
                " updated_at, git_sha, source_md, weight) "
                "VALUES (?,1,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sha, content, content_type, module, page_url,
                 meta.get("page_title", ""), meta.get("section", ""),
                 paragraph_num, meta.get("page_updated", ""),
                 meta.get("created_at", ""), meta.get("updated_at", ""),
                 meta.get("git_sha", ""), meta.get("source_md", ""), weight),
            )
            self._rb.commit()
        else:
            self._hb.execute(
                "INSERT INTO tokens "
                "(token_sha, content, content_type, module, page_url, "
                " page_title, section, paragraph, created_at, weight) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (sha, content, content_type, module, page_url,
                 meta.get("page_title", ""), meta.get("section", ""),
                 paragraph_num, meta.get("created_at", ""), weight),
            )
            self._hb.commit()

        self._registry[sha] = db
        return sha

    def destroy(self, sha: str) -> None:
        if sha not in self._registry:
            raise LibrarianError("SHA not found in registry")

        db_id = self._registry[sha]
        conn = self._rb if db_id == LIB_RB else self._hb

        conn.execute("DELETE FROM edges WHERE source_sha = ?", (sha,))
        conn.execute("DELETE FROM edges WHERE target_sha = ?", (sha,))
        conn.execute("DELETE FROM tokens WHERE token_sha = ?", (sha,))
        conn.commit()

        del self._registry[sha]

    def adjust_weight(self, sha: str, new_weight: float) -> None:
        if sha not in self._registry:
            raise LibrarianError("SHA not found in registry")

        db_id = self._registry[sha]
        conn = self._rb if db_id == LIB_RB else self._hb
        conn.execute(
            "UPDATE tokens SET weight = ? WHERE token_sha = ?",
            (new_weight, sha),
        )
        conn.commit()

    def create_edge(
        self, source_sha: str, target_sha: str,
        rel_type: str, weight: float,
    ) -> None:
        if source_sha not in self._registry:
            raise LibrarianError("source_sha not found in registry")
        if target_sha not in self._registry:
            raise LibrarianError("target_sha not found in registry")

        src_db = self._registry[source_sha]
        conn = self._rb if src_db == LIB_RB else self._hb
        conn.execute(
            "INSERT OR IGNORE INTO edges (source_sha, target_sha, rel_type, weight) "
            "VALUES (?, ?, ?, ?)",
            (source_sha, target_sha, rel_type, weight),
        )
        conn.commit()

    def export_token(self, sha: str) -> dict | None:
        if sha not in self._registry:
            return None
        db_id = self._registry[sha]
        conn = self._rb if db_id == LIB_RB else self._hb
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM tokens WHERE token_sha = ?", (sha,)
        ).fetchone()
        conn.row_factory = None
        if not row:
            return None
        result = dict(row)
        result["database"] = "RB" if db_id == LIB_RB else "HB"
        return result

    def export_hb(self) -> list[dict]:
        self._hb.row_factory = sqlite3.Row
        rows = self._hb.execute("SELECT * FROM tokens").fetchall()
        self._hb.row_factory = None
        result = []
        for row in rows:
            d = dict(row)
            d["database"] = "HB"
            result.append(d)
        return result

    def purge_hb(self) -> int:
        count = self._hb.execute("SELECT COUNT(*) FROM tokens").fetchone()[0]
        # Remove all HB SHAs from registry
        hb_shas = [sha for sha, db in self._registry.items() if db == LIB_HB]
        for sha in hb_shas:
            del self._registry[sha]
        self._hb.execute("DELETE FROM edges")
        self._hb.execute("DELETE FROM tokens")
        self._hb.commit()
        return count

    def sha_exists(self, sha: str) -> bool:
        return sha in self._registry

    def sha_db(self, sha: str) -> int:
        return self._registry.get(sha, -1)

    def count(self, db: int) -> int:
        conn = self._rb if db == LIB_RB else self._hb
        return conn.execute("SELECT COUNT(*) FROM tokens").fetchone()[0]

    def registry_size(self) -> int:
        return len(self._registry)

    @property
    def rb_conn(self) -> sqlite3.Connection:
        """Direct RB connection for read-only queries (modules, pages, FTS)."""
        return self._rb

    @property
    def rb_metadata_conn(self) -> sqlite3.Connection:
        """Writable RB connection for module/page/edge metadata.

        Use this for INSERT/UPDATE/DELETE on modules, pages, and edges
        tables.  NEVER write tokens through this connection — use the
        Librarian create/destroy methods instead.
        """
        return self._rb

    @property
    def hb_conn(self) -> sqlite3.Connection:
        """Direct HB connection for read-only queries."""
        return self._hb

    def close(self) -> None:
        self._rb.close()
        self._hb.close()
        self._registry.clear()


# ---------------------------------------------------------------------------
# Unified LibrarianHandle
# ---------------------------------------------------------------------------

class LibrarianHandle:
    """Unified interface wrapping either C accelerator or Python fallback.

    This is the sole authority for token lifecycle management.
    All token creation, destruction, and weight mutation MUST go through
    this handle.
    """

    def __init__(self, rb_path: str, hb_path: str) -> None:
        self._rb_path = rb_path
        self._hb_path = hb_path
        self._c_handle: ctypes.c_void_p | None = None
        self._py: _PyLibrarian | None = None

        lib = _load_lib()
        if lib:
            handle = lib.lib_open(
                rb_path.encode("utf-8"), hb_path.encode("utf-8"),
            )
            if handle:
                self._c_handle = handle
                self._lib = lib
                logger.info("Librarian opened (C accelerator)")
                return

        # Fallback to pure Python
        self._py = _PyLibrarian(rb_path, hb_path)
        logger.info("Librarian opened (Python fallback)")

    @property
    def is_accelerated(self) -> bool:
        return self._c_handle is not None

    # ------------------------------------------------------------------
    # Token operations
    # ------------------------------------------------------------------

    def create(
        self,
        db: int,
        content: str,
        page_url: str,
        paragraph_num: int,
        module: str,
        content_type: str,
        weight: float = 1.0,
        metadata: dict | None = None,
    ) -> str:
        """Create a token. Returns SHA. Raises LibrarianError on collision."""
        if self._c_handle:
            meta_json = json.dumps(metadata).encode("utf-8") if metadata else None
            result = self._lib.lib_create(
                self._c_handle, db,
                content.encode("utf-8"),
                page_url.encode("utf-8"),
                paragraph_num,
                module.encode("utf-8"),
                content_type.encode("utf-8"),
                float(weight),
                meta_json,
            )
            if not result.ok:
                raise LibrarianError(result.error.decode("utf-8", errors="replace"))
            return result.sha.decode("utf-8")

        return self._py.create(
            db, content, page_url, paragraph_num,
            module, content_type, weight, metadata,
        )

    def destroy(self, sha: str) -> None:
        """Destroy a token by SHA. Raises LibrarianError if not found."""
        if self._c_handle:
            result = self._lib.lib_destroy(
                self._c_handle, sha.encode("utf-8"),
            )
            if not result.ok:
                raise LibrarianError(result.error.decode("utf-8", errors="replace"))
            return

        self._py.destroy(sha)

    def adjust_weight(self, sha: str, new_weight: float) -> None:
        """Adjust token weight — the ONLY mutable property."""
        if self._c_handle:
            result = self._lib.lib_adjust_weight(
                self._c_handle, sha.encode("utf-8"), float(new_weight),
            )
            if not result.ok:
                raise LibrarianError(result.error.decode("utf-8", errors="replace"))
            return

        self._py.adjust_weight(sha, new_weight)

    def create_edge(
        self, source_sha: str, target_sha: str,
        rel_type: str, weight: float = 0.5,
    ) -> None:
        """Create an edge between two tokens (both must exist)."""
        if self._c_handle:
            result = self._lib.lib_create_edge(
                self._c_handle,
                source_sha.encode("utf-8"),
                target_sha.encode("utf-8"),
                rel_type.encode("utf-8"),
                float(weight),
            )
            if not result.ok:
                raise LibrarianError(result.error.decode("utf-8", errors="replace"))
            return

        self._py.create_edge(source_sha, target_sha, rel_type, weight)

    # ------------------------------------------------------------------
    # Closed-world output
    # ------------------------------------------------------------------

    def export_token(self, sha: str) -> dict | None:
        """Export a token as a JSON dict. Closed-world output gate."""
        if self._c_handle:
            ptr = self._lib.lib_export_token(
                self._c_handle, sha.encode("utf-8"),
            )
            if not ptr:
                return None
            raw_bytes = ctypes.string_at(ptr)
            result = json.loads(raw_bytes.decode("utf-8"))
            self._lib.lib_free_string(ptr)
            return result

        return self._py.export_token(sha)

    def export_hb(self) -> list[dict]:
        """Export all HB tokens as a list of dicts."""
        if self._c_handle:
            ptr = self._lib.lib_export_hb(self._c_handle)
            if not ptr:
                return []
            raw_bytes = ctypes.string_at(ptr)
            result = json.loads(raw_bytes.decode("utf-8"))
            self._lib.lib_free_string(ptr)
            return result

        return self._py.export_hb()

    # ------------------------------------------------------------------
    # HB lifecycle
    # ------------------------------------------------------------------

    def purge_hb(self) -> int:
        """Destroy all HB tokens. Called after analysis + user confirmation."""
        if self._c_handle:
            return self._lib.lib_purge_hb(self._c_handle)
        return self._py.purge_hb()

    # ------------------------------------------------------------------
    # Registry queries
    # ------------------------------------------------------------------

    def sha_exists(self, sha: str) -> bool:
        if self._c_handle:
            return bool(self._lib.lib_sha_exists(
                self._c_handle, sha.encode("utf-8"),
            ))
        return self._py.sha_exists(sha)

    def sha_db(self, sha: str) -> int:
        """Which database holds this SHA: 0=RB, 1=HB, -1=not found."""
        if self._c_handle:
            return self._lib.lib_sha_db(
                self._c_handle, sha.encode("utf-8"),
            )
        return self._py.sha_db(sha)

    def count(self, db: int) -> int:
        if self._c_handle:
            return self._lib.lib_count(self._c_handle, db)
        return self._py.count(db)

    def registry_size(self) -> int:
        if self._c_handle:
            return self._lib.lib_registry_size(self._c_handle)
        return self._py.registry_size()

    # ------------------------------------------------------------------
    # Direct DB access (read-only, for modules/pages/FTS queries)
    # ------------------------------------------------------------------

    @property
    def rb_conn(self) -> sqlite3.Connection:
        """Direct RB connection for read-only queries.

        Use this ONLY for reading modules, pages, FTS search, and
        graph_builder queries. NEVER insert/update/delete tokens through
        this connection — use the Librarian methods instead.
        """
        if self._py:
            return self._py.rb_conn
        # For C handle, open a read-only connection
        if not hasattr(self, "_rb_readonly"):
            self._rb_readonly = sqlite3.connect(
                self._rb_path,
                check_same_thread=False,
            )
            self._rb_readonly.execute("PRAGMA query_only=ON")
        return self._rb_readonly

    @property
    def rb_metadata_conn(self) -> sqlite3.Connection:
        """Writable RB connection for module/page/edge metadata.

        Use this for INSERT/UPDATE/DELETE on modules, pages, and edges
        tables.  NEVER write tokens through this connection — use the
        Librarian create/destroy methods instead.
        """
        if self._py:
            return self._py.rb_metadata_conn
        if not hasattr(self, "_rb_writable"):
            self._rb_writable = sqlite3.connect(
                self._rb_path,
                check_same_thread=False,
            )
            self._rb_writable.execute("PRAGMA journal_mode=WAL")
            self._rb_writable.execute("PRAGMA synchronous=NORMAL")
            self._rb_writable.execute("PRAGMA foreign_keys=ON")
        return self._rb_writable

    @property
    def hb_conn(self) -> sqlite3.Connection:
        """Direct HB connection for read-only queries."""
        if self._py:
            return self._py.hb_conn
        if not hasattr(self, "_hb_readonly"):
            self._hb_readonly = sqlite3.connect(
                self._hb_path,
                check_same_thread=False,
            )
            self._hb_readonly.execute("PRAGMA query_only=ON")
        return self._hb_readonly

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        if self._c_handle:
            self._lib.lib_close(self._c_handle)
            self._c_handle = None
            if hasattr(self, "_rb_readonly"):
                self._rb_readonly.close()
            if hasattr(self, "_rb_writable"):
                self._rb_writable.close()
            if hasattr(self, "_hb_readonly"):
                self._hb_readonly.close()
        elif self._py:
            self._py.close()
            self._py = None

    def __del__(self) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Convenience opener
# ---------------------------------------------------------------------------

def open_librarian(rb_path: str | Path, hb_path: str | Path) -> LibrarianHandle:
    """Open the Librarian with both database paths.

    Tries C accelerator first; falls back to pure Python.
    """
    return LibrarianHandle(str(rb_path), str(hb_path))
