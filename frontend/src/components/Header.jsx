import { Link } from "react-router-dom";

const navItems = [
  { label: "How it works", href: "/#how" },
  { label: "Examples", href: "/#gallery" },
  { label: "Pricing", href: "/#packages" },
  { label: "FAQ", href: "/#faq" },
];

export default function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-100 bg-white/85 backdrop-blur">
      <div className="container-app flex h-16 items-center justify-between">
        <Link to="/" className="flex items-center gap-2" data-testid="header-logo">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500 text-white font-semibold">F</span>
          <span className="font-display text-lg font-medium tracking-tight text-slate-900">
            FlowSpace<span className="text-emerald-600">.</span>
          </span>
        </Link>
        <nav className="hidden items-center gap-8 md:flex">
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
        </nav>
        <a
          href="/#packages"
          className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500 px-5 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-600 transition-colors"
          data-testid="header-cta"
        >
          Start now
        </a>
      </div>
    </header>
  );
}
