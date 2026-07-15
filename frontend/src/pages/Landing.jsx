import { useState } from "react";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import BeforeAfterSlider from "@/components/BeforeAfterSlider";
import PricingCard from "@/components/PricingCard";

// Existing assets preserved from the prior FlowSpace project
const HERO_BEFORE =
  "https://images.unsplash.com/photo-1570129476815-ba368ac77013?auto=format&fit=crop&w=1600&q=80";
const HERO_AFTER =
  "https://images.unsplash.com/photo-1727823065187-7b11ee08c1d8?auto=format&fit=crop&w=1600&q=80";

const GALLERY = [
  {
    id: "garage",
    category: "Garage",
    title: "From chaos garage to flow",
    before:
      "https://customer-assets.emergentagent.com/job_organize-design/artifacts/iynilrc8_cluttered_garage.png",
    after:
      "https://customer-assets.emergentagent.com/job_space-transformed/artifacts/9sy0qc1i_organized_garage.png",
  },
  {
    id: "closet",
    category: "Closet",
    title: "Closet, calmed",
    before:
      "https://customer-assets.emergentagent.com/job_organize-design/artifacts/9qy6to10_cluttered_closet.png",
    after:
      "https://customer-assets.emergentagent.com/job_space-transformed/artifacts/l8r8pdii_tidy_closet.png",
  },
  {
    id: "laundry",
    category: "Laundry",
    title: "A laundry room that breathes",
    before:
      "https://customer-assets.emergentagent.com/job_organize-design/artifacts/z2z93f26_cluttered_laundry_room.png",
    after:
      "https://customer-assets.emergentagent.com/job_space-transformed/artifacts/dlxnx33a_tidy_laundry_room.png",
  },
];

const PLANS = [
  {
    id: "free",
    name: "Free",
    tagline: "Try the FlowSpace experience",
    price: 0,
    features: [
      "Upload up to 2 photos",
      "AI-generated organized rooms",
      "Quick, no signup",
    ],
    pdf: false,
  },
  {
    id: "plus",
    name: "Plus",
    tagline: "For one space at a time",
    price: 10,
    features: [
      "Upload up to 3 photos",
      "AI-generated organized rooms",
      "Custom PDF organization plan",
      "Email delivery",
    ],
    pdf: true,
  },
  {
    id: "premium",
    name: "Premium",
    tagline: "For full-room transformations",
    price: 20,
    features: [
      "Upload up to 4 photos",
      "AI-generated organized rooms",
      "Custom PDF organization plan",
      "Shopping & labeling guide",
      "Priority delivery",
    ],
    pdf: true,
  },
];

const VALUES = [
  {
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-5 w-5"
      >
        <rect width="7" height="7" x="3" y="3" rx="1" />
        <rect width="7" height="7" x="14" y="3" rx="1" />
        <rect width="7" height="7" x="14" y="14" rx="1" />
        <rect width="7" height="7" x="3" y="14" rx="1" />
      </svg>
    ),
    title: "Personalized layout",
    body: "Designed for your real space — not a generic template.",
  },
  {
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-5 w-5"
      >
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" x2="12" y1="3" y2="15" />
      </svg>
    ),
    title: "Upload & go",
    body: "Snap a few photos. Skip the questionnaires and consults.",
  },
  {
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-5 w-5"
      >
        <path d="m16.24 7.76-1.804 5.411a2 2 0 0 1-1.265 1.265L7.76 16.24l1.804-5.411a2 2 0 0 1 1.265-1.265z" />
        <circle cx="12" cy="12" r="10" />
      </svg>
    ),
    title: "See it first",
    body: "Visualize the after before lifting a single box.",
  },
  {
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-5 w-5"
      >
        <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />
      </svg>
    ),
    title: "For real life",
    body: "Pretty, practical, and built for how you actually live.",
  },
];

const FAQS = [
  {
    q: "What does FlowSpace actually do?",
    a: "You upload photos of a cluttered room. Our AI generates a clean, organized version of the same room — same angle, same dimensions — with storage bins, shelving and a calmer layout, so you can see exactly how it could look.",
  },
  {
    q: "Do I need an account to get started?",
    a: "Nope. Pick a plan, upload your photos, and we get to work. You'll receive your transformation right in your browser, with a copy delivered to your email.",
  },
  {
    q: "How is the PDF plan different from the AI image?",
    a: "The AI image shows the visual transformation. The PDF (Plus & Premium) walks you through categories, a shopping list, and step-by-step setup — coming soon to your inbox after submission.",
  },
  {
    q: "Which rooms work best?",
    a: "Garages, closets, laundry rooms, mudrooms, pantries, kid rooms, and storage areas all work great. Anything with visible clutter and clear sightlines.",
  },
  {
    q: "What photo formats do you accept?",
    a: "JPG, PNG, and WebP — straight from your phone is perfect. Shoot in landscape with the whole space in frame for best results.",
  },
];

export default function Landing() {
  const [filter, setFilter] = useState("all");
  const filtered =
    filter === "all" ? GALLERY : GALLERY.filter((g) => g.id === filter);

  return (
    <div className="min-h-screen bg-white">
      <Header />

      {/* HERO */}
      <section
        className="relative overflow-hidden bg-white pt-10 md:pt-16"
        data-testid="landing-hero"
      >
        <div className="pointer-events-none absolute inset-0 -z-10">
          <div className="absolute left-1/2 top-[-10%] h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-emerald-100/60 blur-3xl" />
          <div className="absolute right-[-10%] top-[30%] h-[420px] w-[420px] rounded-full bg-sky-100/50 blur-3xl" />
        </div>
        <div className="container-app grid grid-cols-1 items-center gap-12 pb-16 md:gap-16 md:pb-24 lg:grid-cols-[1.05fr_1fr] fade-in">
          <div className="flex flex-col gap-7">
            <span className="eyebrow" data-testid="hero-eyebrow">
              AI-powered room organization
            </span>
            <h1 className="font-display text-[40px] font-light leading-[1.05] tracking-tight text-slate-900 sm:text-[56px] lg:text-[64px]">
              Turn cluttered rooms into
              <span className="block text-emerald-600">calm, organized spaces.</span>
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-slate-600">
              Upload photos of any messy room. Our AI generates a visual plan
              for a cleaner, more functional space — with storage bins, labels,
              and a layout that actually works. Perfect for garages, closets,
              laundry rooms, and everyday home organization.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <a
                href="#packages"
                className="btn-primary"
                data-testid="hero-cta-start"
              >
                Start my project
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
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
              <a
                href="#gallery"
                className="btn-ghost"
                data-testid="hero-cta-examples"
              >
                See examples
              </a>
            </div>
            <div className="flex flex-wrap items-center gap-5 pt-2 text-sm text-slate-500">
              <div className="flex items-center gap-1.5" data-testid="hero-rating">
                {[0, 1, 2, 3, 4].map((i) => (
                  <svg
                    key={i}
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="#fbbf24"
                    stroke="#fbbf24"
                    strokeWidth="1.6"
                    className="h-4 w-4"
                    aria-hidden="true"
                  >
                    <path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z" />
                  </svg>
                ))}
                <span className="ml-1">4.9 / 500+ homes organized</span>
              </div>
            </div>
          </div>
          <div className="relative">
            <div className="absolute -top-6 -left-6 hidden h-28 w-28 rounded-2xl bg-sky-50 md:block" />
            <div className="absolute -bottom-6 -right-6 hidden h-28 w-28 rounded-2xl bg-emerald-50 md:block" />
            <div className="relative">
              <BeforeAfterSlider
                beforeSrc={HERO_BEFORE}
                afterSrc={HERO_AFTER}
                aspect="4/5"
                testId="hero-slider"
              />
            </div>
          </div>
        </div>
      </section>

      {/* VALUE */}
      <section id="value" className="relative bg-slate-50 section-pad">
        <div className="container-app">
          <div className="max-w-2xl fade-in">
            <span className="eyebrow">Why FlowSpace</span>
            <h2 className="mt-4 font-display text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
              A smarter way to organize your space
            </h2>
          </div>
          <div className="mt-14 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
            {VALUES.map((v, i) => (
              <div
                key={i}
                className="group flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-7 card-hover hover:border-emerald-200"
                data-testid={`value-card-${i}`}
              >
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 transition-colors group-hover:bg-emerald-100">
                  {v.icon}
                </span>
                <h3 className="font-display text-xl font-medium text-slate-900">
                  {v.title}
                </h3>
                <p className="text-slate-600">{v.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how" className="relative bg-white section-pad">
        <div className="container-app">
          <div className="flex flex-col items-start gap-4 fade-in">
            <span className="eyebrow">Process</span>
            <h2 className="font-display text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
              Simple. Fast. Done for you.
            </h2>
          </div>
          <div className="mt-16 grid grid-cols-1 gap-8 md:grid-cols-3">
            {[
              {
                n: 1,
                title: "Pick a plan",
                body: "Choose Free, Plus, or Premium — based on how many photos you want transformed.",
              },
              {
                n: 2,
                title: "Upload your photos",
                body: "Snap photos of your messy space, drop them in, and we get to work instantly.",
              },
              {
                n: 3,
                title: "Get your AI transformation",
                body: "See a photorealistic ‘after’ for every room — with optional PDF organization plan.",
              },
            ].map((s) => (
              <div
                key={s.n}
                className="relative rounded-2xl border border-slate-200 bg-white p-8 card-hover"
                data-testid={`how-step-${s.n}`}
              >
                <div className="absolute -top-5 left-8 flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500 font-display text-sm font-semibold text-white shadow-md">
                  {s.n}
                </div>
                <h3 className="mt-3 font-display text-xl font-medium text-slate-900">
                  {s.title}
                </h3>
                <p className="mt-2 text-slate-600">{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section id="packages" className="relative bg-slate-50 section-pad">
        <div className="container-app">
          <div className="mx-auto max-w-2xl text-center fade-in">
            <span className="eyebrow !justify-center">Plans</span>
            <h2 className="mt-4 font-display text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
              Pick a plan that fits your space
            </h2>
            <p className="mt-4 text-slate-600">
              All plans include AI-generated organized room imagery. Upgrade
              for more photos and a personalized PDF plan.
            </p>
          </div>
          <div className="mt-14 grid grid-cols-1 gap-6 lg:grid-cols-3">
            {PLANS.map((p) => (
              <PricingCard
                key={p.id}
                plan={p}
                highlighted={p.id === "plus"}
                testId={`pricing-${p.id}`}
              />
            ))}
          </div>
          <p className="mt-8 text-center text-xs text-slate-500">
            No payment required. Pick a plan and start uploading.
          </p>
        </div>
      </section>

      {/* GALLERY */}
      <section id="gallery" className="relative bg-white section-pad">
        <div className="container-app">
          <div className="flex flex-col items-start gap-4 fade-in">
            <span className="eyebrow">Real transformations</span>
            <h2 className="font-display text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
              Slide to see the change
            </h2>
            <p className="max-w-2xl text-slate-600">
              From chaos to clarity — real rooms reimagined. Drag the divider.
            </p>
          </div>
          <div className="mt-8 flex flex-wrap gap-2">
            {[
              { id: "all", label: "All" },
              { id: "garage", label: "Garage" },
              { id: "closet", label: "Closet" },
              { id: "laundry", label: "Laundry" },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setFilter(t.id)}
                className={`rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                  filter === t.id
                    ? "border-emerald-500 bg-emerald-500 text-white"
                    : "border-slate-200 bg-white text-slate-600 hover:border-emerald-300"
                }`}
                data-testid={`gallery-filter-${t.id}`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-2">
            {filtered.map((g) => (
              <div key={g.id} data-testid={`gallery-item-${g.id}`}>
                <BeforeAfterSlider
                  beforeSrc={g.before}
                  afterSrc={g.after}
                  aspect="4/3"
                  testId={`gallery-slider-${g.id}`}
                />
                <div className="mt-3 flex items-center justify-between">
                  <p className="font-medium text-slate-800">{g.title}</p>
                  <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                    {g.category}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* WHO IT'S FOR */}
      <section className="relative bg-slate-50 section-pad">
        <div className="container-app">
          <div className="max-w-2xl fade-in">
            <span className="eyebrow">Who it&rsquo;s for</span>
            <h2 className="mt-4 font-display text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
              Built for real homes
            </h2>
          </div>
          <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              "Busy families with overflowing garages",
              "Renters with no patience for IKEA trips",
              "First-time homeowners",
              "Anyone tired of clutter",
            ].map((label, i) => (
              <div
                key={i}
                className="flex items-start gap-4 rounded-2xl border border-slate-200 bg-white p-6 hover:border-sky-200"
                data-testid={`who-item-${i}`}
              >
                <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sky-50 text-sky-600">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-5 w-5"
                    aria-hidden="true"
                  >
                    <path d="M3 21V8l9-5 9 5v13" />
                    <path d="M9 21v-7h6v7" />
                  </svg>
                </span>
                <p className="font-medium text-slate-800">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="relative bg-white section-pad">
        <div className="container-app grid grid-cols-1 gap-12 lg:grid-cols-[1fr_1.2fr]">
          <div className="flex flex-col gap-4 fade-in">
            <span className="eyebrow">FAQ</span>
            <h2 className="font-display text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
              Answers, fast
            </h2>
          </div>
          <div className="space-y-3" data-testid="faq-list">
            {FAQS.map((item, i) => (
              <details
                key={i}
                className="group rounded-xl border border-slate-200 bg-slate-50 p-5 open:bg-white open:shadow-sm transition-all"
                data-testid={`faq-item-${i}`}
              >
                <summary className="flex cursor-pointer items-center justify-between text-lg font-medium text-slate-900 list-none">
                  {item.q}
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-5 w-5 text-slate-500 transition-transform group-open:rotate-180"
                    aria-hidden="true"
                  >
                    <path d="m6 9 6 6 6-6" />
                  </svg>
                </summary>
                <p className="mt-3 text-slate-600 leading-relaxed">{item.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="relative bg-white pb-20">
        <div className="container-app">
          <div
            className="relative overflow-hidden rounded-3xl border border-slate-200 bg-gradient-to-br from-emerald-500 to-emerald-600 p-10 text-white shadow-lg md:p-16"
            data-testid="final-cta"
          >
            <div className="absolute -right-16 -top-16 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
            <div className="absolute -bottom-20 -left-16 h-72 w-72 rounded-full bg-sky-400/30 blur-3xl" />
            <div className="relative grid grid-cols-1 items-center gap-10 md:grid-cols-[1.4fr_1fr]">
              <div>
                <h2 className="font-display text-4xl font-light tracking-tight sm:text-5xl">
                  Your space can feel different — fast.
                </h2>
                <p className="mt-4 max-w-xl text-lg text-emerald-50">
                  Upload your room photos and get a visual plan for a cleaner,
                  more functional home. Pick a plan and start in under a minute.
                </p>
              </div>
              <div className="flex md:justify-end">
                <a
                  href="#packages"
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-7 py-4 text-base font-medium text-emerald-700 shadow-sm hover:bg-emerald-50"
                  data-testid="final-cta-start"
                >
                  Choose your plan
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="18"
                    height="18"
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
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
