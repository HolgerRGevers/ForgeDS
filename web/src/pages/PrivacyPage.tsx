import { Link } from "react-router-dom";

export default function PrivacyPage() {
  return (
    <div className="flex min-h-screen justify-center bg-gray-950 px-4 py-12">
      <div className="w-full max-w-2xl space-y-8">
        {/* Header */}
        <div>
          <Link to="/" className="text-sm text-blue-400 hover:text-blue-300">
            &larr; Back to ForgeDS IDE
          </Link>
          <h1 className="mt-4 text-2xl font-bold text-white">Privacy Policy</h1>
          <p className="mt-1 text-sm text-gray-500">Last updated: April 2026</p>
        </div>

        <div className="space-y-6 text-sm leading-relaxed text-gray-300">
          {/* Overview */}
          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">Overview</h2>
            <p>
              ForgeDS IDE is a client-side web application for building Zoho Creator
              applications. It connects to your GitHub account to manage repositories,
              files, branches, and pull requests. This policy explains what data the
              app accesses, stores, and how you can control it.
            </p>
          </section>

          {/* What we access */}
          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">What We Access</h2>
            <p>
              When you sign in with GitHub, the app requests the following OAuth scopes:
            </p>
            <ul className="mt-2 list-inside list-disc space-y-1 text-gray-400">
              <li>
                <span className="font-mono text-blue-400">repo</span> &mdash; Read and write
                access to your public and private repositories (code, commits, branches,
                pull requests, collaborators).
              </li>
              <li>
                <span className="font-mono text-blue-400">read:user</span> &mdash; Read-only
                access to your public profile information (username, avatar, profile URL).
              </li>
            </ul>
            <p className="mt-2">
              These scopes are the minimum required for the IDE to function. The app
              does not request access to your email, organizations, or any other GitHub data
              beyond what these scopes provide.
            </p>
          </section>

          {/* What we store */}
          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">What We Store</h2>
            <p>
              All data is stored locally in your browser&apos;s <code className="rounded bg-gray-800 px-1 py-0.5 text-blue-400">localStorage</code>.
              Nothing is sent to or stored on our servers. Specifically:
            </p>
            <ul className="mt-2 list-inside list-disc space-y-1 text-gray-400">
              <li>Your GitHub OAuth token (for API authentication)</li>
              <li>Your GitHub profile (username, avatar — cached for fast UI rendering)</li>
              <li>Your last selected repository and branch</li>
              <li>Your AI skill preferences and project history</li>
            </ul>
          </section>

          {/* What we don't do */}
          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">What We Don&apos;t Do</h2>
            <ul className="list-inside list-disc space-y-1 text-gray-400">
              <li>We do not operate any backend servers that store your data</li>
              <li>We do not use analytics, tracking, or telemetry of any kind</li>
              <li>We do not share your data with third parties</li>
              <li>We do not sell, rent, or monetize your personal information</li>
              <li>We do not collect data beyond what is needed for the app to function</li>
              <li>We do not use cookies</li>
            </ul>
          </section>

          {/* OAuth proxy */}
          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">Authentication Proxy</h2>
            <p>
              The app uses a Cloudflare Worker as an OAuth proxy during the GitHub Device
              Flow sign-in process. This proxy exists solely to:
            </p>
            <ul className="mt-2 list-inside list-disc space-y-1 text-gray-400">
              <li>Add CORS headers required for browser-based OAuth requests</li>
              <li>Inject the OAuth client secret server-side (so it is never exposed in your browser)</li>
            </ul>
            <p className="mt-2">
              The proxy does not log, cache, or store any request data. After sign-in
              completes, all GitHub API calls are made directly from your browser to
              <code className="rounded bg-gray-800 px-1 py-0.5 text-blue-400"> api.github.com</code>.
            </p>
          </section>

          {/* Rate limits */}
          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">API Rate Limits</h2>
            <p>
              The app respects GitHub&apos;s API rate limits. It monitors rate limit headers
              on every API response, implements exponential backoff for rate-limited requests,
              and throttles batch operations (like uploading multiple files) to stay within
              GitHub&apos;s secondary rate limits.
            </p>
          </section>

          {/* Revoking access */}
          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">Revoking Access</h2>
            <p>You can revoke ForgeDS IDE&apos;s access to your GitHub account at any time:</p>
            <ol className="mt-2 list-inside list-decimal space-y-1 text-gray-400">
              <li>Go to <span className="text-blue-400">GitHub Settings &rarr; Applications &rarr; Authorized OAuth Apps</span></li>
              <li>Find ForgeDS and click &quot;Revoke&quot;</li>
              <li>Your token will be immediately invalidated</li>
            </ol>
            <p className="mt-2">
              To clear all locally stored data, log out of the app or clear your
              browser&apos;s localStorage for this site.
            </p>
          </section>

          {/* Data deletion */}
          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">Data Deletion</h2>
            <p>
              Since all data is stored in your browser, you have full control. To delete
              all ForgeDS IDE data:
            </p>
            <ul className="mt-2 list-inside list-disc space-y-1 text-gray-400">
              <li>Click &quot;Sign out&quot; in the app (clears token and profile)</li>
              <li>Or clear your browser&apos;s site data for this domain (clears everything)</li>
            </ul>
            <p className="mt-2">No server-side data exists that would need separate deletion.</p>
          </section>

          {/* GitHub ToS */}
          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">GitHub Terms Compliance</h2>
            <p>
              ForgeDS IDE complies with GitHub&apos;s{" "}
              <a
                href="https://docs.github.com/en/site-policy/github-terms/github-terms-of-service"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 underline hover:text-blue-300"
              >
                Terms of Service
              </a>
              ,{" "}
              <a
                href="https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 underline hover:text-blue-300"
              >
                Acceptable Use Policies
              </a>
              , and{" "}
              <a
                href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 underline hover:text-blue-300"
              >
                Privacy Statement
              </a>
              .
            </p>
          </section>

          {/* Contact */}
          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">Contact</h2>
            <p>
              For questions about this policy, open an issue on the{" "}
              <a
                href="https://github.com/HolgerRGevers/ForgeDS"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 underline hover:text-blue-300"
              >
                ForgeDS GitHub repository
              </a>
              .
            </p>
          </section>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-800 pt-6 text-center text-xs text-gray-600">
          ForgeDS IDE &mdash; Open source, client-side only, zero data collection.
        </div>
      </div>
    </div>
  );
}
