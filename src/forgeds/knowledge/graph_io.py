"""Python bindings for kb_core.c with pure-Python fallback.

Follows the ctypes auto-compile pattern: try gcc, fallback to cl.exe
on Windows, pure-Python fallback if no compiler is available.

Usage:
    from forgeds.knowledge.graph_io import load_graph, GraphHandle
    g = load_graph("knowledge/knowledge.db")
    print(g.node_count(), g.edge_count())
    neighbors = g.neighbors(some_node_idx)
    bfs_result = g.bfs(start_idx, max_depth=3)
    scores = g.pagerank()
    g.free()
"""

from __future__ import annotations

import ctypes
import logging
import platform
import sqlite3
import subprocess
from collections import defaultdict, deque
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auto-compile C accelerator
# ---------------------------------------------------------------------------

_C_SOURCE = Path(__file__).parent / "kb_core.c"
_SO_NAME = "kb_core.dll" if platform.system() == "Windows" else "kb_core.so"
_SO_PATH = Path(__file__).parent / _SO_NAME
_LIB: ctypes.CDLL | None = None


def _so_is_stale() -> bool:
    """Return True if the compiled .so/.dll is older than kb_core.c."""
    if not _SO_PATH.exists() or not _C_SOURCE.exists():
        return True
    return _C_SOURCE.stat().st_mtime > _SO_PATH.stat().st_mtime


def _try_compile() -> bool:
    """Attempt to compile kb_core.c into a shared library."""
    if not _C_SOURCE.exists():
        return False

    src = str(_C_SOURCE)
    out = str(_SO_PATH)

    logger.info("Compiling C accelerator: %s -> %s", src, out)

    # Try gcc / cc first
    for compiler in ("gcc", "cc"):
        try:
            result = subprocess.run(
                [compiler, "-O2", "-shared", "-fPIC", "-o", out, src, "-lsqlite3"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and _SO_PATH.exists():
                logger.info("C accelerator compiled successfully with %s", compiler)
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # Try MSVC on Windows
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["cl.exe", "/LD", "/O2", f"/Fe:{out}", src, "sqlite3.lib"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and _SO_PATH.exists():
                logger.info("C accelerator compiled successfully with cl.exe")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    logger.warning("C accelerator compilation failed — using Python fallback")
    return False


def _load_lib() -> ctypes.CDLL | None:
    """Load the compiled shared library, compiling first if needed.

    Recompiles if the .c source is newer than the compiled binary.
    """
    global _LIB
    if _LIB is not None:
        return _LIB

    if not _SO_PATH.exists() or _so_is_stale():
        if not _try_compile():
            return None

    try:
        _LIB = ctypes.CDLL(str(_SO_PATH))

        # Set up function signatures
        _LIB.kb_load_from_db.argtypes = [ctypes.c_char_p]
        _LIB.kb_load_from_db.restype = ctypes.c_void_p

        _LIB.kb_node_count.argtypes = [ctypes.c_void_p]
        _LIB.kb_node_count.restype = ctypes.c_int

        _LIB.kb_edge_count.argtypes = [ctypes.c_void_p]
        _LIB.kb_edge_count.restype = ctypes.c_int

        _LIB.kb_find_node.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        _LIB.kb_find_node.restype = ctypes.c_int

        _LIB.kb_node_sha.argtypes = [ctypes.c_void_p, ctypes.c_int]
        _LIB.kb_node_sha.restype = ctypes.c_char_p

        _LIB.kb_neighbors.argtypes = [
            ctypes.c_void_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_float),
            ctypes.c_int,
        ]
        _LIB.kb_neighbors.restype = ctypes.c_int

        _LIB.kb_traverse_bfs.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int), ctypes.c_int,
        ]
        _LIB.kb_traverse_bfs.restype = ctypes.c_int

        _LIB.kb_subgraph.argtypes = [
            ctypes.c_void_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int), ctypes.c_int,
        ]
        _LIB.kb_subgraph.restype = ctypes.c_int

        _LIB.kb_pagerank.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_float),
            ctypes.c_int, ctypes.c_float,
        ]
        _LIB.kb_pagerank.restype = ctypes.c_int

        _LIB.kb_free.argtypes = [ctypes.c_void_p]
        _LIB.kb_free.restype = None

        return _LIB
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Pure-Python fallback graph
# ---------------------------------------------------------------------------

class _PyGraph:
    """Pure-Python graph using adjacency lists. Same interface as C version."""

    def __init__(self, db_path: str) -> None:
        self.nodes: list[str] = []           # index -> SHA
        self._sha_to_idx: dict[str, int] = {}
        self.adj: dict[int, list[tuple[int, float]]] = defaultdict(list)

        conn = sqlite3.connect(db_path)
        try:
            # Load nodes
            for row in conn.execute("SELECT token_sha FROM tokens"):
                sha = row[0]
                if sha not in self._sha_to_idx:
                    idx = len(self.nodes)
                    self.nodes.append(sha)
                    self._sha_to_idx[sha] = idx

            # Load edges
            self._n_edges = 0
            for row in conn.execute("SELECT source_sha, target_sha, weight FROM edges"):
                src_sha, dst_sha, weight = row
                si = self._sha_to_idx.get(src_sha)
                di = self._sha_to_idx.get(dst_sha)
                if si is not None and di is not None:
                    self.adj[si].append((di, weight))
                    self._n_edges += 1
        finally:
            conn.close()

    def node_count(self) -> int:
        return len(self.nodes)

    def edge_count(self) -> int:
        return self._n_edges

    def find_node(self, sha: str) -> int:
        return self._sha_to_idx.get(sha, -1)

    def node_sha(self, idx: int) -> str:
        if 0 <= idx < len(self.nodes):
            return self.nodes[idx]
        return ""

    def neighbors(self, node_idx: int) -> list[tuple[int, float]]:
        return list(self.adj.get(node_idx, []))

    def bfs(self, start_idx: int, max_depth: int = 3, max_nodes: int = 100_000) -> list[int]:
        if start_idx < 0 or start_idx >= len(self.nodes):
            return []

        visited = set()
        result: list[int] = []
        queue: deque[tuple[int, int]] = deque([(start_idx, 0)])
        visited.add(start_idx)

        while queue and len(result) < max_nodes:
            node, depth = queue.popleft()
            result.append(node)
            if depth >= max_depth:
                continue
            for nb, _w in self.adj.get(node, []):
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, depth + 1))

        return result

    def subgraph(self, start_idx: int, max_nodes: int = 100_000) -> list[int]:
        """Connected component via BFS. Capped to prevent OOM on large graphs."""
        if start_idx < 0 or start_idx >= len(self.nodes):
            return []

        visited = set()
        result: list[int] = []
        queue: deque[int] = deque([start_idx])
        visited.add(start_idx)

        while queue and len(result) < max_nodes:
            node = queue.popleft()
            result.append(node)
            for nb, _w in self.adj.get(node, []):
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)

        return result

    def pagerank(self, n_iterations: int = 20, damping: float = 0.85) -> list[float]:
        n = len(self.nodes)
        if n == 0:
            return []

        scores = [1.0 / n] * n
        new_scores = [0.0] * n
        base = (1.0 - damping) / n

        for _ in range(n_iterations):
            for i in range(n):
                new_scores[i] = base
            for src in range(n):
                neighbors = self.adj.get(src, [])
                if not neighbors:
                    continue
                contrib = damping * scores[src] / len(neighbors)
                for dst, _w in neighbors:
                    new_scores[dst] += contrib
            scores, new_scores = new_scores, scores

        return scores


# ---------------------------------------------------------------------------
# Unified GraphHandle
# ---------------------------------------------------------------------------

class GraphHandle:
    """Unified interface wrapping either C accelerator or Python fallback."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._c_handle: ctypes.c_void_p | None = None
        self._py_graph: _PyGraph | None = None

        lib = _load_lib()
        if lib:
            handle = lib.kb_load_from_db(db_path.encode("utf-8"))
            if handle:
                self._c_handle = handle
                self._lib = lib
                return

        # Fallback to pure Python
        self._py_graph = _PyGraph(db_path)

    @property
    def is_accelerated(self) -> bool:
        return self._c_handle is not None

    def node_count(self) -> int:
        if self._c_handle:
            return self._lib.kb_node_count(self._c_handle)
        return self._py_graph.node_count()

    def edge_count(self) -> int:
        if self._c_handle:
            return self._lib.kb_edge_count(self._c_handle)
        return self._py_graph.edge_count()

    def find_node(self, sha: str) -> int:
        if self._c_handle:
            return self._lib.kb_find_node(self._c_handle, sha.encode("utf-8"))
        return self._py_graph.find_node(sha)

    def node_sha(self, idx: int) -> str:
        if self._c_handle:
            result = self._lib.kb_node_sha(self._c_handle, idx)
            return result.decode("utf-8") if result else ""
        return self._py_graph.node_sha(idx)

    def neighbors(self, node_idx: int, max_results: int = 1024) -> list[tuple[int, float]]:
        if self._c_handle:
            out = (ctypes.c_int * max_results)()
            weights = (ctypes.c_float * max_results)()
            count = self._lib.kb_neighbors(
                self._c_handle, node_idx, out, weights, max_results,
            )
            return [(out[i], weights[i]) for i in range(count)]
        return self._py_graph.neighbors(node_idx)

    def bfs(self, start_idx: int, max_depth: int = 3, max_results: int = 4096) -> list[int]:
        if self._c_handle:
            out = (ctypes.c_int * max_results)()
            count = self._lib.kb_traverse_bfs(
                self._c_handle, start_idx, max_depth, out, max_results,
            )
            return [out[i] for i in range(count)]
        return self._py_graph.bfs(start_idx, max_depth)

    def subgraph(self, start_idx: int, max_results: int = 8192) -> list[int]:
        if self._c_handle:
            out = (ctypes.c_int * max_results)()
            count = self._lib.kb_subgraph(self._c_handle, start_idx, out, max_results)
            return [out[i] for i in range(count)]
        return self._py_graph.subgraph(start_idx)

    def pagerank(self, n_iterations: int = 20, damping: float = 0.85) -> list[float]:
        if self._c_handle:
            n = self.node_count()
            scores = (ctypes.c_float * n)()
            self._lib.kb_pagerank(self._c_handle, scores, n_iterations, ctypes.c_float(damping))
            return [scores[i] for i in range(n)]
        return self._py_graph.pagerank(n_iterations, damping)

    def free(self) -> None:
        if self._c_handle:
            self._lib.kb_free(self._c_handle)
            self._c_handle = None
        self._py_graph = None

    def __del__(self) -> None:
        self.free()


# ---------------------------------------------------------------------------
# Convenience loader
# ---------------------------------------------------------------------------

def load_graph(db_path: str | Path) -> GraphHandle:
    """Load a knowledge graph from a SQLite database.

    Tries the C accelerator first; falls back to pure Python.
    """
    return GraphHandle(str(db_path))
