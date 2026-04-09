import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";

export default function LoginPage() {
  const navigate = useNavigate();
  const { status, error, deviceCode, startLogin, cancelLogin } =
    useAuthStore();

  // Redirect once authenticated
  useEffect(() => {
    if (status === "authenticated") {
      navigate("/", { replace: true });
    }
  }, [status, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-950">
      <div className="w-full max-w-md space-y-8 rounded-xl border border-gray-800 bg-gray-900 p-8">
        {/* Logo */}
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight text-white">
            ForgeDS<span className="text-blue-400">_IDE</span>
          </h1>
          <p className="mt-2 text-sm text-gray-400">
            Sign in with GitHub to start building Zoho Creator apps
          </p>
        </div>

        {/* Unauthenticated — show login button */}
        {status === "unauthenticated" && (
          <button
            type="button"
            onClick={startLogin}
            className="flex w-full items-center justify-center gap-3 rounded-lg bg-gray-800 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-gray-700"
          >
            <svg
              className="h-5 w-5"
              fill="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                clipRule="evenodd"
              />
            </svg>
            Sign in with GitHub
          </button>
        )}

        {/* Awaiting code — show spinner */}
        {status === "awaiting_code" && (
          <div className="flex items-center justify-center py-6">
            <svg
              className="h-6 w-6 animate-spin text-blue-400"
              viewBox="0 0 24 24"
              fill="none"
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
                d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
              />
            </svg>
            <span className="ml-3 text-sm text-gray-400">
              Requesting login code...
            </span>
          </div>
        )}

        {/* Polling — show the user code */}
        {status === "polling" && deviceCode && (
          <div className="space-y-6">
            <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6 text-center">
              <p className="text-xs font-medium uppercase tracking-wider text-gray-400">
                Enter this code at GitHub
              </p>
              <p className="mt-3 font-mono text-3xl font-bold tracking-widest text-white">
                {deviceCode.user_code}
              </p>
            </div>

            <a
              href={deviceCode.verification_uri}
              target="_blank"
              rel="noopener noreferrer"
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-500"
            >
              Open GitHub to verify
              <svg
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                />
              </svg>
            </a>

            <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
              <svg
                className="h-4 w-4 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
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
                  d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                />
              </svg>
              Waiting for authorization...
            </div>

            <button
              type="button"
              onClick={cancelLogin}
              className="w-full rounded border border-gray-700 px-3 py-2 text-xs text-gray-400 transition-colors hover:border-gray-500 hover:text-gray-300"
            >
              Cancel
            </button>
          </div>
        )}

        {/* Error */}
        {status === "error" && (
          <div className="space-y-4">
            <div className="rounded-lg border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-400">
              {error}
            </div>
            <button
              type="button"
              onClick={startLogin}
              className="w-full rounded-lg bg-gray-800 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-gray-700"
            >
              Try again
            </button>
          </div>
        )}

        {/* Footer */}
        <p className="text-center text-xs text-gray-600">
          Your GitHub account provides repo access for cloud storage and
          collaboration. No data is stored on our servers.
        </p>
      </div>
    </div>
  );
}
