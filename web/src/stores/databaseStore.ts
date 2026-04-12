import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { DatabaseStore } from "../types/database";

export const useDatabaseStore = create<DatabaseStore>()(persist(
  (set, get) => ({
  // --- State ---
  accessTables: [],
  zohoForms: [],

  tableMappings: [],
  selectedMappingId: null,

  validationResults: [],

  uploadState: {
    status: "idle",
    progress: 0,
    totalRecords: 0,
    uploadedRecords: 0,
    errors: [],
  },

  csvFiles: [],

  // --- Actions ---

  setAccessTables: (tables) => {
    set({ accessTables: tables });
  },

  setZohoForms: (forms) => {
    set({ zohoForms: forms });
  },

  setTableMappings: (mappings) => {
    set({ tableMappings: mappings });
  },

  selectMapping: (id) => {
    set({ selectedMappingId: id });
  },

  updateFieldMapping: (mappingId, fieldMappingId, updates) => {
    set({
      tableMappings: get().tableMappings.map((tm) =>
        tm.id === mappingId
          ? {
              ...tm,
              fieldMappings: tm.fieldMappings.map((fm) =>
                fm.id === fieldMappingId ? { ...fm, ...updates } : fm,
              ),
            }
          : tm,
      ),
    });
  },

  addValidationResult: (result) => {
    set({ validationResults: [result, ...get().validationResults] });
  },

  clearValidationResults: () => {
    set({ validationResults: [] });
  },

  setUploadState: (state) => {
    set({ uploadState: { ...get().uploadState, ...state } });
  },

  addCsvFile: (file) => {
    set({ csvFiles: [...get().csvFiles, file] });
  },

  removeCsvFile: (name) => {
    set({ csvFiles: get().csvFiles.filter((f) => f.name !== name) });
  },
}),
  {
    name: "forgeds-database-mappings",
    partialize: (state) => ({
      accessTables: state.accessTables,
      zohoForms: state.zohoForms,
      tableMappings: state.tableMappings,
      selectedMappingId: state.selectedMappingId,
    }),
  },
));
