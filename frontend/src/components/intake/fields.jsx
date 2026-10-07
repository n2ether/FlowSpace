import React from "react";

export function describedBy(id, { hint, error } = {}) {
    const ids = [];
    if (hint) ids.push(`${id}-hint`);
    if (error) ids.push(`${id}-error`);
    return ids.length ? ids.join(" ") : undefined;
}

export function ErrorText({ id, error }) {
    if (!error) return null;
    return (
        <p id={`${id}-error`} className="mt-1.5 text-sm font-medium text-red-700" data-testid={`error-${id}`}>
            <span aria-hidden="true">! </span>
            {error}
        </p>
    );
}

export function Hint({ id, hint }) {
    if (!hint) return null;
    return (
        <p id={`${id}-hint`} className="mt-1.5 text-xs text-slate-500">
            {hint}
        </p>
    );
}

function OptionalTag() {
    return <span className="ml-1 font-normal text-slate-500">(optional)</span>;
}

export function TextField({
    id,
    label,
    hint,
    error,
    optional = false,
    multiline = false,
    value,
    onChange,
    className = "",
    ...rest
}) {
    const Tag = multiline ? "textarea" : "input";
    return (
        <div className={className}>
            <label htmlFor={id} className="mb-2 block text-sm font-medium text-slate-800">
                {label}
                {optional && <OptionalTag />}
            </label>
            <Tag
                id={id}
                name={id}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className={`input ${error ? "!border-red-500" : ""}`}
                aria-describedby={describedBy(id, { hint, error })}
                aria-invalid={error ? "true" : undefined}
                data-testid={`field-${id}`}
                {...rest}
            />
            <Hint id={id} hint={hint} />
            <ErrorText id={id} error={error} />
        </div>
    );
}

export function SelectField({ id, label, hint, error, optional = false, value, onChange, options, placeholder, className = "" }) {
    return (
        <div className={className}>
            <label htmlFor={id} className="mb-2 block text-sm font-medium text-slate-800">
                {label}
                {optional && <OptionalTag />}
            </label>
            <select
                id={id}
                name={id}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className={`input ${error ? "!border-red-500" : ""}`}
                aria-describedby={describedBy(id, { hint, error })}
                aria-invalid={error ? "true" : undefined}
                data-testid={`field-${id}`}
            >
                {placeholder !== undefined && <option value="">{placeholder}</option>}
                {options.map((o) => (
                    <option key={o.id} value={o.id}>
                        {o.label}
                    </option>
                ))}
            </select>
            <Hint id={id} hint={hint} />
            <ErrorText id={id} error={error} />
        </div>
    );
}

function OptionCard({ type, name, option, checked, onChange, testId }) {
    return (
        <label
            className={`flex min-h-[48px] cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm font-medium transition-colors focus-within:ring-2 focus-within:ring-emerald-500 focus-within:ring-offset-1 ${
                checked
                    ? "border-emerald-500 bg-emerald-50 text-emerald-900"
                    : "border-slate-200 bg-white text-slate-700 hover:border-emerald-300"
            }`}
        >
            <input
                type={type}
                name={name}
                value={option.id}
                checked={checked}
                onChange={onChange}
                className="h-4 w-4 shrink-0 accent-emerald-600"
                data-testid={testId}
            />
            <span className="min-w-0 break-words">{option.label}</span>
        </label>
    );
}

// Radio or checkbox group wrapped in a fieldset; the legend names the group and
// the error is linked to every option through aria-describedby on the fieldset.
export function ChoiceGroup({
    id,
    legend,
    hint,
    error,
    optional = false,
    multiple = false,
    options,
    value,
    onChange,
    columns = "sm:grid-cols-2",
}) {
    const selected = multiple ? value || [] : value;
    const toggle = (optId) => {
        if (!multiple) return onChange(optId);
        const next = selected.includes(optId) ? selected.filter((v) => v !== optId) : [...selected, optId];
        return onChange(next);
    };
    return (
        <fieldset
            id={id}
            aria-describedby={describedBy(id, { hint, error })}
            aria-invalid={error ? "true" : undefined}
            data-testid={`group-${id}`}
        >
            <legend className="mb-2 block text-sm font-medium text-slate-800">
                {legend}
                {optional && <OptionalTag />}
            </legend>
            <Hint id={id} hint={hint} />
            <div className={`mt-2 grid grid-cols-1 gap-2 ${columns}`}>
                {options.map((o) => (
                    <OptionCard
                        key={o.id}
                        type={multiple ? "checkbox" : "radio"}
                        name={id}
                        option={o}
                        checked={multiple ? selected.includes(o.id) : selected === o.id}
                        onChange={() => toggle(o.id)}
                        testId={`${id}-${o.id}`}
                    />
                ))}
            </div>
            <ErrorText id={id} error={error} />
        </fieldset>
    );
}

export function focusField(fieldId) {
    const el = document.getElementById(fieldId);
    if (!el) return;
    const target = el.matches("input,select,textarea,button")
        ? el
        : el.querySelector("input:not([type=hidden]),select,textarea,button");
    (target || el).focus();
}

export const ErrorSummary = React.forwardRef(function ErrorSummary({ errors, labels }, ref) {
    const entries = Object.entries(errors || {});
    if (!entries.length) return null;
    return (
        <div
            ref={ref}
            tabIndex={-1}
            role="alert"
            aria-labelledby="intake-error-summary-title"
            className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-900 focus:outline-none focus:ring-2 focus:ring-red-400"
            data-testid="intake-error-summary"
        >
            <p id="intake-error-summary-title" className="font-semibold">
                {entries.length === 1 ? "One thing needs your attention" : `${entries.length} things need your attention`}
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
                {entries.map(([field, message]) => (
                    <li key={field}>
                        <a
                            href={`#${field}`}
                            className="underline underline-offset-2"
                            onClick={(e) => {
                                e.preventDefault();
                                focusField(field);
                            }}
                        >
                            {labels?.[field] ? `${labels[field]}: ` : ""}
                            {message}
                        </a>
                    </li>
                ))}
            </ul>
        </div>
    );
});
