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

// ------------------------------------------------------------------ les scènes
const TYPES = {};

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
  for (const z of allumes) b = boite(z.g, b);
  for (const p of points) b = [Math.min(b[0], p.xy[0]), Math.min(b[1], p.xy[1]), Math.max(b[2], p.xy[0]), Math.max(b[3], p.xy[1])];
  if (b[2] <= b[0]) { const z = ZONES[sc.zone] || ZONES.france; const [x0, y1] = merc(z[0], z[1]), [x1, y0] = merc(z[2], z[3]); b = [x0, y0, x1, y1]; }
  const zw = ZONE.droite - ZONE.gauche, zh = ZONE.bas - ZONE.haut;
  const largeur = Math.max(b[2] - b[0], (b[3] - b[1]) * zw / zh, 0.0025) * (sc.marge ?? 1.35);
  const fin = { x: (b[0] + b[2]) / 2, y: (b[1] + b[3]) / 2, s: zw / largeur };
  const debut = { x: fin.x, y: fin.y, s: fin.s / (sc.depart_zoom ?? 2.4) };
  const rnd = hasard(sc.graine || 7);
  const taches = [];                       // « taches de pluie » (comme une image radar) dans les zones colorées
  if (sc.effet === "pluie" || sc.effet === "orage")
    for (const z of allumes) { const bb = boite(z.g); for (let i = 0; i < 7; i++) taches.push({ x: mix(bb[0], bb[2], rnd()), y: mix(bb[1], bb[3], rnd()), r: 0.25 + rnd() * 0.35, ph: rnd() * 6 }); }
  const gouttes = Array.from({ length: 220 }, () => ({ x: rnd() * W, y: rnd() * H, v: 0.7 + rnd() * 0.6, l: 18 + rnd() * 26 }));
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
    cx.fillStyle = "#1a2640"; cx.strokeStyle = "rgba(160,180,220,.35)"; cx.lineWidth = 1.4 / s;
    for (const z of tous) { cx.fill(z.p); cx.stroke(z.p); }
    if (deps.length) { cx.fillStyle = "#22314f"; cx.strokeStyle = "rgba(200,215,255,.22)"; cx.lineWidth = 1.2 / s; for (const z of deps) { cx.fill(z.p); cx.stroke(z.p); } }
    for (const z of allumes) {
      const p = ease.sortie(prog(t, z.a, 0.6)); if (p <= 0) continue;
      cx.save(); cx.globalAlpha = 0.25 + 0.6 * p; cx.shadowColor = z.couleur; cx.shadowBlur = 40 * p;
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

// ---- CHIFFRE : un gros nombre qui défile, son unité, une phrase
TYPES.chiffre = async (sc, couche) => {
  const bloc = el("div", "chiffre", couche); bloc.style.top = (sc.y ?? 620) + "px";
  const ligne = el("div", "", bloc); const v = el("span", "valeur", ligne); el("span", "unite", ligne, echapper(sc.unite || ""));
  const tx = el("div", "texte", bloc, marques(sc.texte || ""));
  const brut = String(sc.valeur ?? ""), num = parseFloat(brut.replace(/\s/g, "").replace(",", "."));
  const decimales = (brut.split(/[.,]/)[1] || "").length, prefixe = brut.match(/^[^\d−-]*/)[0];
  const cv = el("canvas", "", couche); cv.width = W; cv.height = H; couche.prepend(cv); const cx = cv.getContext("2d");
  return (t, duree) => {
    const p = ease.sortie(prog(t, 0.1, sc.compte ?? 1.1));
    const val = isNaN(num) ? brut : prefixe + (num * p).toLocaleString("fr-FR", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
    v.textContent = val.replace(/^-/, "−");
    bloc.style.transform = `scale(${mix(0.82, 1, ease.ressort(prog(t, 0, 0.5))) * (1 + 0.04 * prog(t, 0, duree))})`;
    bloc.style.opacity = borne(prog(t, 0, 0.25));
    apparition(tx, t, 0.6, { echelle: false });
    cx.clearRect(0, 0, W, H);                // halo qui respire derrière le chiffre
    const r = 380 + 30 * Math.sin(t * 1.7), y = (sc.y ?? 620) + 130;
    const g = cx.createRadialGradient(W / 2, y, 0, W / 2, y, r); g.addColorStop(0, couleur(sc.couleur || "rouge") + "66"); g.addColorStop(1, "#0000");
    cx.fillStyle = g; cx.fillRect(0, 0, W, H);
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
  const c = el("div", "carte-texte question", couche, `<div class="titre">${echapper(sc.titre || "Et toi ?")}</div><div class="gros" style="margin-top:22px">${marques(sc.texte)}</div><div class="petit" style="color:#333">${echapper(sc.petit || "Dis-le en commentaire 👇")}</div>`);
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

// ---- 3D (reconstitutions, objets de comparaison) : voir scenes3d.js
TYPES["3d"] = (sc, couche) => creer3d(sc, couche, THREE);

// ------------------------------------------------------------------ habillage : titre, sous-titres, étiquettes, source
let SB = null, SCENES = [], GROUPES = [];
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
  SB = sb;
  $(".lieu").textContent = sb.lieu_date || "";
  $("#titre").innerHTML = marques(sb.titre || "");
  $("#source").textContent = sb.source || "";
  $("#logo").style.backgroundImage = `url(${sb.logo || "../../docs/marque/logo-a.png"})`;
  if (sb.etiquette) $(".pastille").textContent = sb.etiquette;
  GROUPES = groupes(sb.mots || []);
  const racine = $("#scenes");
  for (const sc of sb.scenes) {
    const couche = el("div", "couche", racine);
    const dessiner = await (TYPES[sc.type] || TYPES.chiffre)(sc, couche);
    const etiqs = (sc.etiquettes || []).map((e, i) => {
      const d = el("div", "etiquette " + (e.style || ""), couche, marques(e.texte));
      d.style.left = (e.x ?? 70) + "px"; d.style.top = (e.y ?? (ZONE.haut + 10 + i * 70)) + "px"; d._a = e.a ?? 0.25 + i * 0.4;
      return d;
    });
    SCENES.push({ sc, couche, dessiner, etiqs });
  }
  await document.fonts.ready;
  return true;
};

window.rendre = t => {
  SCENES.forEach(({ sc, couche, dessiner, etiqs }, i) => {
    const fin = sc.fin, visible = t >= sc.debut - 0.001 && t < fin + FONDU;
    couche.style.display = visible ? "block" : "none";
    if (!visible) return;
    const entree = i === 0 ? 1 : ease.sortie(prog(t, sc.debut, FONDU)), sortie = i === SCENES.length - 1 ? 1 : 1 - prog(t, fin, FONDU);
    couche.style.opacity = Math.min(entree, sortie);
    couche.style.transform = `scale(${mix(1.04, 1, entree)})`;    // petite poussée à chaque nouvelle scène
    const tl = t - sc.debut;
    dessiner(tl, fin - sc.debut);
    etiqs.forEach(e => apparition(e, tl, e._a));
  });
  // titre : grand au début (l'accroche), puis plus petit pour laisser la place
  const ti = $("#titre"), p = ease.douce(prog(t, SB.titre_reduit ?? 3.0, 0.6));
  ti.style.fontSize = mix(78, 52, p) + "px";
  ti.style.opacity = borne(prog(t, 0, 0.3));
  ti.style.transform = `scale(${mix(0.9, 1, ease.ressort(prog(t, 0, 0.5)))})`;
  $("#entete").style.opacity = borne(prog(t, 0, 0.25));
  $("#mention").textContent = (SCENES.find(s => t >= s.sc.debut && t < s.sc.fin) || SCENES[0])?.sc.mention || "";
  soustitres(t);
  return true;
};
