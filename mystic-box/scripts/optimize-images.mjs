// Converte as imagens originais (original-images/characters, fora do Git)
// para WebP otimizado em src/assets/characters, que é o que vai para o Git e o app.
// Uso: npm run images
import { mkdir, readdir } from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";

const SRC_DIR = "original-images/characters";
const OUT_DIR = "src/assets/characters";
const WIDTH = 600;
const QUALITY = 78;
const EXTENSIONS = new Set([".jpg", ".jpeg", ".jfif", ".png", ".webp", ".avif", ".tif", ".tiff"]);

const files = (await readdir(SRC_DIR)).filter((f) =>
  EXTENSIONS.has(path.extname(f).toLowerCase()),
);
await mkdir(OUT_DIR, { recursive: true });

for (const file of files) {
  const name = path.parse(file).name;
  const out = path.join(OUT_DIR, `${name}.webp`);
  const info = await sharp(path.join(SRC_DIR, file))
    .resize({ width: WIDTH, withoutEnlargement: true })
    .webp({ quality: QUALITY })
    .toFile(out);
  console.log(`${file} -> ${out} (${(info.size / 1024).toFixed(0)} KB)`);
}
console.log(`${files.length} imagem(ns) convertida(s).`);
