export default function Footer() {
  return (
    <footer
      className="border-t border-slate-200 bg-slate-50"
      data-testid="site-footer"
    >
      <div className="container-app py-12 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div>
          <div className="flex items-center gap-2">
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
            <span className="brand-mark text-xl">
              FlowSpace
              <span className="text-slate-400 font-light">.Solutions</span>
            </span>
          </div>
          <p className="mt-3 text-sm text-slate-600 max-w-xs">
            Personalized AI-powered organization systems for garages, closets,
            laundry rooms, storage areas, and every space in between.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-6 text-sm md:col-span-2 md:justify-end">
          <div>
            <h4 className="font-semibold text-slate-900 mb-3">Product</h4>
            <ul className="space-y-2 text-slate-600">
              <li>
                <a
                  href="/#how"
                  className="hover:text-emerald-600"
                  data-testid="footer-link-how"
                >
                  How it works
                </a>
              </li>
              <li>
                <a
                  href="/#packages"
                  className="hover:text-emerald-600"
                  data-testid="footer-link-pricing"
                >
                  Pricing
                </a>
              </li>
              <li>
                <a
                  href="/#gallery"
                  className="hover:text-emerald-600"
                  data-testid="footer-link-examples"
                >
                  Examples
                </a>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold text-slate-900 mb-3">Company</h4>
            <ul className="space-y-2 text-slate-600">
              <li>
                <a
                  href="mailto:contact@flowspace.solutions"
                  className="hover:text-emerald-600"
                  data-testid="footer-link-contact"
                >
                  contact@flowspace.solutions
                </a>
              </li>
              <li>
                <a
                  href="/#faq"
                  className="hover:text-emerald-600"
                  data-testid="footer-link-faq"
                >
                  FAQ
                </a>
              </li>
            </ul>
          </div>
        </div>
      </div>
      <div className="border-t border-slate-200">
        <div className="container-app py-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs text-slate-500">
          <p data-testid="footer-copyright">
            © {new Date().getFullYear()} FlowSpace.Solutions — Turn cluttered
            into clean.
          </p>
          <p>Made with care for real homes.</p>
        </div>
      </div>
    </footer>
  );
}
