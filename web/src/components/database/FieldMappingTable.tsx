import { useCallback, useMemo, useState } from "react";
import { useDatabaseStore } from "../../stores/databaseStore";
import type { FieldMapping, ZohoField } from "../../types/database";

// --- Type compatibility warnings ---

const TYPE_WARNINGS: Record<string, Record<string, string>> = {
  CURRENCY: {
    Decimal:
      "CURRENCY has 4 decimal places, Decimal has 2 — potential precision loss",
    Number: "CURRENCY is fractional, Number is integer — data loss likely",
    Text: "CURRENCY to Text — numeric operations lost",
  },
  BOOLEAN: {
    Checkbox:
      "BOOLEAN uses -1/0, Zoho uses true/false — conversion needed",
    Text: "BOOLEAN to Text — semantic meaning lost",
    Number: "BOOLEAN (-1/0) to Number — values preserved but semantics differ",
  },
  DATETIME: {
    Date: "DATETIME includes time component — time data will be lost",
    Text: "DATETIME to Text — no date operations available",
  },
  MEMO: {
    Text: "MEMO can exceed 255 chars — Zoho Text fields may truncate",
    "Rich Text": "MEMO to Rich Text — formatting may differ",
  },
  LONG: {
    Decimal: "LONG (integer) to Decimal — works but unnecessary precision",
    Text: "LONG to Text — numeric operations lost",
  },
  TEXT: {
    Number: "TEXT to Number — non-numeric values will fail",
    Decimal: "TEXT to Decimal — non-numeric values will fail",
  },
};

function getTypeWarning(accessType: string, zohoType: string): string | null {
  return TYPE_WARNINGS[accessType]?.[zohoType] ?? null;
}

// --- Status icons ---

function StatusIcon({ status, message }: { status: FieldMapping["status"]; message?: string }) {
  switch (status) {
    case "mapped":
      return (
        <span
          className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-green-900/50 text-green-400"
          title={message ?? "Mapped — types compatible"}
        >
          &#10003;
        </span>
      );
    case "warning":
      return (
        <span
          className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-yellow-900/50 text-yellow-400"
          title={message ?? "Type mismatch warning"}
        >
          !
        </span>
      );
    case "error":
      return (
        <span
          className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-red-900/50 text-red-400"
          title={message ?? "Incompatible types or missing required field"}
        >
          &#10005;
        </span>
      );
    case "unmapped":
      return (
        <span
          className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-gray-700 text-gray-500"
          title="Unmapped"
        >
          &mdash;
        </span>
      );
  }
}

// --- Zoho Field Dropdown ---

function ZohoFieldDropdown({
  currentField,
  availableFields,
  onChange,
}: {
  currentField: string;
  availableFields: ZohoField[];
  onChange: (linkName: string, displayName: string, type: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);

  const handleSelect = useCallback(
    (field: ZohoField | null) => {
      if (field) {
        onChange(field.linkName, field.displayName, field.type);
      } else {
        onChange("", "", "");
      }
      setIsOpen(false);
    },
    [onChange],
  );

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex w-full items-center justify-between rounded border px-2 py-1 text-left text-xs transition-colors ${
          currentField
            ? "border-gray-600 bg-gray-800 text-gray-200 hover:border-gray-500"
            : "border-gray-700 bg-gray-800/50 text-gray-500 hover:border-gray-600"
        }`}
      >
        <span className="truncate font-mono">
          {currentField || "--unmapped--"}
        </span>
        <span className="ml-1 text-gray-500">&#9662;</span>
      </button>

      {isOpen && (
        <>
          {/* Backdrop to close dropdown */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute left-0 top-full z-20 mt-1 max-h-48 w-56 overflow-y-auto rounded border border-gray-600 bg-gray-800 shadow-lg">
            {/* Unmapped option */}
            <button
              onClick={() => handleSelect(null)}
              className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-xs text-gray-400 hover:bg-gray-700"
            >
              <span className="font-mono">--unmapped--</span>
            </button>
            <div className="border-t border-gray-700" />
            {availableFields.map((field) => (
              <button
                key={field.linkName}
                onClick={() => handleSelect(field)}
                className={`flex w-full items-center justify-between px-2 py-1.5 text-left text-xs hover:bg-gray-700 ${
                  field.linkName === currentField
                    ? "bg-gray-700/50 text-blue-400"
                    : "text-gray-200"
                }`}
              >
                <span className="truncate font-mono">{field.linkName}</span>
                <span className="ml-2 flex-shrink-0 text-gray-500">
                  {field.type}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// --- Auto-map logic ---

/** Normalise a name for fuzzy matching: lowercase, strip underscores/spaces/hyphens, strip brackets */
function normaliseName(name: string): string {
  return name
    .replace(/^\[|\]$/g, "") // strip Access bracket escaping
    .replace(/[_\-\s]/g, "")
    .toLowerCase();
}

function autoMapFields(
  columns: Array<{ name: string; type: string }>,
  fields: ZohoField[],
): Array<{ accessColumn: string; zohoField: ZohoField | null }> {
  const unmatchedFields = new Set(fields.map((f) => f.linkName));
  const results: Array<{ accessColumn: string; zohoField: ZohoField | null }> = [];

  for (const col of columns) {
    const normCol = normaliseName(col.name);
    let bestMatch: ZohoField | null = null;

    for (const field of fields) {
      if (!unmatchedFields.has(field.linkName)) continue;
      const normField = normaliseName(field.linkName);
      const normDisplay = normaliseName(field.displayName);

      // Exact match on normalised name
      if (normCol === normField || normCol === normDisplay) {
        bestMatch = field;
        break;
      }
      // Contains match (one contains the other)
      if (
        normCol.includes(normField) ||
        normField.includes(normCol) ||
        normCol.includes(normDisplay) ||
        normDisplay.includes(normCol)
      ) {
        if (!bestMatch) bestMatch = field;
      }
    }

    if (bestMatch) {
      unmatchedFields.delete(bestMatch.linkName);
    }
    results.push({ accessColumn: col.name, zohoField: bestMatch });
  }

  return results;
}

// --- Main component ---

export function FieldMappingTable() {
  const tableMappings = useDatabaseStore((s) => s.tableMappings);
  const selectedMappingId = useDatabaseStore((s) => s.selectedMappingId);
  const zohoForms = useDatabaseStore((s) => s.zohoForms);
  const accessTables = useDatabaseStore((s) => s.accessTables);
  const updateFieldMapping = useDatabaseStore((s) => s.updateFieldMapping);
  const setTableMappings = useDatabaseStore((s) => s.setTableMappings);

  // Find selected mapping
  const selectedMapping = useMemo(
    () => tableMappings.find((m) => m.id === selectedMappingId) ?? null,
    [tableMappings, selectedMappingId],
  );

  // Get the Zoho form fields for the selected mapping
  const targetFields = useMemo(() => {
    if (!selectedMapping) return [];
    const form = zohoForms.find((f) => f.name === selectedMapping.zohoForm);
    return form?.fields ?? [];
  }, [selectedMapping, zohoForms]);

  // Get access table columns for auto-map
  const sourceColumns = useMemo(() => {
    if (!selectedMapping) return [];
    const table = accessTables.find(
      (t) => t.name === selectedMapping.accessTable,
    );
    return table?.columns ?? [];
  }, [selectedMapping, accessTables]);

  // Count mapped fields
  const mappedCount = useMemo(() => {
    if (!selectedMapping) return 0;
    return selectedMapping.fieldMappings.filter(
      (fm) => fm.status !== "unmapped",
    ).length;
  }, [selectedMapping]);

  // Handle field mapping change
  const handleFieldChange = useCallback(
    (fieldMappingId: string, linkName: string, _displayName: string, zohoType: string) => {
      if (!selectedMapping) return;

      const fm = selectedMapping.fieldMappings.find(
        (f) => f.id === fieldMappingId,
      );
      if (!fm) return;

      let status: FieldMapping["status"];
      let statusMessage: string | undefined;

      if (!linkName) {
        status = "unmapped";
        statusMessage = undefined;
      } else {
        const warning = getTypeWarning(fm.accessType, zohoType);
        if (warning) {
          status = "warning";
          statusMessage = warning;
        } else {
          status = "mapped";
          statusMessage = undefined;
        }
      }

      updateFieldMapping(selectedMapping.id, fieldMappingId, {
        zohoField: linkName,
        zohoType: zohoType,
        status,
        statusMessage,
        isAutoMapped: false,
      });
    },
    [selectedMapping, updateFieldMapping],
  );

  // Auto-map handler
  const handleAutoMap = useCallback(() => {
    if (!selectedMapping) return;

    const results = autoMapFields(sourceColumns, targetFields);
    const updatedFieldMappings = selectedMapping.fieldMappings.map((fm) => {
      const result = results.find((r) => r.accessColumn === fm.accessColumn);
      if (result?.zohoField) {
        const warning = getTypeWarning(fm.accessType, result.zohoField.type);
        return {
          ...fm,
          zohoField: result.zohoField.linkName,
          zohoType: result.zohoField.type,
          status: (warning ? "warning" : "mapped") as FieldMapping["status"],
          statusMessage: warning ?? undefined,
          isAutoMapped: true,
        };
      }
      return {
        ...fm,
        zohoField: "",
        zohoType: "",
        status: "unmapped" as const,
        statusMessage: undefined,
        isAutoMapped: false,
      };
    });

    // Determine overall table mapping status
    const mappedFields = updatedFieldMappings.filter(
      (f) => f.status !== "unmapped",
    );
    let overallStatus: "complete" | "partial" | "unmapped";
    if (mappedFields.length === 0) {
      overallStatus = "unmapped";
    } else if (mappedFields.length === updatedFieldMappings.length) {
      overallStatus = "complete";
    } else {
      overallStatus = "partial";
    }

    setTableMappings(
      tableMappings.map((tm) =>
        tm.id === selectedMapping.id
          ? { ...tm, fieldMappings: updatedFieldMappings, status: overallStatus }
          : tm,
      ),
    );
  }, [selectedMapping, sourceColumns, targetFields, tableMappings, setTableMappings]);

  // --- Empty state ---
  if (!selectedMapping) {
    return (
      <div className="flex h-full items-center justify-center bg-gray-900 p-8">
        <div className="text-center">
          <p className="text-sm text-gray-500">
            Select a table mapping above to view field mappings
          </p>
        </div>
      </div>
    );
  }

  const totalFields = selectedMapping.fieldMappings.length;

  return (
    <div className="flex h-full flex-col bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-gray-200">
            <span className="font-mono">{selectedMapping.accessTable}</span>
            <span className="mx-2 text-gray-500">&rarr;</span>
            <span className="font-mono">{selectedMapping.zohoForm}</span>
          </h3>
          <span className="rounded-full bg-gray-700 px-2 py-0.5 text-xs font-medium text-gray-300">
            {mappedCount} of {totalFields} fields mapped
          </span>
        </div>
        <button
          onClick={handleAutoMap}
          className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-blue-500"
        >
          Auto-map
        </button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 z-10 bg-gray-800">
            <tr className="border-b border-gray-700">
              <th className="px-4 py-2 font-semibold text-gray-400">
                Access Column
              </th>
              <th className="px-4 py-2 font-semibold text-gray-400">
                Access Type
              </th>
              <th className="min-w-[180px] px-4 py-2 font-semibold text-gray-400">
                Zoho Field
              </th>
              <th className="px-4 py-2 font-semibold text-gray-400">
                Zoho Type
              </th>
              <th className="px-4 py-2 text-center font-semibold text-gray-400">
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {selectedMapping.fieldMappings.map((fm) => (
              <tr
                key={fm.id}
                className="border-b border-gray-800 transition-colors hover:bg-gray-800/40"
              >
                {/* Access Column */}
                <td className="px-4 py-2">
                  <span className="font-mono text-gray-200">
                    {fm.accessColumn}
                  </span>
                  {fm.accessColumn.startsWith("[") && (
                    <span
                      className="ml-1 text-yellow-500"
                      title="Bracket-escaped SQL reserved word"
                    >
                      *
                    </span>
                  )}
                </td>

                {/* Access Type */}
                <td className="px-4 py-2">
                  <span className="rounded bg-gray-700 px-1.5 py-0.5 font-mono text-gray-300">
                    {fm.accessType}
                  </span>
                </td>

                {/* Zoho Field (editable dropdown) */}
                <td className="px-4 py-2">
                  <ZohoFieldDropdown
                    currentField={fm.zohoField}
                    availableFields={targetFields}
                    onChange={(linkName, displayName, type) =>
                      handleFieldChange(fm.id, linkName, displayName, type)
                    }
                  />
                </td>

                {/* Zoho Type */}
                <td className="px-4 py-2">
                  {fm.zohoType ? (
                    <span className="rounded bg-gray-700 px-1.5 py-0.5 font-mono text-gray-300">
                      {fm.zohoType}
                    </span>
                  ) : (
                    <span className="text-gray-600">&mdash;</span>
                  )}
                </td>

                {/* Status */}
                <td className="px-4 py-2 text-center">
                  <div className="flex flex-col items-center gap-0.5">
                    <StatusIcon
                      status={fm.status}
                      message={fm.statusMessage}
                    />
                    {fm.statusMessage && fm.status === "warning" && (
                      <span className="max-w-[200px] text-[10px] leading-tight text-yellow-500/80">
                        {fm.statusMessage}
                      </span>
                    )}
                    {fm.statusMessage && fm.status === "error" && (
                      <span className="max-w-[200px] text-[10px] leading-tight text-red-400/80">
                        {fm.statusMessage}
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {totalFields === 0 && (
          <div className="flex items-center justify-center py-8">
            <p className="text-sm text-gray-500">
              No field mappings defined for this table
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
