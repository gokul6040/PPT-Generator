import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const sourcePath = "C:/Users/GokulDRaj/Downloads/turnb_case_study_20260914_065016.pptx";
const outDir = path.resolve(".ppt-build/inspect-065016");
const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const snapshot = await presentation.inspect({
  kind: "deck,slide,textbox,shape,image,table,chart,notes,layout",
  maxChars: 30000,
});
await fs.writeFile(path.join(outDir, "inspect.ndjson"), snapshot.ndjson);
for (let index = 0; index < presentation.slides.length; index += 1) {
  const slide = presentation.slides.getItem(index);
  const image = await slide.export({ format: "png", scale: 2 });
  await fs.writeFile(path.join(outDir, `slide-${index + 1}.png`), new Uint8Array(await image.arrayBuffer()));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(outDir, `slide-${index + 1}.layout.json`), await layout.text());
}
const montage = await presentation.export({ format: "png", montage: true, scale: 1 });
await fs.writeFile(path.join(outDir, "montage.png"), new Uint8Array(await montage.arrayBuffer()));
