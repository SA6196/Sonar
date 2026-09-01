/**
 * Build-time helper that bundles the project source code into a ZIP archive
 * placed in `public/`. The frontend can then offer a one-click download at
 * `/ebsds-source.zip` without relying on a running filesystem.
 */
import fs from "node:fs";
import path from "node:path";
import JSZip from "jszip";

const ROOT = process.cwd();
const OUTPUT = path.join(ROOT, "public", "ebsds-source.zip");

// Directories / files that should never be shipped as "source".
const EXCLUDES = [
  "node_modules",
  ".git",
  "dist",
  ".workspace",
  ".lovable",
  "public/ebsds-source.zip",
  "bun.lock",
];

function shouldSkip(relativePath) {
  const parts = relativePath.split(path.sep);
  return EXCLUDES.some((ex) => {
    if (ex.includes("/")) {
      return relativePath === ex || relativePath.startsWith(ex + path.sep);
    }
    return parts.includes(ex);
  });
}

function walk(zip, dir, base) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const relative = base ? path.join(base, entry.name) : entry.name;
    if (shouldSkip(relative)) continue;

    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(zip, full, relative);
    } else {
      // Read as buffer so binary files (favicons, etc.) survive the zip.
      zip.file(relative, fs.readFileSync(full));
    }
  }
}

const zip = new JSZip();
walk(zip, ROOT, "");

const buffer = await zip.generateAsync({
  type: "nodebuffer",
  compression: "DEFLATE",
  compressionOptions: { level: 6 },
});

fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
fs.writeFileSync(OUTPUT, buffer);

console.log(
  `Wrote ${path.relative(ROOT, OUTPUT)} (${(buffer.length / 1024).toFixed(1)} KB)`,
);
