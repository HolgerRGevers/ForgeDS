export interface RepoEvent {
  kind: "push" | "pr-merged" | "pr-opened" | "release" | "ci-failed" | "scaffold";
  summary: string;
  occurredAt: string;
}

export interface RepoActivity {
  repoFullName: string;
  events: RepoEvent[];
}

export interface DashboardApp {
  fullName: string;
  displayName: string;
  badge: string;
  badgeColor: string;
  source: "manifest" | "pinned";
  lastUpdated: string;
  hasManifest: boolean;
}
