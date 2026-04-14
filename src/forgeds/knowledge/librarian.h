/*
 * librarian.h — Token lifecycle authority for the ForgeDS knowledge base.
 *
 * The Librarian is the SOLE gatekeeper for token creation, destruction,
 * and weight mutation across both the Reality Database (RB) and the
 * Holographic Database (HB).
 *
 * Invariants enforced:
 *   1. SHA uniqueness — no two tokens (across RB + HB) share a SHA.
 *   2. Immutability   — once created, only weight is mutable.
 *   3. Gated lifecycle — all INSERT/DELETE go through this API.
 *   4. Closed world   — only analysis results leave the system (as JSON).
 *
 * Build:
 *   gcc -O2 -shared -fPIC -o librarian.so librarian.c -lsqlite3
 *   cl.exe /LD /O2 /Fe:librarian.dll librarian.c sqlite3.lib
 */

#ifndef LIBRARIAN_H
#define LIBRARIAN_H

#ifdef _WIN32
  #define LIB_EXPORT __declspec(dllexport)
#else
  #define LIB_EXPORT __attribute__((visibility("default")))
#endif

/* ------------------------------------------------------------------ */
/* Opaque handle                                                       */
/* ------------------------------------------------------------------ */

typedef struct Librarian Librarian;

/* ------------------------------------------------------------------ */
/* Database targets                                                    */
/* ------------------------------------------------------------------ */

typedef enum {
    LIB_RB = 0,   /* Reality Database  — permanent, source of truth */
    LIB_HB = 1    /* Holographic Database — ephemeral projections   */
} LibDB;

/* ------------------------------------------------------------------ */
/* Result struct — returned by every mutating operation                 */
/* ------------------------------------------------------------------ */

typedef struct {
    int  ok;            /* 1 = success, 0 = failure                  */
    char sha[65];       /* SHA-256 hex (64 chars + null)             */
    char error[256];    /* error message if !ok                      */
} LibResult;

/* ------------------------------------------------------------------ */
/* Lifecycle                                                           */
/* ------------------------------------------------------------------ */

/* Open both databases; loads all existing SHAs into the registry.
 * Creates tables if they don't exist.  Returns NULL on failure.       */
LIB_EXPORT Librarian* lib_open(const char *rb_path, const char *hb_path);

/* Close both databases and free all resources.                        */
LIB_EXPORT void lib_close(Librarian *lib);

/* ------------------------------------------------------------------ */
/* Token operations — THE ONLY WAY to create/destroy/mutate tokens     */
/* ------------------------------------------------------------------ */

/* Create a token in the specified database.
 *
 * The Librarian computes SHA-256(content \0 page_url \0 paragraph_num),
 * checks global uniqueness, and INSERTs.  Returns the SHA on success.
 *
 * metadata_json is an optional JSON string stored alongside the token
 * (page_title, section, content_type, module, git_sha, source_md).
 * Pass NULL to omit.                                                  */
LIB_EXPORT LibResult lib_create(
    Librarian  *lib,
    LibDB       db,
    const char *content,
    const char *page_url,
    int         paragraph_num,
    const char *module,
    const char *content_type,
    double      weight,
    const char *metadata_json   /* nullable */
);

/* Destroy a token by SHA.  Removes from whichever DB holds it,
 * deletes associated edges, and revokes the SHA from the registry.    */
LIB_EXPORT LibResult lib_destroy(Librarian *lib, const char *sha);

/* Adjust the weight of edges originating from a token.
 * This is the ONLY mutable property after creation.                   */
LIB_EXPORT LibResult lib_adjust_weight(
    Librarian  *lib,
    const char *sha,
    double      new_weight
);

/* Create an edge between two tokens (both must exist in registry).    */
LIB_EXPORT LibResult lib_create_edge(
    Librarian  *lib,
    const char *source_sha,
    const char *target_sha,
    const char *rel_type,
    double      weight
);

/* ------------------------------------------------------------------ */
/* Closed-world output — JSON only                                     */
/* ------------------------------------------------------------------ */

/* Export a token's data as a JSON string.  Caller must lib_free_string().
 * Returns NULL if the SHA does not exist.                             */
LIB_EXPORT char* lib_export_token(Librarian *lib, const char *sha);

/* Export all HB tokens as a JSON array.  Caller must lib_free_string(). */
LIB_EXPORT char* lib_export_hb(Librarian *lib);

/* Free a string returned by lib_export_*.                             */
LIB_EXPORT void lib_free_string(char *s);

/* ------------------------------------------------------------------ */
/* Batch HB lifecycle — destroy all holographic tokens at once         */
/* ------------------------------------------------------------------ */

/* Destroy all tokens in the Holographic Database.
 * Called after analysis + user confirmation.  Returns count destroyed. */
LIB_EXPORT int lib_purge_hb(Librarian *lib);

/* ------------------------------------------------------------------ */
/* Registry queries (read-only)                                        */
/* ------------------------------------------------------------------ */

/* Check if a SHA exists in the global registry.  Returns 1/0.         */
LIB_EXPORT int lib_sha_exists(Librarian *lib, const char *sha);

/* Return which database holds a SHA: 0=RB, 1=HB, -1=not found.       */
LIB_EXPORT int lib_sha_db(Librarian *lib, const char *sha);

/* Count tokens in a specific database.                                */
LIB_EXPORT int lib_count(Librarian *lib, LibDB db);

/* Return total SHAs in the global registry.                           */
LIB_EXPORT int lib_registry_size(Librarian *lib);

#endif /* LIBRARIAN_H */
