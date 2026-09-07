import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const navItems = [
  { label: "How it works", href: "/#how" },
  { label: "Examples", href: "/#gallery" },
  { label: "Pricing", href: "/#packages" },
  { label: "FAQ", href: "/#faq" },
];

export default function Header() {
  const { member, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const close = () => setOpen(false);

  const onLogout = async () => {
    await logout();
    close();
    if (location.pathname.startsWith("/account")) navigate("/");
  };

  return (
    <header className="sticky top-0 z-40 border-b border-slate-100 bg-white/85 backdrop-blur">
      <div className="container-app flex h-16 items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-2" data-testid="header-logo" onClick={close}>
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500 text-white font-semibold">F</span>
          <span className="font-display text-lg font-medium tracking-tight text-slate-900">
            FlowSpace<span className="text-emerald-600">.</span>
          </span>
        </Link>
        <nav className="hidden items-center gap-7 md:flex">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="text-sm font-medium text-slate-600 hover:text-emerald-600 transition-colors"
              data-testid={`nav-${item.label.replace(/\s+/g, "-").toLowerCase()}`}
            >
              {item.label}
            </a>
          ))}
          <Link
            to={member ? "/account" : "/login"}
            className="text-sm font-medium text-slate-600 hover:text-emerald-600 transition-colors"
            data-testid="nav-members"
          >
            {member ? "My spaces" : "Members"}
          </Link>
        </nav>
        <div className="hidden items-center gap-2 md:flex">
          {member ? (
            <>
              <Link
                to="/account"
                className="max-w-[10rem] truncate text-sm font-medium text-slate-600 hover:text-emerald-600"
                data-testid="header-account"
              >
                {member.name || member.email}
              </Link>
              <button
                type="button"
                onClick={onLogout}
                className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:border-emerald-300 hover:text-emerald-700"
                data-testid="header-logout"
              >
                Log out
              </button>
            </>
          ) : (
            <Link
              to="/login"
              className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:border-emerald-300 hover:text-emerald-700"
              data-testid="header-login"
            >
              Log in
            </Link>
          )}
          <a
            href="/#packages"
            className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500 px-5 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-600 transition-colors"
            data-testid="header-cta"
          >
            Start now
          </a>
        </div>
        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 text-slate-700 md:hidden"
          aria-expanded={open}
          aria-label={open ? "Close menu" : "Open menu"}
          data-testid="header-menu-toggle"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? (
            <span className="text-lg leading-none">×</span>
          ) : (
            <span className="flex flex-col gap-1.5">
              <span className="block h-0.5 w-4 bg-slate-700" />
              <span className="block h-0.5 w-4 bg-slate-700" />
              <span className="block h-0.5 w-4 bg-slate-700" />
            </span>
          )}
        </button>
      </div>
      {open && (
        <div className="border-t border-slate-100 bg-white md:hidden" data-testid="header-mobile-menu">
          <div className="container-app flex flex-col gap-1 py-3">
            {navItems.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={close}
                className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-emerald-50 hover:text-emerald-700"
              >
                {item.label}
              </a>
            ))}
            <Link
              to={member ? "/account" : "/signup"}
              onClick={close}
              className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-emerald-50 hover:text-emerald-700"
              data-testid="nav-members-mobile"
            >
              {member ? "My spaces" : "Create free account"}
            </Link>
            {member ? (
              <button
                type="button"
                onClick={onLogout}
                className="rounded-lg px-3 py-2 text-left text-sm font-medium text-slate-700 hover:bg-emerald-50"
              >
                Log out
              </button>
            ) : (
              <Link
                to="/login"
                onClick={close}
                className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-emerald-50"
              >
                Log in
              </Link>
            )}
            <a
              href="/#packages"
              onClick={close}
              className="mt-1 inline-flex items-center justify-center rounded-full bg-emerald-500 px-5 py-2.5 text-sm font-medium text-white"
            >
              Start now
            </a>
          </div>
        </div>
      )}
    </header>
  );
}
