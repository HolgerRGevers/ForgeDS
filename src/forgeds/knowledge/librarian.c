/*
 * librarian.c — Token lifecycle authority for the ForgeDS knowledge base.
 *
 * Sole gatekeeper for token creation, destruction, and weight mutation
 * across the Reality Database (RB) and Holographic Database (HB).
 *
 * Build:
 *   gcc -O2 -shared -fPIC -o librarian.so librarian.c -lsqlite3
 *   cl.exe /LD /O2 /Fe:librarian.dll librarian.c sqlite3.lib
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sqlite3.h>

#include "sha_hashmap.h"
#include "librarian.h"

/* ------------------------------------------------------------------ */
/* SHA-256 implementation (standalone, no OpenSSL dependency)           */
/* ------------------------------------------------------------------ */

static const unsigned int K256[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,
    0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,
    0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,
    0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,
    0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,
    0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,
    0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,
    0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,
    0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};

#define RR(x,n) (((x)>>(n))|((x)<<(32-(n))))
#define CH(x,y,z) (((x)&(y))^((~(x))&(z)))
#define MAJ(x,y,z) (((x)&(y))^((x)&(z))^((y)&(z)))
#define EP0(x) (RR(x,2)^RR(x,13)^RR(x,22))
#define EP1(x) (RR(x,6)^RR(x,11)^RR(x,25))
#define SIG0(x) (RR(x,7)^RR(x,18)^((x)>>3))
#define SIG1(x) (RR(x,17)^RR(x,19)^((x)>>10))

typedef struct {
    unsigned int state[8];
    unsigned char buf[64];
    unsigned long long bitlen;
    unsigned int buflen;
} SHA256_CTX;

static void _sha256_transform(SHA256_CTX *ctx) {
    unsigned int w[64], a, b, c, d, e, f, g, h, t1, t2;
    int i;

    for (i = 0; i < 16; i++)
        w[i] = ((unsigned int)ctx->buf[i*4]<<24) |
               ((unsigned int)ctx->buf[i*4+1]<<16) |
               ((unsigned int)ctx->buf[i*4+2]<<8) |
               ((unsigned int)ctx->buf[i*4+3]);
    for (i = 16; i < 64; i++)
        w[i] = SIG1(w[i-2]) + w[i-7] + SIG0(w[i-15]) + w[i-16];

    a=ctx->state[0]; b=ctx->state[1]; c=ctx->state[2]; d=ctx->state[3];
    e=ctx->state[4]; f=ctx->state[5]; g=ctx->state[6]; h=ctx->state[7];

    for (i = 0; i < 64; i++) {
        t1 = h + EP1(e) + CH(e,f,g) + K256[i] + w[i];
        t2 = EP0(a) + MAJ(a,b,c);
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }

    ctx->state[0]+=a; ctx->state[1]+=b; ctx->state[2]+=c; ctx->state[3]+=d;
    ctx->state[4]+=e; ctx->state[5]+=f; ctx->state[6]+=g; ctx->state[7]+=h;
}

static void _sha256_init(SHA256_CTX *ctx) {
    ctx->state[0]=0x6a09e667; ctx->state[1]=0xbb67ae85;
    ctx->state[2]=0x3c6ef372; ctx->state[3]=0xa54ff53a;
    ctx->state[4]=0x510e527f; ctx->state[5]=0x9b05688c;
    ctx->state[6]=0x1f83d9ab; ctx->state[7]=0x5be0cd19;
    ctx->bitlen = 0;
    ctx->buflen = 0;
}

static void _sha256_update(SHA256_CTX *ctx, const unsigned char *data, size_t len) {
    for (size_t i = 0; i < len; i++) {
        ctx->buf[ctx->buflen++] = data[i];
        if (ctx->buflen == 64) {
            _sha256_transform(ctx);
            ctx->bitlen += 512;
            ctx->buflen = 0;
        }
    }
}

static void _sha256_final(SHA256_CTX *ctx, unsigned char hash[32]) {
    unsigned int i = ctx->buflen;
    ctx->buf[i++] = 0x80;
    if (i > 56) {
        while (i < 64) ctx->buf[i++] = 0;
        _sha256_transform(ctx);
        i = 0;
    }
    while (i < 56) ctx->buf[i++] = 0;

    ctx->bitlen += ctx->buflen * 8;
    ctx->buf[56] = (unsigned char)(ctx->bitlen >> 56);
    ctx->buf[57] = (unsigned char)(ctx->bitlen >> 48);
    ctx->buf[58] = (unsigned char)(ctx->bitlen >> 40);
    ctx->buf[59] = (unsigned char)(ctx->bitlen >> 32);
    ctx->buf[60] = (unsigned char)(ctx->bitlen >> 24);
    ctx->buf[61] = (unsigned char)(ctx->bitlen >> 16);
    ctx->buf[62] = (unsigned char)(ctx->bitlen >> 8);
    ctx->buf[63] = (unsigned char)(ctx->bitlen);
    _sha256_transform(ctx);

    /* Big-endian output */
    for (i = 0; i < 8; i++) {
        hash[i*4]   = (unsigned char)(ctx->state[i] >> 24);
        hash[i*4+1] = (unsigned char)(ctx->state[i] >> 16);
        hash[i*4+2] = (unsigned char)(ctx->state[i] >> 8);
        hash[i*4+3] = (unsigned char)(ctx->state[i]);
    }
}

/* Compute SHA-256 of (content \0 page_url \0 paragraph_num_str) → hex */
static void _compute_token_sha(
    const char *content, const char *page_url, int paragraph_num,
    char out_hex[65]
) {
    SHA256_CTX ctx;
    unsigned char hash[32];
    char para_str[16];

    snprintf(para_str, sizeof(para_str), "%d", paragraph_num);

    _sha256_init(&ctx);
    _sha256_update(&ctx, (const unsigned char *)content, strlen(content));
    _sha256_update(&ctx, (const unsigned char *)"\0", 1);
    _sha256_update(&ctx, (const unsigned char *)page_url, strlen(page_url));
    _sha256_update(&ctx, (const unsigned char *)"\0", 1);
    _sha256_update(&ctx, (const unsigned char *)para_str, strlen(para_str));
    _sha256_final(&ctx, hash);

    for (int i = 0; i < 32; i++)
        sprintf(out_hex + i * 2, "%02x", hash[i]);
    out_hex[64] = '\0';
}


/* ------------------------------------------------------------------ */
/* Librarian internal structure                                        */
/* ------------------------------------------------------------------ */

struct Librarian {
    sqlite3    *rb;       /* Reality Database connection               */
    sqlite3    *hb;       /* Holographic Database connection            */
    ShaHashMap  registry; /* Global SHA registry (val: 0=RB, 1=HB)     */

    /* Prepared statements — RB */
    sqlite3_stmt *rb_insert_token;
    sqlite3_stmt *rb_delete_token;
    sqlite3_stmt *rb_delete_edges_src;
    sqlite3_stmt *rb_delete_edges_tgt;
    sqlite3_stmt *rb_update_weight;
    sqlite3_stmt *rb_insert_edge;
    sqlite3_stmt *rb_select_token;

    /* Prepared statements — HB */
    sqlite3_stmt *hb_insert_token;
    sqlite3_stmt *hb_delete_token;
    sqlite3_stmt *hb_delete_edges_src;
    sqlite3_stmt *hb_delete_edges_tgt;
    sqlite3_stmt *hb_update_weight;
    sqlite3_stmt *hb_insert_edge;
    sqlite3_stmt *hb_select_token;
};


/* ------------------------------------------------------------------ */
/* DDL for both databases (RB uses full schema, HB uses token schema)  */
/* ------------------------------------------------------------------ */

static const char *RB_DDL =
    "CREATE TABLE IF NOT EXISTS modules ("
    "    name     TEXT PRIMARY KEY,"
    "    base_url TEXT NOT NULL,"
    "    page_count INTEGER NOT NULL DEFAULT 0"
    ");"
    "CREATE TABLE IF NOT EXISTS pages ("
    "    url        TEXT PRIMARY KEY,"
    "    title      TEXT,"
    "    module     TEXT NOT NULL REFERENCES modules(name),"
    "    md_path    TEXT NOT NULL,"
    "    scraped_at TEXT NOT NULL"
    ");"
    "CREATE TABLE IF NOT EXISTS tokens ("
    "    token_sha    TEXT PRIMARY KEY,"
    "    revision     INTEGER NOT NULL DEFAULT 1,"
    "    content      TEXT NOT NULL,"
    "    content_type TEXT NOT NULL,"
    "    module       TEXT NOT NULL,"
    "    page_url     TEXT NOT NULL,"
    "    page_title   TEXT,"
    "    section      TEXT,"
    "    paragraph    INTEGER,"
    "    page_updated TEXT,"
    "    created_at   TEXT NOT NULL,"
    "    updated_at   TEXT NOT NULL,"
    "    git_sha      TEXT NOT NULL,"
    "    source_md    TEXT NOT NULL,"
    "    weight       REAL NOT NULL DEFAULT 1.0"
    ");"
    "CREATE TABLE IF NOT EXISTS edges ("
    "    source_sha TEXT NOT NULL REFERENCES tokens(token_sha),"
    "    target_sha TEXT NOT NULL REFERENCES tokens(token_sha),"
    "    rel_type   TEXT NOT NULL,"
    "    weight     REAL NOT NULL DEFAULT 0.5,"
    "    PRIMARY KEY (source_sha, target_sha, rel_type)"
    ");"
    "CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_sha);"
    "CREATE INDEX IF NOT EXISTS idx_tokens_module ON tokens(module);"
    "CREATE INDEX IF NOT EXISTS idx_tokens_page   ON tokens(page_url);"
    "CREATE VIRTUAL TABLE IF NOT EXISTS tokens_fts USING fts5("
    "    content, token_sha UNINDEXED, module UNINDEXED, content_type UNINDEXED,"
    "    content='tokens', content_rowid='rowid'"
    ");"
    "CREATE TRIGGER IF NOT EXISTS tokens_ai AFTER INSERT ON tokens BEGIN"
    "    INSERT INTO tokens_fts(rowid, content, token_sha, module, content_type)"
    "    VALUES (new.rowid, new.content, new.token_sha, new.module, new.content_type);"
    "END;"
    "CREATE TRIGGER IF NOT EXISTS tokens_ad AFTER DELETE ON tokens BEGIN"
    "    INSERT INTO tokens_fts(tokens_fts, rowid, content, token_sha, module, content_type)"
    "    VALUES ('delete', old.rowid, old.content, old.token_sha, old.module, old.content_type);"
    "END;"
    "CREATE TRIGGER IF NOT EXISTS tokens_au AFTER UPDATE ON tokens BEGIN"
    "    INSERT INTO tokens_fts(tokens_fts, rowid, content, token_sha, module, content_type)"
    "    VALUES ('delete', old.rowid, old.content, old.token_sha, old.module, old.content_type);"
    "    INSERT INTO tokens_fts(rowid, content, token_sha, module, content_type)"
    "    VALUES (new.rowid, new.content, new.token_sha, new.module, new.content_type);"
    "END;";

static const char *HB_DDL =
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
    "    source_sha TEXT NOT NULL REFERENCES tokens(token_sha),"
    "    target_sha TEXT NOT NULL REFERENCES tokens(token_sha),"
    "    rel_type   TEXT NOT NULL,"
    "    weight     REAL NOT NULL DEFAULT 0.5,"
    "    PRIMARY KEY (source_sha, target_sha, rel_type)"
    ");"
    "CREATE INDEX IF NOT EXISTS idx_hb_edges_target ON edges(target_sha);";


/* ------------------------------------------------------------------ */
/* Helper: prepare a statement or return NULL                          */
/* ------------------------------------------------------------------ */

static sqlite3_stmt* _prepare(sqlite3 *db, const char *sql) {
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "librarian: prepare failed: %s\n", sqlite3_errmsg(db));
        return NULL;
    }
    return stmt;
}


/* ------------------------------------------------------------------ */
/* Helper: set LibResult to error                                      */
/* ------------------------------------------------------------------ */

static LibResult _error(const char *msg) {
    LibResult r;
    r.ok = 0;
    r.sha[0] = '\0';
    strncpy(r.error, msg, sizeof(r.error) - 1);
    r.error[sizeof(r.error) - 1] = '\0';
    return r;
}

static LibResult _ok(const char *sha) {
    LibResult r;
    r.ok = 1;
    strncpy(r.sha, sha, 64);
    r.sha[64] = '\0';
    r.error[0] = '\0';
    return r;
}


/* ------------------------------------------------------------------ */
/* Helper: load all SHAs from a database into the registry             */
/* ------------------------------------------------------------------ */

static int _load_shas(Librarian *lib, sqlite3 *db, int db_id) {
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, "SELECT token_sha FROM tokens", -1, &stmt, NULL);
    if (rc != SQLITE_OK) return 0;  /* table may not exist yet */

    int count = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const char *sha = (const char *)sqlite3_column_text(stmt, 0);
        if (sha && sha_map_put(&lib->registry, sha, db_id) == 0)
            count++;
    }
    sqlite3_finalize(stmt);
    return count;
}


/* ------------------------------------------------------------------ */
/* lib_open                                                            */
/* ------------------------------------------------------------------ */

LIB_EXPORT Librarian* lib_open(const char *rb_path, const char *hb_path) {
    Librarian *lib = (Librarian *)calloc(1, sizeof(Librarian));
    if (!lib) return NULL;

    /* Init registry */
    if (sha_map_init(&lib->registry, 16384) < 0) {
        free(lib);
        return NULL;
    }

    /* Open RB */
    int rc = sqlite3_open_v2(rb_path, &lib->rb,
                             SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "librarian: cannot open RB %s: %s\n",
                rb_path, sqlite3_errmsg(lib->rb));
        sha_map_free(&lib->registry);
        free(lib);
        return NULL;
    }
    sqlite3_exec(lib->rb, "PRAGMA journal_mode=WAL", NULL, NULL, NULL);
    sqlite3_exec(lib->rb, "PRAGMA synchronous=NORMAL", NULL, NULL, NULL);
    sqlite3_exec(lib->rb, "PRAGMA foreign_keys=ON", NULL, NULL, NULL);

    /* Open HB */
    rc = sqlite3_open_v2(hb_path, &lib->hb,
                         SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "librarian: cannot open HB %s: %s\n",
                hb_path, sqlite3_errmsg(lib->hb));
        sqlite3_close(lib->rb);
        sha_map_free(&lib->registry);
        free(lib);
        return NULL;
    }
    sqlite3_exec(lib->hb, "PRAGMA journal_mode=WAL", NULL, NULL, NULL);
    sqlite3_exec(lib->hb, "PRAGMA synchronous=NORMAL", NULL, NULL, NULL);
    sqlite3_exec(lib->hb, "PRAGMA foreign_keys=ON", NULL, NULL, NULL);

    /* Create schemas */
    char *err_msg = NULL;
    sqlite3_exec(lib->rb, RB_DDL, NULL, NULL, &err_msg);
    if (err_msg) { sqlite3_free(err_msg); err_msg = NULL; }
    sqlite3_exec(lib->hb, HB_DDL, NULL, NULL, &err_msg);
    if (err_msg) { sqlite3_free(err_msg); err_msg = NULL; }

    /* Load existing SHAs into registry */
    _load_shas(lib, lib->rb, LIB_RB);
    _load_shas(lib, lib->hb, LIB_HB);

    /* Prepare RB statements */
    lib->rb_insert_token = _prepare(lib->rb,
        "INSERT INTO tokens "
        "(token_sha, revision, content, content_type, module, page_url, "
        " page_title, section, paragraph, page_updated, created_at, "
        " updated_at, git_sha, source_md, weight) "
        "VALUES (?,1,?,?,?,?,?,?,?,?,?,?,?,?,?)");
    lib->rb_delete_token = _prepare(lib->rb,
        "DELETE FROM tokens WHERE token_sha = ?");
    lib->rb_delete_edges_src = _prepare(lib->rb,
        "DELETE FROM edges WHERE source_sha = ?");
    lib->rb_delete_edges_tgt = _prepare(lib->rb,
        "DELETE FROM edges WHERE target_sha = ?");
    lib->rb_update_weight = _prepare(lib->rb,
        "UPDATE tokens SET weight = ? WHERE token_sha = ?");
    lib->rb_insert_edge = _prepare(lib->rb,
        "INSERT OR IGNORE INTO edges (source_sha, target_sha, rel_type, weight) "
        "VALUES (?, ?, ?, ?)");
    lib->rb_select_token = _prepare(lib->rb,
        "SELECT token_sha, content, content_type, module, page_url, "
        "page_title, section, paragraph, weight, created_at "
        "FROM tokens WHERE token_sha = ?");

    /* Prepare HB statements */
    lib->hb_insert_token = _prepare(lib->hb,
        "INSERT INTO tokens "
        "(token_sha, content, content_type, module, page_url, "
        " page_title, section, paragraph, created_at, weight) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)");
    lib->hb_delete_token = _prepare(lib->hb,
        "DELETE FROM tokens WHERE token_sha = ?");
    lib->hb_delete_edges_src = _prepare(lib->hb,
        "DELETE FROM edges WHERE source_sha = ?");
    lib->hb_delete_edges_tgt = _prepare(lib->hb,
        "DELETE FROM edges WHERE target_sha = ?");
    lib->hb_update_weight = _prepare(lib->hb,
        "UPDATE tokens SET weight = ? WHERE token_sha = ?");
    lib->hb_insert_edge = _prepare(lib->hb,
        "INSERT OR IGNORE INTO edges (source_sha, target_sha, rel_type, weight) "
        "VALUES (?, ?, ?, ?)");
    lib->hb_select_token = _prepare(lib->hb,
        "SELECT token_sha, content, content_type, module, page_url, "
        "page_title, section, paragraph, weight, created_at "
        "FROM tokens WHERE token_sha = ?");

    return lib;
}


/* ------------------------------------------------------------------ */
/* lib_close                                                           */
/* ------------------------------------------------------------------ */

static void _finalize_all(Librarian *lib) {
    if (lib->rb_insert_token)    sqlite3_finalize(lib->rb_insert_token);
    if (lib->rb_delete_token)    sqlite3_finalize(lib->rb_delete_token);
    if (lib->rb_delete_edges_src) sqlite3_finalize(lib->rb_delete_edges_src);
    if (lib->rb_delete_edges_tgt) sqlite3_finalize(lib->rb_delete_edges_tgt);
    if (lib->rb_update_weight)   sqlite3_finalize(lib->rb_update_weight);
    if (lib->rb_insert_edge)     sqlite3_finalize(lib->rb_insert_edge);
    if (lib->rb_select_token)    sqlite3_finalize(lib->rb_select_token);

    if (lib->hb_insert_token)    sqlite3_finalize(lib->hb_insert_token);
    if (lib->hb_delete_token)    sqlite3_finalize(lib->hb_delete_token);
    if (lib->hb_delete_edges_src) sqlite3_finalize(lib->hb_delete_edges_src);
    if (lib->hb_delete_edges_tgt) sqlite3_finalize(lib->hb_delete_edges_tgt);
    if (lib->hb_update_weight)   sqlite3_finalize(lib->hb_update_weight);
    if (lib->hb_insert_edge)     sqlite3_finalize(lib->hb_insert_edge);
    if (lib->hb_select_token)    sqlite3_finalize(lib->hb_select_token);
}

LIB_EXPORT void lib_close(Librarian *lib) {
    if (!lib) return;
    _finalize_all(lib);
    if (lib->rb) sqlite3_close(lib->rb);
    if (lib->hb) sqlite3_close(lib->hb);
    sha_map_free(&lib->registry);
    free(lib);
}


/* ------------------------------------------------------------------ */
/* lib_create                                                          */
/* ------------------------------------------------------------------ */

LIB_EXPORT LibResult lib_create(
    Librarian  *lib,
    LibDB       db,
    const char *content,
    const char *page_url,
    int         paragraph_num,
    const char *module,
    const char *content_type,
    double      weight,
    const char *metadata_json
) {
    if (!lib) return _error("Librarian handle is NULL");
    if (!content || !page_url || !module || !content_type)
        return _error("Required fields are NULL");

    /* 1. Compute SHA */
    char sha[65];
    _compute_token_sha(content, page_url, paragraph_num, sha);

    /* 2. Check global uniqueness */
    if (sha_map_exists(&lib->registry, sha)) {
        char msg[256];
        snprintf(msg, sizeof(msg),
                 "SHA collision: %.16s... already exists in %s",
                 sha, sha_map_get(&lib->registry, sha) == LIB_RB ? "RB" : "HB");
        return _error(msg);
    }

    /* 3. Parse optional metadata */
    const char *page_title  = "";
    const char *section     = "";
    const char *page_updated = "";
    const char *created_at  = "";
    const char *updated_at  = "";
    const char *git_sha     = "";
    const char *source_md   = "";

    /* Simple JSON field extraction (no dependency needed for flat objects) */
    /* metadata_json format: {"page_title":"...","section":"...",...}       */
    /* We extract fields with a minimal parser.                            */
    char _pt[512]="", _sec[512]="", _pu[128]="", _ca[64]="", _ua[64]="";
    char _gs[128]="", _sm[512]="";

    if (metadata_json && metadata_json[0] == '{') {
        /* Minimal JSON string value extractor */
        #define EXTRACT_FIELD(json, key, buf, bufsz) do { \
            const char *_k = "\"" key "\":\""; \
            const char *_p = strstr(json, _k); \
            if (_p) { \
                _p += strlen(_k); \
                const char *_e = strchr(_p, '"'); \
                if (_e) { \
                    size_t _len = (_e - _p < (bufsz)-1) ? (size_t)(_e - _p) : (bufsz)-1; \
                    memcpy(buf, _p, _len); \
                    buf[_len] = '\0'; \
                } \
            } \
        } while(0)

        EXTRACT_FIELD(metadata_json, "page_title",  _pt,  sizeof(_pt));
        EXTRACT_FIELD(metadata_json, "section",     _sec, sizeof(_sec));
        EXTRACT_FIELD(metadata_json, "page_updated",_pu,  sizeof(_pu));
        EXTRACT_FIELD(metadata_json, "created_at",  _ca,  sizeof(_ca));
        EXTRACT_FIELD(metadata_json, "updated_at",  _ua,  sizeof(_ua));
        EXTRACT_FIELD(metadata_json, "git_sha",     _gs,  sizeof(_gs));
        EXTRACT_FIELD(metadata_json, "source_md",   _sm,  sizeof(_sm));

        #undef EXTRACT_FIELD

        if (_pt[0])  page_title  = _pt;
        if (_sec[0]) section     = _sec;
        if (_pu[0])  page_updated = _pu;
        if (_ca[0])  created_at  = _ca;
        if (_ua[0])  updated_at  = _ua;
        if (_gs[0])  git_sha     = _gs;
        if (_sm[0])  source_md   = _sm;
    }

    /* 4. INSERT into target database */
    int rc;
    if (db == LIB_RB) {
        sqlite3_stmt *s = lib->rb_insert_token;
        sqlite3_reset(s);
        sqlite3_bind_text(s, 1, sha, -1, SQLITE_STATIC);
        sqlite3_bind_text(s, 2, content, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 3, content_type, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 4, module, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 5, page_url, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 6, page_title, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 7, section, -1, SQLITE_TRANSIENT);
        sqlite3_bind_int(s, 8, paragraph_num);
        sqlite3_bind_text(s, 9, page_updated, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 10, created_at, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 11, updated_at, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 12, git_sha, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 13, source_md, -1, SQLITE_TRANSIENT);
        sqlite3_bind_double(s, 14, weight);
        rc = sqlite3_step(s);
    } else {
        sqlite3_stmt *s = lib->hb_insert_token;
        sqlite3_reset(s);
        sqlite3_bind_text(s, 1, sha, -1, SQLITE_STATIC);
        sqlite3_bind_text(s, 2, content, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 3, content_type, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 4, module, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 5, page_url, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 6, page_title, -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s, 7, section, -1, SQLITE_TRANSIENT);
        sqlite3_bind_int(s, 8, paragraph_num);
        sqlite3_bind_text(s, 9, created_at, -1, SQLITE_TRANSIENT);
        sqlite3_bind_double(s, 10, weight);
        rc = sqlite3_step(s);
    }

    if (rc != SQLITE_DONE) {
        char msg[256];
        sqlite3 *target = (db == LIB_RB) ? lib->rb : lib->hb;
        snprintf(msg, sizeof(msg), "INSERT failed: %s", sqlite3_errmsg(target));
        return _error(msg);
    }

    /* 5. Register SHA */
    sha_map_put(&lib->registry, sha, (int)db);

    return _ok(sha);
}


/* ------------------------------------------------------------------ */
/* lib_destroy                                                         */
/* ------------------------------------------------------------------ */

LIB_EXPORT LibResult lib_destroy(Librarian *lib, const char *sha) {
    if (!lib) return _error("Librarian handle is NULL");
    if (!sha) return _error("SHA is NULL");

    int db_id = sha_map_get(&lib->registry, sha);
    if (db_id < 0)
        return _error("SHA not found in registry");

    sqlite3_stmt *del_tok, *del_src, *del_tgt;
    if (db_id == LIB_RB) {
        del_tok = lib->rb_delete_token;
        del_src = lib->rb_delete_edges_src;
        del_tgt = lib->rb_delete_edges_tgt;
    } else {
        del_tok = lib->hb_delete_token;
        del_src = lib->hb_delete_edges_src;
        del_tgt = lib->hb_delete_edges_tgt;
    }

    /* Delete edges first (FK order) */
    sqlite3_reset(del_src);
    sqlite3_bind_text(del_src, 1, sha, -1, SQLITE_STATIC);
    sqlite3_step(del_src);

    sqlite3_reset(del_tgt);
    sqlite3_bind_text(del_tgt, 1, sha, -1, SQLITE_STATIC);
    sqlite3_step(del_tgt);

    /* Delete token */
    sqlite3_reset(del_tok);
    sqlite3_bind_text(del_tok, 1, sha, -1, SQLITE_STATIC);
    int rc = sqlite3_step(del_tok);
    if (rc != SQLITE_DONE) {
        char msg[256];
        sqlite3 *target = (db_id == LIB_RB) ? lib->rb : lib->hb;
        snprintf(msg, sizeof(msg), "DELETE failed: %s", sqlite3_errmsg(target));
        return _error(msg);
    }

    /* Revoke SHA */
    sha_map_remove(&lib->registry, sha);

    return _ok(sha);
}


/* ------------------------------------------------------------------ */
/* lib_adjust_weight                                                   */
/* ------------------------------------------------------------------ */

LIB_EXPORT LibResult lib_adjust_weight(Librarian *lib, const char *sha, double new_weight) {
    if (!lib) return _error("Librarian handle is NULL");
    if (!sha) return _error("SHA is NULL");

    int db_id = sha_map_get(&lib->registry, sha);
    if (db_id < 0)
        return _error("SHA not found in registry");

    sqlite3_stmt *s = (db_id == LIB_RB) ? lib->rb_update_weight : lib->hb_update_weight;
    sqlite3_reset(s);
    sqlite3_bind_double(s, 1, new_weight);
    sqlite3_bind_text(s, 2, sha, -1, SQLITE_STATIC);
    int rc = sqlite3_step(s);
    if (rc != SQLITE_DONE) {
        sqlite3 *target = (db_id == LIB_RB) ? lib->rb : lib->hb;
        char msg[256];
        snprintf(msg, sizeof(msg), "UPDATE weight failed: %s", sqlite3_errmsg(target));
        return _error(msg);
    }

    return _ok(sha);
}


/* ------------------------------------------------------------------ */
/* lib_create_edge                                                     */
/* ------------------------------------------------------------------ */

LIB_EXPORT LibResult lib_create_edge(
    Librarian  *lib,
    const char *source_sha,
    const char *target_sha,
    const char *rel_type,
    double      weight
) {
    if (!lib) return _error("Librarian handle is NULL");
    if (!source_sha || !target_sha || !rel_type)
        return _error("Required edge fields are NULL");

    /* Both SHAs must exist */
    int src_db = sha_map_get(&lib->registry, source_sha);
    int tgt_db = sha_map_get(&lib->registry, target_sha);
    if (src_db < 0)
        return _error("source_sha not found in registry");
    if (tgt_db < 0)
        return _error("target_sha not found in registry");

    /* Edge goes into the source token's database */
    sqlite3_stmt *s = (src_db == LIB_RB) ? lib->rb_insert_edge : lib->hb_insert_edge;
    sqlite3_reset(s);
    sqlite3_bind_text(s, 1, source_sha, -1, SQLITE_STATIC);
    sqlite3_bind_text(s, 2, target_sha, -1, SQLITE_STATIC);
    sqlite3_bind_text(s, 3, rel_type, -1, SQLITE_TRANSIENT);
    sqlite3_bind_double(s, 4, weight);
    sqlite3_step(s);  /* INSERT OR IGNORE — may silently skip duplicates */

    return _ok(source_sha);
}


/* ------------------------------------------------------------------ */
/* lib_export_token — JSON output for a single token                   */
/* ------------------------------------------------------------------ */

LIB_EXPORT char* lib_export_token(Librarian *lib, const char *sha) {
    if (!lib || !sha) return NULL;

    int db_id = sha_map_get(&lib->registry, sha);
    if (db_id < 0) return NULL;

    sqlite3_stmt *s = (db_id == LIB_RB) ? lib->rb_select_token : lib->hb_select_token;
    sqlite3_reset(s);
    sqlite3_bind_text(s, 1, sha, -1, SQLITE_STATIC);

    int rc = sqlite3_step(s);
    if (rc != SQLITE_ROW) return NULL;

    /* Build JSON manually (no dependency) */
    const char *t_sha    = (const char *)sqlite3_column_text(s, 0);
    const char *content  = (const char *)sqlite3_column_text(s, 1);
    const char *ctype    = (const char *)sqlite3_column_text(s, 2);
    const char *mod      = (const char *)sqlite3_column_text(s, 3);
    const char *purl     = (const char *)sqlite3_column_text(s, 4);
    const char *ptitle   = (const char *)sqlite3_column_text(s, 5);
    const char *sect     = (const char *)sqlite3_column_text(s, 6);
    int         para     = sqlite3_column_int(s, 7);
    double      wt       = sqlite3_column_double(s, 8);
    const char *cat      = (const char *)sqlite3_column_text(s, 9);
    const char *db_name  = (db_id == LIB_RB) ? "RB" : "HB";

    /* Estimate buffer size (generous) */
    size_t content_len = content ? strlen(content) : 0;
    size_t buf_size = content_len * 2 + 2048;  /* room for escaping + fields */
    char *buf = (char *)malloc(buf_size);
    if (!buf) return NULL;

    /* Escape content for JSON (minimal: escape quotes and backslashes) */
    char *escaped = (char *)malloc(content_len * 2 + 1);
    if (!escaped) { free(buf); return NULL; }
    size_t ei = 0;
    for (size_t ci = 0; ci < content_len; ci++) {
        char ch = content[ci];
        if (ch == '"' || ch == '\\') escaped[ei++] = '\\';
        else if (ch == '\n') { escaped[ei++] = '\\'; escaped[ei++] = 'n'; continue; }
        else if (ch == '\r') { escaped[ei++] = '\\'; escaped[ei++] = 'r'; continue; }
        else if (ch == '\t') { escaped[ei++] = '\\'; escaped[ei++] = 't'; continue; }
        escaped[ei++] = ch;
    }
    escaped[ei] = '\0';

    snprintf(buf, buf_size,
        "{\"token_sha\":\"%s\",\"database\":\"%s\","
        "\"content\":\"%s\",\"content_type\":\"%s\","
        "\"module\":\"%s\",\"page_url\":\"%s\","
        "\"page_title\":\"%s\",\"section\":\"%s\","
        "\"paragraph\":%d,\"weight\":%.4f,\"created_at\":\"%s\"}",
        t_sha  ? t_sha  : "",
        db_name,
        escaped,
        ctype  ? ctype  : "",
        mod    ? mod    : "",
        purl   ? purl   : "",
        ptitle ? ptitle : "",
        sect   ? sect   : "",
        para, wt,
        cat    ? cat    : ""
    );

    free(escaped);
    return buf;
}


/* ------------------------------------------------------------------ */
/* lib_export_hb — JSON array of all HB tokens                         */
/* ------------------------------------------------------------------ */

LIB_EXPORT char* lib_export_hb(Librarian *lib) {
    if (!lib) return NULL;

    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(lib->hb,
        "SELECT token_sha, content, content_type, module, page_url, "
        "page_title, section, paragraph, weight, created_at FROM tokens",
        -1, &stmt, NULL);
    if (rc != SQLITE_OK) return NULL;

    /* Build JSON array incrementally */
    size_t buf_size = 4096;
    char *buf = (char *)malloc(buf_size);
    if (!buf) { sqlite3_finalize(stmt); return NULL; }
    size_t pos = 0;
    buf[pos++] = '[';

    int first = 1;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const char *sha = (const char *)sqlite3_column_text(stmt, 0);

        /* Get JSON for this token */
        char *token_json = lib_export_token(lib, sha);
        if (!token_json) continue;

        size_t tj_len = strlen(token_json);
        size_t needed = pos + tj_len + 4;  /* comma + brackets */
        if (needed >= buf_size) {
            buf_size = needed * 2;
            char *tmp = (char *)realloc(buf, buf_size);
            if (!tmp) { free(token_json); break; }
            buf = tmp;
        }

        if (!first) buf[pos++] = ',';
        memcpy(buf + pos, token_json, tj_len);
        pos += tj_len;
        first = 0;

        free(token_json);
    }

    buf[pos++] = ']';
    buf[pos] = '\0';

    sqlite3_finalize(stmt);
    return buf;
}


/* ------------------------------------------------------------------ */
/* lib_free_string                                                     */
/* ------------------------------------------------------------------ */

LIB_EXPORT void lib_free_string(char *s) {
    free(s);
}


/* ------------------------------------------------------------------ */
/* lib_purge_hb — destroy all HB tokens                                */
/* ------------------------------------------------------------------ */

LIB_EXPORT int lib_purge_hb(Librarian *lib) {
    if (!lib) return 0;

    /* Collect all HB SHAs first (so we can remove from registry) */
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(lib->hb,
        "SELECT token_sha FROM tokens", -1, &stmt, NULL);
    if (rc != SQLITE_OK) return 0;

    /* Gather SHAs */
    int cap = 256;
    char **shas = (char **)malloc(sizeof(char *) * cap);
    int count = 0;

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const char *sha = (const char *)sqlite3_column_text(stmt, 0);
        if (!sha) continue;
        if (count >= cap) {
            cap *= 2;
            char **tmp = (char **)realloc(shas, sizeof(char *) * cap);
            if (!tmp) break;
            shas = tmp;
        }
        shas[count++] = strdup(sha);
    }
    sqlite3_finalize(stmt);

    /* Remove from registry */
    for (int i = 0; i < count; i++) {
        sha_map_remove(&lib->registry, shas[i]);
        free(shas[i]);
    }
    free(shas);

    /* Bulk delete from HB */
    sqlite3_exec(lib->hb, "DELETE FROM edges", NULL, NULL, NULL);
    sqlite3_exec(lib->hb, "DELETE FROM tokens", NULL, NULL, NULL);

    return count;
}


/* ------------------------------------------------------------------ */
/* Registry queries                                                    */
/* ------------------------------------------------------------------ */

LIB_EXPORT int lib_sha_exists(Librarian *lib, const char *sha) {
    if (!lib || !sha) return 0;
    return sha_map_exists(&lib->registry, sha);
}

LIB_EXPORT int lib_sha_db(Librarian *lib, const char *sha) {
    if (!lib || !sha) return -1;
    return sha_map_get(&lib->registry, sha);
}

LIB_EXPORT int lib_count(Librarian *lib, LibDB db) {
    if (!lib) return 0;
    sqlite3 *target = (db == LIB_RB) ? lib->rb : lib->hb;
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(target,
        "SELECT COUNT(*) FROM tokens", -1, &stmt, NULL);
    if (rc != SQLITE_OK) return 0;
    rc = sqlite3_step(stmt);
    int count = (rc == SQLITE_ROW) ? sqlite3_column_int(stmt, 0) : 0;
    sqlite3_finalize(stmt);
    return count;
}

LIB_EXPORT int lib_registry_size(Librarian *lib) {
    if (!lib) return 0;
    return lib->registry.count;
}
