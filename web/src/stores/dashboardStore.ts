import { create } from "zustand";
import type { DashboardApp, RepoActivity, RepoEvent } from "../types/dashboard";
import {
  listUserRepos,
  hasManifest,
  listRepoEvents,
} from "../services/github-api";
import { useAuthStore } from "./authStore";
import { deriveBadgeInitials, hashToBadgeColor } from "../lib/badge-utils";

const PINNED_KEY = "forgeds-pinned-repos";
const TTL_MS = 5 * 60 * 1000;

interface DashboardState {
  apps: DashboardApp[];
  activity: RepoActivity[];
  pinnedRepos: string[];
  loading: boolean;
  error: string | null;
  lastFetchedAt: number | null;

  refresh: (force?: boolean) => Promise<void>;
  pinRepo: (fullName: string) => Promise<void>;
  unpinRepo: (fullName: string) => Promise<void>;
}

function loadPinned(): string[] {
  try {
    const raw = localStorage.getItem(PINNED_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function savePinned(list: string[]) {
  try {
    localStorage.setItem(PINNED_KEY, JSON.stringify(list));
  } catch {
    // ignore
  }
}

function eventKindFromPayload(type: string): RepoEvent["kind"] {
  if (type === "PushEvent") return "push";
  if (type === "PullRequestEvent") return "pr-opened";
  if (type === "ReleaseEvent") return "release";
  if (type === "WorkflowRunEvent") return "ci-failed";
  return "scaffold";
}

function summarizeEvent(ev: {
  type: string;
  payload: Record<string, unknown>;
}): string {
  switch (ev.type) {
    case "PushEvent": {
      const ref = (ev.payload.ref as string | undefined) ?? "";
      const branch = ref.replace("refs/heads/", "");
      return `Pushed to ${branch}`;
    }
    case "PullRequestEvent": {
      const action = ev.payload.action as string;
      const num = (ev.payload.number as number) ?? 0;
      const pr = ev.payload.pull_request as Record<string, unknown> | undefined;
      if (action === "closed" && pr?.merged) {
        return `PR #${num} merged`;
      }
      return `PR #${num} ${action}`;
    }
    case "ReleaseEvent": {
      const release = ev.payload.release as Record<string, unknown> | undefined;
      const tag = (release?.tag_name as string | undefined) ?? "release";
      return `${tag} published`;
    }
    case "WorkflowRunEvent": {
      const run = ev.payload.workflow_run as Record<string, unknown> | undefined;
      const conclusion = (run?.conclusion as string | undefined) ?? "ran";
      return `CI ${conclusion}`;
    }
    default:
      return ev.type;
  }
}

async function pickBatch<T, R>(
  items: T[],
  size: number,
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  const out: R[] = [];
  for (let i = 0; i < items.length; i += size) {
    const batch = items.slice(i, i + size);
    const results = await Promise.all(batch.map(fn));
    out.push(...results);
  }
  return out;
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  apps: [],
  activity: [],
  pinnedRepos: loadPinned(),
  loading: false,
  error: null,
  lastFetchedAt: null,

  refresh: async (force = false) => {
    const last = get().lastFetchedAt;
    if (!force && last && Date.now() - last < TTL_MS) return;

    const token = useAuthStore.getState().token;
    if (!token) return;

    set({ loading: true, error: null });
    try {
      const repos = await listUserRepos(token);

      const manifestFlags = await pickBatch(repos, 10, async (r) => ({
        full_name: r.full_name,
        has: await hasManifest(token, r.full_name).catch(() => false),
        repo: r,
      }));

      const pinned = get().pinnedRepos;
      const surfaced = manifestFlags.filter(
        (m) => m.has || pinned.includes(m.full_name),
      );

      const apps: DashboardApp[] = surfaced.map((m) => ({
        fullName: m.full_name,
        displayName: m.repo.name,
        badge: deriveBadgeInitials(m.repo.name),
        badgeColor: hashToBadgeColor(m.full_name),
        source: m.has ? "manifest" : "pinned",
        lastUpdated: m.repo.updated_at,
        hasManifest: m.has,
      }));

      apps.sort((a, b) => b.lastUpdated.localeCompare(a.lastUpdated));

      const activityRaw: RepoActivity[] = await pickBatch(
        apps,
        10,
        async (a) => ({
          repoFullName: a.fullName,
          events: (
            await listRepoEvents(token, a.fullName).catch(() => [])
          ).map((ev) => ({
            kind: eventKindFromPayload(ev.type),
            summary: summarizeEvent(ev),
            occurredAt: ev.created_at,
          })),
        }),
      );

      set({
        apps,
        activity: activityRaw,
        loading: false,
        lastFetchedAt: Date.now(),
      });
    } catch (err) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : "Refresh failed",
      });
    }
  },

  pinRepo: async (fullName) => {
    const list = Array.from(new Set([...get().pinnedRepos, fullName]));
    set({ pinnedRepos: list });
    savePinned(list);
    await get().refresh(true);
  },

  unpinRepo: async (fullName) => {
    const list = get().pinnedRepos.filter((n) => n !== fullName);
    set({ pinnedRepos: list });
    savePinned(list);
    await get().refresh(true);
  },
}));
