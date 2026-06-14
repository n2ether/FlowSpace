import { Link } from "react-router-dom";

const navItems = [
  { label: "How it works", href: "/#how" },
  { label: "Examples", href: "/#gallery" },
  { label: "Pricing", href: "/#packages" },
  { label: "FAQ", href: "/#faq" },
];

export default function Header() {
  return (
    <header
      className="sticky top-0 z-40 w-full bg-white/85 backdrop-blur border-b border-slate-100"
      data-testid="site-header"
    >
      <div className="container-app flex h-16 items-center justify-between">
        <Link
          to="/"
          className="flex items-center gap-2"
          data-testid="brand-logo-link"
        >
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500 text-white shadow-sm">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-5 w-5"
              aria-hidden="true"
            >
              <path d="M3 21V8l9-5 9 5v13" />
              <path d="M9 21v-7h6v7" />
            </svg>
          </span>
          <span
            className="brand-mark text-xl sm:text-[22px]"
            data-testid="brand-wordmark"
          >
            FlowSpace
            <span className="text-slate-400 font-light">.Solutions</span>
          </span>
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
    </header>
  );
}
