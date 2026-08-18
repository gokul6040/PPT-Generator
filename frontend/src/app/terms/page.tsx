import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "Terms | TurnB PPT Agent",
  description: "Terms of use for the TurnB PPT Agent pilot.",
};

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms of Use"
      summary="These pilot terms govern use of the TurnB PPT Agent through its web application and Microsoft Teams personal tab."
      sections={[
        {
          heading: "Pilot use",
          content: (
            <p>
              The service is provided for a limited TurnB pilot and may change,
              experience interruptions, or be withdrawn. Access is limited to
              users authorized by TurnB and is subject to applicable company
              policies.
            </p>
          ),
        },
        {
          heading: "Your responsibilities",
          content: (
            <p>
              You must have permission to submit all content and templates you
              provide. Do not upload secrets, regulated information, unlawful
              material, or third-party content unless TurnB has approved that use.
              You are responsible for reviewing generated presentations before
              relying on or distributing them.
            </p>
          ),
        },
        {
          heading: "Generated output",
          content: (
            <p>
              AI-generated content can be incomplete or inaccurate. The service
              does not replace professional, legal, financial, security, or brand
              review. Users remain responsible for factual accuracy, permissions,
              confidentiality, and final presentation quality.
            </p>
          ),
        },
        {
          heading: "Acceptable use",
          content: (
            <p>
              Do not attempt to disrupt the service, bypass access controls,
              introduce malicious content, reverse engineer protected components,
              or use the application in a way that violates law or TurnB policy.
            </p>
          ),
        },
        {
          heading: "Service and support",
          content: (
            <p>
              The pilot is provided without a production availability commitment.
              Report access, output, privacy, or security issues to your TurnB
              administrator. Production rollout will require approved operational,
              support, privacy, and security terms.
            </p>
          ),
        },
      ]}
    />
  );
}
