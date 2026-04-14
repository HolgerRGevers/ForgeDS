/*
 * kb_core.c — In-memory graph compute layer for ForgeDS knowledge base.
 *
 * Reads tokens + edges from knowledge.db via SQLite's C API, loads them
 * into a Compressed Sparse Row (CSR) format for O(1) neighbor access,
 * then exposes BFS, subgraph extraction, and PageRank to Python via ctypes.
 *
 * Build: gcc -O2 -shared -fPIC -o kb_core.so kb_core.c -lsqlite3
 *   (or) cl.exe /LD /O2 kb_core.c sqlite3.lib  (Windows)
 *
 * The Python bindings in graph_io.py auto-compile this if a compiler
 * is available, with a pure-Python fallback otherwise.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sqlite3.h>

/* --------------------------------------------------------------------------
 * Hash map for SHA -> node index (Fix #10 & #11)
 *
 * Open-addressing hash table with FNV-1a hash. Replaces O(n) linear
 * scans in _find_or_add_node and kb_find_node with O(1) amortized.
 * -------------------------------------------------------------------------- */

#define HASH_LOAD_FACTOR 0.7

typedef struct {
    char  *sha;     /* NULL = empty slot */
    int    idx;
} HashEntry;

typedef struct {
    HashEntry *entries;
    int        capacity;
    int        count;
} ShaHashMap;

static unsigned int _fnv1a(const char *s) {
    unsigned int h = 2166136261u;
    for (; *s; s++) {
        h ^= (unsigned char)*s;
        h *= 16777619u;
    }
    return h;
}

static int _hashmap_init(ShaHashMap *m, int capacity) {
    m->capacity = capacity;
    m->count = 0;
    m->entries = calloc(capacity, sizeof(HashEntry));
    if (!m->entries) {
        m->capacity = 0;
        return -1;
    }
    return 0;
}

static void _hashmap_free(ShaHashMap *m) {
    if (!m->entries) return;
    for (int i = 0; i < m->capacity; i++)
        free(m->entries[i].sha);
    free(m->entries);
    m->entries = NULL;
}

static void _hashmap_grow(ShaHashMap *m);

static int _hashmap_get(const ShaHashMap *m, const char *sha) {
    unsigned int h = _fnv1a(sha) % (unsigned int)m->capacity;
    for (int i = 0; i < m->capacity; i++) {
        int slot = (h + i) % m->capacity;
        if (!m->entries[slot].sha)
            return -1;  /* empty slot — not found */
        if (strcmp(m->entries[slot].sha, sha) == 0)
            return m->entries[slot].idx;
    }
    return -1;
}

static int _hashmap_put(ShaHashMap *m, const char *sha, int idx) {
    if (!m->entries) return -1;
    if (m->count >= (int)(m->capacity * HASH_LOAD_FACTOR))
        _hashmap_grow(m);
    if (!m->entries) return -1;  /* grow may have failed */

    unsigned int h = _fnv1a(sha) % (unsigned int)m->capacity;
    for (int i = 0; i < m->capacity; i++) {
        int slot = (h + i) % m->capacity;
        if (!m->entries[slot].sha) {
            m->entries[slot].sha = strdup(sha);
            if (!m->entries[slot].sha) return -1;  /* OOM */
            m->entries[slot].idx = idx;
            m->count++;
            return 0;
        }
        if (strcmp(m->entries[slot].sha, sha) == 0) {
            m->entries[slot].idx = idx;  /* update existing */
            return 0;
        }
    }
    return -1;  /* table full (should not happen with load factor check) */
}

static void _hashmap_grow(ShaHashMap *m) {
    int old_cap = m->capacity;
    HashEntry *old = m->entries;

    int new_cap = old_cap * 2;
    HashEntry *new_entries = calloc(new_cap, sizeof(HashEntry));
    if (!new_entries) {
        /* OOM — leave map unchanged; _hashmap_put will detect via entries check */
        return;
    }
    m->entries = new_entries;
    m->capacity = new_cap;
    m->count = 0;

    for (int i = 0; i < old_cap; i++) {
        if (old[i].sha) {
            _hashmap_put(m, old[i].sha, old[i].idx);
            free(old[i].sha);
        }
    }
    free(old);
}


/* --------------------------------------------------------------------------
 * CSR Graph Structure
 * -------------------------------------------------------------------------- */

#define MAX_SHA_LEN 65   /* SHA-256 hex + null */

typedef struct {
    char sha[MAX_SHA_LEN];
} TokenId;

typedef struct {
    /* Node data */
    int         n_nodes;
    TokenId    *node_ids;       /* node_ids[i] = SHA of node i */

    /* CSR adjacency (outgoing edges) */
    int        *row_ptr;        /* row_ptr[i] .. row_ptr[i+1] = edge range for node i */
    int        *col_idx;        /* col_idx[j] = target node index */
    float      *weights;        /* weights[j] = edge weight */
    int         n_edges;

    /* Hash map for O(1) SHA -> node index lookup (Fix #10 & #11) */
    ShaHashMap  sha_map;
} KBGraph;

/* --------------------------------------------------------------------------
 * Forward declarations
 * -------------------------------------------------------------------------- */

#ifdef _WIN32
  #define KB_EXPORT __declspec(dllexport)
#else
  #define KB_EXPORT __attribute__((visibility("default")))
#endif

KB_EXPORT KBGraph* kb_load_from_db(const char *db_path);
KB_EXPORT int      kb_node_count(const KBGraph *g);
KB_EXPORT int      kb_edge_count(const KBGraph *g);
KB_EXPORT int      kb_find_node(const KBGraph *g, const char *sha);
KB_EXPORT int      kb_neighbors(const KBGraph *g, int node_idx, int *out_buf, float *weight_buf, int buf_size);
KB_EXPORT int      kb_traverse_bfs(const KBGraph *g, int start_idx, int max_depth, int *out_buf, int buf_size);
KB_EXPORT int      kb_subgraph(const KBGraph *g, int start_idx, int *out_buf, int buf_size);
KB_EXPORT int      kb_pagerank(const KBGraph *g, float *out_scores, int n_iterations, float damping);
KB_EXPORT void     kb_free(KBGraph *g);
KB_EXPORT const char* kb_node_sha(const KBGraph *g, int node_idx);

/* --------------------------------------------------------------------------
 * Internal helpers
 * -------------------------------------------------------------------------- */

static int _find_or_add_node(KBGraph *g, const char *sha, int *capacity) {
    /* O(1) amortized lookup via hash map (Fix #10) */
    int idx = _hashmap_get(&g->sha_map, sha);
    if (idx >= 0)
        return idx;

    /* Add new node */
    if (g->n_nodes >= *capacity) {
        int new_cap = *capacity * 2;
        TokenId *tmp = realloc(g->node_ids, sizeof(TokenId) * new_cap);
        if (!tmp) {
            fprintf(stderr, "kb_core: OOM expanding node array\n");
            return -1;
        }
        g->node_ids = tmp;
        *capacity = new_cap;
    }
    idx = g->n_nodes;
    strncpy(g->node_ids[idx].sha, sha, MAX_SHA_LEN - 1);
    g->node_ids[idx].sha[MAX_SHA_LEN - 1] = '\0';
    if (_hashmap_put(&g->sha_map, sha, idx) < 0) {
        fprintf(stderr, "kb_core: OOM inserting into hash map\n");
        return -1;
    }
    g->n_nodes++;
    return idx;
}

/* Temp edge list used during loading before CSR conversion */
typedef struct {
    int src, dst;
    float weight;
} TempEdge;

/* --------------------------------------------------------------------------
 * Load from SQLite -> CSR
 * -------------------------------------------------------------------------- */

KB_EXPORT KBGraph* kb_load_from_db(const char *db_path) {
    sqlite3 *db = NULL;
    sqlite3_stmt *stmt = NULL;
    int rc;

    rc = sqlite3_open_v2(db_path, &db, SQLITE_OPEN_READONLY, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "kb_core: cannot open %s: %s\n", db_path, sqlite3_errmsg(db));
        return NULL;
    }

    KBGraph *g = calloc(1, sizeof(KBGraph));
    if (!g) {
        sqlite3_close(db);
        return NULL;
    }
    int node_cap = 4096;
    g->node_ids = malloc(sizeof(TokenId) * node_cap);
    if (!g->node_ids) {
        free(g);
        sqlite3_close(db);
        return NULL;
    }
    g->n_nodes = 0;
    if (_hashmap_init(&g->sha_map, 8192) < 0) {
        free(g->node_ids);
        free(g);
        sqlite3_close(db);
        return NULL;
    }

    /* Pass 1: collect all unique node SHAs from tokens table */
    rc = sqlite3_prepare_v2(db, "SELECT token_sha FROM tokens", -1, &stmt, NULL);
    if (rc == SQLITE_OK) {
        while (sqlite3_step(stmt) == SQLITE_ROW) {
            const char *sha = (const char *)sqlite3_column_text(stmt, 0);
            _find_or_add_node(g, sha, &node_cap);
        }
        sqlite3_finalize(stmt);
    }

    /* Pass 2: load edges into temp list */
    int edge_cap = 8192;
    TempEdge *temp_edges = malloc(sizeof(TempEdge) * edge_cap);
    if (!temp_edges) {
        kb_free(g);
        sqlite3_close(db);
        return NULL;
    }
    int n_temp = 0;

    rc = sqlite3_prepare_v2(db, "SELECT source_sha, target_sha, weight FROM edges", -1, &stmt, NULL);
    if (rc == SQLITE_OK) {
        while (sqlite3_step(stmt) == SQLITE_ROW) {
            const char *src_sha = (const char *)sqlite3_column_text(stmt, 0);
            const char *dst_sha = (const char *)sqlite3_column_text(stmt, 1);
            float w = (float)sqlite3_column_double(stmt, 2);

            int si = _find_or_add_node(g, src_sha, &node_cap);
            int di = _find_or_add_node(g, dst_sha, &node_cap);
            if (si < 0 || di < 0) continue;  /* OOM in node addition — skip edge */

            if (n_temp >= edge_cap) {
                int new_cap = edge_cap * 2;
                TempEdge *tmp = realloc(temp_edges, sizeof(TempEdge) * new_cap);
                if (!tmp) {
                    fprintf(stderr, "kb_core: OOM expanding edge list\n");
                    break;
                }
                temp_edges = tmp;
                edge_cap = new_cap;
            }
            temp_edges[n_temp].src = si;
            temp_edges[n_temp].dst = di;
            temp_edges[n_temp].weight = w;
            n_temp++;
        }
        sqlite3_finalize(stmt);
    }

    sqlite3_close(db);

    /* Convert temp edge list -> CSR */
    g->n_edges = n_temp;
    g->row_ptr = calloc(g->n_nodes + 1, sizeof(int));
    g->col_idx = n_temp ? malloc(sizeof(int) * n_temp) : NULL;
    g->weights = n_temp ? malloc(sizeof(float) * n_temp) : NULL;

    if (!g->row_ptr || (n_temp && (!g->col_idx || !g->weights))) {
        free(temp_edges);
        kb_free(g);
        return NULL;
    }

    /* Count edges per source node */
    for (int i = 0; i < n_temp; i++)
        g->row_ptr[temp_edges[i].src + 1]++;

    /* Prefix sum */
    for (int i = 1; i <= g->n_nodes; i++)
        g->row_ptr[i] += g->row_ptr[i - 1];

    /* Fill col_idx and weights using a working copy of row_ptr */
    int *cursor = malloc(sizeof(int) * (g->n_nodes + 1));
    if (!cursor) {
        free(temp_edges);
        kb_free(g);
        return NULL;
    }
    memcpy(cursor, g->row_ptr, sizeof(int) * (g->n_nodes + 1));

    for (int i = 0; i < n_temp; i++) {
        int pos = cursor[temp_edges[i].src]++;
        g->col_idx[pos] = temp_edges[i].dst;
        g->weights[pos] = temp_edges[i].weight;
    }

    free(cursor);
    free(temp_edges);

    return g;
}

/* --------------------------------------------------------------------------
 * Query functions
 * -------------------------------------------------------------------------- */

KB_EXPORT int kb_node_count(const KBGraph *g) {
    return g ? g->n_nodes : 0;
}

KB_EXPORT int kb_edge_count(const KBGraph *g) {
    return g ? g->n_edges : 0;
}

KB_EXPORT int kb_find_node(const KBGraph *g, const char *sha) {
    /* O(1) amortized via hash map (Fix #11) */
    if (!g || !sha) return -1;
    return _hashmap_get(&g->sha_map, sha);
}

KB_EXPORT const char* kb_node_sha(const KBGraph *g, int node_idx) {
    if (!g || node_idx < 0 || node_idx >= g->n_nodes) return NULL;
    return g->node_ids[node_idx].sha;
}

KB_EXPORT int kb_neighbors(const KBGraph *g, int node_idx,
                           int *out_buf, float *weight_buf, int buf_size) {
    if (!g || node_idx < 0 || node_idx >= g->n_nodes) return 0;

    int start = g->row_ptr[node_idx];
    int end = g->row_ptr[node_idx + 1];
    int count = end - start;
    if (count > buf_size) count = buf_size;

    for (int i = 0; i < count; i++) {
        out_buf[i] = g->col_idx[start + i];
        if (weight_buf)
            weight_buf[i] = g->weights[start + i];
    }
    return count;
}

KB_EXPORT int kb_traverse_bfs(const KBGraph *g, int start_idx,
                              int max_depth, int *out_buf, int buf_size) {
    if (!g || start_idx < 0 || start_idx >= g->n_nodes) return 0;

    char *visited = calloc(g->n_nodes, 1);
    int *queue = malloc(sizeof(int) * g->n_nodes);
    int *depth = malloc(sizeof(int) * g->n_nodes);
    if (!visited || !queue || !depth) {
        free(visited);
        free(queue);
        free(depth);
        return 0;
    }
    int head = 0, tail = 0;
    int out_count = 0;

    visited[start_idx] = 1;
    queue[tail] = start_idx;
    depth[tail] = 0;
    tail++;

    while (head < tail) {
        int node = queue[head];
        int d = depth[head];
        head++;

        if (out_count < buf_size) {
            out_buf[out_count++] = node;
        }

        if (d >= max_depth) continue;

        int s = g->row_ptr[node];
        int e = g->row_ptr[node + 1];
        for (int i = s; i < e; i++) {
            int nb = g->col_idx[i];
            if (!visited[nb]) {
                visited[nb] = 1;
                queue[tail] = nb;
                depth[tail] = d + 1;
                tail++;
            }
        }
    }

    free(visited);
    free(queue);
    free(depth);
    return out_count;
}

KB_EXPORT int kb_subgraph(const KBGraph *g, int start_idx,
                          int *out_buf, int buf_size) {
    /* Connected component via BFS with unlimited depth */
    return kb_traverse_bfs(g, start_idx, g->n_nodes, out_buf, buf_size);
}

KB_EXPORT int kb_pagerank(const KBGraph *g, float *out_scores,
                          int n_iterations, float damping) {
    if (!g || !out_scores || g->n_nodes == 0) return 0;

    int n = g->n_nodes;
    float *scores = out_scores;
    float *buf_a = malloc(sizeof(float) * n);
    float *buf_b = malloc(sizeof(float) * n);
    if (!buf_a || !buf_b) {
        free(buf_a);
        free(buf_b);
        return 0;
    }
    float init_val = 1.0f / n;

    for (int i = 0; i < n; i++)
        buf_a[i] = init_val;

    /* Double-buffer swap: alternate between buf_a and buf_b (Fix #12 C-side) */
    float *cur = buf_a;
    float *nxt = buf_b;

    for (int iter = 0; iter < n_iterations; iter++) {
        for (int i = 0; i < n; i++)
            nxt[i] = (1.0f - damping) / n;

        for (int src = 0; src < n; src++) {
            int s = g->row_ptr[src];
            int e = g->row_ptr[src + 1];
            int out_degree = e - s;
            if (out_degree == 0) continue;

            float contrib = damping * cur[src] / out_degree;
            for (int j = s; j < e; j++) {
                nxt[g->col_idx[j]] += contrib;
            }
        }

        /* Swap buffers */
        float *tmp = cur;
        cur = nxt;
        nxt = tmp;
    }

    /* Copy final scores to output buffer */
    memcpy(scores, cur, sizeof(float) * n);

    free(buf_a);
    free(buf_b);
    return n;
}

KB_EXPORT void kb_free(KBGraph *g) {
    if (!g) return;
    _hashmap_free(&g->sha_map);
    free(g->node_ids);
    free(g->row_ptr);
    free(g->col_idx);
    free(g->weights);
    free(g);
}
