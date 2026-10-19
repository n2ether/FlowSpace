import React from "react";
import { Link } from "react-router-dom";
import LegalLayout, { BulletList, LegalSection, SupportLink } from "../components/LegalLayout";

const linkClass = "font-medium text-emerald-700 hover:text-emerald-800";

export default function Support() {
    return (
        <LegalLayout
            eyebrow="Support"
            title="We're here to help"
            testId="page-support"
            intro="Questions about your plan, your account, or a payment? A real person on the FlowSpace team reads every message."
        >
            <LegalSection title="Email us">
                <p className="text-lg">
                    <SupportLink />
                </p>
            </LegalSection>

            <LegalSection title="What to include">
                <BulletList
                    items={[
                        "The email address on your FlowSpace account.",
                        "Which space your message is about, for example \"garage\" or \"primary closet\".",
                        "What happened and what you expected, with a screenshot if it helps.",
                        "For payment questions, the date and amount of the charge. Never send your card number.",
                    ]}
                />
            </LegalSection>

            <LegalSection title="When you'll hear back">
                <p>
                    We aim to reply promptly on business days. Replies can take longer during busy periods, or if we need
                    to look into something with you. Sending everything listed above in your first message helps us
                    help you faster.
                </p>
            </LegalSection>

            <LegalSection title="Quick links">
                <ul className="space-y-2">
                    <li>
                        <Link to="/forgot-password" className={linkClass} data-testid="support-link-reset">
                            Reset your password
                        </Link>
                    </li>
                    <li>
                        <Link to="/privacy" className={linkClass} data-testid="support-link-privacy">
                            Privacy Policy
                        </Link>
                    </li>
                    <li>
                        <Link to="/photo-use" className={linkClass} data-testid="support-link-photo-use">
                            Photo Use
                        </Link>
                    </li>
                    <li>
                        <Link to="/terms" className={linkClass} data-testid="support-link-terms">
                            Terms of Purchase
                        </Link>
                    </li>
                </ul>
            </LegalSection>
        </LegalLayout>
    );
}
