// Enregistre une vidéo « 100 % fabriquée » : ouvre page.html dans Chromium sans écran, dessine chaque image (rendre(t))
// et l'envoie à ffmpeg. 30 images par seconde, 1080 × 1920, H.264 de haute qualité. Le son est ajouté ensuite (Python).
//   node robot/rendu/rendre.mjs storyboard.json sortie.mp4 [--debut 0] [--fin 10] [--ips 30] [--processus 2]
// Plusieurs morceaux de la vidéo peuvent être dessinés en même temps (--processus, un par paire de cœurs), puis recollés.
import { createRequire } from "node:module";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const { chromium } = createRequire(import.meta.url)("playwright");   // installé à part (npm), pas dans le dépôt
const ICI = path.dirname(fileURLToPath(import.meta.url)), RACINE = path.resolve(ICI, "../..");
const args = process.argv.slice(2), opt = n => { const i = args.indexOf("--" + n); return i >= 0 ? args[i + 1] : null; };
const [fichierSb, sortie] = args.filter((a, i) => !a.startsWith("--") && !(i && args[i - 1].startsWith("--")));
const sb = JSON.parse(fs.readFileSync(fichierSb, "utf8"));
const IPS = +(opt("ips") || sb.ips || 30), DEBUT = +(opt("debut") || 0), FIN = +(opt("fin") || sb.duree);
const PROC = Math.max(1, +(opt("processus") || Math.max(1, Math.floor(os.cpus().length / 2))));

// petit serveur local : le navigateur refuse de lire les fichiers (cartes, polices) directement sur le disque
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json", ".geojson": "application/json",
  ".ttf": "font/ttf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp" };
// tuiles satellite de la NASA (GIBS, domaine public) : téléchargées une fois, gardées en cache sur le disque
const CACHE_TUILES = path.join(process.env.ROBOT_CACHE || path.join(os.homedir(), ".cache", "buzz-insolite"), "tuiles");
async function servirTuile(url, r) {
  const m = url.match(/^\/tuile\/(BlueMarble_NextGeneration|VIIRS_Black_Marble)\/(\d+)\/(\d+)\/(\d+)\.(jpeg|png)$/);
  if (!m) { r.writeHead(404); return r.end(); }
  const [, couche, z, y, x, ext] = m, fichier = path.join(CACHE_TUILES, couche, z, y, `${x}.${ext}`);
  try {
    if (!fs.existsSync(fichier)) {
      const date = couche === "VIIRS_Black_Marble" ? "2016-01-01/" : "";
      const src = `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${couche}/default/${date}GoogleMapsCompatible_Level8/${z}/${y}/${x}.${ext}`;
      let rep = null;
      for (let essai = 0; essai < 3 && !(rep && rep.ok); essai++) {
        rep = await fetch(src, { headers: { "User-Agent": "buzz-insolite-robot" } }).catch(() => null);
        if (!(rep && rep.ok)) await new Promise(ok => setTimeout(ok, 800 * (essai + 1)));
      }
      if (!rep || !rep.ok) { r.writeHead(404); return r.end(); }
      fs.mkdirSync(path.dirname(fichier), { recursive: true });
      fs.writeFileSync(fichier, Buffer.from(await rep.arrayBuffer()));
    }
    r.writeHead(200, { "Content-Type": ext === "png" ? "image/png" : "image/jpeg" }); fs.createReadStream(fichier).pipe(r);
  } catch { r.writeHead(404); r.end(); }
}
const serveur = http.createServer((q, r) => {
  if (q.url.startsWith("/tuile/")) return servirTuile(q.url, r);
  const p = path.join(RACINE, decodeURIComponent(q.url.split("?")[0]));
  if (!p.startsWith(RACINE) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { "Content-Type": TYPES[path.extname(p)] || "application/octet-stream" }); fs.createReadStream(p).pipe(r);
});
await new Promise(ok => serveur.listen(0, "127.0.0.1", ok));
const ADRESSE = `http://127.0.0.1:${serveur.address().port}/robot/rendu/page.html`;
// les fichiers du storyboard (photos…) sont servis par le même serveur s'ils sont dans le dépôt, sinon copiés à côté
for (const sc of sb.scenes) if (sc.fichier && path.isAbsolute(sc.fichier)) {
  const dest = path.join(RACINE, "robot/rendu/.medias", path.basename(sc.fichier));
  fs.mkdirSync(path.dirname(dest), { recursive: true }); fs.copyFileSync(sc.fichier, dest); sc.fichier = "./.medias/" + path.basename(sc.fichier);
}

const navigateur = await chromium.launch({
  executablePath: process.env.CHROME || undefined,
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--disable-gpu-vsync", "--font-render-hinting=none"],
});

async function morceau(n, a, b, fichier) {   // dessine les images de a à b (secondes) dans `fichier`
  const page = await navigateur.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  const erreurs = [];
  page.on("pageerror", e => erreurs.push(e.message));
  page.on("console", m => { if (m.type() === "error") erreurs.push(m.text()); });
  await page.goto(ADRESSE);
  await page.waitForFunction(() => typeof window.charger === "function", null, { timeout: 60000 }).catch(() => {});
  if (erreurs.length) throw new Error("page de rendu : " + erreurs.join(" | "));
  await page.evaluate(s => window.charger(s), sb);
  const cdp = await page.context().newCDPSession(page);
  const ff = spawn("ffmpeg", ["-v", "error", "-y", "-f", "image2pipe", "-framerate", String(IPS), "-c:v", "mjpeg", "-i", "-",
    "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", "-r", String(IPS), "-movflags", "+faststart", fichier],
    { stdio: ["pipe", "inherit", "inherit"] });
  const premiere = Math.round(a * IPS), derniere = Math.round(b * IPS);
  for (let i = premiere; i < derniere; i++) {
    await page.evaluate(t => window.rendre(t), i / IPS);
    const { data } = await cdp.send("Page.captureScreenshot", { format: "jpeg", quality: 94, optimizeForSpeed: true });
    if (!ff.stdin.write(Buffer.from(data, "base64"))) await new Promise(ok => ff.stdin.once("drain", ok));
    if (n === 0 && (i - premiere) % (IPS * 5) === 0) console.log(`rendu : ${Math.round(100 * (i - premiere) / (derniere - premiere))} %`);
  }
  if (erreurs.length) throw new Error("page de rendu : " + erreurs.join(" | "));
  ff.stdin.end();
  await new Promise((ok, ko) => ff.on("close", c => (c ? ko(new Error("ffmpeg : code " + c)) : ok())));
  await page.close();
}

const debutCalcul = Date.now();
try {
  const duree = FIN - DEBUT, n = Math.min(PROC, Math.max(1, Math.floor(duree / 4)));
  if (n === 1) await morceau(0, DEBUT, FIN, sortie);
  else {
    const dossier = fs.mkdtempSync(path.join(os.tmpdir(), "rendu-")), parts = [];
    await Promise.all(Array.from({ length: n }, (_, k) => {
      const a = DEBUT + duree * k / n, b = DEBUT + duree * (k + 1) / n, f = path.join(dossier, `part${k}.mp4`); parts.push(f);
      return morceau(k, Math.round(a * IPS) / IPS, Math.round(b * IPS) / IPS, f);
    }));
    fs.writeFileSync(path.join(dossier, "liste.txt"), parts.map(p => `file '${p}'`).join("\n"));
    const r = spawnSync("ffmpeg", ["-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", path.join(dossier, "liste.txt"), "-c", "copy", "-movflags", "+faststart", sortie]);
    if (r.status) throw new Error("recollage : " + r.stderr);
    fs.rmSync(dossier, { recursive: true, force: true });
  }
  console.log(`rendu terminé en ${Math.round((Date.now() - debutCalcul) / 1000)} s : ${sortie}`);
} finally {
  await navigateur.close(); serveur.close();
}
