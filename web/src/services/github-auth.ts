/**
 * GitHub Device Flow authentication.
 *
 * Flow:
 * 1. POST /login/device/code  -> returns user_code + device_code
 * 2. User visits github.com/login/device and enters user_code
 * 3. App polls POST /login/oauth/access_token until authorized
 *
 * All requests go through a Cloudflare Worker proxy that:
 *  - Adds CORS headers (GitHub's endpoints have none)
 *  - Injects client_id and client_secret server-side (never exposed in JS)
 *
 * Set VITE_GITHUB_AUTH_PROXY to the Worker URL.
 */

const AUTH_PROXY = import.meta.env.VITE_GITHUB_AUTH_PROXY ?? "";

const SCOPES = "repo read:user";

export interface DeviceCodeResult {
  device_code: string;
  user_code: string;
  verification_uri: string;
  expires_in: number;
  interval: number;
}

export interface TokenResult {
  access_token: string;
  token_type: string;
  scope: string;
}

/** Step 1 — request a device + user code. */
export async function requestDeviceCode(): Promise<DeviceCodeResult> {
  if (!AUTH_PROXY) {
    throw new Error(
      "VITE_GITHUB_AUTH_PROXY is not configured. Set it to the Cloudflare Worker URL.",
    );
  }

  const res = await fetch(`${AUTH_PROXY}/login/device/code`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    // client_id is injected by the proxy — only send scope
    body: JSON.stringify({ scope: SCOPES }),
  });

  if (!res.ok) {
    throw new Error(`Device code request failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Step 3 — poll for access token.
 * Resolves when the user authorizes, rejects on expiry / denial.
 */
export async function pollForAccessToken(
  deviceCode: string,
  interval: number,
  expiresIn: number,
  signal?: AbortSignal,
): Promise<TokenResult> {
  const deadline = Date.now() + expiresIn * 1000;
  let wait = interval * 1000; // GitHub's minimum poll interval in ms

  while (Date.now() < deadline) {
    if (signal?.aborted) throw new Error("Login cancelled");

    await sleep(wait);

    // client_id + client_secret injected by the proxy
    const res = await fetch(`${AUTH_PROXY}/login/oauth/access_token`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        device_code: deviceCode,
        grant_type: "urn:ietf:params:oauth:grant-type:device_code",
      }),
    });

    if (!res.ok) {
      throw new Error(`Token poll failed: ${res.status}`);
    }

    const data = await res.json();

    if (data.access_token) {
      return data as TokenResult;
    }

    switch (data.error) {
      case "authorization_pending":
        // Normal — user hasn't entered the code yet.
        break;
      case "slow_down":
        wait += 5000;
        break;
      case "expired_token":
        throw new Error("Device code expired. Please try again.");
      case "access_denied":
        throw new Error("Authorization denied by user.");
      default:
        throw new Error(data.error_description ?? data.error ?? "Unknown error");
    }
  }

  throw new Error("Device code expired. Please try again.");
}

/** Fetch the authenticated user's profile. */
export async function fetchCurrentUser(
  token: string,
): Promise<{
  login: string;
  id: number;
  avatar_url: string;
  name: string | null;
  email: string | null;
  html_url: string;
}> {
  const res = await fetch("https://api.github.com/user", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Failed to fetch user: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
