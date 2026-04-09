import { useCallback, useState } from "react";
import { useDatabaseStore } from "../../stores/databaseStore";
import { useBridgeStore } from "../../stores/bridgeStore";
import type { ValidationResult, ValidationDetail } from "../../types/database";

// --- Step indicator ---

function StepIndicator({ current }: { current: 1 | 2 | 3 }) {
  const steps = [
    { num: 1, label: "Preview" },
    { num: 2, label: "Mock Upload" },
    { num: 3, label: "Complete" },
  ] as const;

  return (
    <div className="flex items-center gap-1">
      {steps.map((step, idx) => (
        <div key={step.num} className="flex items-center">
          <div
            className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
              step.num === current
                ? "bg-blue-600 text-white"
                : step.num < current
                  ? "bg-green-900/50 text-green-400"
                  : "bg-gray-700 text-gray-500"
            }`}
          >
            {step.num < current ? "\u2713" : step.num}
          </div>
          <span
            className={`ml-1 text-xs ${
              step.num === current ? "text-gray-200" : "text-gray-500"
            }`}
          >
            {step.label}
          </span>
          {idx < steps.length - 1 && (
            <div
              className={`mx-2 h-px w-6 ${
                step.num < current ? "bg-green-600" : "bg-gray-700"
              }`}
            />
          )}
        </div>
      ))}
    </div>
  );
}

// --- Progress bar ---

function ProgressBar({
  progress,
  label,
}: {
  progress: number;
  label?: string;
}) {
  return (
    <div className="space-y-1">
      {label && <p className="text-xs text-gray-400">{label}</p>}
      <div className="h-2 overflow-hidden rounded-full bg-gray-700">
        <div
          className="h-full rounded-full bg-blue-500 transition-all duration-300"
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>
      <p className="text-right text-[10px] text-gray-500">{progress}%</p>
    </div>
  );
}

// --- Step 1: Preview ---

function StepPreview({
  onValidate,
  onNext,
  validating,
}: {
  onValidate: () => void;
  onNext: () => void;
  validating: boolean;
}) {
  const tableMappings = useDatabaseStore((s) => s.tableMappings);
  const csvFiles = useDatabaseStore((s) => s.csvFiles);

  const unmappedFields = tableMappings.reduce((count, tm) => {
    return (
      count + tm.fieldMappings.filter((fm) => fm.status === "unmapped").length
    );
  }, 0);

  const warningFields = tableMappings.reduce((count, tm) => {
    return (
      count + tm.fieldMappings.filter((fm) => fm.status === "warning").length
    );
  }, 0);

  return (
    <div className="space-y-4">
      <h4 className="text-sm font-semibold text-gray-200">Upload Preview</h4>

      {/* Table summaries */}
      {tableMappings.length === 0 ? (
        <p className="text-xs text-gray-500">No table mappings configured</p>
      ) : (
        <div className="space-y-2">
          {tableMappings.map((tm) => {
            const mappedCount = tm.fieldMappings.filter(
              (fm) => fm.status !== "unmapped",
            ).length;
            const csv = csvFiles.find(
              (f) =>
                f.name.toLowerCase().replace(".csv", "") ===
                tm.accessTable.toLowerCase(),
            );
            return (
              <div
                key={tm.id}
                className="rounded border border-gray-700 bg-gray-800/50 px-3 py-2"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-gray-200">
                    {tm.accessTable}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                      tm.status === "complete"
                        ? "bg-green-900/50 text-green-400"
                        : tm.status === "partial"
                          ? "bg-yellow-900/50 text-yellow-400"
                          : "bg-gray-700 text-gray-500"
                    }`}
                  >
                    {tm.status}
                  </span>
                </div>
                <div className="mt-1 flex gap-4 text-[10px] text-gray-500">
                  <span>
                    {mappedCount}/{tm.fieldMappings.length} fields mapped
                  </span>
                  <span>
                    Records: {csv ? csv.rowCount || "loaded" : "no CSV"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Warnings */}
      {(unmappedFields > 0 || warningFields > 0) && (
        <div className="space-y-1 rounded border border-yellow-900/50 bg-yellow-900/10 px-3 py-2">
          {unmappedFields > 0 && (
            <p className="text-xs text-yellow-400">
              {unmappedFields} unmapped field
              {unmappedFields !== 1 ? "s" : ""} will be skipped
            </p>
          )}
          {warningFields > 0 && (
            <p className="text-xs text-yellow-400">
              {warningFields} field{warningFields !== 1 ? "s" : ""} with type
              warnings
            </p>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={onValidate}
          disabled={validating}
          className="rounded border border-gray-600 bg-gray-800 px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:border-gray-500 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {validating ? "Validating..." : "Validate First"}
        </button>
        <button
          onClick={onNext}
          disabled={tableMappings.length === 0}
          className="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Next: Mock Upload
        </button>
      </div>
    </div>
  );
}

// --- Step 2: Mock Upload ---

function StepMockUpload({ onBack, onNext }: { onBack: () => void; onNext: () => void }) {
  const uploadState = useDatabaseStore((s) => s.uploadState);
  const setUploadState = useDatabaseStore((s) => s.setUploadState);
  const tableMappings = useDatabaseStore((s) => s.tableMappings);
  const sendStream = useBridgeStore((s) => s.sendStream);

  const [mockRunning, setMockRunning] = useState(false);
  const [mockComplete, setMockComplete] = useState(false);

  const runMockUpload = useCallback(async () => {
    setMockRunning(true);
    setMockComplete(false);
    setUploadState({
      status: "uploading",
      progress: 0,
      totalRecords: 0,
      uploadedRecords: 0,
      errors: [],
    });

    try {
      await sendStream(
        "mock_upload",
        { tables: tableMappings.map((tm) => tm.accessTable) },
        (chunk) => {
          if (chunk.currentTable) {
            setUploadState({
              currentTable: chunk.currentTable as string,
              progress: (chunk.progress as number) ?? uploadState.progress,
              totalRecords: (chunk.totalRecords as number) ?? uploadState.totalRecords,
              uploadedRecords:
                (chunk.uploadedRecords as number) ?? uploadState.uploadedRecords,
            });
          }
        },
      );
      setUploadState({ status: "complete", progress: 100 });
      setMockComplete(true);
    } catch {
      setUploadState({ status: "error", errors: ["Mock upload failed"] });
      setMockComplete(true);
    } finally {
      setMockRunning(false);
    }
  }, [sendStream, tableMappings, setUploadState, uploadState]);

  return (
    <div className="space-y-4">
      <h4 className="text-sm font-semibold text-gray-200">
        Mock Upload Preview
      </h4>
      <p className="text-xs text-gray-400">
        This simulates the upload process without writing to Zoho Creator.
      </p>

      {/* Progress */}
      {uploadState.status === "uploading" && (
        <div className="space-y-2">
          <ProgressBar
            progress={uploadState.progress}
            label={
              uploadState.currentTable
                ? `Uploading ${uploadState.currentTable}... ${uploadState.uploadedRecords}/${uploadState.totalRecords} records`
                : "Preparing..."
            }
          />
        </div>
      )}

      {uploadState.status === "complete" && mockComplete && (
        <div className="rounded border border-green-900/50 bg-green-900/10 px-3 py-2">
          <p className="text-xs text-green-400">
            Mock upload complete. {uploadState.uploadedRecords} records
            processed.
          </p>
        </div>
      )}

      {uploadState.status === "error" && (
        <div className="rounded border border-red-900/50 bg-red-900/10 px-3 py-2">
          <p className="text-xs text-red-400">Mock upload encountered errors</p>
          {uploadState.errors.map((err, i) => (
            <p key={i} className="mt-1 text-[10px] text-red-300">
              {err}
            </p>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={onBack}
          disabled={mockRunning}
          className="rounded border border-gray-600 bg-gray-800 px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:border-gray-500 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Back
        </button>
        {!mockComplete && (
          <button
            onClick={runMockUpload}
            disabled={mockRunning}
            className="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {mockRunning ? "Running..." : "Run Mock Upload"}
          </button>
        )}
        {mockComplete && (
          <button
            onClick={onNext}
            className="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-500"
          >
            Next: Review
          </button>
        )}
      </div>
    </div>
  );
}

// --- Step 3: Complete ---

function StepComplete({ onBack }: { onBack: () => void }) {
  const uploadState = useDatabaseStore((s) => s.uploadState);
  const [showConfirm, setShowConfirm] = useState(false);

  const hasErrors = uploadState.errors.length > 0;

  return (
    <div className="space-y-4">
      <h4 className="text-sm font-semibold text-gray-200">Upload Summary</h4>

      {/* Summary */}
      <div
        className={`rounded border px-3 py-2 ${
          hasErrors
            ? "border-red-900/50 bg-red-900/10"
            : "border-green-900/50 bg-green-900/10"
        }`}
      >
        <p
          className={`text-xs ${hasErrors ? "text-red-400" : "text-green-400"}`}
        >
          {hasErrors
            ? "Upload completed with errors"
            : "Mock upload completed successfully"}
        </p>
        <div className="mt-1 flex gap-4 text-[10px] text-gray-400">
          <span>Records: {uploadState.uploadedRecords}</span>
          <span>Errors: {uploadState.errors.length}</span>
        </div>
      </div>

      {/* Error list */}
      {hasErrors && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-gray-400">Errors:</p>
          {uploadState.errors.map((err, i) => (
            <div
              key={i}
              className="flex items-start gap-2 rounded bg-gray-800/50 px-2 py-1"
            >
              <span className="inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-red-900/50 text-[10px] text-red-400">
                &#10005;
              </span>
              <span className="text-xs text-gray-300">{err}</span>
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={onBack}
          className="rounded border border-gray-600 bg-gray-800 px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:border-gray-500 hover:bg-gray-700"
        >
          Back
        </button>

        {/* Upload Live with confirmation */}
        {!showConfirm ? (
          <button
            onClick={() => setShowConfirm(true)}
            className="rounded bg-orange-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-orange-500"
          >
            Upload Live
          </button>
        ) : (
          <div className="flex items-center gap-2 rounded border border-orange-600/50 bg-orange-900/10 px-3 py-1.5">
            <span className="text-xs text-orange-300">
              This will write to Zoho Creator. Proceed?
            </span>
            <button
              onClick={() => setShowConfirm(false)}
              className="rounded border border-gray-600 bg-gray-800 px-2 py-0.5 text-xs text-gray-300 hover:bg-gray-700"
            >
              Cancel
            </button>
            <button
              disabled
              className="rounded bg-orange-600 px-2 py-0.5 text-xs font-medium text-white opacity-50"
              title="Live upload not yet implemented"
            >
              Confirm
            </button>
          </div>
        )}

        <button
          disabled
          className="rounded border border-gray-600 bg-gray-800 px-3 py-1.5 text-xs font-medium text-gray-400 opacity-50"
          title="Report download not yet implemented"
        >
          Download Report
        </button>
      </div>
    </div>
  );
}

// --- Main component ---

export function UploadWizard() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const addValidationResult = useDatabaseStore((s) => s.addValidationResult);
  const send = useBridgeStore((s) => s.send);
  const [validating, setValidating] = useState(false);

  const handleValidate = useCallback(async () => {
    setValidating(true);
    try {
      const response = await send("run_validation", { tool: "validate" });
      const result: ValidationResult = {
        id: crypto.randomUUID(),
        timestamp: new Date().toLocaleTimeString(),
        tool: "validate",
        status: (response?.status as ValidationResult["status"]) ?? "pass",
        summary: (response?.summary as string) ?? "Pre-upload validation completed",
        details: (response?.details as ValidationDetail[]) ?? [],
      };
      addValidationResult(result);
    } catch {
      const result: ValidationResult = {
        id: crypto.randomUUID(),
        timestamp: new Date().toLocaleTimeString(),
        tool: "validate",
        status: "fail",
        summary: "Pre-upload validation failed",
        details: [
          {
            severity: "error",
            message: "Bridge connection error or tool unavailable",
          },
        ],
      };
      addValidationResult(result);
    } finally {
      setValidating(false);
    }
  }, [send, addValidationResult]);

  return (
    <div className="flex h-full flex-col bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700 px-4 py-2.5">
        <h3 className="text-sm font-semibold text-gray-200">Upload Wizard</h3>
        <StepIndicator current={step} />
      </div>

      {/* Step content */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {step === 1 && (
          <StepPreview
            onValidate={handleValidate}
            onNext={() => setStep(2)}
            validating={validating}
          />
        )}
        {step === 2 && (
          <StepMockUpload
            onBack={() => setStep(1)}
            onNext={() => setStep(3)}
          />
        )}
        {step === 3 && <StepComplete onBack={() => setStep(2)} />}
      </div>
    </div>
  );
}
