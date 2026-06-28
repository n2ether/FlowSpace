import { useEffect, useState } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Footer() {
  const [devLoginEnabled, setDevLoginEnabled] = useState(false);

  useEffect(() => {
    let cancelled = false;
    axios
      .get(`${API}/config`)
      .then((r) => {
        if (!cancelled) setDevLoginEnabled(!!r.data?.dev_login_enabled);
      })
      .catch(() => {
        /* ignore — link just stays hidden */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <footer
      className="border-t border-slate-200 bg-slate-50"
      data-testid="site-footer"
    >
      <div className="container-app py-12 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div>
          <img
            src="https://customer-assets.emergentagent.com/job_organize-design/artifacts/rb6cf6gu_FlowSpace%20Logo.png"
            alt="FlowSpace — Clear space. Create flow. Live better."
            className="h-12 w-auto"
            data-testid="footer-logo-image"
          />
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
          <div className="flex items-center gap-4">
            {devLoginEnabled && (
              <a
                href="/dev/login"
                className="text-slate-400 hover:text-emerald-600"
                data-testid="footer-dev-login-link"
              >
                Sign in for testing
              </a>
            )}
            <p>Made with care for real homes.</p>
          </div>
        </div>
      </div>
    </footer>
  );
}
