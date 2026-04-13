import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { ConnectionStatus } from "./ConnectionStatus";
import { UserMenu } from "./UserMenu";
import type { ConnectionStatus as ConnStatus } from "../types/bridge";

interface AppShellProps {
  children: ReactNode;
  bridgeStatus?: ConnStatus;
}

const navItems = [
  { to: "/", label: "Prompt", phase: 1 },
  { to: "/ide", label: "IDE", phase: 2 },
  { to: "/database", label: "Database", phase: 3 },
  { to: "/api", label: "API", phase: 4 },
];

export function AppShell({ children, bridgeStatus }: AppShellProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="flex h-screen flex-col bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="flex items-center justify-between bg-gray-800 px-3 py-2 shadow-md sm:px-4">
        {/* Left: hamburger + logo */}
        <div className="flex items-center gap-2">
          {/* Hamburger (mobile only) */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen((v) => !v)}
            className="flex h-8 w-8 items-center justify-center rounded text-gray-400 hover:bg-gray-700 hover:text-white lg:hidden"
            aria-label="Toggle menu"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {mobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>

          {/* Logo */}
          <NavLink to="/" className="flex items-center gap-2">
            <span className="text-base font-bold tracking-tight text-white sm:text-lg">
              ForgeDS<span className="text-blue-400">_IDE</span>
            </span>
          </NavLink>
        </div>

        {/* Desktop navigation */}
        <nav className="hidden items-center gap-1 lg:flex">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "text-white underline underline-offset-4 decoration-blue-400 decoration-2"
                    : item.phase > 1
                      ? "text-gray-500 hover:text-gray-300"
                      : "text-gray-300 hover:text-white"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Right side: bridge status + user menu */}
        <div className="flex items-center gap-2 sm:gap-3">
          {bridgeStatus === "connected" && (
            <span className="hidden sm:block"><ConnectionStatus /></span>
          )}
          {bridgeStatus === "connected" && (
            <span className="block sm:hidden">
              <span className="h-2 w-2 rounded-full bg-green-500 inline-block" title="Bridge connected" />
            </span>
          )}
          {bridgeStatus === "connecting" && (
            <span className="text-xs text-yellow-500" title="Bridge connecting...">
              <span className="hidden sm:inline">Bridge...</span>
              <span className="inline sm:hidden h-2 w-2 rounded-full bg-yellow-400 animate-pulse" />
            </span>
          )}
          <UserMenu />
        </div>
      </header>

      {/* Mobile navigation dropdown */}
      {mobileMenuOpen && (
        <nav className="border-b border-gray-700 bg-gray-800 px-3 py-2 lg:hidden">
          <div className="flex flex-col gap-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `rounded px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-gray-700 text-white"
                      : item.phase > 1
                        ? "text-gray-500 hover:bg-gray-700 hover:text-gray-300"
                        : "text-gray-300 hover:bg-gray-700 hover:text-white"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
          {bridgeStatus && (
            <div className="mt-2 border-t border-gray-700 pt-2 text-xs text-gray-500">
              Bridge: {bridgeStatus}
            </div>
          )}
        </nav>
      )}

      {/* Main content */}
      <main className="flex-1 overflow-hidden">{children}</main>

      {/* Footer */}
      <footer className="safe-bottom flex items-center justify-center border-t border-gray-800 bg-gray-900 px-4 py-1.5">
        <NavLink
          to="/privacy"
          className="text-[10px] text-gray-600 transition-colors hover:text-gray-400"
        >
          Privacy Policy
        </NavLink>
      </footer>
    </div>
  );
}
