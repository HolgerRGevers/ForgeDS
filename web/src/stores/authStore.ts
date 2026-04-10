import { create } from "zustand";
import {
  requestDeviceCode,
  pollForAccessToken,
  fetchCurrentUser,
} from "../services/github-auth";
import type { AuthStatus, GitHubUser, DeviceCodeResponse } from "../types/github";

const TOKEN_KEY = "forgeds-github-token";
const USER_KEY = "forgeds-github-user";

interface AuthState {
  status: AuthStatus;
  user: GitHubUser | null;
  token: string | null;
  error: string | null;
  deviceCode: DeviceCodeResponse | null;

  startLogin: () => Promise<void>;
  cancelLogin: () => void;
  logout: () => void;
  restoreSession: () => Promise<void>;
  handleTokenExpired: () => void;
}

let abortController: AbortController | null = null;

export const useAuthStore = create<AuthState>((set) => ({
  status: "unauthenticated",
  user: null,
  token: null,
  error: null,
  deviceCode: null,

  startLogin: async () => {
    try {
      set({ status: "awaiting_code", error: null });

      const dc = await requestDeviceCode();
      set({ deviceCode: dc, status: "polling" });

      // Start polling in background
      abortController = new AbortController();
      const result = await pollForAccessToken(
        dc.device_code,
        dc.interval,
        dc.expires_in,
        abortController.signal,
      );

      // Got token — fetch user profile
      const user = await fetchCurrentUser(result.access_token);

      localStorage.setItem(TOKEN_KEY, result.access_token);
      localStorage.setItem(USER_KEY, JSON.stringify(user));

      set({
        status: "authenticated",
        token: result.access_token,
        user: user as GitHubUser,
        deviceCode: null,
        error: null,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed";
      if (message !== "Login cancelled") {
        set({ status: "error", error: message, deviceCode: null });
      }
    } finally {
      abortController = null;
    }
  },

  cancelLogin: () => {
    abortController?.abort();
    abortController = null;
    set({ status: "unauthenticated", deviceCode: null, error: null });
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    set({
      status: "unauthenticated",
      user: null,
      token: null,
      error: null,
      deviceCode: null,
    });
  },

  handleTokenExpired: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    set({
      status: "unauthenticated",
      user: null,
      token: null,
      error: "Your session has expired. Please sign in again.",
      deviceCode: null,
    });
  },

  restoreSession: async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    const rawUser = localStorage.getItem(USER_KEY);
    if (!token || !rawUser) return;

    try {
      const cachedUser = JSON.parse(rawUser) as GitHubUser;
      // Immediately set cached data so the UI is responsive
      set({ status: "authenticated", token, user: cachedUser });

      // Validate token is still good by fetching fresh profile
      const freshUser = await fetchCurrentUser(token);
      localStorage.setItem(USER_KEY, JSON.stringify(freshUser));
      set({ user: freshUser as GitHubUser });
    } catch {
      // Token expired or revoked
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      set({ status: "unauthenticated", token: null, user: null });
    }
  },
}));
