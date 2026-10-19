import React from "react";
import { Link } from "react-router-dom";
import LegalLayout, { BulletList, LegalSection, SupportLink } from "../components/LegalLayout";

export default function PhotoUse() {
    return (
        <LegalLayout
            eyebrow="Your photos"
            title="Photo Use"
            testId="page-photo-use"
            intro="Your photos show the inside of your home. Here is exactly how FlowSpace uses them, and how to keep them as private as possible."
        >
            <LegalSection title="Photos are used to make your plan">
                <p>
                    We use the photos you upload only to produce your organization plan: your Design Plan, Room Flow and
                    Companion Guide. A person on our team may look at them while reviewing your plan.
                </p>
            </LegalSection>

            <LegalSection title="No marketing or public display without permission">
                <p>
                    We do not use your photos, or the organized images made from them, in advertising, social media, our
                    website gallery, or anywhere public unless you give us explicit permission first. If we ever want to
                    feature your space, we will ask, and you can say no.
                </p>
            </LegalSection>

            <LegalSection title="AI providers process your photos">
                <p>
                    To create the organized visuals in your plan, your photos are sent to AI image and text processing
                    providers that work on our behalf. They process the photos to generate images and written guidance for
                    your plan. See our <Link to="/privacy" className="font-medium text-emerald-700 hover:text-emerald-800">Privacy Policy</Link> for
                    the providers we use.
                </p>
            </LegalSection>

            <LegalSection title="Before you take a photo">
                <p>For your privacy, please try to keep the following out of frame:</p>
                <BulletList
                    items={[
                        "People, including children and anyone who hasn't agreed to be photographed.",
                        "Documents, mail, screens, and anything showing names, addresses or account numbers.",
                        "Sensitive items such as medication, valuables, safes, keys, or security systems.",
                    ]}
                />
                <p>If something like this ends up in a photo, you can ask us to delete it.</p>
            </LegalSection>

            <LegalSection title="Deleting your photos">
                <p>
                    You can ask us to delete your photos at any time by emailing <SupportLink />. Tell us the email on your
                    account and which space the photos belong to. We will confirm when they have been removed.
                </p>
            </LegalSection>
        </LegalLayout>
    );
}
