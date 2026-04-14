/*
 * sha_hashmap.h — Open-addressing hash map for SHA-256 hex strings.
 *
 * Shared between kb_core.c (graph compute) and librarian.c (token lifecycle).
 * Uses FNV-1a hash with linear probing and automatic growth at 70% load.
 *
 * Usage:
 *     ShaHashMap map;
 *     sha_map_init(&map, 1024);
 *     sha_map_put(&map, "abc123...", 42);
 *     int idx = sha_map_get(&map, "abc123...");  // 42 or -1
 *     sha_map_remove(&map, "abc123...");          // 0 on success
 *     sha_map_free(&map);
 */

#ifndef SHA_HASHMAP_H
#define SHA_HASHMAP_H

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#define SHA_MAP_LOAD_FACTOR 0.7
#define SHA_MAP_TOMBSTONE ((char *)(intptr_t)-1)

typedef struct {
    char *sha;   /* NULL = empty, TOMBSTONE = deleted */
    int   val;
} ShaMapEntry;

typedef struct {
    ShaMapEntry *entries;
    int          capacity;
    int          count;       /* live entries (excludes tombstones) */
    int          occupied;    /* live + tombstones (for load factor) */
} ShaHashMap;

/* ------------------------------------------------------------------ */
/* FNV-1a hash                                                        */
/* ------------------------------------------------------------------ */

static unsigned int _sha_map_fnv1a(const char *s) {
    unsigned int h = 2166136261u;
    for (; *s; s++) {
        h ^= (unsigned char)*s;
        h *= 16777619u;
    }
    return h;
}

/* ------------------------------------------------------------------ */
/* Init / Free                                                        */
/* ------------------------------------------------------------------ */

static int sha_map_init(ShaHashMap *m, int capacity) {
    m->capacity = capacity;
    m->count = 0;
    m->occupied = 0;
    m->entries = (ShaMapEntry *)calloc(capacity, sizeof(ShaMapEntry));
    if (!m->entries) {
        m->capacity = 0;
        return -1;
    }
    return 0;
}

static void sha_map_free(ShaHashMap *m) {
    if (!m->entries) return;
    for (int i = 0; i < m->capacity; i++) {
        if (m->entries[i].sha && m->entries[i].sha != SHA_MAP_TOMBSTONE)
            free(m->entries[i].sha);
    }
    free(m->entries);
    m->entries = NULL;
    m->capacity = 0;
    m->count = 0;
    m->occupied = 0;
}

/* ------------------------------------------------------------------ */
/* Forward declare grow (used by put)                                 */
/* ------------------------------------------------------------------ */

static void _sha_map_grow(ShaHashMap *m);

/* ------------------------------------------------------------------ */
/* Get: returns value or -1 if not found                              */
/* ------------------------------------------------------------------ */

static int sha_map_get(const ShaHashMap *m, const char *sha) {
    if (!m->entries || m->capacity == 0) return -1;
    unsigned int h = _sha_map_fnv1a(sha) % (unsigned int)m->capacity;
    for (int i = 0; i < m->capacity; i++) {
        int slot = (h + i) % m->capacity;
        if (!m->entries[slot].sha)
            return -1;  /* empty — not found */
        if (m->entries[slot].sha == SHA_MAP_TOMBSTONE)
            continue;   /* skip tombstone */
        if (strcmp(m->entries[slot].sha, sha) == 0)
            return m->entries[slot].val;
    }
    return -1;
}

/* ------------------------------------------------------------------ */
/* Put: returns 0 on success, -1 on OOM                               */
/* ------------------------------------------------------------------ */

static int sha_map_put(ShaHashMap *m, const char *sha, int val) {
    if (!m->entries) return -1;
    if (m->occupied >= (int)(m->capacity * SHA_MAP_LOAD_FACTOR))
        _sha_map_grow(m);
    if (!m->entries) return -1;

    unsigned int h = _sha_map_fnv1a(sha) % (unsigned int)m->capacity;
    int first_tombstone = -1;

    for (int i = 0; i < m->capacity; i++) {
        int slot = (h + i) % m->capacity;

        if (!m->entries[slot].sha) {
            /* Empty slot — insert here (or at earlier tombstone) */
            int target = (first_tombstone >= 0) ? first_tombstone : slot;
            m->entries[target].sha = strdup(sha);
            if (!m->entries[target].sha) return -1;
            m->entries[target].val = val;
            m->count++;
            if (first_tombstone < 0) m->occupied++;
            return 0;
        }
        if (m->entries[slot].sha == SHA_MAP_TOMBSTONE) {
            if (first_tombstone < 0) first_tombstone = slot;
            continue;
        }
        if (strcmp(m->entries[slot].sha, sha) == 0) {
            m->entries[slot].val = val;  /* update existing */
            return 0;
        }
    }
    return -1;  /* table full (should not happen) */
}

/* ------------------------------------------------------------------ */
/* Remove: returns 0 on success, -1 if not found                      */
/* ------------------------------------------------------------------ */

static int sha_map_remove(ShaHashMap *m, const char *sha) {
    if (!m->entries || m->capacity == 0) return -1;
    unsigned int h = _sha_map_fnv1a(sha) % (unsigned int)m->capacity;
    for (int i = 0; i < m->capacity; i++) {
        int slot = (h + i) % m->capacity;
        if (!m->entries[slot].sha)
            return -1;  /* not found */
        if (m->entries[slot].sha == SHA_MAP_TOMBSTONE)
            continue;
        if (strcmp(m->entries[slot].sha, sha) == 0) {
            free(m->entries[slot].sha);
            m->entries[slot].sha = SHA_MAP_TOMBSTONE;
            m->entries[slot].val = -1;
            m->count--;
            /* occupied stays the same (tombstone still occupies) */
            return 0;
        }
    }
    return -1;
}

/* ------------------------------------------------------------------ */
/* Exists: returns 1 if SHA is in the map, 0 otherwise                */
/* ------------------------------------------------------------------ */

static int sha_map_exists(const ShaHashMap *m, const char *sha) {
    return sha_map_get(m, sha) >= 0;
}

/* ------------------------------------------------------------------ */
/* Grow: double capacity and rehash                                   */
/* ------------------------------------------------------------------ */

static void _sha_map_grow(ShaHashMap *m) {
    int old_cap = m->capacity;
    ShaMapEntry *old = m->entries;

    int new_cap = old_cap * 2;
    ShaMapEntry *new_entries = (ShaMapEntry *)calloc(new_cap, sizeof(ShaMapEntry));
    if (!new_entries) return;  /* OOM — leave unchanged */

    m->entries = new_entries;
    m->capacity = new_cap;
    m->count = 0;
    m->occupied = 0;

    for (int i = 0; i < old_cap; i++) {
        if (old[i].sha && old[i].sha != SHA_MAP_TOMBSTONE) {
            sha_map_put(m, old[i].sha, old[i].val);
            free(old[i].sha);
        }
    }
    free(old);
}

#endif /* SHA_HASHMAP_H */
