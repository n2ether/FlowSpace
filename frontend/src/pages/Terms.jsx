import React from "react";
import { Link } from "react-router-dom";
import LegalLayout, { BulletList, LegalSection, SupportLink } from "../components/LegalLayout";

export default function Terms() {
    return (
        <LegalLayout
            eyebrow="Terms"
            title="Terms of Purchase"
            testId="page-terms"
            intro="These terms explain what you get when you order a FlowSpace plan and what we ask of you in return. By creating an account or placing an order, you agree to them."
        >
            <LegalSection title="What you receive">
                <p>Each FlowSpace plan is a digital organization plan for one space, delivered by email as PDFs:</p>
                <BulletList
                    items={[
                        "Design Plan: an organized visual of your space, based on your photos.",
                        "Room Flow: a map of the zones in your space and what belongs in each.",
                        "Companion Guide: practical steps, shopping notes and setup guidance.",
                    ]}
                />
                <p>
                    What is included depends on the plan you choose. FlowSpace provides design guidance only. We do not
                    sell or install products, and we do not visit your home.
                </p>
            </LegalSection>

            <LegalSection title="AI-generated visuals are representative">
                <p>
                    The organized images in your plan are created with AI from your photos. They show the idea of the
                    finished space, not an exact picture of it. Products, colors, sizes and proportions may look different
                    in real life, and any product shown is an example rather than a specific item you must buy.
                </p>
            </LegalSection>

            <LegalSection title="Check measurements before you buy">
                <p>
                    Any dimensions in your plan are based on your photos and the measurements you gave us. Please measure
                    your space and check product sizes yourself before buying or installing anything.
                </p>
            </LegalSection>

            <LegalSection title="Your safety when installing">
                <p>You are responsible for setting up your space safely. In particular:</p>
                <BulletList
                    items={[
                        "Anchor tall or heavy furniture and shelving to the wall, following the manufacturer's instructions.",
                        "Check weight limits for shelves, rails, hooks and wall fixings, and use fixings suited to your wall.",
                        "Keep chemicals, tools and heavy items out of reach of children and pets.",
                        "Use a qualified professional for electrical, plumbing or structural work.",
                    ]}
                />
            </LegalSection>

            {/*
              OWNER REVIEW REQUIRED: placeholder refund and redo policy.
              Confirm the redo window, refund conditions and how many redos are offered
              before launch, and keep this section consistent with Stripe settings and support replies.
            */}
            <LegalSection title="Refunds and redos">
                <p data-testid="terms-refund-policy">
                    If your plan doesn't match the space you photographed, or something is clearly wrong, email us and we
                    will redo it once at no charge. If a redo doesn't fix the problem, or we can't produce a usable plan
                    from your photos, we will refund your payment. Because each plan is custom digital work, we don't
                    offer refunds simply for a change of mind once the plan has been delivered. Free plans are not
                    eligible for refunds.
                </p>
            </LegalSection>

            <LegalSection title="Payments">
                <p>
                    Payments are processed securely by Stripe. FlowSpace never sees your full card number. Prices are
                    shown before you pay, and you are charged once per plan.
                </p>
            </LegalSection>

            <LegalSection title="Your account and content">
                <p>
                    Keep your password private; you are responsible for activity on your account. You keep ownership of
                    your photos. You give us permission to use them only to create and deliver your plan, as described on
                    our <Link to="/photo-use" className="font-medium text-emerald-700 hover:text-emerald-800">Photo Use</Link> page
                    and in our <Link to="/privacy" className="font-medium text-emerald-700 hover:text-emerald-800">Privacy Policy</Link>.
                    Please only upload photos of spaces you have the right to photograph.
                </p>
            </LegalSection>

            <LegalSection title="Limits of our service">
                <p>
                    Plans are provided as general guidance. To the extent the law allows, FlowSpace is not responsible for
                    damage or injury that results from installing, buying or using products, and our total responsibility
                    for any claim is limited to the amount you paid for the plan involved.
                </p>
            </LegalSection>

            <LegalSection title="Support">
                <p>
                    Questions about an order, a redo, or a refund? Email <SupportLink /> or visit our{" "}
                    <Link to="/support" className="font-medium text-emerald-700 hover:text-emerald-800">Support</Link> page.
                </p>
            </LegalSection>
        </LegalLayout>
    );
}
