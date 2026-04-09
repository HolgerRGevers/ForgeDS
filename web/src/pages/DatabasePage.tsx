import { useCallback, useEffect, useState } from "react";
import { useDatabaseStore } from "../stores/databaseStore";
import { useBridgeStore } from "../stores/bridgeStore";
import {
  SourceTargetPanel,
  FieldMappingTable,
  ValidationConsole,
  UploadWizard,
} from "../components/database";

type BottomTab = "validation" | "upload";

export default function DatabasePage() {
  const status = useBridgeStore((s) => s.status);
  const connect = useBridgeStore((s) => s.connect);
  const send = useBridgeStore((s) => s.send);

  const accessTables = useDatabaseStore((s) => s.accessTables);
  const zohoForms = useDatabaseStore((s) => s.zohoForms);
  const setAccessTables = useDatabaseStore((s) => s.setAccessTables);
  const setZohoForms = useDatabaseStore((s) => s.setZohoForms);
  const setTableMappings = useDatabaseStore((s) => s.setTableMappings);

  const [activeTab, setActiveTab] = useState<BottomTab>("validation");
  const [loading, setLoading] = useState(false);
  const [schemaStatus, setSchemaStatus] = useState<string | null>(null);

  // Load schema from bridge
  const loadSchema = useCallback(async () => {
    setLoading(true);
    setSchemaStatus(null);
    try {
      const response = await send("get_schema", {});
      if (response) {
        if (Array.isArray(response.accessTables)) {
          setAccessTables(response.accessTables as never[]);
        }
        if (Array.isArray(response.zohoForms)) {
          setZohoForms(response.zohoForms as never[]);
        }
        if (Array.isArray(response.tableMappings)) {
          setTableMappings(response.tableMappings as never[]);
        }
        const tableCount = Array.isArray(response.accessTables)
          ? response.accessTables.length
          : 0;
        const formCount = Array.isArray(response.zohoForms)
          ? response.zohoForms.length
          : 0;
        setSchemaStatus(`Schema loaded: ${tableCount} tables, ${formCount} forms`);
      }
    } catch {
      setSchemaStatus("Failed to load schema");
    } finally {
      setLoading(false);
    }
  }, [send, setAccessTables, setZohoForms, setTableMappings]);

  // Refresh: clear state and reload
  const refreshSchema = useCallback(async () => {
    setAccessTables([]);
    setZohoForms([]);
    setTableMappings([]);
    setSchemaStatus(null);
    await loadSchema();
  }, [loadSchema, setAccessTables, setZohoForms, setTableMappings]);

  // On mount: connect and load schema
  useEffect(() => {
    if (status === "disconnected") {
      connect();
    }
  }, [status, connect]);

  useEffect(() => {
    if (status === "connected" && accessTables.length === 0 && zohoForms.length === 0) {
      loadSchema();
    }
  }, [status, accessTables.length, zohoForms.length, loadSchema]);

  // Connection status badge
  const connectionBadge = (() => {
    switch (status) {
      case "connected":
        return (
          <span className="rounded-full bg-green-900/50 px-2.5 py-0.5 text-xs font-medium text-green-400">
            Connected
          </span>
        );
      case "connecting":
        return (
          <span className="rounded-full bg-yellow-900/50 px-2.5 py-0.5 text-xs font-medium text-yellow-400">
            Connecting...
          </span>
        );
      default:
        return (
          <span className="rounded-full bg-gray-700 px-2.5 py-0.5 text-xs font-medium text-gray-400">
            Disconnected
          </span>
        );
    }
  })();

  return (
    <div className="flex h-full flex-col bg-gray-900">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-gray-700 px-4 py-2">
        <div className="flex items-center gap-2">
          <button
            onClick={loadSchema}
            disabled={loading || status !== "connected"}
            className="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Loading..." : "Load Schema"}
          </button>
          <button
            onClick={refreshSchema}
            disabled={loading || status !== "connected"}
            className="rounded border border-gray-600 bg-gray-800 px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:border-gray-500 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Refresh
          </button>
        </div>

        <div className="flex items-center gap-3">
          {schemaStatus && (
            <span className="text-xs text-gray-400">{schemaStatus}</span>
          )}
          {connectionBadge}
        </div>
      </div>

      {/* Source/Target Panel (~40%) */}
      <div className="min-h-0" style={{ flex: "4 1 0%" }}>
        <SourceTargetPanel />
      </div>

      {/* Field Mapping Table (~35%) */}
      <div className="min-h-0 border-t border-gray-700" style={{ flex: "3.5 1 0%" }}>
        <FieldMappingTable />
      </div>

      {/* Bottom tabs (~25%) */}
      <div className="flex min-h-0 flex-col border-t border-gray-700" style={{ flex: "2.5 1 0%" }}>
        {/* Tab bar */}
        <div className="flex border-b border-gray-700">
          <button
            onClick={() => setActiveTab("validation")}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              activeTab === "validation"
                ? "border-b-2 border-blue-500 text-blue-400"
                : "text-gray-400 hover:text-gray-300"
            }`}
          >
            Validation
          </button>
          <button
            onClick={() => setActiveTab("upload")}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              activeTab === "upload"
                ? "border-b-2 border-blue-500 text-blue-400"
                : "text-gray-400 hover:text-gray-300"
            }`}
          >
            Upload
          </button>
        </div>

        {/* Tab content */}
        <div className="min-h-0 flex-1">
          {activeTab === "validation" ? <ValidationConsole /> : <UploadWizard />}
        </div>
      </div>
    </div>
  );
}
