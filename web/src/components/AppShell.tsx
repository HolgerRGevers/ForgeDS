import type { ReactNode } from "react";
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
  return (
    <div className="flex h-screen flex-col bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="flex items-center justify-between bg-gray-800 px-4 py-2 shadow-md">
        {/* Logo */}
        <NavLink to="/" className="flex items-center gap-2">
          <span className="text-lg font-bold tracking-tight text-white">
            ForgeDS<span className="text-blue-400">_IDE</span>
          </span>
        </NavLink>

        {/* Navigation */}
        <nav className="flex items-center gap-1">
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
        <div className="flex items-center gap-3">
          {bridgeStatus === "connected" && <ConnectionStatus />}
          {bridgeStatus === "connecting" && (
            <span className="text-xs text-yellow-500" title="Bridge connecting...">
              Bridge...
            </span>
          )}
          <UserMenu />
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
