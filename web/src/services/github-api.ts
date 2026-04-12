/**
 * GitHub REST API wrapper.
 *
 * All calls use the stored OAuth token. Every function accepts the token
 * explicitly so the module stays stateless — callers (stores) manage the
 * token lifecycle.
 *
 * Includes rate limit tracking, exponential backoff on 429/403, and
 * automatic 401 detection for expired tokens.
 */

const API = "https://api.github.com";

// ── Rate limit state ─────────────────────────────────────────────────────

let rateLimitRemaining = 5000;
let rateLimitReset = 0; // Unix epoch seconds

export function getRateLimitInfo() {
  return { remaining: rateLimitRemaining, resetAt: rateLimitReset };
}

// ── Errors ───────────────────────────────────────────────────────────────

export class TokenExpiredError extends Error {
  constructor() {
    super("GitHub token expired or revoked");
    this.name = "TokenExpiredError";
  }
}

export class RateLimitError extends Error {
  resetAt: number;
  constructor(resetAt: number) {
    const waitSec = Math.max(0, resetAt - Math.floor(Date.now() / 1000));
    super(`GitHub API rate limit reached. Resets in ${waitSec}s.`);
    this.name = "RateLimitError";
    this.resetAt = resetAt;
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function headers(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

function updateRateLimits(res: Response) {
  const remaining = res.headers.get("x-ratelimit-remaining");
  const reset = res.headers.get("x-ratelimit-reset");
  if (remaining !== null) rateLimitRemaining = parseInt(remaining, 10);
  if (reset !== null) rateLimitReset = parseInt(reset, 10);
}

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 1000;

async function request<T>(
  token: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  // Pre-flight check: if we know we're near the limit, block early
  if (rateLimitRemaining < 10) {
    const now = Math.floor(Date.now() / 1000);
    if (rateLimitReset > now) {
      throw new RateLimitError(rateLimitReset);
    }
  }

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    if (attempt > 0) {
      await sleep(BASE_DELAY_MS * Math.pow(2, attempt - 1));
    }

    const res = await fetch(`${API}${path}`, {
      ...init,
      headers: { ...headers(token), ...(init?.headers ?? {}) },
    });

    updateRateLimits(res);

    // Success
    if (res.ok) {
      return res.json();
    }

    // 401 — token expired or revoked
    if (res.status === 401) {
      throw new TokenExpiredError();
    }

    // 429 — primary rate limit
    if (res.status === 429) {
      const retryAfter = res.headers.get("retry-after");
      if (retryAfter && attempt < MAX_RETRIES) {
        await sleep(parseInt(retryAfter, 10) * 1000);
        continue;
      }
      throw new RateLimitError(rateLimitReset);
    }

    // 403 — could be secondary rate limit
    if (res.status === 403) {
      const body = await res.text().catch(() => "");
      if (body.includes("rate limit") || body.includes("abuse")) {
        if (attempt < MAX_RETRIES) continue;
        throw new RateLimitError(rateLimitReset);
      }
      throw new Error(`GitHub API 403: ${path} — ${body}`);
    }

    // Other errors — don't retry
    const body = await res.text().catch(() => "");
    lastError = new Error(`GitHub API ${res.status}: ${path} — ${body}`);
    break;
  }

  throw lastError ?? new Error(`GitHub API request failed: ${path}`);
}

// ── Repositories ──────────────────────────────────────────────────────────

export interface RepoRaw {
  owner: { login: string };
  name: string;
  full_name: string;
  default_branch: string;
  private: boolean;
  updated_at: string;
  description: string | null;
  html_url: string;
  permissions?: { admin: boolean; push: boolean; pull: boolean };
}

export async function listRepos(
  token: string,
  page = 1,
  perPage = 30,
): Promise<RepoRaw[]> {
  return request<RepoRaw[]>(
    token,
    `/user/repos?sort=updated&per_page=${perPage}&page=${page}&affiliation=owner,collaborator`,
  );
}

export async function getRepo(
  token: string,
  owner: string,
  repo: string,
): Promise<RepoRaw> {
  return request<RepoRaw>(token, `/repos/${owner}/${repo}`);
}

// ── Create repository ────────────────────────────────────────────────────

export interface CreateRepoOptions {
  name: string;
  description?: string;
  private?: boolean;
  auto_init?: boolean;
}

export async function createRepo(
  token: string,
  options: CreateRepoOptions,
): Promise<RepoRaw> {
  return request<RepoRaw>(token, `/user/repos`, {
    method: "POST",
    body: JSON.stringify({
      name: options.name,
      description: options.description ?? "",
      private: options.private ?? false,
      auto_init: options.auto_init ?? true,
    }),
  });
}

// ── Branches ──────────────────────────────────────────────────────────────

export interface BranchRaw {
  name: string;
  commit: { sha: string };
  protected: boolean;
}

export async function listBranches(
  token: string,
  owner: string,
  repo: string,
): Promise<BranchRaw[]> {
  return request<BranchRaw[]>(token, `/repos/${owner}/${repo}/branches`);
}

// ── File tree ─────────────────────────────────────────────────────────────

export interface TreeEntryRaw {
  path: string;
  mode: string;
  type: "blob" | "tree";
  sha: string;
  size?: number;
}

export interface TreeRaw {
  sha: string;
  tree: TreeEntryRaw[];
  truncated: boolean;
}

export async function getTree(
  token: string,
  owner: string,
  repo: string,
  sha: string,
  recursive = true,
): Promise<TreeRaw> {
  const q = recursive ? "?recursive=1" : "";
  return request<TreeRaw>(
    token,
    `/repos/${owner}/${repo}/git/trees/${sha}${q}`,
  );
}

// ── File content ──────────────────────────────────────────────────────────

export interface ContentRaw {
  name: string;
  path: string;
  sha: string;
  size: number;
  content: string; // Base64
  encoding: string;
  html_url: string;
}

export async function getFileContent(
  token: string,
  owner: string,
  repo: string,
  path: string,
  ref?: string,
): Promise<ContentRaw> {
  const q = ref ? `?ref=${encodeURIComponent(ref)}` : "";
  return request<ContentRaw>(
    token,
    `/repos/${owner}/${repo}/contents/${encodeURIComponent(path)}${q}`,
  );
}

export async function createOrUpdateFile(
  token: string,
  owner: string,
  repo: string,
  path: string,
  content: string,
  message: string,
  sha?: string,
  branch?: string,
): Promise<{ content: ContentRaw; commit: { sha: string } }> {
  const body: Record<string, string> = {
    message,
    content: btoa(unescape(encodeURIComponent(content))), // UTF-8 safe Base64
  };
  if (sha) body.sha = sha;
  if (branch) body.branch = branch;

  return request(token, `/repos/${owner}/${repo}/contents/${encodeURIComponent(path)}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function createOrUpdateFileBase64(
  token: string,
  owner: string,
  repo: string,
  path: string,
  base64Content: string,
  message: string,
  sha?: string,
  branch?: string,
): Promise<{ content: ContentRaw; commit: { sha: string } }> {
  const body: Record<string, string> = {
    message,
    content: base64Content,
  };
  if (sha) body.sha = sha;
  if (branch) body.branch = branch;

  return request(token, `/repos/${owner}/${repo}/contents/${encodeURIComponent(path)}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function deleteFile(
  token: string,
  owner: string,
  repo: string,
  path: string,
  sha: string,
  message: string,
  branch?: string,
): Promise<void> {
  const body: Record<string, string> = { message, sha };
  if (branch) body.branch = branch;

  await request<{ commit: { sha: string } }>(
    token,
    `/repos/${owner}/${repo}/contents/${encodeURIComponent(path)}`,
    { method: "DELETE", body: JSON.stringify(body) },
  );
}

// ── Commits ───────────────────────────────────────────────────────────────

export interface CommitRaw {
  sha: string;
  commit: {
    message: string;
    author: { name: string; date: string };
  };
  author: { login: string; avatar_url: string } | null;
  html_url: string;
}

export async function listCommits(
  token: string,
  owner: string,
  repo: string,
  branch?: string,
  path?: string,
  perPage = 20,
): Promise<CommitRaw[]> {
  const params = new URLSearchParams({ per_page: String(perPage) });
  if (branch) params.set("sha", branch);
  if (path) params.set("path", path);
  return request<CommitRaw[]>(
    token,
    `/repos/${owner}/${repo}/commits?${params}`,
  );
}

// ── Refs (for programmatic commits) ───────────────────────────────────────

export async function getRef(
  token: string,
  owner: string,
  repo: string,
  ref: string,
): Promise<{ ref: string; object: { sha: string } }> {
  return request(token, `/repos/${owner}/${repo}/git/ref/${ref}`);
}

export async function updateRef(
  token: string,
  owner: string,
  repo: string,
  ref: string,
  sha: string,
): Promise<void> {
  await request(token, `/repos/${owner}/${repo}/git/refs/${ref}`, {
    method: "PATCH",
    body: JSON.stringify({ sha }),
  });
}

// ── Collaborators ─────────────────────────────────────────────────────────

export interface CollaboratorRaw {
  login: string;
  avatar_url: string;
  permissions: { admin: boolean; push: boolean; pull: boolean };
}

export async function listCollaborators(
  token: string,
  owner: string,
  repo: string,
): Promise<CollaboratorRaw[]> {
  return request<CollaboratorRaw[]>(
    token,
    `/repos/${owner}/${repo}/collaborators`,
  );
}

// ── Branches (create / delete) ────────────────────────────────────────────

export async function createBranch(
  token: string,
  owner: string,
  repo: string,
  branchName: string,
  fromSha: string,
): Promise<{ ref: string; object: { sha: string } }> {
  return request(token, `/repos/${owner}/${repo}/git/refs`, {
    method: "POST",
    body: JSON.stringify({ ref: `refs/heads/${branchName}`, sha: fromSha }),
  });
}

export async function deleteBranch(
  token: string,
  owner: string,
  repo: string,
  branchName: string,
): Promise<void> {
  await request<void>(
    token,
    `/repos/${owner}/${repo}/git/refs/heads/${branchName}`,
    { method: "DELETE" },
  );
}

// ── Pull Requests ─────────────────────────────────────────────────────────

export interface PullRequestRaw {
  number: number;
  title: string;
  state: "open" | "closed";
  draft: boolean;
  html_url: string;
  head: { ref: string; sha: string };
  base: { ref: string };
  user: { login: string; avatar_url: string };
  created_at: string;
  updated_at: string;
  body: string | null;
  mergeable: boolean | null;
  changed_files?: number;
}

export async function listPullRequests(
  token: string,
  owner: string,
  repo: string,
  state: "open" | "closed" | "all" = "open",
): Promise<PullRequestRaw[]> {
  return request<PullRequestRaw[]>(
    token,
    `/repos/${owner}/${repo}/pulls?state=${state}&per_page=20`,
  );
}

export async function createPullRequest(
  token: string,
  owner: string,
  repo: string,
  title: string,
  body: string,
  head: string,
  base: string,
  draft = false,
): Promise<PullRequestRaw> {
  return request<PullRequestRaw>(token, `/repos/${owner}/${repo}/pulls`, {
    method: "POST",
    body: JSON.stringify({ title, body, head, base, draft }),
  });
}
