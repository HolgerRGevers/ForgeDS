import { useCallback, useState } from "react";
import { useApiStore } from "../../stores/apiStore";
import { useBridgeStore } from "../../stores/bridgeStore";

/* ------------------------------------------------------------------ */
/*  Suggestion chips                                                   */
/* ------------------------------------------------------------------ */

const SUGGESTIONS = [
  "Return all pending claims with total amount",
  "Fetch claim status by ID",
  "Get ESG summary grouped by department",
  "Create a journal entry from approved claim",
] as const;

/* ------------------------------------------------------------------ */
/*  Spinner                                                            */
/* ------------------------------------------------------------------ */

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function ApiAiPrompt() {
  const draftApi = useApiStore((s) => s.draftApi);
  const updateDraft = useApiStore((s) => s.updateDraft);

  const bridgeStatus = useBridgeStore((s) => s.status);
  const send = useBridgeStore((s) => s.send);

  const [prompt, setPrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDisconnected = bridgeStatus !== "connected";

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!prompt.trim() || !draftApi || isDisconnected) return;

      setIsGenerating(true);
      setError(null);

      try {
        const apiConfig = {
          method: draftApi.method,
          parameters: draftApi.parameters,
          responseType: draftApi.responseType,
          name: draftApi.name,
          functionName: draftApi.functionName,
        };

        const response = await send("generate_api_code", {
          prompt: prompt.trim(),
          apiConfig,
        });

        if (response.code && typeof response.code === "string") {
          updateDraft({ generatedCode: response.code });
        } else {
          setError("No code was returned from the AI.");
        }
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Code generation failed";
        setError(message);
      } finally {
        setIsGenerating(false);
      }
    },
    [prompt, draftApi, isDisconnected, send, updateDraft],
  );

  const handleSuggestionClick = useCallback((suggestion: string) => {
    setPrompt(suggestion);
    setError(null);
  }, []);

  if (!draftApi) return null;

  return (
    <div className="space-y-2">
      {/* Suggestion chips */}
      <div className="flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => handleSuggestionClick(suggestion)}
            disabled={isGenerating}
            className="rounded-full border border-gray-600 bg-gray-800 px-2.5 py-0.5 text-xs text-gray-400 transition-colors hover:border-blue-500 hover:text-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {suggestion}
          </button>
        ))}
      </div>

      {/* Prompt bar */}
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <input
          type="text"
          value={prompt}
          onChange={(e) => {
            setPrompt(e.target.value);
            setError(null);
          }}
          placeholder={
            isDisconnected
              ? "Connect bridge to use AI generation"
              : "Describe what this API should do..."
          }
          disabled={isGenerating || isDisconnected}
          className="flex-1 rounded-md border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 transition-colors focus:border-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isGenerating || isDisconnected || !prompt.trim()}
          className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isGenerating ? (
            <>
              <Spinner />
              Generating...
            </>
          ) : (
            "Generate"
          )}
        </button>
      </form>

      {/* Error message */}
      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}
    </div>
  );
}
