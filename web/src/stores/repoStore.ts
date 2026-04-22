import { create } from "zustand";
import * as gh from "../services/github-api";
import { sleep, TokenExpiredError } from "../services/github-api";
import type {
  RepoInfo,
  BranchInfo,
  GitTreeNode,
  CommitInfo,
  FileChange,
} from "../types/github";
import { useAuthStore } from "./authStore";

export interface Collaborator {
  login: string;
  avatar_url: string;
  role: "admin" | "write" | "read";
}

export interface PullRequestInfo {
  number: number;
  title: string;
  state: "open" | "closed";
  draft: boolean;
  html_url: string;
  headBranch: string;
  baseBranch: string;
  author: string;
  avatar_url: string;
}

interface RepoState {
  repos: RepoInfo[];
  selectedRepo: RepoInfo | null;
  selectedBranch: string;
  branches: BranchInfo[];
  repoTree: GitTreeNode[];
  repoLoading: boolean;
  commits: CommitInfo[];
  pendingChanges: Map<string, FileChange>;
  collaborators: Collaborator[];
  pullRequests: PullRequestInfo[];

  fetchRepos: () => Promise<void>;
  selectRepo: (owner: string, repo: string) => Promise<void>;
  selectBranch: (branch: string) => Promise<void>;
  fetchTree: () => Promise<void>;
  fetchFileContent: (path: string) => Promise<string>;
  stageChange: (
    path: string,
    content: string,
    action: FileChange["action"],
    originalSha?: string,
  ) => void;
  commitChanges: (message: string) => Promise<void>;
  discardChanges: () => void;
  fetchCommits: () => Promise<void>;
  uploadResource: (filename: string, content: string) => Promise<void>;
  fetchCollaborators: () => Promise<void>;
  fetchPullRequests: () => Promise<void>;
  createBranch: (name: string) => Promise<void>;
  deleteBranch: (name: string) => Promise<void>;
  createPR: (title: string, body: string, base: string, draft?: boolean) => Promise<string>;
  createNewRepo: (name: string, description: string, isPrivate: boolean, autoInit: boolean) => Promise<void>;
  batchUploadFiles: (files: Array<{ path: string; content: string; isBinary: boolean }>, commitMessage: string) => Promise<void>;
  batchUploadToBranch: (branchName: string, files: Array<{ path: string; content: string; isBinary: boolean }>, commitMessage: string) => Promise<void>;
  setSelectedRepoByFullName: (fullName: string) => Promise<void>;
}

/** Get token or throw. */
function token(): string {
  const t = useAuthStore.getState().token;
  if (!t) throw new Error("Not authenticated");
  return t;
}

/** Handle TokenExpiredError by logging out. Rethrows other errors. */
function handleApiError(err: unknown): never {
  if (err instanceof TokenExpiredError) {
    useAuthStore.getState().handleTokenExpired();
  }
  throw err;
}

/** Convert flat GitHub tree entries into a nested GitTreeNode[]. */
function buildTree(entries: gh.TreeEntryRaw[]): GitTreeNode[] {
  const root: GitTreeNode[] = [];
  const dirs = new Map<string, GitTreeNode>();

  // Sort so directories come before files, then alphabetically
  const sorted = [...entries].sort((a, b) => {
    if (a.type !== b.type) return a.type === "tree" ? -1 : 1;
    return a.path.localeCompare(b.path);
  });

  for (const entry of sorted) {
    const parts = entry.path.split("/");
    const name = parts[parts.length - 1];
    const node: GitTreeNode = {
      path: entry.path,
      name,
      type: entry.type,
      sha: entry.sha,
      size: entry.size,
      children: entry.type === "tree" ? [] : undefined,
      loaded: entry.type === "tree",
    };

    if (entry.type === "tree") {
      dirs.set(entry.path, node);
    }

    if (parts.length === 1) {
      root.push(node);
    } else {
      const parentPath = parts.slice(0, -1).join("/");
      const parent = dirs.get(parentPath);
      if (parent?.children) {
        parent.children.push(node);
      } else {
        // Orphan — put at root
        root.push(node);
      }
    }
  }

  return root;
}

const SELECTED_REPO_KEY = "forgeds-selected-repo";

export const useRepoStore = create<RepoState>((set, get) => ({
  repos: [],
  selectedRepo: null,
  selectedBranch: "",
  branches: [],
  repoTree: [],
  repoLoading: false,
  commits: [],
  pendingChanges: new Map(),
  collaborators: [],
  pullRequests: [],

  fetchRepos: async () => {
    set({ repoLoading: true });
    try {
      const raw = await gh.listRepos(token());
      const repos: RepoInfo[] = raw.map((r) => ({
        owner: r.owner.login,
        name: r.name,
        full_name: r.full_name,
        default_branch: r.default_branch,
        private: r.private,
        updated_at: r.updated_at,
        description: r.description,
        html_url: r.html_url,
        permissions: r.permissions,
      }));
      set({ repos });
    } catch (err) {
      handleApiError(err);
    } finally {
      set({ repoLoading: false });
    }
  },

  selectRepo: async (owner, repo) => {
    set({ repoLoading: true, repoTree: [], commits: [], pendingChanges: new Map() });
    try {
      const raw = await gh.getRepo(token(), owner, repo);
      const info: RepoInfo = {
        owner: raw.owner.login,
        name: raw.name,
        full_name: raw.full_name,
        default_branch: raw.default_branch,
        private: raw.private,
        updated_at: raw.updated_at,
        description: raw.description,
        html_url: raw.html_url,
        permissions: raw.permissions,
      };

      // Fetch branches
      const branchesRaw = await gh.listBranches(token(), owner, repo);
      const branches: BranchInfo[] = branchesRaw.map((b) => ({
        name: b.name,
        sha: b.commit.sha,
        protected: b.protected,
      }));

      localStorage.setItem(SELECTED_REPO_KEY, JSON.stringify({ owner, repo }));

      set({
        selectedRepo: info,
        selectedBranch: raw.default_branch,
        branches,
      });

      // Fetch tree for default branch
      await get().fetchTree();
      await get().fetchCommits();
    } finally {
      set({ repoLoading: false });
    }
  },

  selectBranch: async (branch) => {
    set({ selectedBranch: branch, repoTree: [], pendingChanges: new Map() });
    await get().fetchTree();
    await get().fetchCommits();
  },

  fetchTree: async () => {
    const { selectedRepo, selectedBranch } = get();
    if (!selectedRepo) return;

    set({ repoLoading: true });
    try {
      const ref = await gh.getRef(
        token(),
        selectedRepo.owner,
        selectedRepo.name,
        `heads/${selectedBranch}`,
      );
      const tree = await gh.getTree(
        token(),
        selectedRepo.owner,
        selectedRepo.name,
        ref.object.sha,
        true,
      );
      set({ repoTree: buildTree(tree.tree) });
    } finally {
      set({ repoLoading: false });
    }
  },

  fetchFileContent: async (path) => {
    const { selectedRepo, selectedBranch } = get();
    if (!selectedRepo) throw new Error("No repo selected");

    const raw = await gh.getFileContent(
      token(),
      selectedRepo.owner,
      selectedRepo.name,
      path,
      selectedBranch,
    );
    // GitHub returns Base64 content
    return decodeURIComponent(escape(atob(raw.content.replace(/\n/g, ""))));
  },

  stageChange: (path, content, action, originalSha) => {
    const changes = new Map(get().pendingChanges);
    changes.set(path, { path, content, action, originalSha });
    set({ pendingChanges: changes });
  },

  commitChanges: async (message) => {
    const { selectedRepo, selectedBranch, pendingChanges } = get();
    if (!selectedRepo || pendingChanges.size === 0) return;

    // Commit each file change via the Contents API (throttled)
    let i = 0;
    for (const [, change] of pendingChanges) {
      if (i > 0) await sleep(200);
      if (change.action === "delete") {
        if (change.originalSha) {
          await gh.deleteFile(
            token(),
            selectedRepo.owner,
            selectedRepo.name,
            change.path,
            change.originalSha,
            message,
            selectedBranch,
          );
        }
      } else {
        await gh.createOrUpdateFile(
          token(),
          selectedRepo.owner,
          selectedRepo.name,
          change.path,
          change.content,
          message,
          change.originalSha,
          selectedBranch,
        );
      }
      i++;
    }

    set({ pendingChanges: new Map() });
    // Refresh tree and commits
    await get().fetchTree();
    await get().fetchCommits();
  },

  discardChanges: () => {
    set({ pendingChanges: new Map() });
  },

  fetchCommits: async () => {
    const { selectedRepo, selectedBranch } = get();
    if (!selectedRepo) return;

    const raw = await gh.listCommits(
      token(),
      selectedRepo.owner,
      selectedRepo.name,
      selectedBranch,
    );
    const commits: CommitInfo[] = raw.map((c) => ({
      sha: c.sha,
      message: c.commit.message,
      author: c.author?.login ?? c.commit.author.name,
      avatar_url: c.author?.avatar_url ?? "",
      date: c.commit.author.date,
      html_url: c.html_url,
    }));
    set({ commits });
  },

  uploadResource: async (filename, content) => {
    const { selectedRepo, selectedBranch } = get();
    if (!selectedRepo) throw new Error("No repo selected");

    const path = `resources/${filename}`;
    // Check if file already exists to get its sha
    let sha: string | undefined;
    try {
      const existing = await gh.getFileContent(
        token(),
        selectedRepo.owner,
        selectedRepo.name,
        path,
        selectedBranch,
      );
      sha = existing.sha;
    } catch {
      // File doesn't exist yet — that's fine
    }

    await gh.createOrUpdateFile(
      token(),
      selectedRepo.owner,
      selectedRepo.name,
      path,
      content,
      `Add resource: ${filename}`,
      sha,
      selectedBranch,
    );

    await get().fetchTree();
  },

  fetchCollaborators: async () => {
    const { selectedRepo } = get();
    if (!selectedRepo) return;

    try {
      const raw = await gh.listCollaborators(
        token(),
        selectedRepo.owner,
        selectedRepo.name,
      );
      const collaborators: Collaborator[] = raw.map((c) => ({
        login: c.login,
        avatar_url: c.avatar_url,
        role: c.permissions.admin
          ? "admin"
          : c.permissions.push
            ? "write"
            : "read",
      }));
      set({ collaborators });
    } catch {
      // May fail on repos where user doesn't have admin access
      set({ collaborators: [] });
    }
  },

  fetchPullRequests: async () => {
    const { selectedRepo } = get();
    if (!selectedRepo) return;

    const raw = await gh.listPullRequests(
      token(),
      selectedRepo.owner,
      selectedRepo.name,
    );
    const pullRequests: PullRequestInfo[] = raw.map((pr) => ({
      number: pr.number,
      title: pr.title,
      state: pr.state,
      draft: pr.draft,
      html_url: pr.html_url,
      headBranch: pr.head.ref,
      baseBranch: pr.base.ref,
      author: pr.user.login,
      avatar_url: pr.user.avatar_url,
    }));
    set({ pullRequests });
  },

  createBranch: async (name) => {
    const { selectedRepo, selectedBranch } = get();
    if (!selectedRepo) throw new Error("No repo selected");

    const ref = await gh.getRef(
      token(),
      selectedRepo.owner,
      selectedRepo.name,
      `heads/${selectedBranch}`,
    );
    await gh.createBranch(
      token(),
      selectedRepo.owner,
      selectedRepo.name,
      name,
      ref.object.sha,
    );

    // Refresh branches and switch to the new one
    const branchesRaw = await gh.listBranches(
      token(),
      selectedRepo.owner,
      selectedRepo.name,
    );
    const branches: BranchInfo[] = branchesRaw.map((b) => ({
      name: b.name,
      sha: b.commit.sha,
      protected: b.protected,
    }));
    set({ branches, selectedBranch: name });
    await get().fetchTree();
  },

  deleteBranch: async (name) => {
    const { selectedRepo } = get();
    if (!selectedRepo) throw new Error("No repo selected");

    await gh.deleteBranch(
      token(),
      selectedRepo.owner,
      selectedRepo.name,
      name,
    );

    // Refresh branches
    const branchesRaw = await gh.listBranches(
      token(),
      selectedRepo.owner,
      selectedRepo.name,
    );
    const branches: BranchInfo[] = branchesRaw.map((b) => ({
      name: b.name,
      sha: b.commit.sha,
      protected: b.protected,
    }));
    set({ branches });
  },

  createPR: async (title, body, base, draft = false) => {
    const { selectedRepo, selectedBranch } = get();
    if (!selectedRepo) throw new Error("No repo selected");

    const pr = await gh.createPullRequest(
      token(),
      selectedRepo.owner,
      selectedRepo.name,
      title,
      body,
      selectedBranch,
      base,
      draft,
    );

    await get().fetchPullRequests();
    return pr.html_url;
  },

  createNewRepo: async (name, description, isPrivate, autoInit) => {
    const raw = await gh.createRepo(token(), {
      name,
      description,
      private: isPrivate,
      auto_init: autoInit,
    });
    const info: RepoInfo = {
      owner: raw.owner.login,
      name: raw.name,
      full_name: raw.full_name,
      default_branch: raw.default_branch,
      private: raw.private,
      updated_at: raw.updated_at,
      description: raw.description,
      html_url: raw.html_url,
      permissions: raw.permissions,
    };
    set({ repos: [info, ...get().repos] });
    await get().selectRepo(raw.owner.login, raw.name);
  },

  batchUploadFiles: async (files, commitMessage) => {
    const { selectedRepo, selectedBranch } = get();
    if (!selectedRepo) throw new Error("No repo selected");

    for (let i = 0; i < files.length; i++) {
      if (i > 0) await sleep(200); // Throttle to respect secondary rate limits
      const file = files[i];
      const path = file.path;
      let sha: string | undefined;
      try {
        const existing = await gh.getFileContent(
          token(),
          selectedRepo.owner,
          selectedRepo.name,
          path,
          selectedBranch,
        );
        sha = existing.sha;
      } catch {
        // File doesn't exist yet
      }

      if (file.isBinary) {
        await gh.createOrUpdateFileBase64(
          token(),
          selectedRepo.owner,
          selectedRepo.name,
          path,
          file.content,
          commitMessage,
          sha,
          selectedBranch,
        );
      } else {
        await gh.createOrUpdateFile(
          token(),
          selectedRepo.owner,
          selectedRepo.name,
          path,
          file.content,
          commitMessage,
          sha,
          selectedBranch,
        );
      }
    }

    await get().fetchTree();
    await get().fetchCommits();
  },

  setSelectedRepoByFullName: async (fullName) => {
    const existing = get().repos.find((r) => r.full_name === fullName);
    if (existing) {
      await get().selectRepo(existing.owner, existing.name);
      return;
    }
    const [owner, repo] = fullName.split("/");
    await get().selectRepo(owner, repo);
  },

  batchUploadToBranch: async (branchName, files, commitMessage) => {
    const { selectedRepo, selectedBranch } = get();
    if (!selectedRepo) throw new Error("No repo selected");

    // Create the feature branch from current HEAD
    const ref = await gh.getRef(
      token(),
      selectedRepo.owner,
      selectedRepo.name,
      `heads/${selectedBranch}`,
    );
    await gh.createBranch(
      token(),
      selectedRepo.owner,
      selectedRepo.name,
      branchName,
      ref.object.sha,
    );

    // Upload files to the new branch
    for (let i = 0; i < files.length; i++) {
      if (i > 0) await sleep(200);
      const file = files[i];

      if (file.isBinary) {
        await gh.createOrUpdateFileBase64(
          token(),
          selectedRepo.owner,
          selectedRepo.name,
          file.path,
          file.content,
          commitMessage,
          undefined,
          branchName,
        );
      } else {
        await gh.createOrUpdateFile(
          token(),
          selectedRepo.owner,
          selectedRepo.name,
          file.path,
          file.content,
          commitMessage,
          undefined,
          branchName,
        );
      }
    }

    // Switch to the new branch
    const branchesRaw = await gh.listBranches(
      token(),
      selectedRepo.owner,
      selectedRepo.name,
    );
    const branches: BranchInfo[] = branchesRaw.map((b) => ({
      name: b.name,
      sha: b.commit.sha,
      protected: b.protected,
    }));
    set({ branches, selectedBranch: branchName });
    await get().fetchTree();
    await get().fetchCommits();
  },
}));
