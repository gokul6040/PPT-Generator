import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const sourcePath = "C:/Users/GokulDRaj/OneDrive - turnb.com/Desktop/ALL ELSE/Autonomous PPT Agent/.ppt-build/point-format-check-candidate.pptx";
const outputDir = "C:/Users/GokulDRaj/OneDrive - turnb.com/Desktop/ALL ELSE/Autonomous PPT Agent/.ppt-build/point-format-check-render";
await fs.mkdir(outputDir, { recursive: true });
const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
for (let index = 0; index < presentation.slides.count; index += 1) {
  const png = await presentation.export({
    slide: presentation.slides.getItem(index), format: "png", scale: 1.5,
  });
  await fs.writeFile(
    path.join(outputDir, `slide-${index + 1}.png`),
    new Uint8Array(await png.arrayBuffer()),
  );
}
console.log(outputDir);
