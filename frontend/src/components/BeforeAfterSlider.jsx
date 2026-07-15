import { ReactCompareSlider, ReactCompareSliderImage } from "react-compare-slider";

export default function BeforeAfterSlider({
  beforeSrc,
  afterSrc,
  beforeAlt = "Before",
  afterAlt = "After",
  aspect = "4/5",
  testId = "before-after-slider",
}) {
  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 shadow-xl"
      style={{ aspectRatio: aspect }}
      data-testid={testId}
    >
      <ReactCompareSlider
        itemOne={
          <ReactCompareSliderImage src={beforeSrc} alt={beforeAlt} style={{ objectFit: "cover" }} />
        }
        itemTwo={
          <ReactCompareSliderImage src={afterSrc} alt={afterAlt} style={{ objectFit: "cover" }} />
        }
        position={50}
        style={{ height: "100%", width: "100%" }}
      />
      <span
        className="pointer-events-none absolute left-4 top-4 rounded-full bg-white/90 px-3 py-1 text-[11px] font-medium uppercase tracking-widest text-slate-700 shadow-sm backdrop-blur"
        data-testid={`${testId}-before-label`}
      >
        Before
      </span>
      <span
        className="pointer-events-none absolute right-4 top-4 rounded-full bg-emerald-500 px-3 py-1 text-[11px] font-medium uppercase tracking-widest text-white shadow-sm"
        data-testid={`${testId}-after-label`}
      >
        After
      </span>
    </div>
  );
}
