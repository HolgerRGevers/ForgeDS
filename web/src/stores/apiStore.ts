import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  ApiParameter,
  ApiStore,
  CustomApiDefinition,
  StatusCodeMapping,
  WizardStep,
} from "../types/api";

/** Generate a link name from a display name (lowercase, underscores for spaces) */
function toLinkName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\s_]/g, "")
    .replace(/\s+/g, "_");
}

/** Create a blank draft with sensible defaults */
function createEmptyDraft(): CustomApiDefinition {
  const now = Date.now();
  return {
    id: now.toString(36),
    name: "",
    linkName: "",
    description: "",
    method: "GET",
    auth: "oauth2",
    userScope: "all_users",
    parameters: [],
    responseType: "standard",
    statusCodes: [],
    application: "",
    namespace: "",
    functionName: "",
    generatedCode: "",
    createdAt: now,
    updatedAt: now,
  };
}

export const useApiStore = create<ApiStore>()(persist(
  (set, get) => ({
  // --- State ---
  apis: [],
  selectedApiId: null,

  wizardStep: "basic" as WizardStep,
  draftApi: null,
  isCreating: false,

  // --- Actions ---

  setApis: (apis) => {
    set({ apis });
  },

  selectApi: (id) => {
    set({ selectedApiId: id });
  },

  // --- Wizard actions ---

  startCreate: () => {
    set({
      draftApi: createEmptyDraft(),
      wizardStep: "basic",
      isCreating: true,
    });
  },

  startEdit: (id) => {
    const api = get().apis.find((a) => a.id === id);
    if (api) {
      set({
        draftApi: { ...api },
        wizardStep: "basic",
        isCreating: true,
      });
    }
  },

  setWizardStep: (step) => {
    set({ wizardStep: step });
  },

  updateDraft: (updates) => {
    const draft = get().draftApi;
    if (!draft) return;

    const merged = { ...draft, ...updates, updatedAt: Date.now() };

    // Auto-generate linkName when name changes
    if (updates.name !== undefined) {
      merged.linkName = toLinkName(updates.name);
    }

    set({ draftApi: merged });
  },

  addParameter: (param: ApiParameter) => {
    const draft = get().draftApi;
    if (!draft) return;
    set({
      draftApi: {
        ...draft,
        parameters: [...draft.parameters, param],
        updatedAt: Date.now(),
      },
    });
  },

  removeParameter: (paramId) => {
    const draft = get().draftApi;
    if (!draft) return;
    set({
      draftApi: {
        ...draft,
        parameters: draft.parameters.filter((p) => p.id !== paramId),
        updatedAt: Date.now(),
      },
    });
  },

  updateParameter: (paramId, updates) => {
    const draft = get().draftApi;
    if (!draft) return;
    set({
      draftApi: {
        ...draft,
        parameters: draft.parameters.map((p) =>
          p.id === paramId ? { ...p, ...updates } : p,
        ),
        updatedAt: Date.now(),
      },
    });
  },

  addStatusCode: (mapping: StatusCodeMapping) => {
    const draft = get().draftApi;
    if (!draft) return;
    set({
      draftApi: {
        ...draft,
        statusCodes: [...draft.statusCodes, mapping],
        updatedAt: Date.now(),
      },
    });
  },

  removeStatusCode: (statusCode) => {
    const draft = get().draftApi;
    if (!draft) return;
    set({
      draftApi: {
        ...draft,
        statusCodes: draft.statusCodes.filter(
          (sc) => sc.statusCode !== statusCode,
        ),
        updatedAt: Date.now(),
      },
    });
  },

  saveDraft: () => {
    const draft = get().draftApi;
    if (!draft) return;

    const existing = get().apis.find((a) => a.id === draft.id);
    const apis = existing
      ? get().apis.map((a) => (a.id === draft.id ? draft : a))
      : [...get().apis, draft];

    set({
      apis,
      draftApi: null,
      isCreating: false,
      wizardStep: "basic",
    });
  },

  cancelDraft: () => {
    set({
      draftApi: null,
      isCreating: false,
      wizardStep: "basic",
    });
  },

  deleteApi: (id) => {
    set({
      apis: get().apis.filter((a) => a.id !== id),
      selectedApiId: get().selectedApiId === id ? null : get().selectedApiId,
    });
  },
}),
  {
    name: "forgeds-api-definitions",
    partialize: (state) => ({
      apis: state.apis,
      selectedApiId: state.selectedApiId,
    }),
  },
));
