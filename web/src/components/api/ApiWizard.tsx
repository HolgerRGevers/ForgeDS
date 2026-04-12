import { useCallback, useState } from "react";
import { useApiStore } from "../../stores/apiStore";
import type {
  ApiParameter,
  ContentType,
  HttpMethod,
  WizardStep,
} from "../../types/api";

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const STEPS: { key: WizardStep; label: string }[] = [
  { key: "basic", label: "Basic Details" },
  { key: "request", label: "Request" },
  { key: "response", label: "Response" },
  { key: "actions", label: "Actions" },
  { key: "summary", label: "Summary" },
];

const STEP_INDEX: Record<WizardStep, number> = {
  basic: 0,
  request: 1,
  response: 2,
  actions: 3,
  summary: 4,
};

const HTTP_METHODS: HttpMethod[] = ["GET", "POST", "PUT", "DELETE"];

const USER_SCOPE_OPTIONS = [
  { value: "admin_only", label: "Admin only" },
  { value: "selective_users", label: "Selective users" },
  { value: "all_users", label: "All users" },
  { value: "portal_users", label: "Portal users" },
] as const;

const CONTENT_TYPES: ContentType[] = [
  "application/json",
  "multipart/form-data",
];

const PARAM_TYPES = ["text", "number", "date", "boolean"] as const;

/* ------------------------------------------------------------------ */
/*  Step indicator                                                     */
/* ------------------------------------------------------------------ */

function StepIndicator({
  current,
  onJump,
}: {
  current: WizardStep;
  onJump: (step: WizardStep) => void;
}) {
  const currentIdx = STEP_INDEX[current];

  return (
    <nav className="flex items-center justify-between border-b border-gray-700 px-6 py-3">
      {STEPS.map((s, i) => {
        const isCompleted = i < currentIdx;
        const isCurrent = i === currentIdx;
        const clickable = isCompleted || isCurrent;

        return (
          <button
            key={s.key}
            type="button"
            disabled={!clickable}
            onClick={() => clickable && onJump(s.key)}
            className={`flex items-center gap-2 text-sm font-medium transition-colors ${
              isCurrent
                ? "text-blue-400"
                : isCompleted
                  ? "text-green-400 hover:text-green-300"
                  : "cursor-default text-gray-500"
            }`}
          >
            {/* Circle / checkmark */}
            <span
              className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                isCompleted
                  ? "bg-green-600 text-white"
                  : isCurrent
                    ? "bg-blue-600 text-white"
                    : "bg-gray-700 text-gray-400"
              }`}
            >
              {isCompleted ? "\u2713" : i + 1}
            </span>
            <span className="hidden sm:inline">{s.label}</span>

            {/* Connector line (not after last) */}
            {i < STEPS.length - 1 && (
              <span
                className={`ml-2 hidden h-0.5 w-8 sm:block ${
                  i < currentIdx ? "bg-green-600" : "bg-gray-700"
                }`}
              />
            )}
          </button>
        );
      })}
    </nav>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 1 - Basic Details                                             */
/* ------------------------------------------------------------------ */

function StepBasic() {
  const draft = useApiStore((s) => s.draftApi)!;
  const updateDraft = useApiStore((s) => s.updateDraft);

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-white">Basic Details</h2>

      {/* Name */}
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-300">
          Name <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          value={draft.name}
          onChange={(e) => updateDraft({ name: e.target.value })}
          placeholder="e.g. Get Pending Claims"
          className="w-full rounded border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
        />
      </div>

      {/* Link Name (read-only) */}
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-300">
          Link Name
        </label>
        <input
          type="text"
          value={draft.linkName}
          readOnly
          className="w-full rounded border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-400"
        />
        {draft.linkName && (
          <p className="mt-1 text-xs text-gray-500">
            URL: /api/v2/&#123;owner&#125;/&#123;app&#125;/{draft.linkName}
          </p>
        )}
      </div>

      {/* Description */}
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-300">
          Description
        </label>
        <textarea
          value={draft.description}
          onChange={(e) => updateDraft({ description: e.target.value })}
          rows={3}
          placeholder="Optional description of what this API does"
          className="w-full rounded border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
        />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 2 - Request                                                   */
/* ------------------------------------------------------------------ */

function StepRequest() {
  const draft = useApiStore((s) => s.draftApi)!;
  const updateDraft = useApiStore((s) => s.updateDraft);
  const addParameter = useApiStore((s) => s.addParameter);
  const removeParameter = useApiStore((s) => s.removeParameter);
  const updateParameter = useApiStore((s) => s.updateParameter);

  const showContentType = draft.method === "POST" || draft.method === "PUT";

  const handleAddParam = () => {
    addParameter({
      id: Date.now().toString(36),
      key: "",
      type: "text",
      required: false,
      description: "",
    });
  };

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-white">Request</h2>

      {/* Method */}
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-300">
          Method
        </label>
        <select
          value={draft.method}
          onChange={(e) =>
            updateDraft({ method: e.target.value as HttpMethod })
          }
          className="rounded border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
        >
          {HTTP_METHODS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>

      {/* Authentication */}
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-300">
          Authentication
        </label>
        <div className="flex gap-4">
          {(["oauth2", "public_key"] as const).map((mode) => (
            <label key={mode} className="flex items-center gap-2 text-sm text-gray-300">
              <input
                type="radio"
                name="auth"
                checked={draft.auth === mode}
                onChange={() => updateDraft({ auth: mode })}
                className="accent-blue-500"
              />
              {mode === "oauth2" ? "OAuth2" : "Public Key"}
            </label>
          ))}
        </div>
      </div>

      {/* Content Type (POST/PUT only) */}
      {showContentType && (
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-300">
            Content Type
          </label>
          <select
            value={draft.contentType ?? "application/json"}
            onChange={(e) =>
              updateDraft({ contentType: e.target.value as ContentType })
            }
            className="rounded border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
          >
            {CONTENT_TYPES.map((ct) => (
              <option key={ct} value={ct}>
                {ct}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* User Scope */}
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-300">
          User Scope
        </label>
        <select
          value={draft.userScope}
          onChange={(e) =>
            updateDraft({
              userScope: e.target.value as (typeof USER_SCOPE_OPTIONS)[number]["value"],
            })
          }
          className="rounded border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
        >
          {USER_SCOPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {/* Parameters */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <label className="text-sm font-medium text-gray-300">
            Parameters
          </label>
          <button
            type="button"
            onClick={handleAddParam}
            className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-500"
          >
            + Add Parameter
          </button>
        </div>

        {draft.parameters.length === 0 ? (
          <p className="text-xs text-gray-500 italic">
            No parameters defined yet.
          </p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-700 text-xs text-gray-400">
                <th className="pb-1 pr-2">Key</th>
                <th className="pb-1 pr-2">Type</th>
                <th className="pb-1 pr-2">Required</th>
                <th className="pb-1 pr-2">Description</th>
                <th className="pb-1 w-8" />
              </tr>
            </thead>
            <tbody>
              {draft.parameters.map((p) => (
                <tr key={p.id} className="border-b border-gray-800">
                  <td className="py-1 pr-2">
                    <input
                      type="text"
                      value={p.key}
                      onChange={(e) =>
                        updateParameter(p.id, { key: e.target.value })
                      }
                      placeholder="param_name"
                      className="w-full rounded border border-gray-600 bg-gray-800 px-2 py-1 text-xs text-gray-100 focus:border-blue-500 focus:outline-none"
                    />
                  </td>
                  <td className="py-1 pr-2">
                    <select
                      value={p.type}
                      onChange={(e) =>
                        updateParameter(p.id, {
                          type: e.target.value as ApiParameter["type"],
                        })
                      }
                      className="rounded border border-gray-600 bg-gray-800 px-2 py-1 text-xs text-gray-100 focus:border-blue-500 focus:outline-none"
                    >
                      {PARAM_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="py-1 pr-2 text-center">
                    <input
                      type="checkbox"
                      checked={p.required}
                      onChange={(e) =>
                        updateParameter(p.id, { required: e.target.checked })
                      }
                      className="accent-blue-500"
                    />
                  </td>
                  <td className="py-1 pr-2">
                    <input
                      type="text"
                      value={p.description}
                      onChange={(e) =>
                        updateParameter(p.id, { description: e.target.value })
                      }
                      placeholder="description"
                      className="w-full rounded border border-gray-600 bg-gray-800 px-2 py-1 text-xs text-gray-100 focus:border-blue-500 focus:outline-none"
                    />
                  </td>
                  <td className="py-1">
                    <button
                      type="button"
                      onClick={() => removeParameter(p.id)}
                      className="text-red-400 hover:text-red-300"
                      title="Remove parameter"
                    >
                      &times;
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 3 - Response                                                  */
/* ------------------------------------------------------------------ */

function StepResponse() {
  const draft = useApiStore((s) => s.draftApi)!;
  const updateDraft = useApiStore((s) => s.updateDraft);
  const addStatusCode = useApiStore((s) => s.addStatusCode);
  const removeStatusCode = useApiStore((s) => s.removeStatusCode);

  const [newStatus, setNewStatus] = useState(200);
  const [newResponse, setNewResponse] = useState(0);

  const handleAddStatusCode = () => {
    addStatusCode({ statusCode: newStatus, responseCode: newResponse });
    setNewStatus(200);
    setNewResponse(0);
  };

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-white">Response</h2>

      {/* Response Type toggle */}
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-300">
          Response Type
        </label>
        <div className="flex gap-4">
          {(["standard", "custom"] as const).map((rt) => (
            <label key={rt} className="flex items-center gap-2 text-sm text-gray-300">
              <input
                type="radio"
                name="responseType"
                checked={draft.responseType === rt}
                onChange={() => updateDraft({ responseType: rt })}
                className="accent-blue-500"
              />
              {rt.charAt(0).toUpperCase() + rt.slice(1)}
            </label>
          ))}
        </div>
      </div>

      {draft.responseType === "standard" ? (
        <div className="rounded border border-gray-700 bg-gray-800/50 p-4 text-sm text-gray-400">
          Will return status codes currently followed by Creator's REST APIs.
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-gray-400">
            Define custom status code mappings. The API will return custom
            response codes instead of Creator defaults.
          </p>

          {/* Existing mappings */}
          {draft.statusCodes.length > 0 && (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-700 text-xs text-gray-400">
                  <th className="pb-1 pr-2">Status Code</th>
                  <th className="pb-1 pr-2">Response Code</th>
                  <th className="pb-1 w-8" />
                </tr>
              </thead>
              <tbody>
                {draft.statusCodes.map((sc) => (
                  <tr key={sc.statusCode} className="border-b border-gray-800">
                    <td className="py-1 pr-2 text-gray-200">{sc.statusCode}</td>
                    <td className="py-1 pr-2 text-gray-200">
                      {sc.responseCode}
                    </td>
                    <td className="py-1">
                      <button
                        type="button"
                        onClick={() => removeStatusCode(sc.statusCode)}
                        className="text-red-400 hover:text-red-300"
                        title="Remove"
                      >
                        &times;
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* Add status code */}
          <div className="flex items-end gap-2">
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Status Code
              </label>
              <input
                type="number"
                value={newStatus}
                onChange={(e) => setNewStatus(Number(e.target.value))}
                className="w-24 rounded border border-gray-600 bg-gray-800 px-2 py-1 text-xs text-gray-100 focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Response Code
              </label>
              <input
                type="number"
                value={newResponse}
                onChange={(e) => setNewResponse(Number(e.target.value))}
                className="w-24 rounded border border-gray-600 bg-gray-800 px-2 py-1 text-xs text-gray-100 focus:border-blue-500 focus:outline-none"
              />
            </div>
            <button
              type="button"
              onClick={handleAddStatusCode}
              className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-500"
            >
              + Add Status Code
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 4 - Actions                                                   */
/* ------------------------------------------------------------------ */

function StepActions() {
  const draft = useApiStore((s) => s.draftApi)!;
  const updateDraft = useApiStore((s) => s.updateDraft);

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-white">Actions</h2>

      {/* Application */}
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-300">
          Application
        </label>
        <select
          value={draft.application || "Expense Reimbursement Management"}
          onChange={(e) => updateDraft({ application: e.target.value })}
          className="w-full rounded border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
        >
          <option value="Expense Reimbursement Management">
            Expense Reimbursement Management
          </option>
        </select>
      </div>

      {/* Namespace */}
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-300">
          Namespace
        </label>
        <select
          value={draft.namespace || "Default"}
          onChange={(e) => updateDraft({ namespace: e.target.value })}
          className="w-full rounded border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
        >
          <option value="Default">Default</option>
        </select>
      </div>

      {/* Function name */}
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-300">
          Function
        </label>
        <input
          type="text"
          value={draft.functionName}
          onChange={(e) => updateDraft({ functionName: e.target.value })}
          placeholder="e.g. get_pending_claims"
          className="w-full rounded border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
        />
        <p className="mt-1 text-xs text-gray-500">
          Custom API supports only Deluge functions.
        </p>
      </div>

      {/* Warning when no function name */}
      {!draft.functionName && (
        <div className="rounded border border-yellow-700 bg-yellow-900/20 px-4 py-2 text-sm text-yellow-400">
          No functions to list. Please create a function to associate here.
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 5 - Summary                                                   */
/* ------------------------------------------------------------------ */

function SummarySection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded border border-gray-700 bg-gray-800/50 p-4">
      <h3 className="mb-2 text-sm font-semibold text-gray-300">{title}</h3>
      {children}
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-0.5 text-sm">
      <span className="text-gray-400">{label}</span>
      <span className="text-gray-200">{value || "-"}</span>
    </div>
  );
}

function StepSummary({ onBackToEdit }: { onBackToEdit: () => void }) {
  const draft = useApiStore((s) => s.draftApi)!;

  const scopeLabel =
    USER_SCOPE_OPTIONS.find((o) => o.value === draft.userScope)?.label ??
    draft.userScope;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Summary</h2>
        <button
          type="button"
          onClick={onBackToEdit}
          className="text-sm text-blue-400 hover:text-blue-300"
        >
          Back to Edit
        </button>
      </div>

      <SummarySection title="Basic Details">
        <SummaryRow label="Name" value={draft.name} />
        <SummaryRow label="Link Name" value={draft.linkName} />
        <SummaryRow label="Description" value={draft.description} />
      </SummarySection>

      <SummarySection title="Request">
        <SummaryRow label="Method" value={draft.method} />
        <SummaryRow
          label="Authentication"
          value={draft.auth === "oauth2" ? "OAuth2" : "Public Key"}
        />
        <SummaryRow label="User Scope" value={scopeLabel} />
        {(draft.method === "POST" || draft.method === "PUT") && (
          <SummaryRow
            label="Content Type"
            value={draft.contentType ?? "application/json"}
          />
        )}
        <SummaryRow
          label="Parameters"
          value={`${draft.parameters.length} defined`}
        />
        {draft.parameters.length > 0 && (
          <div className="mt-1 space-y-0.5 pl-2">
            {draft.parameters.map((p) => (
              <div key={p.id} className="text-xs text-gray-400">
                <span className="font-mono text-gray-300">{p.key || "(unnamed)"}</span>
                {" "}
                ({p.type}){p.required ? " *required" : ""}
              </div>
            ))}
          </div>
        )}
      </SummarySection>

      <SummarySection title="Response">
        <SummaryRow
          label="Response Type"
          value={
            draft.responseType === "standard" ? "Standard" : "Custom"
          }
        />
        {draft.responseType === "custom" && draft.statusCodes.length > 0 && (
          <div className="mt-1 space-y-0.5 pl-2">
            {draft.statusCodes.map((sc) => (
              <div
                key={sc.statusCode}
                className="text-xs text-gray-400"
              >
                {sc.statusCode} &rarr; {sc.responseCode}
              </div>
            ))}
          </div>
        )}
      </SummarySection>

      <SummarySection title="Actions">
        <SummaryRow
          label="Application"
          value={draft.application || "Expense Reimbursement Management"}
        />
        <SummaryRow label="Namespace" value={draft.namespace || "Default"} />
        <SummaryRow label="Function" value={draft.functionName} />
      </SummarySection>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main wizard component                                              */
/* ------------------------------------------------------------------ */

export function ApiWizard() {
  const draftApi = useApiStore((s) => s.draftApi);
  const wizardStep = useApiStore((s) => s.wizardStep);
  const setWizardStep = useApiStore((s) => s.setWizardStep);
  const saveDraft = useApiStore((s) => s.saveDraft);
  const updateDraft = useApiStore((s) => s.updateDraft);

  const [validationError, setValidationError] = useState<string | null>(null);

  const currentIdx = STEP_INDEX[wizardStep];
  const isFirst = currentIdx === 0;
  const isLast = currentIdx === STEPS.length - 1;

  /** Validate the current step before advancing */
  const validate = useCallback((): boolean => {
    if (!draftApi) return false;

    switch (wizardStep) {
      case "basic":
        if (!draftApi.name.trim()) {
          setValidationError("Name is required.");
          return false;
        }
        break;
      // Other steps have no hard requirements
    }
    setValidationError(null);
    return true;
  }, [draftApi, wizardStep]);

  const handleNext = useCallback(() => {
    if (!validate()) return;
    const next = STEPS[currentIdx + 1];
    if (next) setWizardStep(next.key);
  }, [validate, currentIdx, setWizardStep]);

  const handleBack = useCallback(() => {
    const prev = STEPS[currentIdx - 1];
    if (prev) {
      setValidationError(null);
      setWizardStep(prev.key);
    }
  }, [currentIdx, setWizardStep]);

  const handleJump = useCallback(
    (step: WizardStep) => {
      // Allow jumping to any completed or current step
      const targetIdx = STEP_INDEX[step];
      if (targetIdx <= currentIdx) {
        setValidationError(null);
        setWizardStep(step);
      }
    },
    [currentIdx, setWizardStep],
  );

  const handleSave = useCallback(() => {
    if (!draftApi) return;
    // Set defaults for application/namespace if empty
    if (!draftApi.application) {
      updateDraft({ application: "Expense Reimbursement Management" });
    }
    if (!draftApi.namespace) {
      updateDraft({ namespace: "Default" });
    }
    saveDraft();
  }, [draftApi, updateDraft, saveDraft]);

  if (!draftApi) {
    return (
      <div className="flex h-full items-center justify-center text-gray-500">
        No API draft in progress.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border border-gray-700 bg-gray-900">
      {/* Step indicator */}
      <StepIndicator current={wizardStep} onJump={handleJump} />

      {/* Step content */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {wizardStep === "basic" && <StepBasic />}
        {wizardStep === "request" && <StepRequest />}
        {wizardStep === "response" && <StepResponse />}
        {wizardStep === "actions" && <StepActions />}
        {wizardStep === "summary" && (
          <StepSummary onBackToEdit={() => setWizardStep("basic")} />
        )}

        {/* Validation error */}
        {validationError && (
          <p className="mt-3 text-sm text-red-400">{validationError}</p>
        )}
      </div>

      {/* Navigation buttons */}
      <div className="flex items-center justify-between border-t border-gray-700 px-6 py-3">
        <button
          type="button"
          disabled={isFirst}
          onClick={handleBack}
          className={`rounded px-4 py-2 text-sm font-medium transition-colors ${
            isFirst
              ? "cursor-not-allowed text-gray-600"
              : "text-gray-300 hover:bg-gray-800 hover:text-white"
          }`}
        >
          Back
        </button>

        {isLast ? (
          <button
            type="button"
            onClick={handleSave}
            className="rounded bg-green-600 px-5 py-2 text-sm font-medium text-white hover:bg-green-500"
          >
            {draftApi.createdAt === draftApi.updatedAt
              ? "Create API"
              : "Save Changes"}
          </button>
        ) : (
          <button
            type="button"
            onClick={handleNext}
            className="rounded bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-500"
          >
            Next
          </button>
        )}
      </div>
    </div>
  );
}
