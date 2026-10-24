import React from "react";
import { ChoiceGroup, SelectField, TextField } from "./fields";
import { PRIORITIES, SPACE_TYPES, SPECIFICS_MAX } from "../../lib/intake/model";

export default function StepSpace({ form, update, errors }) {
    return (
        <div className="space-y-7">
            <SelectField
                id="space_type"
                label="Which space are we planning?"
                value={form.space_type}
                onChange={(v) => update({ space_type: v })}
                options={SPACE_TYPES}
                placeholder="Choose one…"
                error={errors.space_type}
            />
            {form.space_type === "other" && (
                <TextField
                    id="other_label"
                    label="Which space is it?"
                    hint="The beta plans one indoor room or storage area at a time, e.g. “entryway closet” or “playroom”."
                    value={form.other_label}
                    onChange={(v) => update({ other_label: v })}
                    maxLength={60}
                    error={errors.other_label}
                />
            )}
            <ChoiceGroup
                id="priority"
                legend="What would make the biggest difference?"
                hint="Choose one main priority."
                options={PRIORITIES}
                value={form.priority}
                onChange={(v) => update({ priority: v })}
                error={errors.priority}
            />
            <TextField
                id="specifics"
                label="Anything specific you want to solve?"
                hint="One sentence is enough."
                optional
                value={form.specifics}
                onChange={(v) => update({ specifics: v })}
                maxLength={SPECIFICS_MAX}
                error={errors.specifics}
            />
        </div>
    );
}
