import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "Privacy | TurnB PPT Agent",
  description: "Privacy notice for the TurnB PPT Agent pilot.",
};

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy Notice"
      summary="This notice explains how the TurnB PPT Agent handles information during the initial Microsoft Teams personal-tab pilot."
      sections={[
        {
          heading: "Information the pilot processes",
          content: (
            <>
              <p>
                The application processes the text, documents, presentation
                templates, and instructions that you submit so it can generate
                case-study presentations. Generated presentations and related
                artifacts may be stored in TurnB-managed Azure storage according
                to the application&apos;s existing configuration.
              </p>
              <p>
                Standard operational information, such as request times, error
                details, and service diagnostics, may be recorded to keep the
                service reliable and secure.
              </p>
            </>
          ),
        },
        {
          heading: "Microsoft Teams data",
          content: (
            <p>
              This pilot does not request Microsoft Graph permissions, use Teams
              chat or channel messages, or add Microsoft Entra single sign-on.
              The Teams JavaScript SDK is initialized only to support hosting the
              existing web application as a personal tab.
            </p>
          ),
        },
        {
          heading: "How information is used",
          content: (
            <p>
              Submitted information is used to operate the presentation workflow,
              generate requested outputs, troubleshoot failures, and protect the
              service. Do not submit information that you are not authorized to
              provide to TurnB&apos;s configured AI and Azure services.
            </p>
          ),
        },
        {
          heading: "Retention and access",
          content: (
            <p>
              Access and retention follow TurnB&apos;s internal policies and the
              settings of the Azure services used by this application. For access,
              correction, deletion, retention, or security questions, contact your
              TurnB administrator or privacy owner.
            </p>
          ),
        },
        {
          heading: "Changes to this notice",
          content: (
            <p>
              This notice may be updated as the pilot changes. Material production
              additions such as Microsoft Entra SSO, Microsoft Graph access, or a
              new database will require an updated privacy and security review.
            </p>
          ),
        },
      ]}
    />
  );
}
