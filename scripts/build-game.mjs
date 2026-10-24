import { build } from "esbuild";
import { mkdir, writeFile, readFile, copyFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";
import { createHash } from "node:crypto";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const out = resolve(root, "static/experiences/releases/daily-adventure-v1");
await mkdir(out, { recursive: true });
const scene = await build({
  entryPoints: { scene: resolve(root, "frontend/experiences/scene.js") },
  outdir: out, bundle: true, splitting: false, format: "esm",
  minify: !process.env.KNN_BUILD_DEBUG, target: ["es2022"], legalComments: "linked", metafile: true,
  entryNames: "[name]-[hash]", sourcemap: false,
});
const sceneFile = Object.keys(scene.metafile.outputs).find((path) => path.endsWith(".js"));
const sceneHash = createHash("md5").update(createHash("md5").update(await readFile(sceneFile)).digest("hex")).digest("hex").slice(0, 10);
const runtime = await build({
  entryPoints: [resolve(root, "frontend/experiences/runtime.js")],
  outfile: resolve(out, "runtime.js"), bundle: true, format: "esm",
  minify: true, target: ["es2022"], metafile: true,
  plugins: [{
    name: "separate-scene",
    setup(builder) {
      builder.onResolve({ filter: /^\.\/scene\.js$/ }, () => ({
        path: "./" + sceneFile.replaceAll("\\", "/").split("/").at(-1) + "?v=" + sceneHash, external: true,
      }));
    },
  }],
});
const sizes = [];
for (const path of [...Object.keys(scene.metafile.outputs), ...Object.keys(runtime.metafile.outputs)]) {
  const bytes = await readFile(path);
  if (path.endsWith(".js")) await writeFile(path + ".gz", gzipSync(bytes, { level: 9 }));
  sizes.push({ file: path.replace(root, ""), bytes: bytes.length, gzip: gzipSync(bytes).length });
}
await writeFile(resolve(out, "build-sizes.json"), JSON.stringify(sizes, null, 2));
await copyFile(resolve(root, "node_modules/@babylonjs/core/license.md"), resolve(out, "BABYLON-LICENSE.txt"));
await copyFile(resolve(root, "node_modules/@babylonjs/core/NOTICE.md"), resolve(out, "BABYLON-NOTICE.txt"));
console.log(JSON.stringify(sizes));
