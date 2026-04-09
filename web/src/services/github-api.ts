/**
 * GitHub REST API wrapper.
 *
 * All calls use the stored OAuth token. Every function accepts the token
 * explicitly so the module stays stateless — callers (stores) manage the
 * token lifecycle.
 */

const API = "https://api.github.com";

function headers(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

async function request<T>(
  token: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { ...headers(token), ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`GitHub API ${res.status}: ${path} — ${body}`);
  }
  return res.json();
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

  await fetch(`${API}/repos/${owner}/${repo}/contents/${encodeURIComponent(path)}`, {
    method: "DELETE",
    headers: headers(token),
    body: JSON.stringify(body),
  });
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
