/**
 * Cloudflare Worker — GitHub OAuth Device Flow proxy.
 *
 * Solves two problems for the ForgeDS IDE (a static SPA on GitHub Pages):
 *  1. GitHub's OAuth endpoints return no CORS headers → browser blocks the response.
 *  2. The token exchange requires client_secret → can't ship it in frontend JS.
 *
 * Environment variables (set via `wrangler secret put`):
 *   CLIENT_ID     — GitHub OAuth App client ID
 *   CLIENT_SECRET — GitHub OAuth App client secret
 *
 * Endpoints:
 *   POST /login/device/code         → proxies to github.com/login/device/code
 *   POST /login/oauth/access_token  → proxies to github.com/login/oauth/access_token
 */

const GITHUB = "https://github.com";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Accept",
};

export default {
  async fetch(request, env) {
    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    const path = url.pathname;

    // Only proxy the two OAuth paths
    if (path !== "/login/device/code" && path !== "/login/oauth/access_token") {
      return new Response("Not found", { status: 404, headers: CORS_HEADERS });
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405, headers: CORS_HEADERS });
    }

    // Parse the incoming body from the browser
    let body = {};
    try {
      body = await request.json();
    } catch {
      // empty body is fine for some requests
    }

    // Inject credentials — browser never sees client_secret
    body.client_id = env.CLIENT_ID;
    if (path === "/login/oauth/access_token") {
      body.client_secret = env.CLIENT_SECRET;
    }

    // Forward to GitHub
    const ghResponse = await fetch(`${GITHUB}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    });

    // Return GitHub's response with CORS headers
    const responseBody = await ghResponse.text();
    return new Response(responseBody, {
      status: ghResponse.status,
      headers: {
        "Content-Type": "application/json",
        ...CORS_HEADERS,
      },
    });
  },
};
