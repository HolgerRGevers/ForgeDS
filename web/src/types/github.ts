// GitHub API type definitions

export interface GitHubUser {
  login: string;
  id: number;
  avatar_url: string;
  name: string | null;
  email: string | null;
  html_url: string;
}

export interface RepoInfo {
  owner: string;
  name: string;
  full_name: string;
  default_branch: string;
  private: boolean;
  updated_at: string;
  description: string | null;
  html_url: string;
  permissions?: { admin: boolean; push: boolean; pull: boolean };
}

export interface GitTreeNode {
  path: string;
  name: string;
  type: "blob" | "tree";
  sha: string;
  size?: number;
  children?: GitTreeNode[];
  /** True if children have been fetched (for lazy loading) */
  loaded?: boolean;
}

export interface FileChange {
  path: string;
  content: string;
  action: "create" | "update" | "delete";
  originalSha?: string;
}

export interface CommitInfo {
  sha: string;
  message: string;
  author: string;
  avatar_url: string;
  date: string;
  html_url: string;
}

export interface BranchInfo {
  name: string;
  sha: string;
  protected: boolean;
}

export interface DeviceCodeResponse {
  device_code: string;
  user_code: string;
  verification_uri: string;
  expires_in: number;
  interval: number;
}

export type AuthStatus =
  | "unauthenticated"
  | "awaiting_code"
  | "polling"
  | "authenticated"
  | "error";

export interface AuthStore {
  status: AuthStatus;
  user: GitHubUser | null;
  token: string | null;
  error: string | null;
  deviceCode: DeviceCodeResponse | null;

  startLogin: () => Promise<void>;
  pollForToken: () => Promise<void>;
  logout: () => void;
  restoreSession: () => Promise<void>;
}

export interface RepoStore {
  repos: RepoInfo[];
  selectedRepo: RepoInfo | null;
  selectedBranch: string;
  branches: BranchInfo[];
  repoTree: GitTreeNode[];
  repoLoading: boolean;
  commits: CommitInfo[];
  pendingChanges: Map<string, FileChange>;

  fetchRepos: () => Promise<void>;
  selectRepo: (owner: string, repo: string) => Promise<void>;
  selectBranch: (branch: string) => Promise<void>;
  fetchTree: (path?: string) => Promise<void>;
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
}
