import path from "node:path";
import { pathToFileURL } from "node:url";

const workspaceDir = "C:/Users/GokulDRaj/OneDrive - turnb.com/Desktop/ALL ELSE/Autonomous PPT Agent";
const skillDir = "C:/Users/GokulDRaj/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations";
const runtimePython = "C:/Users/GokulDRaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const { finalizePresentation } = await import(pathToFileURL(
  path.join(skillDir, "container_tools", "artifact_tool_utils.mjs"),
).href);

const result = await finalizePresentation({
  workspaceDir,
  candidatePath: path.join(workspaceDir, ".ppt-build", "point-format-check-candidate.pptx"),
  finalPath: path.join(workspaceDir, "output", "turnb_case_study_point_format_check_v2_20260914.pptx"),
  pythonExecutable: runtimePython,
  integrityValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-bullet-geometry", "--validate-heading-fit"],
  explicitTotalSlideCount: 3,
  requiredNativeTableOwnerSlides: [],
  verifyArtifactToolImport: true,
  receiptPath: path.join(workspaceDir, ".codex-finalizer", "point-format-check-v2.validation.json"),
});
console.log(JSON.stringify(result, null, 2));
