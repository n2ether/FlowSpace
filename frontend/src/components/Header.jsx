import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

const navItems = [
  { label: "How it works", href: "/#how" },
  { label: "Examples", href: "/#gallery" },
  { label: "Pricing", href: "/#packages" },
  { label: "FAQ", href: "/#faq" },
];

function UserMenu({ user, onLogout }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const initial = (user.name || user.email || "?").trim().charAt(0).toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-2 py-1.5 hover:border-emerald-300"
        data-testid="user-menu-trigger"
      >
        {user.picture ? (
          <img src={user.picture} alt="" className="h-7 w-7 rounded-full object-cover" />
        ) : (
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500 text-xs font-semibold text-white">
            {initial}
          </span>
        )}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-4 w-4 text-slate-500"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      {open && (
        <div
          className="absolute right-0 mt-2 w-64 origin-top-right rounded-xl border border-slate-200 bg-white p-2 shadow-lg"
          data-testid="user-menu-panel"
        >
          <div className="px-3 py-2.5">
            <p className="text-sm font-semibold text-slate-900 truncate">{user.name}</p>
            <p className="text-xs text-slate-500 truncate">{user.email}</p>
            <p className="mt-2 text-[11px] uppercase tracking-widest text-emerald-700">
              Free remaining: {user.free_remaining}/{user.free_cap}
            </p>
          </div>
          <div className="my-1 h-px bg-slate-100" />
          <Link
            to="/projects"
            onClick={() => setOpen(false)}
            className="block rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            data-testid="user-menu-projects"
          >
            My projects
          </Link>
          <button
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
            className="w-full text-left rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50"
            data-testid="user-menu-logout"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export default function Header() {
  const { user, loading, signIn, logout } = useAuth();

  return (
    <header
      className="sticky top-0 z-40 w-full bg-white/85 backdrop-blur border-b border-slate-100"
      data-testid="site-header"
    >
      <div className="container-app flex h-16 items-center justify-between gap-4">
        <Link
          to="/"
          className="flex items-center gap-2"
          data-testid="brand-logo-link"
        >
          <img
            src="https://customer-assets.emergentagent.com/job_organize-design/artifacts/rb6cf6gu_FlowSpace%20Logo.png"
            alt="FlowSpace.Solutions — Clear space. Create flow. Live better."
            className="h-10 sm:h-11 w-auto"
            data-testid="brand-logo-image"
          />
        </Link>

        <nav className="hidden md:flex items-center gap-7" data-testid="site-nav">
          {navItems.map((it) => (
            <a
              key={it.href}
              href={it.href}
              className="text-sm font-medium text-slate-600 hover:text-emerald-600 transition-colors"
              data-testid={`nav-${it.label.toLowerCase().replace(/\s+/g, "-")}`}
            >
              {it.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          {!loading && user && <UserMenu user={user} onLogout={logout} />}
          {!loading && !user && (
            <button
              onClick={() => signIn("/projects")}
              className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:border-emerald-300 hover:text-emerald-700"
              data-testid="header-signin-btn"
            >
              Sign in
            </button>
          )}
          <a
            href="/#packages"
            className="btn-primary !py-2.5 !px-5 text-sm"
            data-testid="header-cta-start"
          >
            Start project
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M5 12h14" />
              <path d="m12 5 7 7-7 7" />
            </svg>
          </a>
        </div>
      </div>
    </header>
  );
}
