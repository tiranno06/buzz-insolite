// Moteur des vidéos « 100 % fabriquées » (demande de l'auteur du 26/11, d'après curioverse.actu et vudenhaut.fr) :
// tout ce qu'on voit est dessiné ici (cartes, chiffres, étiquettes, 3D) — aucune image reprise d'un autre média.
// charger(storyboard) prépare tout ; rendre(t) dessine l'image de l'instant t (en secondes). Rien ne dépend de l'horloge :
// la même seconde donne toujours la même image (rendu image par image, 30 images par seconde, par rendre.mjs).
import * as THREE from "three";
import { creer3d } from "./scenes3d.js";

const W = 1080, H = 1920, FONDU = 0.35;
// zone où l'on dessine les cartes et les objets : sous le titre, au-dessus des sous-titres
export const ZONE = { haut: 430, bas: 1250, gauche: 40, droite: 1040 };

// ------------------------------------------------------------------ petits outils
export const borne = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const prog = (t, a, d) => borne((t - a) / Math.max(d, 1e-6));
export const ease = {
  sortie: x => 1 - Math.pow(1 - x, 3),
  douce: x => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  ressort: x => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); },
};
export const mix = (a, b, x) => a + (b - a) * x;
export function hasard(graine) {          // nombres « au hasard » mais toujours les mêmes (même vidéo = mêmes images)
  let s = graine >>> 0 || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}
export const el = (tag, cls, parent, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  if (parent) parent.appendChild(e);
  return e;
};
export const echapper = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
// « **mot** » = mot important (en jaune)
export const marques = s => echapper(s).replace(/\*\*(.+?)\*\*/g, '<span class="cle">$1</span>');
const COULEURS = { orange: "#ff8a1f", rouge: "#e8323f", jaune: "#ffd600", bleu: "#3b8cff", vert: "#2ecc71", violet: "#9b59ff", gris: "#7d8aa5" };
export const couleur = c => COULEURS[c] || c || COULEURS.orange;

// apparition « ressort » d'un élément (étiquette, repère, carte) à l'instant a
export function apparition(e, t, a, { duree = 0.45, glisse = 24, echelle = true } = {}) {
  const p = prog(t, a, duree);
  e.style.opacity = borne(p * 2.2);
  const k = echelle ? mix(0.6, 1, ease.ressort(p)) : 1;
  e.style.transform = (e.dataset.base || "") + ` translateY(${(1 - ease.sortie(p)) * glisse}px) scale(${k})`;
  e.style.visibility = p <= 0 ? "hidden" : "visible";
}

// ------------------------------------------------------------------ données géographiques (chargées une fois)
const GEO = {};
async function geo(nom) {
  if (!GEO[nom]) GEO[nom] = await (await fetch(`./geo/${nom}.geojson`)).json();
  return GEO[nom];
}
// projection de Mercator : longitude / latitude → coordonnées « monde » entre 0 et 1
export const merc = (lon, lat) => {
  const l = borne(lat, -85, 85) * Math.PI / 180;
  return [(lon + 180) / 360, (1 - Math.log(Math.tan(l) + 1 / Math.cos(l)) / Math.PI) / 2];
};
function chemin(geom) {                    // Path2D en coordonnées « monde »
  const p = new Path2D();
  const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.type === "MultiPolygon" ? geom.coordinates : [];
  for (const poly of polys) for (const anneau of poly) {
    anneau.forEach(([lon, lat], i) => { const [x, y] = merc(lon, lat); i ? p.lineTo(x, y) : p.moveTo(x, y); });
    p.closePath();
  }
  return p;
}
function boite(geom, b = [1, 1, 0, 0]) {
  const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.type === "MultiPolygon" ? geom.coordinates : [];
  for (const poly of polys) for (const [lon, lat] of poly[0]) {
    const [x, y] = merc(lon, lat);
    b = [Math.min(b[0], x), Math.min(b[1], y), Math.max(b[2], x), Math.max(b[3], y)];
  }
  return b;
}
const ZONES = {                            // vues toutes prêtes (longitude ouest, sud, est, nord)
  france: [-5.3, 41.2, 9.8, 51.3], monde: [-170, -58, 190, 78], europe: [-12, 34, 35, 66], usa: [-126, 23, -66, 50],
};

// ------------------------------------------------------------------ fond satellite NASA (domaine public)
// Blue Marble (jour) ou lumières des villes (nuit), servies par rendre.mjs (/tuile/…, gardées en cache). Toutes les tuiles
// nécessaires au zoom de la scène sont chargées AVANT la 1re image : chaque image est complète et toujours la même.
export const SAT = { jour: { couche: "BlueMarble_NextGeneration", ext: "jpeg" }, nuit: { couche: "VIIRS_Black_Marble", ext: "png" } };
const TUILES = new Map();
const zoomPour = s => Math.max(2, Math.min(8, Math.ceil(Math.log2(s / 256))));
function tuilesVisibles(z, cx0, cy0, s) {
  const n = 2 ** z, hw = W / 2 / s, hh = H / 2 / s, out = [];
  for (let x = Math.floor((cx0 - hw) * n); x <= Math.floor((cx0 + hw) * n); x++)
    for (let y = Math.max(0, Math.floor((cy0 - hh) * n)); y <= Math.min(n - 1, Math.floor((cy0 + hh) * n)); y++) out.push([z, ((x % n) + n) % n, y, x]);
  return out;
}
function tuile(fond, z, x, y) {
  const cle = `${fond}/${z}/${x}/${y}`;
  if (!TUILES.has(cle)) {
    const im = new Image(), { couche, ext } = SAT[fond];
    im._pret = new Promise(ok => { im.onload = ok; im.onerror = ok; });
    // (28/11) aperçu en direct sur le site : pas de serveur local, les tuiles viennent directement de la NASA (GIBS)
    im.src = globalThis.TUILES_DIRECTES
      ? `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${couche}/default/${couche === "VIIRS_Black_Marble" ? "2016-01-01/" : ""}GoogleMapsCompatible_Level8/${z}/${y}/${x}.${ext}`
      : `/tuile/${couche}/${z}/${y}/${x}.${ext}`;
    TUILES.set(cle, im);
  }
  return TUILES.get(cle);
}
function dessinerSatellite(cx, fond, cx0, cy0, s) {
  const z = zoomPour(s), n = 2 ** z;
  for (const [zz, x, y, xbrut] of tuilesVisibles(z, cx0, cy0, s)) {
    let im = tuile(fond, zz, x, y);
    if (im.naturalWidth) { cx.drawImage(im, xbrut / n, y / n, 1.003 / n, 1.003 / n); continue; }
    for (let k = 1; k <= 3 && zz - k >= 1; k++) {   // tuile absente : celle du zoom au-dessus, agrandie
      const m = 2 ** k, p = tuile(fond, zz - k, Math.floor(x / m), Math.floor(y / m));
      if (p.naturalWidth) { const t = 256 / m; cx.drawImage(p, (x % m) * t, (y % m) * t, t, t, xbrut / n, y / n, 1.003 / n, 1.003 / n); break; }
    }
  }
}

// ------------------------------------------------------------------ les scènes
const TYPES = {};
export const BASES = new Set(["carte", "3d", "photo", "fond"]);   // le « monde » qui reste à l'écran ; le reste s'affiche PAR-DESSUS

// ---- CARTE : pays / départements colorés, villes, flèche, pluie / neige, zoom lent
TYPES.carte = async (sc, couche) => {
  const cv = el("canvas", "", couche); cv.width = W; cv.height = H;
  const cx = cv.getContext("2d");
  const pays = await geo("pays");
  const france = sc.departements?.length || sc.zone === "france" ? await geo("departements") : null;
  const tous = pays.features.map(f => ({ p: chemin(f.geometry), iso: f.properties.iso, nom: f.properties.nom, g: f.geometry }));
  const deps = france ? france.features.map(f => ({ p: chemin(f.geometry), code: f.properties.code, nom: f.properties.nom, g: f.geometry })) : [];
  const allumes = [];                      // zones colorées : {p, couleur, a}
  for (const d of sc.departements || []) {
    const code = String(d.code ?? d).padStart(2, "0"), x = deps.find(z => z.code === code || z.nom === d.nom);
    if (x) allumes.push({ ...x, couleur: couleur(d.couleur || sc.couleur), a: d.a ?? 0.3, etiquette: d.etiquette });
  }
  for (const d of sc.pays || []) {
    const iso = d.iso ?? d, x = tous.find(z => z.iso === iso || z.nom === d.nom);
    if (x) allumes.push({ ...x, couleur: couleur(d.couleur || sc.couleur || "rouge"), a: d.a ?? 0.3, etiquette: d.etiquette });
  }
  const points = (sc.points || []).map(p => ({ ...p, xy: merc(p.lon, p.lat) }));
  // vue d'arrivée : ce qui est coloré + les villes (sinon la zone demandée)
  let b = [1, 1, 0, 0];
  // un lieu précis (ville) : on plonge sur lui, le pays coloré reste autour ; sinon on cadre ce qui est coloré
  if (!points.length || sc.cadrer_zones) for (const z of allumes) b = boite(z.g, b);
  for (const p of points) b = [Math.min(b[0], p.xy[0]), Math.min(b[1], p.xy[1]), Math.max(b[2], p.xy[0]), Math.max(b[3], p.xy[1])];
  // rien de coloré ni aucun lieu : la zone demandée (un lieu seul = un point : on zoome dessus)
  if (!allumes.length && !points.length) { const z = ZONES[sc.zone] || ZONES.france; const [x0, y1] = merc(z[0], z[1]), [x1, y0] = merc(z[2], z[3]); b = [x0, y0, x1, y1]; }
  const zw = ZONE.droite - ZONE.gauche, zh = ZONE.bas - ZONE.haut;
  const largeur = Math.max(b[2] - b[0], (b[3] - b[1]) * zw / zh, points.length && !allumes.length ? 0.0025 : points.length ? 0.012 : 0.0025) * (sc.marge ?? 1.35);
  const fin = { x: (b[0] + b[2]) / 2, y: (b[1] + b[3]) / 2, s: zw / largeur };
  const debut = { x: fin.x, y: fin.y, s: fin.s / (sc.depart_zoom ?? 2.4) };
  const rnd = hasard(sc.graine || 7);
  const taches = [];                       // « taches de pluie » (comme une image radar) dans les zones colorées
  if (sc.effet === "pluie" || sc.effet === "orage")
    for (const z of allumes) { const bb = boite(z.g); for (let i = 0; i < 7; i++) taches.push({ x: mix(bb[0], bb[2], rnd()), y: mix(bb[1], bb[3], rnd()), r: 0.25 + rnd() * 0.35, ph: rnd() * 6 }); }
  const gouttes = Array.from({ length: 220 }, () => ({ x: rnd() * W, y: rnd() * H, v: 0.7 + rnd() * 0.6, l: 18 + rnd() * 26 }));
  const fondSat = sc.satellite === false ? null : (sc.nuit ? "nuit" : "jour");
  if (fondSat) {                           // toutes les tuiles du zoom, chargées d'avance (et celles du zoom au-dessus)
    const a_charger = new Map();
    for (let i = 0; i <= 24; i++) {
      const k = ease.douce(i / 24), s = Math.exp(mix(Math.log(debut.s), Math.log(fin.s), k)) * 1.06;
      for (const [z, x, y] of tuilesVisibles(zoomPour(s), fin.x, fin.y, s)) { a_charger.set(`${z}/${x}/${y}`, [z, x, y]); a_charger.set(`${z - 1}/${x >> 1}/${y >> 1}`, [z - 1, x >> 1, y >> 1]); }
    }
    await Promise.all([...a_charger.values()].filter(([z]) => z >= 1).map(([z, x, y]) => tuile(fondSat, z, x, y)._pret));
  }
  const reperes = points.map(p => { const e = el("div", "repere", couche, echapper(p.nom)); return e; });
  const etiqs = allumes.filter(z => z.etiquette).map(z => {
    const e = el("div", "repere", couche, echapper(z.etiquette)); const bb = boite(z.g); e._xy = [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2]; e._a = z.a; return e; });
  return (t, duree) => {
    const k = ease.douce(prog(t, 0, Math.min(duree, sc.zoom_duree ?? 2.6)));
    const derive = 1 + 0.05 * prog(t, 0, duree);           // tout bouge doucement, toujours
    const s = Math.exp(mix(Math.log(debut.s), Math.log(fin.s), k)) * derive;
    const ox = (ZONE.gauche + ZONE.droite) / 2 - fin.x * s, oy = (ZONE.haut + ZONE.bas) / 2 - fin.y * s;
    const proj = ([x, y]) => [ox + x * s, oy + y * s];
    cx.setTransform(1, 0, 0, 1, 0, 0);
    const fond = cx.createLinearGradient(0, 0, 0, H); fond.addColorStop(0, "#08101f"); fond.addColorStop(1, "#0e1a30");
    cx.fillStyle = fond; cx.fillRect(0, 0, W, H);
    cx.setTransform(s, 0, 0, s, ox, oy);
    cx.lineJoin = "round";
    if (fondSat) {                           // vraie Terre vue du ciel, un peu assombrie pour que les couleurs ressortent
      cx.fillStyle = "#1a2640"; for (const z of tous) cx.fill(z.p);
      dessinerSatellite(cx, fondSat, fin.x, fin.y, s);
      cx.save(); cx.setTransform(1, 0, 0, 1, 0, 0); cx.fillStyle = fondSat === "nuit" ? "rgba(30,45,90,.10)" : "rgba(6,12,28,.34)"; cx.fillRect(0, 0, W, H); cx.restore();
      cx.strokeStyle = fondSat === "nuit" ? "rgba(140,180,255,.55)" : "rgba(255,255,255,.45)"; cx.lineWidth = 1.8 / s; for (const z of tous) cx.stroke(z.p);
      if (deps.length) { cx.strokeStyle = "rgba(255,255,255,.22)"; cx.lineWidth = 1.1 / s; for (const z of deps) cx.stroke(z.p); }
    } else {
      cx.fillStyle = "#1a2640"; cx.strokeStyle = "rgba(160,180,220,.35)"; cx.lineWidth = 1.4 / s;
      for (const z of tous) { cx.fill(z.p); cx.stroke(z.p); }
      if (deps.length) { cx.fillStyle = "#22314f"; cx.strokeStyle = "rgba(200,215,255,.22)"; cx.lineWidth = 1.2 / s; for (const z of deps) { cx.fill(z.p); cx.stroke(z.p); } }
    }
    for (const z of allumes) {
      const p = ease.sortie(prog(t, z.a, 0.6)); if (p <= 0) continue;
      // une ville précise dans un grand pays (Iowa, 27/11 : tout l'écran rouge) : le pays n'est plus qu'un voile léger
      const leger = points.length && !sc.cadrer_zones ? 0.35 : 1;
      cx.save(); cx.globalAlpha = ((fondSat ? 0.18 : 0.25) + (fondSat ? 0.32 : 0.6) * p) * leger; cx.shadowColor = z.couleur; cx.shadowBlur = 40 * p;
      cx.fillStyle = z.couleur; cx.fill(z.p); cx.restore();
      cx.strokeStyle = z.couleur; cx.lineWidth = 3.5 / s; cx.globalAlpha = p; cx.stroke(z.p); cx.globalAlpha = 1;
    }
    const visibles = borne(prog(t, 0.6, 1));
    for (const tc of taches) {               // taches qui « respirent » (comme une image radar)
      const r = tc.r * (b[2] - b[0]) / 5 * (1 + 0.15 * Math.sin(t * 1.6 + tc.ph));   // rayon en coordonnées « monde »
      const g = cx.createRadialGradient(tc.x, tc.y, 0, tc.x, tc.y, r);
      g.addColorStop(0, `rgba(255,120,40,${0.6 * visibles})`); g.addColorStop(1, "rgba(255,120,40,0)");
      cx.fillStyle = g; cx.beginPath(); cx.arc(tc.x, tc.y, r, 0, 7); cx.fill();
    }
    // flèche (perturbation, trajet…) dessinée petit à petit
    for (const f of sc.fleches || []) {
      const p = ease.douce(prog(t, f.a ?? 0.8, f.duree ?? 1.6)); if (p <= 0) continue;
      const A = merc(f.de[1], f.de[0]), B = merc(f.vers[1], f.vers[0]);
      const C = [(A[0] + B[0]) / 2 - (B[1] - A[1]) * 0.25, (A[1] + B[1]) / 2 + (B[0] - A[0]) * 0.25];
      cx.save(); cx.setTransform(1, 0, 0, 1, 0, 0);
      const [a, c, bb2] = [proj(A), proj(C), proj(B)];
      cx.strokeStyle = couleur(f.couleur || "jaune"); cx.lineWidth = 10; cx.lineCap = "round"; cx.shadowColor = "#000"; cx.shadowBlur = 12;
      cx.beginPath(); const n = 40;
      for (let i = 0; i <= n * p; i++) { const u = i / n, x = (1 - u) ** 2 * a[0] + 2 * (1 - u) * u * c[0] + u * u * bb2[0], y = (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * c[1] + u * u * bb2[1]; i ? cx.lineTo(x, y) : cx.moveTo(x, y); }
      cx.stroke(); cx.restore();
    }
    cx.setTransform(1, 0, 0, 1, 0, 0);
    if (sc.effet === "pluie" || sc.effet === "orage" || sc.effet === "neige") {   // pluie / neige par-dessus la carte
      cx.strokeStyle = "rgba(170,200,255,.35)"; cx.fillStyle = "rgba(255,255,255,.8)"; cx.lineWidth = 2.2;
      for (const g of gouttes) {
        const y = (g.y + t * (sc.effet === "neige" ? 90 : 1500) * g.v) % H, x = (g.x + (sc.effet === "neige" ? Math.sin(t + g.y) * 20 : -y * 0.12)) % W;
        if (sc.effet === "neige") { cx.beginPath(); cx.arc(x, y, 3 + g.v * 2, 0, 7); cx.fill(); }
        else { cx.beginPath(); cx.moveTo(x, y); cx.lineTo(x - g.l * 0.12, y + g.l); cx.stroke(); }
      }
      if (sc.effet === "orage") { const e = Math.max(0, Math.sin(t * 2.3) - 0.97) * 30; if (e > 0) { cx.fillStyle = `rgba(255,255,255,${e * 0.4})`; cx.fillRect(0, 0, W, H); } }
    }
    points.forEach((p, i) => { const [x, y] = proj(p.xy); const e = reperes[i]; e.style.left = x + "px"; e.style.top = y + "px"; e.dataset.base = "translate(-14px,-50%)"; apparition(e, t, p.a ?? 1 + i * 0.35); });
    etiqs.forEach(e => { const [x, y] = proj(e._xy); e.style.left = x + "px"; e.style.top = y + "px"; e.dataset.base = "translate(-14px,-50%)"; apparition(e, t, (e._a ?? 0.3) + 0.4); });
  };
};

// voile sombre et doux derrière un encadré : on lit le chiffre, et le décor continue de bouger derrière
function voile(cx, y, t) {
  if (cx._fait === y) return;                // dessiné une fois : il ne change pas (rien à recalculer à chaque image)
  cx._fait = y; cx.clearRect(0, 0, W, H);
  cx.fillStyle = "rgba(5,9,20,.30)"; cx.fillRect(0, 0, W, H);          // le décor s'assombrit un peu…
  const g = cx.createRadialGradient(W / 2, y, 60, W / 2, y, 620); g.addColorStop(0, "rgba(5,9,20,.55)"); g.addColorStop(1, "rgba(5,9,20,0)");
  cx.fillStyle = g; cx.fillRect(0, 0, W, H);                             // …et davantage derrière l'encadré
}

// ---- CHIFFRE : un gros nombre qui défile, son unité, une phrase
TYPES.chiffre = async (sc, couche) => {
  const bloc = el("div", "chiffre", couche); bloc.style.top = (sc.y ?? 620) + "px";
  const ligne = el("div", "", bloc); const v = el("span", "valeur", ligne); el("span", "unite", ligne, echapper(sc.unite || ""));
  const tx = el("div", "texte", bloc, marques(sc.texte || ""));
  if (sc.emoji) { const e = el("div", "emoji", bloc, echapper(sc.emoji)); e.style.cssText = "font-size:150px;line-height:1;margin-bottom:10px"; bloc.prepend(e); }
  const brut = String(sc.valeur ?? ""), num = parseFloat(brut.replace(/\s/g, "").replace(",", "."));
  const decimales = (brut.split(/[.,]/)[1] || "").length, prefixe = brut.match(/^[^\d−-]*/)[0];
  const cv = el("canvas", "", couche); cv.width = W; cv.height = H; couche.prepend(cv); const cx = cv.getContext("2d");
  return (t, duree) => {
    const p = ease.sortie(prog(t, 0.1, sc.compte ?? 1.1));
    const val = isNaN(num) ? brut : prefixe + (num * p).toLocaleString("fr-FR", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
    v.textContent = val.replace(/^-/, "−");
    if (isNaN(num)) v.style.fontSize = (brut.length > 9 ? 104 : brut.length > 5 ? 140 : 190) + "px";   // mot-clé géant
    bloc.style.transform = `scale(${mix(0.82, 1, ease.ressort(prog(t, 0, 0.5))) * (1 + 0.04 * prog(t, 0, duree))})`;
    bloc.style.opacity = borne(prog(t, 0, 0.25));
    apparition(tx, t, 0.6, { echelle: false });
    voile(cx, (sc.y ?? 620) + 130, t);
  };
};

// ---- FRISE : les étapes s'allument l'une après l'autre
TYPES.frise = async (sc, couche) => {
  const f = el("div", "frise", couche); f.style.top = (sc.y ?? 480) + "px";
  const etapes = (sc.etapes || []).map(e => { const d = el("div", "etape", f); el("div", "heure", d, echapper(e.heure || "")); el("div", "quoi", d, marques(e.texte || "")); return d; });
  return (t, duree) => etapes.forEach((e, i) => apparition(e, t, (sc.etapes[i].a ?? (0.3 + i * Math.max(0.6, (duree - 1) / etapes.length))), { echelle: false }));
};

// ---- CITATION et QUESTION FINALE : carte blanche / jaune
TYPES.citation = async (sc, couche) => {
  const c = el("div", "carte-texte", couche, `<div class="gros">« ${marques(sc.texte)} »</div>${sc.auteur ? `<div class="petit">— ${echapper(sc.auteur)}</div>` : ""}`);
  c.style.top = (sc.y ?? 600) + "px";
  return (t, duree) => { apparition(c, t, 0.15); c.style.rotate = `${-1.5 + 1.5 * ease.sortie(prog(t, 0, 0.6))}deg`; };
};
TYPES.question = async (sc, couche) => {
  const c = el("div", "carte-texte question", couche, `<div class="titre">${echapper(sc.titre || "Et toi ?")}</div><div class="gros" style="margin-top:22px">${marques(sc.texte)}</div><div class="petit" style="color:#333">${echapper(sc.petit || "Dis-le en commentaire 👇")}</div><div class="abonne">＋ ABONNE-TOI POUR LA SUITE</div>`);
  c.style.top = (sc.y ?? 560) + "px";
  return t => { apparition(c, t, 0.1); c.style.scale = String(1 + 0.025 * Math.sin(t * 2.2)); };
};

// ---- PHOTO libre (portrait Wikipédia…) : lent zoom, cadre arrondi, crédit
TYPES.photo = async (sc, couche) => {
  const img = new Image(); img.src = sc.fichier; await img.decode().catch(() => {});
  const cv = el("canvas", "", couche); cv.width = W; cv.height = H; const cx = cv.getContext("2d");
  const cr = el("div", "credit", couche, echapper(sc.credit || "")); cr.style.top = (ZONE.bas - 10) + "px";
  return (t, duree) => {
    cx.clearRect(0, 0, W, H);
    if (!img.naturalWidth) return;
    const bx = 90, by = ZONE.haut + 20, bw = W - 260, bh = ZONE.bas - ZONE.haut - 60;
    const k = 1.06 + 0.08 * prog(t, 0, duree), r = Math.max(bw / img.naturalWidth, bh / img.naturalHeight) * k;
    const w = img.naturalWidth * r, h = img.naturalHeight * r;
    cx.save(); cx.shadowColor = "#000a"; cx.shadowBlur = 40; cx.fillStyle = "#000"; cx.beginPath(); cx.roundRect(bx, by, bw, bh, 28); cx.fill(); cx.restore();
    cx.save(); cx.beginPath(); cx.roundRect(bx, by, bw, bh, 28); cx.clip();
    cx.drawImage(img, bx + (bw - w) / 2 - 20 * prog(t, 0, duree), by + (bh - h) / 2, w, h); cx.restore();
  };
};

// ---- PICTOGRAMME GÉANT (emoji en couleur) : il tombe, rebondit, puis flotte doucement
TYPES.icone = async (sc, couche) => {
  const b = el("div", "icone", couche); b.style.top = (sc.y ?? 520) + "px";
  const p = el("div", "picto emoji", b, echapper(sc.emoji || "📰"));
  const v = sc.valeur ? el("div", "valeur", b, marques(sc.valeur)) : null;
  const tx = sc.texte ? el("div", "texte", b, marques(sc.texte)) : null;
  const cv = el("canvas", "", couche); cv.width = W; cv.height = H; couche.prepend(cv); const cx = cv.getContext("2d");
  return (t, duree) => {
    const k = ease.ressort(prog(t, 0, 0.55));
    p.style.transform = `translateY(${(1 - k) * -260 + Math.sin(t * 2) * 10}px) rotate(${Math.sin(t * 1.3) * 4}deg) scale(${mix(0.4, 1, k)})`;
    p.style.opacity = borne(prog(t, 0, 0.2));
    if (v) apparition(v, t, 0.35, { echelle: true });
    if (tx) apparition(tx, t, 0.6, { echelle: false });
    voile(cx, (sc.y ?? 520) + 200, t);
  };
};
TYPES.mot = (sc, couche) => (sc.emoji ? TYPES.icone(sc, couche) : TYPES.chiffre(sc, couche));

// ---- DOCUMENT OFFICIEL (décret, loi, rapport, plainte) : la feuille arrive, les lignes s'écrivent, le tampon s'abat
TYPES.document = async (sc, couche) => {
  const d = el("div", "document", couche); d.style.top = (sc.y ?? 470) + "px";
  el("div", "entete-doc", d, echapper(sc.entete || "Document officiel"));
  el("div", "titre-doc", d, marques(sc.titre || "DÉCRET"));
  const lignes = Array.from({ length: 6 }, (_, i) => { const l = el("div", "ligne-doc", d); l.style.width = (i % 3 === 2 ? 62 : 100) + "%"; return l; });
  const tampon = sc.tampon ? el("div", "tampon", d, echapper(sc.tampon)) : null;
  const tx = sc.texte ? el("div", "doc-texte", couche, marques(sc.texte)) : null; if (tx) { tx.style.position = "absolute"; tx.style.left = "60px"; tx.style.right = "140px"; tx.style.top = ((sc.y ?? 470) + 670) + "px"; }
  return (t, duree) => {
    const k = ease.sortie(prog(t, 0, 0.6));
    d.style.transform = `translateY(${(1 - k) * 500}px) rotate(${mix(-14, -3, k) + Math.sin(t * 0.8) * 0.6}deg) scale(${1 + 0.03 * prog(t, 0, duree)})`;
    d.style.opacity = borne(k * 1.5);
    lignes.forEach((l, i) => { l.style.transform = `scaleX(${ease.sortie(prog(t, 0.45 + i * 0.12, 0.35))})`; });
    if (tampon) { const s = prog(t, sc.tampon_a ?? 1.4, 0.25); tampon.style.opacity = s > 0 ? 1 : 0;
      tampon.style.transform = `rotate(-12deg) scale(${s < 1 ? mix(2.6, 1, ease.sortie(s)) : 1 + Math.max(0, 0.06 - (t - (sc.tampon_a ?? 1.4) - 0.25) * 0.2)})`; }
    if (tx) apparition(tx, t, 0.8, { echelle: false });
  };
};

// ---- CALENDRIER : la page du jour se retourne
TYPES.calendrier = async (sc, couche) => {
  const c = el("div", "calendrier", couche); c.style.top = (sc.y ?? 440) + "px";
  el("div", "mois", c, echapper(sc.mois || "")); el("div", "jour", c, echapper(sc.jour || "")); el("div", "annee", c, echapper(sc.annee || ""));
  const tx = sc.texte ? el("div", "doc-texte", couche, marques(sc.texte)) : null; if (tx) { tx.style.position = "absolute"; tx.style.left = "60px"; tx.style.right = "140px"; tx.style.top = ((sc.y ?? 500) + 560) + "px"; }
  return t => {
    const k = ease.ressort(prog(t, 0, 0.7));
    c.style.transform = `perspective(1400px) rotateX(${mix(-95, 0, k)}deg) rotate(${Math.sin(t * 0.9) * 1.2}deg)`;
    c.style.opacity = borne(prog(t, 0, 0.25));
    if (tx) apparition(tx, t, 0.7, { echelle: false });
  };
};

// ---- PERSONNAGES : « 3 sur 10 », « 1 femme sur 2 »… les personnages se colorent un par un
const PERSO = c => `<svg class="perso" viewBox="0 0 60 85"><circle cx="30" cy="16" r="14" fill="${c}"/><path d="M6 85 V52 a24 24 0 0 1 48 0 V85 Z" fill="${c}"/></svg>`;
TYPES.personnes = async (sc, couche) => {
  const total = Math.max(2, Math.min(20, +sc.total || 10)), n = Math.max(0, Math.min(total, +sc.colores || 1));
  const f = el("div", "foule", couche); f.style.top = (sc.y ?? 520) + "px";
  const persos = Array.from({ length: total }, () => { const s = el("div", "", f, PERSO("#3a4766")); return s; });
  const tx = el("div", "doc-texte", couche, marques(sc.texte || `${n} sur ${total}`)); tx.style.position = "absolute"; tx.style.left = "60px"; tx.style.right = "140px";
  const parLigne = Math.max(1, Math.floor((W - 300 + 18) / 138)), lignes = Math.ceil(total / parLigne);
  tx.style.top = ((sc.y ?? 520) + lignes * 188 + 30) + "px";            // sous la dernière rangée
  return t => {
    persos.forEach((p, i) => {
      apparition(p, t, 0.05 * i, { glisse: 40 });
      const svg = p.firstChild, on = i < n && t > 0.7 + i * 0.12;
      svg.querySelectorAll("circle,path").forEach(x => x.setAttribute("fill", on ? couleur(sc.couleur || "rouge") : "#3a4766"));
    });
    apparition(tx, t, 0.9, { echelle: false });
  };
};

// ---- COMPARAISON : barres qui poussent (ex. « 9 départements → 60 départements »)
TYPES.barres = async (sc, couche) => {
  const cv = el("canvas", "", couche); cv.width = W; cv.height = H; const cx = cv.getContext("2d");
  const max = Math.max(...(sc.barres || []).map(b => +b.valeur || 0), 1);
  return t => {
    cx.clearRect(0, 0, W, H);
    (sc.barres || []).forEach((b, i) => {
      const p = ease.sortie(prog(t, 0.3 + i * 0.5, 0.9)), y = (sc.y ?? 560) + i * 210, w = 760 * (+b.valeur / max) * p;
      cx.font = "700 40px Poppins"; cx.fillStyle = "#fff"; cx.globalAlpha = borne(p * 3); cx.fillText(b.texte || "", 100, y);
      cx.fillStyle = couleur(b.couleur || (i ? "jaune" : "gris")); cx.beginPath(); cx.roundRect(100, y + 22, Math.max(w, 8), 84, 16); cx.fill();
      cx.font = "900 64px Poppins"; cx.fillStyle = "#fff"; cx.fillText(Math.round(+b.valeur * p).toLocaleString("fr-FR") + (b.unite ? " " + b.unite : ""), 120 + Math.max(w, 8), y + 88);
      cx.globalAlpha = 1;
    });
  };
};

// ---- FOND ANIMÉ (28/11) : sujet sans lieu (découverte, appli, record en ligne) — jamais un fond figé : un dégradé aux
// couleurs de la famille qui respire, une grille en perspective qui défile, des points lumineux qui flottent
const FONDS = { science_espace: ["#071233", "#1b2f7a", "#7fb2ff"], sante: ["#06231f", "#0f5a50", "#7fe0cf"],
                techno: ["#0b0b24", "#30186b", "#b48cff"], economie: ["#0a1d12", "#185c34", "#8fe3a8"],
                record: ["#24100a", "#7a2a10", "#ffb36b"], sport: ["#0a1d12", "#11592f", "#ffd600"],
                animal: ["#14210b", "#3f6a1c", "#d8f08a"], celebrite: ["#24081d", "#7a1760", "#ff9ad8"],
                decision: ["#0b1222", "#25365e", "#ffd600"], proces: ["#160f0a", "#4a3420", "#e3c38f"] };
TYPES.fond = async (sc, couche) => {
  const cv = el("canvas", "", couche); cv.width = W; cv.height = H; const cx = cv.getContext("2d");
  const [c1, c2, c3] = FONDS[sc.famille] || ["#0b1222", "#2a1240", "#ffd600"];
  const r = (k => () => (k = (k * 16807) % 2147483647) / 2147483647)(97), points = Array.from({ length: 46 }, () => [r() * W, r() * H, 2 + r() * 5, r()]);
  return t => {
    const g = cx.createLinearGradient(0, 0, W * (0.6 + 0.2 * Math.sin(t * 0.2)), H);
    g.addColorStop(0, c1); g.addColorStop(0.55 + 0.1 * Math.sin(t * 0.3), c2); g.addColorStop(1, c1);
    cx.fillStyle = g; cx.fillRect(0, 0, W, H);
    cx.strokeStyle = c3 + "4d"; cx.lineWidth = 3;                       // grille en perspective qui avance vers nous
    const hz = H * 0.62;
    for (let k = 0; k < 14; k++) { const u = ((k + (t * 0.6) % 1) / 14) ** 2, y = hz + (H - hz) * u; cx.beginPath(); cx.moveTo(0, y); cx.lineTo(W, y); cx.stroke(); }
    for (let k = -8; k <= 8; k++) { cx.beginPath(); cx.moveTo(W / 2 + k * 40, hz); cx.lineTo(W / 2 + k * 260, H); cx.stroke(); }
    for (const [x, y, rr, ph] of points) {                              // poussière lumineuse qui flotte
      const yy = (y - t * (12 + ph * 20)) % H, a = 0.45 + 0.4 * Math.sin(t * 1.5 + ph * 9);
      cx.fillStyle = c3; cx.globalAlpha = Math.max(0, a); cx.beginPath(); cx.arc(x + Math.sin(t + ph * 6) * 14, yy < 0 ? yy + H : yy, rr, 0, 7); cx.fill();
    }
    cx.globalAlpha = 1;
  };
};

// ---- ÉCHELLE (28/11, sujets sans action à reconstituer : record, science, découverte) : deux colonnes qui montent côte à
// côte, le sujet et une référence connue (« 3 fois la tour Eiffel »), avec leur pictogramme au sommet et leur taille
TYPES.echelle = async (sc, couche) => {
  const cv = el("canvas", "", couche); cv.width = W; cv.height = H; const cx = cv.getContext("2d");
  const a = +String(sc.valeur).replace(",", ".").replace(/[^\d.]/g, "") || 1, b = +String(sc.ref_valeur).replace(",", ".").replace(/[^\d.]/g, "") || 1;
  const max = Math.max(a, b), HAUT = 600, BAS = (sc.y ?? 1260);
  const tx = sc.texte ? el("div", "jauge-texte", couche, marques(sc.texte)) : null; if (tx) tx.style.top = (BAS + 30) + "px";
  const colonnes = [{ v: a, nom: sc.nom || "", emoji: sc.emoji || "📏", unite: sc.unite || "", coul: "#ffd600", x: W / 2 - 250 },
                    { v: b, nom: sc.ref_nom || "", emoji: sc.ref_emoji || "🗼", unite: sc.unite || "", coul: "#8fa3c8", x: W / 2 + 110 }];
  return t => {
    cx.clearRect(0, 0, W, H); voile(cx, BAS - HAUT / 2, t);
    colonnes.forEach((c, i) => {
      const p = ease.sortie(prog(t, 0.2 + i * 0.6, 1.1)), h = Math.max(10, HAUT * (c.v / max) * p), x = c.x, w = 200;
      cx.globalAlpha = borne(prog(t, i * 0.6, 0.3));
      cx.fillStyle = c.coul; cx.beginPath(); cx.roundRect(x, BAS - h, w, h, [18, 18, 0, 0]); cx.fill();
      cx.font = "110px 'Noto Color Emoji'"; cx.textAlign = "center"; cx.textBaseline = "alphabetic";
      cx.fillText(c.emoji, x + w / 2, BAS - h - 18 + Math.sin(t * 2 + i) * 6);
      cx.font = "900 60px Poppins"; cx.fillStyle = "#fff"; cx.shadowColor = "#000"; cx.shadowBlur = 14;
      cx.fillText(Math.round(c.v * p).toLocaleString("fr-FR") + (c.unite ? " " + c.unite : ""), x + w / 2, Math.max(ZONE.haut + 150, BAS - h - 140));
      cx.font = "900 46px Poppins"; cx.fillStyle = i ? "#cfd8ea" : "#ffd600"; cx.fillText(c.nom.toUpperCase().slice(0, 16), x + w / 2, BAS + 58);
      cx.shadowBlur = 0; cx.globalAlpha = 1;
    });
    cx.fillStyle = "rgba(255,255,255,.35)"; cx.fillRect(110, BAS, W - 300, 4);
    if (sc.rapport && t > 1.8) {                       // « × 3 » qui apparaît entre les deux colonnes
      cx.globalAlpha = borne(prog(t, 1.8, 0.4)); cx.font = "900 92px Poppins"; cx.fillStyle = "#ff5a64"; cx.textAlign = "center";
      cx.fillText(sc.rapport, W / 2 + 30, BAS - HAUT * 0.75); cx.globalAlpha = 1;
    }
    if (tx) apparition(tx, t, 1.2, { echelle: false });
  };
};

// ---- AVANT / APRÈS (décision, loi, prix, travaux) : deux cartes, un rideau glisse de AVANT vers APRÈS
TYPES.avant_apres = async (sc, couche) => {
  const Y = sc.y ?? 520;
  const bloc = el("div", "", couche); bloc.style.cssText = `position:absolute;left:70px;right:150px;top:${Y}px;height:560px`;
  const carte = (titre, texte, fond, coul) => {
    const c = el("div", "", bloc, `<div style="font:900 46px Poppins;color:${coul};letter-spacing:.06em">${titre}</div>` +
      `<div style="font:900 78px Poppins;color:#fff;line-height:1.1;margin-top:40px">${marques(texte || "")}</div>`);
    c.style.cssText = `position:absolute;inset:0;border-radius:32px;padding:60px 60px;background:${fond};box-shadow:0 20px 60px #0009;display:flex;flex-direction:column;justify-content:center`;
    return c;
  };
  const av = carte("AVANT", sc.avant, "rgba(40,52,80,.96)", "#9fb3d9"), ap = carte("APRÈS", sc.apres, "rgba(150,20,32,.96)", "#ffd600");
  const tx = sc.texte ? el("div", "jauge-texte", couche, marques(sc.texte)) : null; if (tx) tx.style.top = (Y + 600) + "px";
  return t => {
    apparition(bloc, t, 0, { echelle: true });
    const k = ease.douce(prog(t, sc.bascule ?? 1.6, 0.9));              // le rideau découvre APRÈS de gauche à droite
    ap.style.clipPath = `inset(0 ${100 - k * 100}% 0 0 round 32px)`;
    av.style.opacity = String(1 - 0.35 * k);
    bloc.style.transform += ` rotate(${Math.sin(t * 1.4) * 0.6}deg)`;
    if (tx) apparition(tx, t, 2.4, { echelle: false });
  };
};

// ---- COURBE (évolution : prix, températures, nombre de cas) : la ligne se dessine point par point, la dernière valeur grossit
TYPES.courbe = async (sc, couche) => {
  const cv = el("canvas", "", couche); cv.width = W; cv.height = H; const cx = cv.getContext("2d");
  const pts = (sc.points || []).map(p => ({ l: String(p[0] ?? p.label ?? ""), v: +String(p[1] ?? p.valeur).replace(",", ".").replace(/[^\d.-]/g, "") || 0 })).slice(0, 8);
  const X0 = 150, X1 = W - 360, Y0 = (sc.y ?? 1150), Y1 = Y0 - 520;
  const vmin = Math.min(0, ...pts.map(p => p.v)), vmax = Math.max(...pts.map(p => p.v), 1);
  const xy = (i, v) => [mix(X0, X1, pts.length > 1 ? i / (pts.length - 1) : 0.5), mix(Y0, Y1, (v - vmin) / (vmax - vmin || 1))];
  const tx = sc.texte ? el("div", "jauge-texte", couche, marques(sc.texte)) : null; if (tx) tx.style.top = (Y0 + 80) + "px";
  return t => {
    cx.clearRect(0, 0, W, H); voile(cx, (Y0 + Y1) / 2, t);
    const p = ease.douce(prog(t, 0.3, 1.8)) * (pts.length - 1);
    cx.strokeStyle = "rgba(255,255,255,.18)"; cx.lineWidth = 3; cx.beginPath(); cx.moveTo(X0, Y0); cx.lineTo(X1, Y0); cx.stroke();
    cx.strokeStyle = couleur(sc.couleur || "jaune"); cx.lineWidth = 12; cx.lineJoin = cx.lineCap = "round"; cx.shadowColor = "#000"; cx.shadowBlur = 16;
    cx.beginPath();
    for (let i = 0; i <= Math.floor(p) && i < pts.length; i++) { const [x, y] = xy(i, pts[i].v); i ? cx.lineTo(x, y) : cx.moveTo(x, y); }
    const i0 = Math.floor(p), f = p - i0;
    if (i0 + 1 < pts.length) { const [a, b] = [xy(i0, pts[i0].v), xy(i0 + 1, pts[i0 + 1].v)]; cx.lineTo(mix(a[0], b[0], f), mix(a[1], b[1], f)); }
    cx.stroke(); cx.shadowBlur = 0;
    pts.forEach((q, i) => {
      if (i > p + 0.01) return;
      const [x, y] = xy(i, q.v), dernier = i === pts.length - 1;
      cx.fillStyle = "#fff"; cx.beginPath(); cx.arc(x, y, dernier ? 16 : 10, 0, 7); cx.fill();
      cx.font = "800 40px Poppins"; cx.textAlign = "center"; cx.fillStyle = "rgba(255,255,255,.85)"; cx.fillText(q.l.slice(0, 10), x, Y0 + 56);
      cx.font = (dernier ? "900 76px" : "800 48px") + " Poppins"; cx.fillStyle = dernier ? "#ffd600" : "#fff";
      cx.fillText(q.v.toLocaleString("fr-FR") + (dernier && sc.unite ? " " + sc.unite : ""), x, y - (dernier ? 34 : 22));
    });
    if (tx) apparition(tx, t, 1.6, { echelle: false });
  };
};

// ---- JAUGE de vitesse (d'après bonnequestion.tv) : l'aiguille monte jusqu'à la vitesse, zone rouge au-delà de la limite
TYPES.jauge = async (sc, couche) => {
  const cv = el("canvas", "", couche); cv.width = W; cv.height = H; const cx = cv.getContext("2d");
  const v = +String(sc.valeur).replace(",", ".").replace(/[^\d.]/g, "") || 0, lim = +sc.limite || 0;
  const max = Math.max(50, Math.ceil(Math.max(v, lim) * 1.25 / 50) * 50), X = W / 2 - 50, Y = (sc.y ?? 860), R = 300;
  const A0 = Math.PI * 0.75, A1 = Math.PI * 2.25, ang = x => mix(A0, A1, borne(x / max));
  const tx = sc.texte ? el("div", "jauge-texte", couche, marques(sc.texte)) : null; if (tx) tx.style.top = (Y + R + 40) + "px";
  return t => {
    cx.clearRect(0, 0, W, H); voile(cx, Y - R - 80, t);
    const a = borne(prog(t, 0, 0.35)), k = ease.sortie(prog(t, 0.3, 1.6)), cur = v * k + (k >= 1 ? Math.sin(t * 13) * max * 0.004 : 0);
    cx.globalAlpha = a;
    cx.fillStyle = "rgba(11,18,34,.88)"; cx.beginPath(); cx.arc(X, Y, R + 30, 0, 7); cx.fill();
    cx.lineWidth = 34; cx.lineCap = "butt";
    cx.strokeStyle = "rgba(255,255,255,.16)"; cx.beginPath(); cx.arc(X, Y, R - 20, A0, A1); cx.stroke();
    if (lim) { cx.strokeStyle = "rgba(232,50,63,.55)"; cx.beginPath(); cx.arc(X, Y, R - 20, ang(lim), A1); cx.stroke(); }
    cx.strokeStyle = lim && cur > lim ? "#e8323f" : "#ffd600"; cx.beginPath(); cx.arc(X, Y, R - 20, A0, ang(cur)); cx.stroke();
    cx.fillStyle = "rgba(255,255,255,.7)"; cx.font = "700 30px Poppins"; cx.textAlign = "center"; cx.textBaseline = "middle";
    for (let g = 0; g <= max; g += max / 5) { const q = ang(g); cx.fillText(Math.round(g), X + Math.cos(q) * (R - 80), Y + Math.sin(q) * (R - 80)); }
    const q = ang(cur); cx.strokeStyle = "#fff"; cx.lineWidth = 10; cx.lineCap = "round";
    cx.beginPath(); cx.moveTo(X, Y); cx.lineTo(X + Math.cos(q) * (R - 50), Y + Math.sin(q) * (R - 50)); cx.stroke();
    cx.fillStyle = "#fff"; cx.beginPath(); cx.arc(X, Y, 18, 0, 7); cx.fill();
    cx.font = "900 120px Poppins"; cx.fillStyle = lim && cur > lim ? "#ff5a64" : "#fff"; cx.fillText(Math.round(cur).toLocaleString("fr-FR"), X, Y + 150);
    cx.font = "800 40px Poppins"; cx.fillStyle = "#ffd600"; cx.fillText(sc.unite || "km/h", X, Y + 228);
    if (lim) { cx.font = "800 30px Poppins"; cx.fillStyle = "#fff"; cx.fillText(`LIMITE : ${lim}`, X, Y - R - 60); }
    cx.globalAlpha = 1; cx.textAlign = "start"; cx.textBaseline = "alphabetic";
    if (tx) apparition(tx, t, 1.2, { echelle: false });
  };
};

// ---- SUITE : rien par-dessus, on revoit le décor (la 3D qui reprend après un encadré)
TYPES.suite = async () => () => {};

// ---- 3D (reconstitutions, objets de comparaison) : voir scenes3d.js
TYPES["3d"] = (sc, couche) => creer3d(sc, couche, THREE);

// ------------------------------------------------------------------ habillage : titre, sous-titres, étiquettes, source
let SB = null, SCENES = [], GROUPES = [], DUREE = 0;
const $ = s => document.querySelector(s);

function groupes(mots) {                  // sous-titres : 2 lignes de ~18 signes au plus, coupés aux pauses et à la ponctuation
  const out = []; let g = [], n = 0;
  mots.forEach((m, i) => {
    const suivant = mots[i + 1], pause = suivant ? suivant.d - m.f : 9;
    g.push(m); n += m.m.length + 1;
    if (!suivant || n > 30 || /[.!?…:;]$/.test(m.m) || (pause > 0.32 && n > 8) || (/,$/.test(m.m) && n > 14)) { out.push(g); g = []; n = 0; }
  });
  return out;
}
function soustitres(t) {
  const st = $("#soustitres");
  const i = GROUPES.findIndex((g, k) => t >= g[0].d - 0.08 && (k === GROUPES.length - 1 || t < GROUPES[k + 1][0].d - 0.08));
  if (i < 0 || t > GROUPES[i].at(-1).f + 0.9) { st.innerHTML = ""; st._i = -1; return; }
  if (st._i !== i) {
    st._i = i; st.innerHTML = "";
    const ligne = el("div", "ligne", st);
    GROUPES[i].forEach(m => { const e = el("span", "mot" + (m.cle ? " cle" : ""), ligne, echapper(m.m)); e._m = m; ligne.append(" "); });
  }
  const ligne = st.firstChild, p = prog(t, GROUPES[i][0].d - 0.08, 0.18);
  ligne.style.transform = `translateY(${(1 - ease.sortie(p)) * 18}px) scale(${mix(0.94, 1, ease.sortie(p))})`;
  for (const e of ligne.children) {
    const m = e._m, actif = t >= m.d - 0.02 && t < m.f + 0.05;
    e.classList.toggle("actif", actif);
    e.style.opacity = t < m.d - 0.02 ? 0.5 : 1;          // les mots pas encore dits restent pâles
  }
}

window.charger = async sb => {
  globalThis.ECHELLE_3D = sb.echelle_3d ?? 2 / 3;          // 3D aux 2/3 de la résolution (vitesse, 28/11)
  SB = sb;
  $(".lieu").textContent = sb.lieu_date || "";
  $("#titre").innerHTML = marques(sb.titre || "");
  $("#source").textContent = sb.source || "";
  $("#logo").style.backgroundImage = `url(${sb.logo || "../../docs/marque/logo-a.png"})`;
  if (sb.etiquette) $(".pastille").textContent = sb.etiquette;
  GROUPES = groupes(sb.mots || []);
  CHRONO = (sb.chrono || []).filter(c => c && c.heure != null).sort((a, b) => a.a - b.a);
  if (CHRONO.length) {
    $("#chrono").style.display = "flex";
    const nb = new Set(CHRONO.map(c => c.chapitre || c.heure)).size;
    for (let i = 0; i < nb; i++) el("div", "barre", $("#chrono .barres"), "<i></i>");
  }
  $("#viseur .rec span").textContent = sb.viseur || "";
  const racine = $("#scenes");
  for (const sc of sb.scenes) {
    const couche = el("div", "couche", racine);
    const dessiner = await (TYPES[sc.type] || TYPES.chiffre)(sc, couche);
    const etiqs = (sc.etiquettes || []).map((e, i) => {
      const d = el("div", "etiquette " + (e.style || ""), couche, marques(e.texte));
      d.style.left = (e.x ?? 70) + "px"; d.style.top = (e.y ?? (ZONE.haut + 10 + i * 70)) + "px"; d._a = e.a ?? 0.25 + i * 0.4; d._auto = e.y == null;
      return d;
    });
    SCENES.push({ sc, couche, dessiner, etiqs });
  }
  DUREE = sb.duree || Math.max(...sb.scenes.map(s => s.fin));
  SCENES.forEach((s, i) => {                 // un décor reste jusqu'au décor suivant (les encadrés passent par-dessus)
    const suivant = SCENES.slice(i + 1).find(x => BASES.has(x.sc.type));
    s.finDecor = suivant ? suivant.sc.debut : DUREE;
  });
  await document.fonts.ready;
  const ti = $("#titre");                    // gros titre : jamais plus de 2 lignes (il chevauchait les étiquettes)
  for (TITRE_MAX = 78; TITRE_MAX > 46; TITRE_MAX -= 2) { ti.style.fontSize = TITRE_MAX + "px"; if (ti.offsetHeight <= TITRE_MAX * 1.02 * 2 + 6) break; }
  return true;
};
let TITRE_MAX = 78, CHRONO = [];

window.rendre = t => {
  // encadré (chiffre, pictogramme, document…) affiché : le décor derrière s'assombrit un peu, sans jamais disparaître
  const voileDecor = Math.max(0, ...SCENES.filter(s => !BASES.has(s.sc.type) && !["question", "suite", "calendrier"].includes(s.sc.type) && t >= s.sc.debut && t < s.sc.fin + FONDU)
    .map(s => Math.min(prog(t, s.sc.debut, FONDU), 1 - prog(t, s.sc.fin, FONDU))));
  SCENES.forEach(({ sc, couche, dessiner, etiqs, finDecor }, i) => {
    const base = BASES.has(sc.type), fin = base ? finDecor : sc.fin, visible = t >= sc.debut - 0.001 && t < fin + FONDU;
    couche.style.display = visible ? "block" : "none";
    if (!visible) return;
    const entree = i === 0 || (base && sc.debut === 0) ? 1 : ease.sortie(prog(t, sc.debut, FONDU)),
          sortie = fin >= DUREE - 0.01 ? 1 : 1 - prog(t, fin, FONDU);
    couche.style.opacity = Math.min(entree, sortie);
    couche.style.transform = `scale(${mix(1.04, 1, entree)})`;    // petite poussée à chaque nouvelle scène
    // (pas de filtre CSS : sans carte graphique il doublait le temps de chaque image ; le voile est dessiné par l'encadré)
    const tl = t - sc.debut;
    dessiner(tl, (base ? finDecor : fin) - sc.debut);
    const basTitre = $("#entete").getBoundingClientRect().bottom;   // étiquettes juste sous le titre (qui rétrécit)
    etiqs.forEach((e, n) => {
      if (e._auto) e.style.top = Math.max(ZONE.haut - 20, basTitre + 22) + n * 66 + "px";
      apparition(e, tl, e._a);
      if (base && voileDecor > 0) e.style.opacity = String(+e.style.opacity * (1 - voileDecor));   // l'encadré prend la place
      // un décor qui reste à l'écran garde ses étiquettes seulement pendant SES phrases (avant : elles revenaient sous la
      // question et se superposaient à celles de la scène suivante)
      if (base && t >= sc.fin) e.style.opacity = String(+e.style.opacity * (1 - prog(t, sc.fin, 0.25)));
    });
  });
  // titre : grand au début (l'accroche), puis plus petit pour laisser la place
  const ti = $("#titre"), p = ease.douce(prog(t, SB.titre_reduit ?? 3.0, 0.6));
  ti.style.fontSize = mix(TITRE_MAX, Math.min(52, TITRE_MAX), p) + "px";
  ti.style.opacity = borne(prog(t, 0, 0.3));
  ti.style.transform = `scale(${mix(0.9, 1, ease.ressort(prog(t, 0, 0.5)))})`;
  $("#entete").style.opacity = borne(prog(t, 0, 0.25));
  $("#mention").textContent = (SCENES.find(s => t >= s.sc.debut && t < s.sc.fin) || SCENES[0])?.sc.mention || "";
  // horloge des faits + chapitres : l'heure change avec la phrase qui la dit, la barre avance d'étape en étape
  if (CHRONO.length) {
    let i = -1; CHRONO.forEach((c, k) => { if (t >= c.a - 0.05) i = k; });
    const c = $("#chrono"); c.style.opacity = i < 0 ? 0 : borne(prog(t, CHRONO[i].a - 0.05, 0.3));
    if (i >= 0) {
      const h = c.querySelector(".heure"); if (h.textContent !== CHRONO[i].heure) h.textContent = CHRONO[i].heure;
      const chap = [...new Set(CHRONO.map(x => x.chapitre || x.heure))], n = chap.indexOf(CHRONO[i].chapitre || CHRONO[i].heure);
      const suivant = CHRONO.find((x, k) => k > i && (x.chapitre || x.heure) !== chap[n]), fin = suivant ? suivant.a : DUREE;
      const debutChap = CHRONO.find(x => (x.chapitre || x.heure) === chap[n]).a;
      [...c.querySelectorAll(".barre i")].forEach((b, k) => b.style.width = (k < n ? 100 : k > n ? 0 : 100 * borne(prog(t, debutChap, fin - debutChap))) + "%");
      c.querySelector(".chapitre").textContent = CHRONO[i].chapitre ? `${n + 1}/${chap.length} · ${CHRONO[i].chapitre}` : "";
    }
  }
  // viseur de l'accroche : coins de caméra + « ● RECONSTITUTION » + heure qui défile
  const acc = SCENES.find(s => s.sc.accroche && t >= s.sc.debut && t < s.sc.fin);
  const vi = $("#viseur"); vi.style.display = acc ? "block" : "none";
  if (acc) {
    vi.style.opacity = borne(prog(t, 0, 0.2)) * (1 - prog(t, acc.sc.fin - 0.25, 0.25));
    const s0 = (SB.viseur_heure ?? 45177) + Math.floor(t), hh = String(Math.floor(s0 / 3600) % 24).padStart(2, "0"),
          mm = String(Math.floor(s0 / 60) % 60).padStart(2, "0"), ss = String(s0 % 60).padStart(2, "0");
    vi.querySelector(".rec span").textContent = `${SB.viseur || ""}   ${hh}:${mm}:${ss}`;
  }
  soustitres(t);
  return true;
};
