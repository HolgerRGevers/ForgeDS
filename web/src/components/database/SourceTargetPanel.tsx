import { useCallback, useRef } from "react";
import { useDatabaseStore } from "../../stores/databaseStore";
import type { TableMapping } from "../../types/database";

// --- Status colors ---

const statusColors: Record<TableMapping["status"], string> = {
  complete: "bg-green-500",
  partial: "bg-yellow-500",
  unmapped: "bg-gray-500",
};

const statusLineColors: Record<TableMapping["status"], string> = {
  complete: "text-green-400",
  partial: "text-yellow-400",
  unmapped: "text-gray-500",
};

// --- Count badge ---

function CountBadge({ count, label }: { count: number; label?: string }) {
  return (
    <span className="ml-auto rounded-full bg-gray-700 px-2 py-0.5 text-xs font-medium text-gray-300">
      {count}
      {label ? ` ${label}` : ""}
    </span>
  );
}

// --- Status dot ---

function StatusDot({ mapped }: { mapped: boolean }) {
  return (
    <span
      className={`inline-block h-2 w-2 flex-shrink-0 rounded-full ${mapped ? "bg-green-500" : "bg-gray-500"}`}
      title={mapped ? "Mapped" : "Unmapped"}
    />
  );
}

// --- CSV chip ---

function CsvChip({
  name,
  onRemove,
}: {
  name: string;
  onRemove: () => void;
}) {
  return (
    <span className="inline-flex items-center gap-1 rounded bg-gray-700 px-2 py-0.5 text-xs text-gray-300">
      {name}
      <button
        onClick={onRemove}
        className="ml-0.5 text-gray-500 hover:text-red-400"
        title={`Remove ${name}`}
      >
        x
      </button>
    </span>
  );
}

// --- Main component ---

export function SourceTargetPanel() {
  const accessTables = useDatabaseStore((s) => s.accessTables);
  const zohoForms = useDatabaseStore((s) => s.zohoForms);
  const tableMappings = useDatabaseStore((s) => s.tableMappings);
  const selectedMappingId = useDatabaseStore((s) => s.selectedMappingId);
  const csvFiles = useDatabaseStore((s) => s.csvFiles);
  const selectMapping = useDatabaseStore((s) => s.selectMapping);
  const addCsvFile = useDatabaseStore((s) => s.addCsvFile);
  const removeCsvFile = useDatabaseStore((s) => s.removeCsvFile);

  const dropRef = useRef<HTMLDivElement>(null);

  // Build lookup maps
  const mappingByAccess = new Map<string, TableMapping>();
  const mappingByZoho = new Map<string, TableMapping>();
  for (const m of tableMappings) {
    mappingByAccess.set(m.accessTable, m);
    mappingByZoho.set(m.zohoForm, m);
  }

  // Click handler for table/form cards
  const handleCardClick = useCallback(
    (mappingId: string | undefined) => {
      if (mappingId) {
        selectMapping(
          mappingId === selectedMappingId ? null : mappingId,
        );
      }
    },
    [selectMapping, selectedMappingId],
  );

  // CSV drop handlers
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const files = Array.from(e.dataTransfer.files);
      for (const file of files) {
        if (file.name.toLowerCase().endsWith(".csv")) {
          addCsvFile({ name: file.name, rowCount: 0 });
        }
      }
    },
    [addCsvFile],
  );

  return (
    <div className="flex h-full flex-col bg-gray-900">
      {/* Panel header */}
      <div className="flex items-center border-b border-gray-700 px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
          Source / Target Mapping
        </span>
      </div>

      {/* Three-column layout */}
      <div className="flex flex-1 gap-0 overflow-hidden">
        {/* Left column: Access Tables */}
        <div className="flex w-5/12 flex-col border-r border-gray-700/50">
          <div className="flex items-center border-b border-gray-700/50 px-3 py-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              Access Tables
            </h3>
            <CountBadge count={accessTables.length} />
          </div>

          <div className="flex-1 overflow-y-auto px-2 py-1">
            {accessTables.length === 0 && (
              <p className="px-2 py-4 text-center text-sm text-gray-500">
                No tables loaded
              </p>
            )}
            {accessTables.map((table) => {
              const mapping = mappingByAccess.get(table.name);
              const isSelected = mapping?.id === selectedMappingId;
              return (
                <button
                  key={table.name}
                  onClick={() => handleCardClick(mapping?.id)}
                  className={`mb-1 flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm transition-colors ${
                    isSelected
                      ? "border border-blue-500 bg-gray-800"
                      : "border border-transparent hover:bg-gray-800/60"
                  } ${mapping ? "cursor-pointer" : "cursor-default"}`}
                >
                  <StatusDot mapped={!!mapping} />
                  <span className="flex-1 truncate font-mono text-gray-200">
                    {table.name}
                  </span>
                  <CountBadge count={table.columns.length} label="cols" />
                </button>
              );
            })}
          </div>

          {/* CSV drop zone */}
          <div className="border-t border-gray-700/50 px-2 py-2">
            <div
              ref={dropRef}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              className="flex min-h-[48px] flex-col items-center justify-center rounded border-2 border-dashed border-gray-600 px-2 py-2 text-center text-xs text-gray-500 transition-colors hover:border-gray-500"
            >
              Drop CSV exports here
            </div>
            {csvFiles.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {csvFiles.map((f) => (
                  <CsvChip
                    key={f.name}
                    name={f.name}
                    onRemove={() => removeCsvFile(f.name)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Middle column: Connection lines */}
        <div className="flex w-2/12 flex-col border-r border-gray-700/50">
          <div className="flex items-center justify-center border-b border-gray-700/50 px-1 py-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              Mappings
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto px-1 py-1">
            {tableMappings.length === 0 && (
              <p className="py-4 text-center text-xs text-gray-600">
                No mappings
              </p>
            )}
            {tableMappings.map((m) => {
              const isSelected = m.id === selectedMappingId;
              return (
                <button
                  key={m.id}
                  onClick={() => handleCardClick(m.id)}
                  className={`mb-1 flex w-full flex-col items-center rounded px-1 py-1.5 text-center transition-colors ${
                    isSelected
                      ? "border border-blue-500 bg-gray-800"
                      : "border border-transparent hover:bg-gray-800/60"
                  }`}
                >
                  <span className="truncate text-[10px] font-mono text-gray-400">
                    {m.accessTable}
                  </span>
                  <span className={`text-sm ${statusLineColors[m.status]}`}>
                    &darr;
                  </span>
                  <span className="truncate text-[10px] font-mono text-gray-400">
                    {m.zohoForm}
                  </span>
                  <span
                    className={`mt-0.5 inline-block h-1.5 w-1.5 rounded-full ${statusColors[m.status]}`}
                    title={m.status}
                  />
                </button>
              );
            })}
          </div>
        </div>

        {/* Right column: Zoho Creator Forms */}
        <div className="flex w-5/12 flex-col">
          <div className="flex items-center border-b border-gray-700/50 px-3 py-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              Zoho Creator Forms
            </h3>
            <CountBadge count={zohoForms.length} />
          </div>

          <div className="flex-1 overflow-y-auto px-2 py-1">
            {zohoForms.length === 0 && (
              <p className="px-2 py-4 text-center text-sm text-gray-500">
                No forms loaded
              </p>
            )}
            {zohoForms.map((form) => {
              const mapping = mappingByZoho.get(form.name);
              const isSelected = mapping?.id === selectedMappingId;
              return (
                <button
                  key={form.name}
                  onClick={() => handleCardClick(mapping?.id)}
                  className={`mb-1 flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm transition-colors ${
                    isSelected
                      ? "border border-blue-500 bg-gray-800"
                      : "border border-transparent hover:bg-gray-800/60"
                  } ${mapping ? "cursor-pointer" : "cursor-default"}`}
                >
                  <StatusDot mapped={!!mapping} />
                  <span className="flex-1 truncate text-gray-200">
                    {form.displayName}
                  </span>
                  <CountBadge count={form.fields.length} label="fields" />
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
