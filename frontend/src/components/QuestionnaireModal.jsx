import React from "react";
import { Dialog, DialogContent } from "./ui/dialog";
import { useLang } from "../context/LanguageContext";
import Questionnaire from "./Questionnaire";

const QuestionnaireModal = ({ open, onOpenChange, presetPackage = "" }) => {
    const { t } = useLang();
    const q = t.questionnaire;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                className="max-h-[92vh] w-[95vw] max-w-3xl overflow-y-auto rounded-3xl border border-slate-200 bg-white p-0 shadow-2xl"
                data-testid="questionnaire-modal"
            >
                <div className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 px-6 py-5 backdrop-blur md:px-10">
                    <h2 className="font-heading text-2xl font-light tracking-tight text-slate-900 md:text-3xl">
                        {q.title}
                    </h2>
                    <p className="mt-1 text-sm text-slate-500">{q.sub}</p>
                </div>
                <div className="px-6 py-6 md:px-10 md:py-8">
                    <Questionnaire
                        presetPackage={presetPackage}
                        embedded
                        onDone={() => {
                            // Auto-close 4s after completion
                            setTimeout(() => onOpenChange(false), 4000);
                        }}
                    />
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default QuestionnaireModal;
