/**
 * Export / Import full IDE project state as a JSON file.
 * Gathers persisted slices from all stores and produces a downloadable blob.
 */

import { useIdeStore } from "../stores/ideStore";
import { useApiStore } from "../stores/apiStore";
import { useDatabaseStore } from "../stores/databaseStore";
import { useSkillStore } from "../stores/skillStore";
import { useRepoStore } from "../stores/repoStore";

/** Shape of the exported JSON file. */
export interface ProjectSnapshot {
  _format: "forgeds-project-state";
  _version: 1;
  exportedAt: string;
  ide: {
    tabs: Array<{
      id: string;
      name: string;
      path: string;
      content: string;
      language: string;
      isDirty: boolean;
    }>;
    activeTabId: string | null;
  };
  api: {
    apis: unknown[];
    selectedApiId: string | null;
  };
  database: {
    accessTables: unknown[];
    zohoForms: unknown[];
    tableMappings: unknown[];
    selectedMappingId: string | null;
  };
  skills: {
    activeSkillIds: string[];
  };
  repo: {
    selectedRepo: { owner: string; name: string } | null;
  };
}

/** Gather current state from all stores into a snapshot. */
export function captureSnapshot(): ProjectSnapshot {
  const ide = useIdeStore.getState();
  const api = useApiStore.getState();
  const db = useDatabaseStore.getState();
  const skills = useSkillStore.getState();
  const repo = useRepoStore.getState();

  return {
    _format: "forgeds-project-state",
    _version: 1,
    exportedAt: new Date().toISOString(),
    ide: {
      tabs: ide.tabs.map((t) => ({
        id: t.id,
        name: t.name,
        path: t.path,
        content: t.content,
        language: t.language,
        isDirty: t.isDirty,
      })),
      activeTabId: ide.activeTabId,
    },
    api: {
      apis: api.apis,
      selectedApiId: api.selectedApiId,
    },
    database: {
      accessTables: db.accessTables,
      zohoForms: db.zohoForms,
      tableMappings: db.tableMappings,
      selectedMappingId: db.selectedMappingId,
    },
    skills: {
      activeSkillIds: skills.activeSkillIds,
    },
    repo: {
      selectedRepo: repo.selectedRepo
        ? { owner: repo.selectedRepo.owner, name: repo.selectedRepo.name }
        : null,
    },
  };
}

/** Trigger a browser download of the snapshot as JSON. */
export function exportProjectState(): void {
  const snapshot = captureSnapshot();
  const json = JSON.stringify(snapshot, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = `forgeds-state-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** Validate that an object looks like a ProjectSnapshot. */
function isValidSnapshot(data: unknown): data is ProjectSnapshot {
  if (typeof data !== "object" || data === null) return false;
  const obj = data as Record<string, unknown>;
  return obj._format === "forgeds-project-state" && obj._version === 1;
}

/** Import a snapshot, restoring state into all stores. */
export function applySnapshot(snapshot: ProjectSnapshot): void {
  // IDE tabs
  if (snapshot.ide) {
    useIdeStore.setState({
      tabs: (snapshot.ide.tabs ?? []).map((t) => ({
        id: t.id,
        name: t.name,
        path: t.path,
        content: t.content,
        language: t.language,
        isDirty: t.isDirty ?? false,
      })),
      activeTabId: snapshot.ide.activeTabId ?? null,
    });
  }

  // API definitions
  if (snapshot.api) {
    useApiStore.setState({
      apis: (snapshot.api.apis ?? []) as ReturnType<typeof useApiStore.getState>["apis"],
      selectedApiId: snapshot.api.selectedApiId ?? null,
    });
  }

  // Database mappings
  if (snapshot.database) {
    useDatabaseStore.setState({
      accessTables: (snapshot.database.accessTables ?? []) as ReturnType<typeof useDatabaseStore.getState>["accessTables"],
      zohoForms: (snapshot.database.zohoForms ?? []) as ReturnType<typeof useDatabaseStore.getState>["zohoForms"],
      tableMappings: (snapshot.database.tableMappings ?? []) as ReturnType<typeof useDatabaseStore.getState>["tableMappings"],
      selectedMappingId: snapshot.database.selectedMappingId ?? null,
    });
  }

  // Skills — only restore active selection, not the skill definitions themselves
  if (snapshot.skills?.activeSkillIds) {
    for (const id of snapshot.skills.activeSkillIds) {
      useSkillStore.getState().activateSkill(id);
    }
  }
}

/**
 * Prompt the user with a file picker, read the selected JSON file,
 * validate it, and apply the snapshot. Returns a result message.
 */
export function importProjectState(): Promise<string> {
  return new Promise((resolve, reject) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json";

    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) {
        reject(new Error("No file selected"));
        return;
      }

      try {
        const text = await file.text();
        const data = JSON.parse(text);

        if (!isValidSnapshot(data)) {
          reject(new Error("Invalid project state file — missing format marker"));
          return;
        }

        applySnapshot(data);
        resolve(`Imported project state from ${data.exportedAt}`);
      } catch (err) {
        reject(
          err instanceof SyntaxError
            ? new Error("File is not valid JSON")
            : err,
        );
      }
    };

    // If user cancels the picker, nothing happens (no reject needed)
    input.click();
  });
}
