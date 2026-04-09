import { useEffect, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";

interface AuthGuardProps {
  children: ReactNode;
}

/**
 * Wraps protected routes. Redirects to /login if the user is not
 * authenticated. Tries to restore a previous session on mount.
 */
export function AuthGuard({ children }: AuthGuardProps) {
  const navigate = useNavigate();
  const { status, restoreSession } = useAuthStore();

  // On mount, try to restore a saved session from localStorage
  useEffect(() => {
    if (status === "unauthenticated") {
      restoreSession();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // After restore attempt, redirect if still unauthenticated
  useEffect(() => {
    if (status === "unauthenticated") {
      // Small delay to let restoreSession() run first
      const id = setTimeout(() => {
        if (useAuthStore.getState().status === "unauthenticated") {
          navigate("/login", { replace: true });
        }
      }, 100);
      return () => clearTimeout(id);
    }
  }, [status, navigate]);

  if (status !== "authenticated") {
    // Show a minimal loading state while restoring session
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950">
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
      </div>
    );
  }

  return <>{children}</>;
}
