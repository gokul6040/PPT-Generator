import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const sourcePath = "C:/Users/GokulDRaj/Downloads/turnb_case_study_20260914_065016.pptx";
const workspaceDir = path.resolve(".");
const skillDir = "C:/Users/GokulDRaj/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations";
const stagingDir = path.join(workspaceDir, ".codex-finalizer");
const finalPath = path.join(workspaceDir, "output", "turnb_case_study_fixed_20260914.pptx");
const runtimePython = "C:/Users/GokulDRaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";

const { finalizePresentation } = await import(pathToFileURL(
  path.join(skillDir, "container_tools", "artifact_tool_utils.mjs"),
).href);

const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const before = await presentation.inspect({
  kind: "slide,textbox,shape",
  maxChars: 12000,
});
await fs.writeFile(path.join(workspaceDir, ".ppt-build", "inspect-065016", "before-fix.ndjson"), before.ndjson);

const approachTitle = presentation.resolve("sh/ozy1ofad");
approachTitle.text.set([[ 
  { run: "T", textStyle: { bold: true, color: "#028482", typeface: "Segoe UI", fontSize: "14pt" } },
  { run: "urnB Approach", textStyle: { bold: true, color: "#000000", typeface: "Segoe UI", fontSize: "14pt" } },
]]);

const approachSlide = presentation.resolve("sl/hwbqtkby");
const approachBody = approachSlide.shapes.add({
  geometry: "textbox",
  name: "Approach body",
  position: { left: 67.2, top: 177.6, width: 1152, height: 470.4 },
  fill: "none",
  line: { fill: "none", width: 0 },
});
approachBody.text.set([
  [{ run: "A trusted lease-data foundation and AI-enabled decision tools replaced manual reporting", textStyle: { bold: true } }],
  ["• Built a validated data pipeline that removes duplicate and erroneous CRM records, creating a trusted lease-data source for enterprise reporting."],
  ["• Delivered Power BI dashboards for revenue collection, leasing pipeline status, and occupancy trends based on finalized daily data."],
  ["• Deployed a Microsoft Teams and M365 Copilot agent so non-technical users can query lease data in natural language."],
  ["• Developed 12-month revenue forecasts and tenant churn risk scores to support earlier retention decisions."],
]);
approachBody.text.style = {
  typeface: "Segoe UI",
  fontSizePt: 12,
  color: "#000000",
  autoFit: "shrinkText",
  verticalAlignment: "top",
  insets: { top: 0, right: 0, bottom: 0, left: 0 },
};
approachBody.text.get("A trusted lease-data foundation and AI-enabled decision tools replaced manual reporting").bold = true;

const impactTitle = presentation.resolve("sh/d0jax03i");
impactTitle.text.set([[ 
  { run: "B", textStyle: { bold: true, color: "#028482", typeface: "Segoe UI", fontSize: "14pt" } },
  { run: "usiness Impact and Implications", textStyle: { bold: true, color: "#000000", typeface: "Segoe UI", fontSize: "14pt" } },
]]);

const impactBody = presentation.resolve("sh/298ryl4v");
impactBody.text.set([
  [{ run: "Verified data enables earlier action on renewals, vacancies, and tenant risk", textStyle: { bold: true } }],
  ["• Leasing managers can query verified portfolio metrics in Microsoft Teams instead of compiling ad-hoc reports from raw CRM extracts."],
  ["• A unified Lease Data Estate aligns the AI agent and Power BI dashboards around the same validated figures."],
  ["• Leadership can link maintenance history to renewal probability, helping teams address operational issues before they affect retention or revenue."],
  ["• Revenue forecasts and churn risk scores support earlier action to protect cash flow and occupancy."],
]);
impactBody.text.style = {
  typeface: "Segoe UI",
  fontSizePt: 12,
  color: "#000000",
  autoFit: "shrinkText",
  verticalAlignment: "top",
  insets: { top: 0, right: 0, bottom: 0, left: 0 },
};
impactBody.text.get("Verified data enables earlier action on renewals, vacancies, and tenant risk").bold = true;

for (let index = 0; index < presentation.slides.length; index += 1) {
  const slide = presentation.slides.getItem(index);
  const rendered = await slide.export({ format: "png", scale: 2 });
  await fs.writeFile(
    path.join(workspaceDir, ".ppt-build", "inspect-065016", `revised-slide-${index + 1}.png`),
    new Uint8Array(await rendered.arrayBuffer()),
  );
}
const snapshot = await presentation.inspect({
  kind: "slide,textbox,shape",
  maxChars: 14000,
});
await fs.writeFile(path.join(workspaceDir, ".ppt-build", "inspect-065016", "after-fix.ndjson"), snapshot.ndjson);

await fs.mkdir(stagingDir, { recursive: true });
await fs.mkdir(path.dirname(finalPath), { recursive: true });
const candidatePath = path.join(stagingDir, "turnb_case_study_fixed_candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

await finalizePresentation({
  explicitTotalSlideCount: 3,
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: runtimePython,
  integrityValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-bullet-geometry", "--validate-heading-fit"],
  fontPolicy: {
    basis: "reference",
    families: ["Segoe UI"],
    referencePath: sourcePath,
    referenceSha256: "6440343df16151eb971c71b4925e2e86b4f412af99ffbf29a93aa874666e789e",
  },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "turnb_case_study_fixed_20260914.validation.json"),
});
