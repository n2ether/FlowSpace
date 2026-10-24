import React from "react";
import { Link } from "react-router-dom";
import LegalLayout, { BulletList, LegalSection, SupportLink } from "../components/LegalLayout";

export default function Privacy() {
    return (
        <LegalLayout
            eyebrow="Privacy"
            title="Privacy Policy"
            testId="page-privacy"
            intro="FlowSpace turns photos of your closets, garages, laundry rooms, pantries, mudrooms and storage spaces into an organization plan. This page explains what information we collect to do that, how we use it, who helps us process it, and how you can ask us to delete it."
        >
            <LegalSection title="What we collect">
                <BulletList
                    items={[
                        "Account details: your name, email address, and a securely hashed password. We never store your password in readable form.",
                        "Intake answers: what you tell us about your space, such as the room type, what bothers you about it, what has to stay, measurements you choose to share, and style preferences.",
                        "Photos: the pictures you upload of your space.",
                        "Payment details: payments are handled by Stripe. FlowSpace never sees or stores your full card number. We receive a confirmation of payment, the amount, and limited details Stripe shares with merchants.",
                        "Basic technical information: such as your IP address and browser type, which our hosting and security tools use to keep the service running and to prevent abuse.",
                    ]}
                />
            </LegalSection>

            <LegalSection title="How we use it">
                <BulletList
                    items={[
                        "To create your organization plan, including your Design Plan, Room Flow and Companion Guide.",
                        "To email your plan, account messages such as password resets, and replies to your support requests.",
                        "To run your account, so you can come back to the spaces you've organized.",
                        "To review and improve the quality of plans. During the beta, a person on our team may review your plan before it is sent.",
                        "To prevent fraud and abuse and to meet legal obligations.",
                    ]}
                />
                <p>
                    We do not sell your personal information. We do not use your photos in marketing without your explicit
                    permission. See our <Link to="/photo-use" className="font-medium text-emerald-700 hover:text-emerald-800">Photo Use</Link> page
                    for details.
                </p>
            </LegalSection>

            <LegalSection title="Who helps us process it">
                <p>
                    We rely on a small number of service providers to run FlowSpace. They process information on our behalf
                    to provide their service to us:
                </p>
                <BulletList
                    items={[
                        "Stripe, for payments.",
                        "Resend, for sending email.",
                        "AI image and text processing providers, which receive your photos and intake answers to generate the visuals and written parts of your plan.",
                        "Railway, for hosting our website, application and database.",
                    ]}
                />
                <p>
                    Each provider has its own terms and privacy practices. We choose providers we believe handle data
                    responsibly, but we can't control every aspect of how a third party operates. Providers may change over
                    time; we will update this page when they do.
                </p>
            </LegalSection>

            <LegalSection title="How long we keep it">
                <p>
                    We keep your account, intake answers, photos and plans while your account is active, so you can return
                    to them. We keep payment records for as long as we need them for accounting, tax and legal reasons.
                </p>
            </LegalSection>

            <LegalSection title="Deleting your information">
                <p>
                    You can ask us to delete your photos, your plans, or your whole account at any time by emailing{" "}
                    <SupportLink />. We will confirm once it's done. Some records, such as payment records, may need to be
                    kept where the law requires it. Copies in backups are removed as those backups expire.
                </p>
            </LegalSection>

            <LegalSection title="Security">
                <p>
                    We use reasonable measures to protect your information, including encrypted connections and hashed
                    passwords. No online service can promise perfect security, so please use a password you don't use
                    anywhere else.
                </p>
            </LegalSection>

            <LegalSection title="Changes to this policy">
                <p>
                    If we make meaningful changes, we will update this page and the "Last updated" line above.
                </p>
            </LegalSection>

            <LegalSection title="Contact">
                <p>
                    Questions about privacy? Email <SupportLink />.
                </p>
            </LegalSection>
        </LegalLayout>
    );
}
