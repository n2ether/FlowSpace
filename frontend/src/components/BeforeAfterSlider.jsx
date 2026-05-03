import React from "react";
import {
    ReactCompareSlider,
    ReactCompareSliderImage,
} from "react-compare-slider";

const BeforeAfterSlider = ({
    beforeUrl,
    afterUrl,
    beforeLabel = "Before",
    afterLabel = "After",
    className = "",
    testIdPrefix = "ba-slider",
}) => {
    return (
        <div
            className={`relative overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 ${className}`}
            data-testid={`${testIdPrefix}-wrapper`}
        >
            <ReactCompareSlider
                itemOne={
                    <ReactCompareSliderImage
                        src={beforeUrl}
                        alt="Before"
                        style={{ objectFit: "cover" }}
                    />
                }
                itemTwo={
                    <ReactCompareSliderImage
                        src={afterUrl}
                        alt="After"
                        style={{ objectFit: "cover" }}
                    />
                }
                style={{ height: "100%", width: "100%" }}
                changePositionOnHover={false}
            />
            <span
                className="pointer-events-none absolute left-4 top-4 rounded-full bg-white/90 px-3 py-1 text-xs font-medium uppercase tracking-widest text-slate-700 shadow-sm backdrop-blur"
                data-testid={`${testIdPrefix}-before-label`}
            >
                {beforeLabel}
            </span>
            <span
                className="pointer-events-none absolute right-4 top-4 rounded-full bg-emerald-500 px-3 py-1 text-xs font-medium uppercase tracking-widest text-white shadow-sm"
                data-testid={`${testIdPrefix}-after-label`}
            >
                {afterLabel}
            </span>
        </div>
    );
};

export default BeforeAfterSlider;
