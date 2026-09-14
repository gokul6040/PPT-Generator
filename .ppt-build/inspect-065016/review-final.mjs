import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const deckPath = path.resolve("output/turnb_case_study_fixed_20260914.pptx");
const outDir = path.resolve(".ppt-build/inspect-065016/final-review");
await fs.mkdir(outDir, { recursive: true });
const presentation = await PresentationFile.importPptx(await FileBlob.load(deckPath));
const snapshot = await presentation.inspect({ kind: "deck,slide,textbox,shape", maxChars: 16000 });
await fs.writeFile(path.join(outDir, "inspect.ndjson"), snapshot.ndjson);
for (let index = 0; index < presentation.slides.length; index += 1) {
  const image = await presentation.slides.getItem(index).export({ format: "png", scale: 2 });
  await fs.writeFile(path.join(outDir, `slide-${index + 1}.png`), new Uint8Array(await image.arrayBuffer()));
}
const montage = await presentation.export({ format: "png", montage: true, scale: 1 });
await fs.writeFile(path.join(outDir, "montage.png"), new Uint8Array(await montage.arrayBuffer()));
