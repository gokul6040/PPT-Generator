import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = process.cwd();
const skillDir = "C:/Users/GokulDRaj/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations";
const runtimePython = "C:/Users/GokulDRaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const sourcePath = "C:/Users/GokulDRaj/Downloads/turnb_case_study_20260914_130317.pptx";
const stagingDir = path.join(workspaceDir, ".codex-finalizer");
const outputDir = path.join(workspaceDir, "output");
const candidatePath = path.join(stagingDir, "adaptive-content-sizing-candidate.pptx");
const finalPath = path.join(outputDir, "turnb_case_study_adaptive_content_sizing_v3.pptx");

await fs.mkdir(stagingDir, { recursive: true });
await fs.mkdir(outputDir, { recursive: true });

const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const before = await presentation.inspect({
  kind: "slide,textbox,shape",
  include: "id,slide,name,text,bbox",
  maxChars: 12000,
});
console.log(before.ndjson);

const bodyShapes = [];
for (const line of before.ndjson.split("\n")) {
  if (!line.trim()) continue;
  const item = JSON.parse(line);
  if ((item.kind === "textbox" || item.kind === "shape") && String(item.text ?? "").includes("•")) {
    bodyShapes.push(item);
  }
}
if (bodyShapes.length !== 3) {
  throw new Error(`Expected one bullet body text box per slide; found ${bodyShapes.length}.`);
}

for (const item of bodyShapes) {
  // Keep dense slides slightly smaller, then distribute short lists down the
  // canvas so the sparse layout feels intentional rather than unfinished.
  const fontSizePt = String(item.text).length < 690 ? 18 : 16;
  const extraGapPt = fontSizePt === 18 ? 24 : 18;
  const lines = String(item.text).split("\n").filter(Boolean);
  const body = presentation.resolve(item.id);
  body.text = lines.map((line, index) => {
    const isHeadline = index === 0;
    const isLast = index === lines.length - 1;
    const spaceAfter = isLast ? 0 : ((isHeadline ? 10 : 6) + extraGapPt) * 100;
    if (isHeadline) {
      return { runs: [{ run: line, textStyle: { bold: true } }], spaceAfter };
    }
    return {
      bulletCharacter: "•",
      marginLeft: 22 * 12700,
      indent: -10 * 12700,
      runs: [line.replace(/^•\s*/, "")],
      spaceAfter,
    };
  });
  body.text.style = {
    typeface: "Segoe UI",
    fontSize: fontSizePt * (4 / 3),
    color: "#000000",
    autoFit: "none",
  };
}

const after = await presentation.inspect({
  kind: "slide,textbox,shape",
  include: "id,slide,name,text,bbox",
  maxChars: 12000,
});
console.log(after.ndjson);

for (let index = 0; index < presentation.slides.count; index += 1) {
  const slide = presentation.slides.getItem(index);
  const preview = await presentation.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(
    path.join(workspaceDir, ".codex-build", `adaptive-slide-${index + 1}.png`),
    new Uint8Array(await preview.arrayBuffer()),
  );
}

await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
const { finalizePresentation } = await import(pathToFileURL(
  path.join(skillDir, "container_tools", "artifact_tool_utils.mjs"),
).href);
await finalizePresentation({
  explicitTotalSlideCount: 3,
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: runtimePython,
  integrityValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-bullet-geometry", "--validate-heading-fit"],
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "adaptive-content-sizing-v3-validation.json"),
});
console.log(finalPath);
