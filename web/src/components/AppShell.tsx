import type { ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { BridgePill } from "./ConnectionStatus";
import { UserMenu } from "./UserMenu";
import { BrandMark } from "./BrandMark";

interface AppShellProps {
  children: ReactNode;
}

const navItems = [
  { to: "/ide", label: "Prompt", phase: 1 },
  { to: "/ide", label: "IDE", phase: 2 },
  { to: "/database", label: "Database", phase: 3 },
  { to: "/api", label: "API", phase: 4 },
];

type HeaderVariant = "minimal" | "wizard" | "full";

function variantFor(pathname: string): HeaderVariant {
  if (pathname.startsWith("/new/")) return "wizard";
  if (pathname.startsWith("/dashboard")) return "minimal";
  return "full";
}

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const variant = variantFor(location.pathname);

  return (
    <div className="flex h-screen flex-col bg-gray-950 text-gray-100">
      <header className="flex items-center justify-between bg-gray-800 px-4 py-2 shadow-md">
        <NavLink to="/dashboard" className="flex items-center gap-2">
          <BrandMark size={24} />
          <span className="text-lg font-medium tracking-tight">
            <span className="text-gray-100">Forge</span>
            <span className="text-[#c2662d]">DS</span>
          </span>
        </NavLink>

        {variant === "full" && (
          <nav className="flex items-center gap-1">
            {navItems.map((item) => (
              <NavLink
                key={`${item.to}-${item.label}`}
                to={item.to}
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
        )}

        <div className="flex items-center gap-3">
          {variant === "wizard" && (
            <button
              type="button"
              onClick={() => {
                if (confirm("Cancel this prototype? Your answers will be lost.")) {
                  navigate("/dashboard");
                }
              }}
              className="text-xs text-gray-400 hover:text-white"
            >
              × Cancel
            </button>
          )}
          {variant === "full" && <BridgePill />}
          <UserMenu />
        </div>
      </header>

      <main className="flex-1 overflow-hidden">{children}</main>

      <footer className="flex items-center justify-center border-t border-gray-800 bg-gray-900 px-4 py-1.5">
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
