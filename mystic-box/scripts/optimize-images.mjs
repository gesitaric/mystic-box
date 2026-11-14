// Converte as imagens originais (original-images/<pasta>, fora do Git)
// para WebP otimizado em src/assets/<pasta>, que é o que vai para o Git e o app.
// Uso: npm run images
import { mkdir, readdir } from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";

const SETS = [
  { name: "characters", width: 600, quality: 78 },
  // Relíquias aparecem pequenas (ícones e cartões do painel), então bastam 320px.
  { name: "relics", width: 320, quality: 80 },
];
const EXTENSIONS = new Set([".jpg", ".jpeg", ".jfif", ".png", ".webp", ".avif", ".tif", ".tiff"]);

let total = 0;
for (const set of SETS) {
  const srcDir = path.join("original-images", set.name);
  const outDir = path.join("src/assets", set.name);
  const files = (await readdir(srcDir).catch(() => [])).filter((f) =>
    EXTENSIONS.has(path.extname(f).toLowerCase()),
  );
  await mkdir(outDir, { recursive: true });

  for (const file of files) {
    const name = path.parse(file).name;
    const out = path.join(outDir, `${name}.webp`);
    const info = await sharp(path.join(srcDir, file))
      .resize({ width: set.width, withoutEnlargement: true })
      .webp({ quality: set.quality })
      .toFile(out);
    console.log(`${file} -> ${out} (${(info.size / 1024).toFixed(0)} KB)`);
  }
  total += files.length;
}
console.log(`${total} imagem(ns) convertida(s).`);
