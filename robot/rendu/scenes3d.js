// Scènes 3D des vidéos « 100 % fabriquées » : reconstitutions simples (style maquette, comme curioverse.actu) et objets de
// comparaison (cube d'eau…). Tout est construit ici avec des formes simples : aucune image ni modèle 3D d'ailleurs.
// Une scène décrit : un décor, des objets (id, type, position), des actions dans le temps, une caméra, des repères.
// Les actions sont rejouées depuis le début à chaque image : la même seconde donne toujours la même image.
import { ZONE, borne, prog, ease, mix, hasard, el, echapper, couleur, apparition } from "./moteur.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

// ------------------------------------------------------------------ vrais modèles 3D (Kenney, CC0 : usage commercial permis)
// type d'objet → [dossier, variantes], taille réelle en mètres, mesurée sur la longueur ("l") ou la hauteur ("h").
// Un type absent d'ici (citerne, bus, avion, hélico, grand cargo, foule, bâtiment officiel…) garde sa forme dessinée.
const MODELES = {
  voiture: ["car-kit", ["sedan", "suv", "hatchback-sports", "taxi", "sedan-sports"], 4.5, "l"],
  taxi: ["car-kit", ["taxi"], 4.5, "l"],
  camionnette: ["car-kit", ["van", "delivery"], 5.2, "l"],
  camion: ["car-kit", ["truck", "truck-flat", "garbage-truck"], 9, "l"],
  police: ["car-kit", ["police"], 4.8, "l"],
  ambulance: ["car-kit", ["ambulance"], 6, "l"],
  pompiers: ["car-kit", ["firetruck"], 8.5, "l"],
  tracteur: ["car-kit", ["tractor"], 4, "l"],
  debris: ["car-kit", ["debris-tire", "debris-door", "debris-bumper", "debris-plate-a"], 1.1, "l"],
  plot: ["car-kit", ["cone"], 0.8, "h"],
  personne: ["mini-characters", ["character-male-a", "character-female-a", "character-male-b", "character-female-b", "character-male-c", "character-female-c", "character-worker"], 1.75, "h"],
  soldat: ["mini-characters", ["character-soldier"], 1.8, "h"],
  bateau: ["watercraft-kit", ["boat-tug-a"], 18, "l"],
  vedette: ["watercraft-kit", ["boat-speed-a"], 9, "l"],
  barque: ["watercraft-kit", ["boat-fishing-small"], 6, "l"],
  voilier: ["watercraft-kit", ["boat-sail-a"], 10, "l"],
  conteneur: ["watercraft-kit", ["cargo-container-a", "cargo-container-b", "cargo-container-c"], 12, "l"],
  train: ["train-kit", ["train-electric-city-a"], 22, "l"],
  tgv: ["train-kit", ["train-electric-bullet-a"], 25, "l"],
  wagon_citerne: ["train-kit", ["train-carriage-tank"], 16, "l"],
  arbre: ["nature-kit", ["tree_default", "tree_oak", "tree_detailed", "tree_pineRoundA"], 7, "h"],
  palmier: ["nature-kit", ["tree_palmTall"], 9, "h"],
  rocher: ["nature-kit", ["rock_largeA"], 3, "h"],
  maison: ["city-kit-suburban", ["building-type-a", "building-type-b", "building-type-c", "building-type-d", "building-type-e", "building-type-f"], 9, "h"],
  immeuble: ["city-kit-commercial", ["building-a", "building-b", "building-c", "building-d", "building-e", "building-f", "building-g", "building-h"], 20, "h"],
  gratte_ciel: ["city-kit-commercial", ["building-skyscraper-a", "building-skyscraper-b", "building-skyscraper-c"], 70, "h"],
  // Quaternius (CC0, OpenGameArt, convertis en .glb le 27/11) : bus, car scolaire, feux, panneaux, hôpital, banque, magasin
  bus: ["quaternius", ["transport-Bus", "transport-SchoolBus"], 12, "l"],
  feu_tricolore: ["quaternius", ["transport-TrafficLight"], 3.4, "h"],
  panneau: ["quaternius", ["transport-TrafficSign1", "transport-TrafficSign2", "transport-TrafficSign3"], 2.5, "h"],
  hopital: ["quaternius", ["bati-Hospital"], 22, "h"],
  banque: ["quaternius", ["bati-Bank"], 12, "h"],
  magasin: ["quaternius", ["bati-Shop"], 7, "h"],
  residence: ["quaternius", ["bati-Flat", "bati-Flat2"], 16, "h"],
};
const GLTF = new Map(), chargeur = new GLTFLoader();
async function prechargerModeles(types) {
  const a_charger = [];
  for (const t of new Set(types)) for (const v of (MODELES[t] || [null, []])[1]) {
    const cle = `${MODELES[t][0]}/${v}`;
    if (!GLTF.has(cle)) { GLTF.set(cle, null); a_charger.push(chargeur.loadAsync(`./modeles/${cle}.glb`).then(g => GLTF.set(cle, g.scene)).catch(() => GLTF.delete(cle))); }
  }
  await Promise.all(a_charger);
}
const modelePret = t => MODELES[t] && MODELES[t][1].some(v => GLTF.get(`${MODELES[t][0]}/${v}`));
function modele(T, type, o = {}, graine = 1) {
  const [kit, variantes, taille, mesure] = MODELES[type];
  const dispo = variantes.filter(v => GLTF.get(`${kit}/${v}`)), nom = o.variante && dispo.includes(o.variante) ? o.variante : dispo[Math.abs(graine) % dispo.length];
  const brut = GLTF.get(`${kit}/${nom}`).clone(true), g = new T.Group(), pivot = new T.Group();
  let b = new T.Box3().setFromObject(brut), d = b.getSize(new T.Vector3());
  if (mesure === "l" && d.z > d.x) brut.rotation.y = Math.PI / 2;        // l'avant du véhicule vers +x (le sens de la marche)
  b = new T.Box3().setFromObject(brut); d = b.getSize(new T.Vector3());
  const voulu = o.longueur && mesure === "l" ? o.longueur : o.hauteur && mesure === "h" ? o.hauteur : taille;
  const k = voulu / (mesure === "l" ? Math.max(d.x, d.z) : d.y);
  pivot.add(brut); pivot.scale.setScalar(k);
  const c = b.getCenter(new T.Vector3());
  brut.position.set(-c.x, -b.min.y, -c.z);
  brut.traverse(m => { if (m.isMesh) { m.castShadow = false; if (o.couleur && m.material && /body|carrosserie/i.test(m.material.name || "")) { m.material = m.material.clone(); m.material.color.set(couleur(o.couleur)); } } });
  g.add(pivot);
  g.userData.taille = [d.x * k, d.y * k, d.z * k];
  return g;
}
export const TYPES_MODELES = Object.keys(MODELES);

const W = 1080, H = 1920;
let RENDU = null;                         // un seul moteur WebGL pour toutes les scènes (le navigateur en limite le nombre)
function moteur(THREE) {
  if (!RENDU) {
    RENDU = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, alpha: true });
    RENDU.setPixelRatio(1); RENDU.setSize(W, H, false);
    RENDU.outputColorSpace = THREE.SRGBColorSpace;
    RENDU.toneMapping = THREE.ACESFilmicToneMapping; RENDU.toneMappingExposure = 1.05;
    RENDU.shadowMap.enabled = true; RENDU.shadowMap.type = THREE.PCFSoftShadowMap;   // vraies ombres portées (27/11)
  }
  return RENDU;
}

// ------------------------------------------------------------------ textures dessinées (route, fenêtres, eau)
function texture(THREE, w, h, dessin, repete = [1, 1]) {
  const c = document.createElement("canvas"); c.width = w; c.height = h; dessin(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(...repete); t.anisotropy = 4; return t;
}
const texRoute = (THREE, voies) => texture(THREE, 512, 256, (c, w, h) => {   // route dans le sens de la longueur (axe x)
  c.fillStyle = "#3a3f47"; c.fillRect(0, 0, w, h);
  const r = hasard(3); for (let i = 0; i < 2500; i++) { c.fillStyle = `rgba(255,255,255,${r() * 0.04})`; c.fillRect(r() * w, r() * h, 2, 2); }
  c.fillStyle = "#e9e9e9"; c.fillRect(0, 4, w, 5); c.fillRect(0, h - 9, w, 5);
  for (let v = 1; v < voies; v++) for (let x = 0; x < w; x += 128) c.fillRect(x, v * h / voies - 2, 64, 4);
}, [60, 1]);
const texFenetres = (THREE, graine, nuit) => texture(THREE, 128, 256, (c, w, h) => {
  const r = hasard(graine);
  c.fillStyle = nuit ? "#2c3346" : "#b9a38b"; c.fillRect(0, 0, w, h);
  for (let y = 10; y < h - 10; y += 22) for (let x = 8; x < w - 8; x += 20) {
    c.fillStyle = nuit ? (r() < 0.55 ? `rgba(255,${200 + r() * 40},120,${0.6 + r() * 0.4})` : "#1b2030") : (r() < 0.5 ? "#4d5b6e" : "#647792");
    c.fillRect(x, y, 12, 14);
  }
});

// ------------------------------------------------------------------ objets (formes simples, échelle en mètres)
function boite(THREE, l, h, p, mat) { const m = new THREE.Mesh(new THREE.BoxGeometry(l, h, p), mat); return m; }
function roues(THREE, g, l, p, r = 0.42, n = 2) {
  const mat = new THREE.MeshLambertMaterial({ color: 0x15171c }), geo = new THREE.CylinderGeometry(r, r, 0.32, 16);
  const liste = [];
  for (let i = 0; i < n; i++) for (const cote of [-1, 1]) {
    const x = n === 2 ? (i ? -l / 2 + 0.85 : l / 2 - 0.85) : mix(-l / 2 + 0.9, l / 2 - 0.9, i / (n - 1));
    const w = new THREE.Mesh(geo, mat); w.rotation.x = Math.PI / 2; w.position.set(x, r, cote * p / 2); g.add(w); liste.push(w);
  }
  g.userData.roues = liste; g.userData.rayon = r;
}
const lambert = (THREE, c, e) => new THREE.MeshLambertMaterial({ color: new THREE.Color(couleur(c)), emissive: e ? new THREE.Color(e) : 0x000000 });
const FABRIQUES = {
  voiture(T, o) {
    const g = new T.Group(), m = lambert(T, o.couleur || "#d9dde4");
    const c = boite(T, 4.3, 0.75, 1.8, m); c.position.y = 0.75; g.add(c);
    const h = boite(T, 2.3, 0.7, 1.62, m); h.position.set(-0.25, 1.45, 0); g.add(h);
    const v = boite(T, 2.32, 0.5, 1.64, lambert(T, "#26303f")); v.position.set(-0.25, 1.45, 0); g.add(v);
    roues(T, g, 4.3, 1.8, 0.38); g.userData.taille = [4.3, 1.8, 1.8]; return g;
  },
  camion(T, o) {
    const g = new T.Group();
    const cab = boite(T, 2.4, 2.6, 2.5, lambert(T, o.couleur || "#f2f2f2")); cab.position.set(4.6, 1.9, 0); g.add(cab);
    const vit = boite(T, 0.1, 1.0, 2.2, lambert(T, "#26303f")); vit.position.set(5.82, 2.5, 0); g.add(vit);
    const rem = boite(T, 8.5, 3.0, 2.55, lambert(T, o.couleur2 || "#c9ced6")); rem.position.set(-1.2, 2.2, 0); g.add(rem);
    roues(T, g, 11.5, 2.4, 0.55, 4); g.userData.taille = [11.5, 3.6, 2.5]; return g;
  },
  citerne(T, o) {
    const g = new T.Group();
    // cabine colorée, citerne argentée avec bandes rouges et losange « matière dangereuse », châssis sombre
    const cab = boite(T, 2.4, 2.6, 2.5, lambert(T, o.couleur || "#e8742a")); cab.position.set(4.6, 1.9, 0); g.add(cab);
    const vit = boite(T, 0.1, 1.0, 2.2, lambert(T, "#26303f")); vit.position.set(5.82, 2.5, 0); g.add(vit);
    const chassis = boite(T, 10.8, 0.4, 2.2, lambert(T, "#2b2e34")); chassis.position.set(-0.2, 0.75, 0); g.add(chassis);
    const cu = new T.Mesh(new T.CylinderGeometry(1.25, 1.25, 8.6, 28), new T.MeshPhongMaterial({ color: 0xd9dee5, shininess: 60, specular: 0x666666 }));
    cu.rotation.z = Math.PI / 2; cu.position.set(-1.2, 2.25, 0); g.add(cu);
    for (const x of [-4.6, 2.2]) { const f = new T.Mesh(new T.CylinderGeometry(1.27, 1.27, 0.12, 28), lambert(T, "#b8bec7")); f.rotation.z = Math.PI / 2; f.position.set(x, 2.25, 0); g.add(f); }
    for (const z of [-1.26, 1.26]) {
      const b = boite(T, 8.2, 0.28, 0.04, lambert(T, "#c0392b")); b.position.set(-1.2, 1.75, z); g.add(b);
      const l = boite(T, 0.75, 0.75, 0.04, lambert(T, "#f39c12")); l.rotation.z = Math.PI / 4; l.position.set(1.0, 2.35, z * 1.01); g.add(l);
    }
    roues(T, g, 11.5, 2.4, 0.55, 4); g.userData.taille = [11.5, 3.6, 2.5]; return g;
  },
  bus(T, o) {
    const g = new T.Group(), m = lambert(T, o.couleur || "#f1f1f1");
    const c = boite(T, o.longueur || 7, 2.6, 2.3, m); c.position.y = 1.7; g.add(c);
    const v = boite(T, (o.longueur || 7) - 0.6, 0.8, 2.32, lambert(T, "#26303f")); v.position.y = 2.25; g.add(v);
    roues(T, g, o.longueur || 7, 2.3, 0.5); g.userData.taille = [o.longueur || 7, 3, 2.3]; return g;
  },
  moto(T, o) {
    const g = new T.Group(); const c = boite(T, 1.9, 0.5, 0.4, lambert(T, o.couleur || "#d63031")); c.position.y = 0.8; g.add(c);
    const p = new T.Mesh(new T.CapsuleGeometry(0.25, 0.6, 4, 8), lambert(T, "#333")); p.position.set(-0.1, 1.45, 0); g.add(p);
    roues(T, g, 1.9, 0.12, 0.34); g.userData.taille = [2, 1.6, 0.5]; return g;
  },
  avion(T, o) {
    const g = new T.Group(), m = lambert(T, o.couleur || "#f4f6f8"), l = o.longueur || 16;
    const f = new T.Mesh(new T.CapsuleGeometry(1.1, l - 2.2, 6, 16), m); f.rotation.z = Math.PI / 2; g.add(f);
    const a = boite(T, 2.6, 0.18, l * 0.95, m); a.position.set(0.3, -0.2, 0); g.add(a);
    const d = boite(T, 1.6, 2.4, 0.15, m); d.position.set(-l / 2 + 1, 1.4, 0); g.add(d);
    const s = boite(T, 1.2, 0.14, 4.6, m); s.position.set(-l / 2 + 1, 0.4, 0); g.add(s);
    for (const z of [-1.6, 1.6]) { const r = new T.Mesh(new T.CylinderGeometry(0.45, 0.45, 2, 12), lambert(T, "#9aa3ad")); r.rotation.z = Math.PI / 2; r.position.set(-l / 2 + 3.2, 0.7, z); g.add(r); }
    g.userData.taille = [l, 3, l]; return g;
  },
  helico(T, o) {
    const g = new T.Group(), m = lambert(T, o.couleur || "#e74c3c");
    const c = new T.Mesh(new T.SphereGeometry(1.3, 16, 12), m); c.scale.set(1.5, 1, 1); c.position.y = 1.5; g.add(c);
    const q = boite(T, 5, 0.35, 0.35, m); q.position.set(-3.2, 1.8, 0); g.add(q);
    const p = boite(T, 9, 0.05, 0.35, lambert(T, "#222")); p.position.y = 2.9; g.add(p); g.userData.pale = p;
    g.userData.taille = [9, 3, 3]; return g;
  },
  bateau(T, o) {
    const g = new T.Group(), l = o.longueur || 40;
    const c = boite(T, l, 4, l * 0.16, lambert(T, o.couleur || "#2d3e50")); c.position.y = 1; g.add(c);
    const b = boite(T, l * 0.98, 0.6, l * 0.162, lambert(T, "#b23b3b")); b.position.y = -0.6; g.add(b);
    const p = boite(T, l * 0.12, 5, l * 0.14, lambert(T, "#f1f1f1")); p.position.set(-l * 0.38, 5.5, 0); g.add(p);
    const r = hasard(l); const cols = ["#d35400", "#2980b9", "#27ae60", "#c0392b", "#f39c12", "#7f8c8d"];
    for (let x = -l * 0.28; x < l * 0.42; x += 3.2) for (let z = -1; z <= 1; z++) if (r() < 0.85) {
      const k = boite(T, 3, 2.5, l * 0.045, lambert(T, cols[Math.floor(r() * cols.length)])); k.position.set(x, 4.3 + (r() < 0.5 ? 2.5 : 0), z * l * 0.048); g.add(k);
    }
    g.userData.taille = [l, 8, l * 0.16]; return g;
  },
  train(T, o) {
    const g = new T.Group(), n = o.wagons || 4;
    for (let i = 0; i < n; i++) { const w = boite(T, 18, 3.6, 2.9, lambert(T, i ? (o.couleur2 || "#dfe6e9") : (o.couleur || "#2d6cdf"))); w.position.set(-i * 18.6, 2.4, 0); g.add(w); }
    g.userData.taille = [n * 18.6, 4, 3]; return g;
  },
  batiment(T, o) {
    const g = new T.Group(), h = o.hauteur || 18, l = o.largeur || 14;
    const tex = texFenetres(T, o.graine || 5, o.nuit !== false); tex.repeat.set(l / 8, h / 16);
    const m = new T.MeshLambertMaterial({ map: tex, emissive: 0xffffff, emissiveMap: o.nuit !== false ? tex : null, emissiveIntensity: o.nuit !== false ? 0.55 : 0 });
    const b = boite(T, l, h, o.profondeur || 12, m); b.position.y = h / 2; g.add(b);
    const toit = boite(T, l + 0.6, 0.8, (o.profondeur || 12) + 0.6, lambert(T, "#3b4150")); toit.position.y = h + 0.4; g.add(toit);
    if ((o.graine || 0) % 3 === 0) { const c = boite(T, l * 0.3, 2.5, 3, lambert(T, "#4a505e")); c.position.set(l * 0.15, h + 2, 0); g.add(c); }
    g.userData.taille = [l, h, o.profondeur || 12]; return g;
  },
  entrepot(T, o) {                         // dépôt, hangar, usine : grand bâtiment bas, toit arrondi en tôle, porte, panneau danger
    const g = new T.Group(), l = o.largeur || 34, pr = o.profondeur || 18, h = o.hauteur || 8;
    const mur = boite(T, l, h, pr, lambert(T, o.couleur || "#a89f8c")); mur.position.y = h / 2; g.add(mur);
    const toit = new T.Mesh(new T.CylinderGeometry(pr / 2, pr / 2, l, 24, 1, false, 0, Math.PI), lambert(T, "#8a9099"));
    toit.rotation.z = Math.PI / 2; toit.rotation.y = Math.PI / 2; toit.position.y = h; g.add(toit);
    for (const x of [-l / 4, l / 4]) { const p_ = boite(T, 7, 6, 0.3, lambert(T, "#3c4149")); p_.position.set(x, 3, pr / 2 + 0.15); g.add(p_); }
    const panneau = boite(T, 1.6, 1.6, 0.1, lambert(T, "#f39c12")); panneau.rotation.z = Math.PI / 4; panneau.position.set(0, h - 1.5, pr / 2 + 0.2); g.add(panneau);
    g.userData.taille = [l, h + pr / 2, pr]; return g;
  },
  arbre(T, o) {
    const g = new T.Group(); const t = new T.Mesh(new T.CylinderGeometry(0.25, 0.35, 2.2, 8), lambert(T, "#6d4c2f")); t.position.y = 1.1; g.add(t);
    const f = new T.Mesh(new T.IcosahedronGeometry(1.8, 0), lambert(T, o.couleur || "#2f8f4e")); f.position.y = 3.4; g.add(f);
    g.userData.taille = [3, 5, 3]; return g;
  },
  personne(T, o) {
    const g = new T.Group(); const c = new T.Mesh(new T.CapsuleGeometry(0.28, 0.9, 4, 8), lambert(T, o.couleur || "#ffd600")); c.position.y = 0.75; g.add(c);
    const t = new T.Mesh(new T.SphereGeometry(0.22, 12, 8), lambert(T, "#f1c27d")); t.position.y = 1.55; g.add(t);
    g.userData.taille = [0.6, 1.8, 0.6]; return g;
  },
  muret(T, o) {
    const g = new T.Group(); const b = boite(T, o.longueur || 60, o.hauteur || 1.0, 0.6, lambert(T, "#bfc5cc")); b.position.y = (o.hauteur || 1) / 2; g.add(b);
    g.userData.taille = [o.longueur || 60, 1, 0.6]; return g;
  },
  mur(T, o) { const g = new T.Group(); const b = boite(T, o.epaisseur || 3.7, o.hauteur || 8, o.largeur || 10, lambert(T, "#e8e3da")); b.position.y = (o.hauteur || 8) / 2; g.add(b); g.userData.taille = [3.7, 8, 10]; return g; },
  foule(T, o) {                            // manifestation, rassemblement : des dizaines de personnes qui bougent
    const g = new T.Group(), n = Math.min(120, o.nombre || 50), r = o.rayon || 9, rr = hasard(n * 7 + 3);
    const corps = new T.InstancedMesh(new T.CapsuleGeometry(0.28, 0.9, 3, 6), new T.MeshLambertMaterial(), n);
    const tetes = new T.InstancedMesh(new T.SphereGeometry(0.22, 8, 6), new T.MeshLambertMaterial({ color: 0xe0b48a }), n);
    const COUL = ["#2d3436", "#c0392b", "#2980b9", "#7f8c8d", "#f1c40f", "#16a085", "#8e44ad", "#ecf0f1", "#d35400"];
    const pos = [];
    for (let i = 0; i < n; i++) {
      const a = rr() * Math.PI * 2, d = Math.sqrt(rr()) * r;
      pos.push([Math.cos(a) * d * 1.6, Math.sin(a) * d, rr() * 6]);
      corps.setColorAt(i, new T.Color(COUL[Math.floor(rr() * COUL.length)]));
    }
    g.add(corps, tetes);
    const m = new T.Matrix4();
    g.userData.anime = t => {                // chacun sautille un peu, à son rythme
      pos.forEach(([x, z, ph], i) => {
        const y = Math.max(0, Math.sin(t * 5 + ph)) * 0.25;
        m.makeTranslation(x, 0.75 + y, z); corps.setMatrixAt(i, m);
        m.makeTranslation(x, 1.55 + y, z); tetes.setMatrixAt(i, m);
      });
      corps.instanceMatrix.needsUpdate = tetes.instanceMatrix.needsUpdate = true;
    };
    g.userData.anime(0);
    g.userData.taille = [r * 3.2, 1.8, r * 2]; return g;
  },
  police(T, o) { return vehiculeUrgence(T, o, "#f4f6f8", "#1e4fd8", ["#1e6bff", "#ff2b2b"]); },
  pompiers(T, o) { return vehiculeUrgence(T, Object.assign({ longueur: 8.5 }, o), "#d61f26", "#f4f6f8", ["#ff2b2b", "#ff2b2b"]); },
  ambulance(T, o) { return vehiculeUrgence(T, o, "#f4f6f8", "#f39c12", ["#1e6bff", "#1e6bff"]); },
  batiment_officiel(T, o) {                // ministère, parlement, palais de justice : colonnes, fronton, drapeau
    const g = new T.Group(), l = o.largeur || 34, p = 16, h = 14, pierre = lambert(T, o.couleur || "#e8e1d3");
    const base = boite(T, l + 4, 1.6, p + 4, pierre); base.position.y = 0.8; g.add(base);
    const corps_ = boite(T, l, h, p, pierre); corps_.position.set(0, 1.6 + h / 2, -2); g.add(corps_);
    for (let x = -l / 2 + 2; x <= l / 2 - 2; x += 4) { const c = new T.Mesh(new T.CylinderGeometry(0.7, 0.8, h, 12), pierre); c.position.set(x, 1.6 + h / 2, p / 2 + 0.2); g.add(c); }
    const tri = new T.Shape(); tri.moveTo(-l / 2 - 1, 0); tri.lineTo(l / 2 + 1, 0); tri.lineTo(0, 5); tri.closePath();
    const fronton = new T.Mesh(new T.ExtrudeGeometry(tri, { depth: p + 1, bevelEnabled: false }), pierre);   // toit triangulaire
    fronton.position.set(0, 1.6 + h, -2 - (p + 1) / 2); g.add(fronton);
    const mat_ = boite(T, 0.25, 10, 0.25, lambert(T, "#888")); mat_.position.set(0, 1.6 + h + 5, -2); g.add(mat_);
    const drap = new T.Mesh(new T.PlaneGeometry(4, 2.6, 8, 1), lambert(T, o.drapeau || "#e8323f")); drap.position.set(2, 1.6 + h + 8.6, -2); g.add(drap);
    const pts = drap.geometry.attributes.position, x0 = Float32Array.from(pts.array);
    g.userData.anime = t => { for (let i = 0; i < pts.count; i++) pts.setZ(i, Math.sin(t * 4 + x0[i * 3] * 1.4) * 0.25 * (x0[i * 3] + 2) / 4); pts.needsUpdate = true; };
    g.userData.taille = [l + 4, h + 6, p + 4]; return g;
  },
  cube_eau(T, o) {                         // 1 m³ d'eau = 1 000 litres (comparaisons)
    const g = new T.Group(), c = o.cote || 1;
    const verre = new T.Mesh(new T.BoxGeometry(c, c, c), new T.MeshLambertMaterial({ color: 0xbfe0ff, transparent: true, opacity: 0.18 }));
    verre.position.y = c / 2; g.add(verre);
    const ar = new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(c, c, c)), new T.LineBasicMaterial({ color: 0xffffff }));
    ar.position.y = c / 2; g.add(ar);
    const eau = new T.Mesh(new T.BoxGeometry(c * 0.98, c, c * 0.98), new T.MeshLambertMaterial({ color: 0x2f86ff, transparent: true, opacity: 0.8, emissive: 0x0b3a8a }));
    g.add(eau); g.userData.eau = eau; g.userData.cote = c; g.userData.taille = [c, c, c]; return g;
  },
};

// véhicule de secours ou de police : caisse, bande de couleur, gyrophares qui clignotent
function vehiculeUrgence(T, o, coul, bande, feux) {
  const g = new T.Group(), l = o.longueur || 6;
  const c = boite(T, l, 2.4, 2.3, lambert(T, coul)); c.position.y = 1.6; g.add(c);
  const b = boite(T, l + 0.02, 0.4, 2.32, lambert(T, bande)); b.position.y = 1.4; g.add(b);
  const v = boite(T, 0.1, 0.9, 2.0, lambert(T, "#26303f")); v.position.set(l / 2 + 0.01, 2.2, 0); g.add(v);
  const gyro = feux.map((f, i) => { const m = new T.Mesh(new T.BoxGeometry(0.5, 0.3, 0.7), new T.MeshBasicMaterial({ color: f })); m.position.set(l / 2 - 1, 2.95, i ? 0.5 : -0.5); g.add(m); return m; });
  const halo = new T.Sprite(new T.SpriteMaterial({ color: feux[0], blending: T.AdditiveBlending, transparent: true, depthWrite: false, opacity: 0.6,
    map: texture(T, 64, 64, c_ => { const gr = c_.createRadialGradient(32, 32, 0, 32, 32, 32); gr.addColorStop(0, "#fff"); gr.addColorStop(1, "rgba(255,255,255,0)"); c_.fillStyle = gr; c_.fillRect(0, 0, 64, 64); }) }));
  halo.scale.set(6, 6, 1); halo.position.set(l / 2 - 1, 3.2, 0); g.add(halo);
  g.userData.anime = t => { const k = Math.floor(t * 6) % 2; gyro.forEach((m, i) => { m.visible = (i + k) % 2 === 0; }); halo.material.color.set(feux[k % feux.length]); halo.material.opacity = 0.35 + 0.35 * (k ? 1 : 0); };
  roues(T, g, l, 2.3, 0.45); g.userData.taille = [l, 3, 2.3]; return g;
}

// ------------------------------------------------------------------ décors
function decor(T, scene, sc) {
  const d = sc.decor || "autoroute", nuit = (sc.moment || "soir") !== "jour";
  const ciel = { jour: [0x9cc9ff, 0xdfeeff], soir: [0x1d2a4a, 0x3b4f7a], nuit: [0x070b16, 0x141d33] }[sc.moment || "soir"];
  // ciel en dégradé (horizon plus clair) et brume : la profondeur d'une vraie maquette filmée
  const degrade = { jour: ["#5d9be0", "#cfe4ff"], soir: ["#0f1a33", "#4a5d8c"], nuit: ["#03060f", "#1a2442"] }[sc.moment || "soir"];
  scene.background = texture(T, 4, 256, (c, w, h) => { const g = c.createLinearGradient(0, 0, 0, h); g.addColorStop(0, degrade[0]); g.addColorStop(0.75, degrade[1]); g.addColorStop(1, degrade[1]); c.fillStyle = g; c.fillRect(0, 0, w, h); });
  scene.background.wrapS = scene.background.wrapT = T.ClampToEdgeWrapping; scene.background.repeat.set(1, 1);
  scene.fog = new T.Fog(ciel[1], 140, sc.brouillard || 480);
  const jour = sc.moment === "jour";          // plein jour : lumière franche, comme une maquette au soleil
  scene.add(new T.HemisphereLight(nuit && !jour ? 0x8fa6d6 : 0xffffff, nuit && !jour ? 0x1a1f2b : 0x8a8f7a, jour ? 2.4 : nuit ? 1.1 : 1.6));
  const soleil = new T.DirectionalLight(jour ? 0xfff2dd : nuit ? 0xb7c7ff : 0xffffff, jour ? 3.0 : nuit ? 1.2 : 2.2); soleil.position.set(-60, 120, 40); scene.add(soleil);
  // ombres portées : une zone de 120 m autour de l'action (la caméra de l'ombre suit ce qu'on filme)
  if (sc.ombres !== false) {
    soleil.castShadow = true; soleil.shadow.mapSize.set(2048, 2048); soleil.shadow.bias = -0.0004; soleil.shadow.normalBias = 0.04;
    Object.assign(soleil.shadow.camera, { left: -60, right: 60, top: 60, bottom: -60, near: 10, far: 400 });
    scene.add(soleil.target); scene.userData.soleil = soleil;
  }
  const sol = (c, w = 2000, h = 2000) => { const m = new T.Mesh(new T.PlaneGeometry(w, h), new T.MeshLambertMaterial({ color: c })); m.rotation.x = -Math.PI / 2; m.position.y = -0.02; scene.add(m); return m; };
  const r = hasard(sc.graine || 11);
  if (d === "autoroute" || d === "route" || d === "ville") {
    sol(d === "ville" ? 0x2a2f38 : 0x2f3a2f);
    const voies = sc.voies || (d === "autoroute" ? 6 : 2), larg = voies * 3.6;
    const route = new T.Mesh(new T.PlaneGeometry(1200, larg), new T.MeshLambertMaterial({ map: texRoute(T, voies) }));
    route.rotation.x = -Math.PI / 2; scene.add(route);
    if (d === "autoroute") { const m = FABRIQUES.muret(T, { longueur: 1200 }); m.position.z = 0; m.visible = sc.terre_plein !== false; scene.add(m); }
    if (d !== "route" || sc.batiments) for (let x = -300; x < 300; x += 16 + r() * 10) for (const cote of [-1, 1]) {
      if (r() < 0.2 || (cote > 0 && sc.cote_camera !== false && r() < 0.75)) continue;   // côté caméra : peu d'immeubles (vue dégagée)
      // quartier varié (27/11) : immeubles, résidences, magasins, parfois un hôpital ou une banque (Quaternius, CC0)
      const tirage = r(), typeB = tirage < 0.12 ? "gratte_ciel" : tirage < 0.3 && modelePret("residence") ? "residence"
        : tirage < 0.42 && modelePret("magasin") ? "magasin" : tirage < 0.46 && modelePret("hopital") ? "hopital"
        : tirage < 0.5 && modelePret("banque") ? "banque" : "immeuble";
      const b = !nuit && modelePret(typeB) ? modele(T, typeB, { hauteur: typeB === "immeuble" ? 12 + r() * 20 : typeB === "gratte_ciel" ? 50 + r() * 30 : undefined }, Math.floor(r() * 99)) :
        FABRIQUES.batiment(T, { hauteur: r() < 0.15 ? 40 + r() * 30 : 8 + r() * 26, largeur: 9 + r() * 10, profondeur: 9 + r() * 8,
                                        graine: Math.floor(r() * 99), nuit });
      b.position.set(x, 0, cote * (larg / 2 + 12 + r() * 10) + (cote > 0 ? 25 : 0)); if (cote > 0) b.scale.y = 0.5; scene.add(b);
    }
    if (d === "route") for (let x = -300; x < 300; x += 8 + r() * 14) for (const cote of [-1, 1]) { const a = modelePret("arbre") ? modele(T, "arbre", { hauteur: 5 + r() * 5 }, Math.floor(r() * 99)) : FABRIQUES.arbre(T, {}); a.position.set(x, 0, cote * (larg / 2 + 4 + r() * 20)); scene.add(a); }
    // trottoirs, lampadaires (ampoule lumineuse, sans vraie lumière : le rendu reste rapide), arbres
    for (const cote of [-1, 1]) { const t_ = boite(T, 1200, 0.25, 3, lambert(T, "#8a8f98")); t_.position.set(0, 0.12, cote * (larg / 2 + 1.5)); scene.add(t_); }
    const mat_poteau = lambert(T, "#5b6270"), mat_ampoule = new T.MeshBasicMaterial({ color: nuit ? 0xffd58a : 0xdddddd });
    const halo = new T.SpriteMaterial({ map: texture(T, 64, 64, c => { const g = c.createRadialGradient(32, 32, 0, 32, 32, 32); g.addColorStop(0, "rgba(255,210,140,.9)"); g.addColorStop(1, "rgba(255,210,140,0)"); c.fillStyle = g; c.fillRect(0, 0, 64, 64); }), blending: T.AdditiveBlending, depthWrite: false, transparent: true });
    for (let x = -300; x < 300; x += 30) for (const cote of [-1, 1]) {
      const p_ = boite(T, 0.25, 9, 0.25, mat_poteau); p_.position.set(x, 4.5, cote * (larg / 2 + 0.6)); scene.add(p_);
      const b_ = boite(T, 1.6, 0.25, 0.5, mat_ampoule); b_.position.set(x, 9, cote * (larg / 2 - 0.2)); scene.add(b_);
      if (nuit) { const h_ = new T.Sprite(halo); h_.scale.set(9, 9, 1); h_.position.set(x, 8.6, cote * (larg / 2 - 0.2)); scene.add(h_);
        const tache = new T.Mesh(new T.CircleGeometry(4, 24), new T.MeshBasicMaterial({ color: 0xffc977, transparent: true, opacity: 0.12, depthWrite: false }));
        tache.rotation.x = -Math.PI / 2; tache.position.set(x, 0.05, cote * (larg / 2 - 2)); scene.add(tache); }
    }
    if (d === "ville" && modelePret("feu_tricolore"))    // feux tricolores aux carrefours, des deux côtés
      for (let x = -240; x < 240; x += 60) for (const cote of [-1, 1]) {
        const f = modele(T, "feu_tricolore", {}, 1); f.position.set(x + cote * 3, 0, cote * (larg / 2 + 1.2)); f.rotation.y = cote > 0 ? Math.PI : 0; scene.add(f);
      }
    scene.userData.voies = { larg, n: voies };
  } else if (d === "usine") {              // site industriel / militaire : entrepôts, cheminées, cuves, clôture
    sol(0x3b4232);
    const beton = new T.Mesh(new T.PlaneGeometry(260, 180), lambert(T, "#6f747c")); beton.rotation.x = -Math.PI / 2; beton.position.y = 0.01; scene.add(beton);
    const route = new T.Mesh(new T.PlaneGeometry(1200, 7.2), new T.MeshLambertMaterial({ map: texRoute(T, 2) })); route.rotation.x = -Math.PI / 2; route.position.set(0, 0.02, 30); scene.add(route);
    const toles = ["#9aa3ad", "#b7a98f", "#8c96a3", "#a3a7ab"];
    for (let i = 0; i < 9; i++) {                // hangars à toit arrondi
      const l = 26 + r() * 18, pr = 16 + r() * 8, h = 7 + r() * 5, x = -110 + (i % 5) * 50 + r() * 6, z = i < 5 ? -40 - r() * 10 : -95;
      if (Math.abs(x) < 18 && z > -60) continue;   // le centre reste libre pour l'événement
      const g = new T.Group(); const mur = boite(T, l, h, pr, lambert(T, toles[i % 4])); mur.position.y = h / 2; g.add(mur);
      const toit = new T.Mesh(new T.CylinderGeometry(pr / 2, pr / 2, l, 20, 1, false, 0, Math.PI), lambert(T, "#7d858f"));
      toit.rotation.z = Math.PI / 2; toit.rotation.y = Math.PI / 2; toit.position.y = h; g.add(toit);
      const porte = boite(T, 6, 5, 0.2, lambert(T, "#3c4149")); porte.position.set(0, 2.5, pr / 2 + 0.1); g.add(porte);
      g.position.set(x, 0, z); scene.add(g);
    }
    for (let i = 0; i < 3; i++) { const c = new T.Mesh(new T.CylinderGeometry(1.6, 2.2, 34, 16), lambert(T, "#8f6f5a")); c.position.set(70 + i * 9, 17, -70); scene.add(c);
      const b = new T.Mesh(new T.CylinderGeometry(1.7, 1.7, 1.2, 16), lambert(T, "#c0392b")); b.position.set(70 + i * 9, 30, -70); scene.add(b); }
    for (let i = 0; i < 4; i++) { const cu = new T.Mesh(new T.CylinderGeometry(6, 6, 9, 24), lambert(T, "#d6dade")); cu.position.set(-80 + i * 15, 4.5, 20); scene.add(cu); }
    const mat_cl = lambert(T, "#7a8088");
    for (let x = -130; x <= 130; x += 4) { const p_ = boite(T, 0.15, 2.4, 0.15, mat_cl); p_.position.set(x, 1.2, 45); scene.add(p_); }
    const grillage = new T.Mesh(new T.PlaneGeometry(260, 2.2), new T.MeshBasicMaterial({ color: 0x9aa0a8, transparent: true, opacity: 0.25, side: T.DoubleSide, depthWrite: false }));
    grillage.position.set(0, 1.2, 45); scene.add(grillage);
  } else if (d === "place") {               // grande place de ville (manifestation, rassemblement, bâtiment officiel)
    sol(0x2a2f38);
    const dalles = new T.Mesh(new T.PlaneGeometry(140, 100), new T.MeshLambertMaterial({ map: texture(T, 256, 256, (c, w, h) => {
      c.fillStyle = "#8b8f96"; c.fillRect(0, 0, w, h); c.strokeStyle = "rgba(0,0,0,.18)"; c.lineWidth = 2;
      for (let i = 0; i <= w; i += 32) { c.beginPath(); c.moveTo(i, 0); c.lineTo(i, h); c.stroke(); c.beginPath(); c.moveTo(0, i); c.lineTo(w, i); c.stroke(); } }, [14, 10]) }));
    dalles.rotation.x = -Math.PI / 2; scene.add(dalles);
    for (let a = 0; a < Math.PI * 2; a += 0.22) {
      if (Math.sin(a) > 0.55) continue;        // côté caméra dégagé
      const b = FABRIQUES.batiment(T, { hauteur: 12 + r() * 22, largeur: 12 + r() * 8, graine: Math.floor(r() * 99), nuit });
      b.position.set(Math.cos(a) * 95, 0, Math.sin(a) * 70); b.rotation.y = -a + Math.PI / 2; scene.add(b);
    }
    for (let i = 0; i < 10; i++) { const ar = FABRIQUES.arbre(T, {}); ar.position.set(-60 + i * 13, 0, 42); scene.add(ar); }
  } else if (d === "mer" || d === "port" || d === "plage") {
    const eau = sol(0x1f5f8b, 3000, 3000); eau.material = new T.MeshLambertMaterial({ color: 0x1b5a86, emissive: 0x06223a });
    scene.userData.eau = eau;
    if (d !== "mer") { const s = new T.Mesh(new T.BoxGeometry(2000, 2, 260), lambert(T, d === "plage" ? "#e6d3a3" : "#8d969e")); s.position.set(0, -0.6, 200); scene.add(s); }
  } else if (d === "piste") {
    sol(0x3c5a3a); const p = new T.Mesh(new T.PlaneGeometry(1600, 45), new T.MeshLambertMaterial({ map: texRoute(T, 2) })); p.rotation.x = -Math.PI / 2; p.material.map.repeat.set(80, 1); scene.add(p);
  } else if (d === "voie_ferree") {
    sol(0x3d4a34); const b = new T.Mesh(new T.BoxGeometry(1600, 0.4, 5), lambert(T, "#6b6257")); b.position.y = 0.2; scene.add(b);
    for (const z of [-0.75, 0.75]) { const rail = new T.Mesh(new T.BoxGeometry(1600, 0.15, 0.12), lambert(T, "#c8c8c8")); rail.position.set(0, 0.5, z); scene.add(rail); }
  } else if (d === "studio") {          // fond uni pour les objets de comparaison (cube d'eau…)
    scene.background = new T.Color(0x0b1222); scene.fog = null; sol(0x141d33);
  } else if (d === "foret") {              // forêt (feu de forêt, tempête) : collines boisées, une route qui traverse
    sol(0x34472c);
    const route = new T.Mesh(new T.PlaneGeometry(1200, 7.2), new T.MeshLambertMaterial({ map: texRoute(T, 2) })); route.rotation.x = -Math.PI / 2; route.position.y = 0.02; scene.add(route);
    for (let i = 0; i < 170; i++) {
      const x = -160 + r() * 320, z = -140 + r() * 200; if (Math.abs(z) < 7) continue;
      const a = modelePret("arbre") ? modele(T, "arbre", { hauteur: 6 + r() * 8 }, Math.floor(r() * 99)) : FABRIQUES.arbre(T, {});
      a.position.set(x, 0, z); a.userData.arbre = true; scene.add(a); (scene.userData.arbres ||= []).push(a);
    }
  } else sol(0x3a4a35);                  // campagne
}

// ------------------------------------------------------------------ état des objets à l'instant t (actions rejouées)
function etat(o, actions, t, objets, profondeur = 0) {
  const e = { x: o.x || 0, y: o.y || 0, z: o.z || 0, cap: (o.cap || 0) * Math.PI / 180, roulis: 0, tangage: 0, brule: -1, visible: o.a == null || t >= o.a, distance: 0, explose: -1, secousse: 0 };
  for (const a of actions.filter(a => a.objet === o.id).sort((p, q) => p.a - q.a)) {
    if (t < a.a) break;
    const d = a.d || 1, p = prog(t, a.a, d),
          k = a.faire === "avancer" || a.faire === "changer_voie" || a.faire === "fuir" ? p
            : ["freiner", "deraper", "tonneau"].includes(a.faire) ? ease.sortie(p) : ease.douce(p);
    if (["avancer", "heurter", "changer_voie", "tomber", "voler", "freiner", "deraper", "tonneau", "fuir"].includes(a.faire)) {
      let [vx, vz] = a.vers || (a.distance ? [e.x + a.distance, e.z] : [e.x, e.z]);   // sans destination : « distance » depuis ici
      // le choc se fait là où la cible SE TROUVE à cet instant (avant : sa place de départ → la voiture frappait le vide)
      if (a.faire === "heurter" && a.cible) { const c = objets.find(x => x.id === a.cible);
        if (c) { const ce = profondeur < 2 ? etat(c, actions, a.a + d, objets, profondeur + 1) : { x: c.x || 0, z: c.z || 0 };
                 vx = ce.x - (a.ecart ?? 7.5); vz = ce.z; } }
      const vy = a.faire === "tomber" ? (a.vers?.[2] ?? 0) : a.faire === "voler" ? (a.vers?.[2] ?? e.y) : e.y;
      const ax = e.x, az = e.z, ay = e.y;
      e.x = mix(ax, vx, k); e.z = mix(az, vz, k); e.y = mix(ay, vy, a.faire === "tomber" ? p * p : k);
      e.distance += Math.hypot(vx - ax, vz - az) * k;
      if (a.faire === "tomber") e.tangage = mix(0, (a.angle ?? -35) * Math.PI / 180, ease.sortie(p));
      if (a.faire === "heurter") { e.secousse = Math.max(e.secousse, p >= 1 ? Math.max(0, 1 - (t - a.a - d) * 2.5) : 0);
        if (p >= 1) e.ecrase = Math.max(e.ecrase || 0, borne((t - a.a - d) / 0.15)); }
    }
    if (a.faire === "tourner") e.cap += (a.angle || 90) * Math.PI / 180 * k;
    if (a.faire === "deraper") e.cap += (a.angle ?? 160) * Math.PI / 180 * ease.douce(p);          // tête-à-queue
    if (a.faire === "tonneau") { e.roulis += Math.PI * 2 * (a.tours ?? 1.5) * k; e.y += 1.6 * Math.sin(Math.PI * p); }
    if (a.faire === "fuir" && p < 1) e.y += Math.abs(Math.sin(t * 14)) * 0.25;                       // on court
    if (a.faire === "effondrer") { e.effondre = Math.max(e.effondre || 0, p * p); if (e.effondreT == null) e.effondreT = a.a; }
    if (a.faire === "se_coucher") { e.roulis = (a.angle ?? 90) * Math.PI / 180 * ease.sortie(p); e.y += 0.6 * Math.sin(Math.PI * p); }
    if (a.faire === "couler") { e.roulis = (a.angle ?? 25) * Math.PI / 180 * k; e.y = mix(e.y, -(a.profondeur ?? 6), k); }
    if (a.faire === "bruler" && e.brule < 0) e.brule = a.a;
    if (a.faire === "exploser" && e.explose < 0) e.explose = a.a;
    if (a.faire === "disparaitre") e.visible = t < a.a;
    if (a.faire === "apparaitre") e.visible = true;
  }
  // SOUFFLE d'une explosion voisine : ce qui est proche est repoussé, penche et prend feu (plus fort si plus près)
  // (ni un bâtiment, ni ce qui vole : le drone de l'Iowa brûlait en plein ciel, 27/11)
  if (profondeur < 1 && !["batiment", "entrepot", "immeuble", "maison", "batiment_officiel", "muret", "mur", "avion", "helico"].includes(o.type) && e.y < 4)
    for (const a of actions) {
      if (a.faire !== "exploser" || a.objet === o.id || t < a.a) continue;
      const src = objets.find(x => x.id === a.objet); if (!src) continue;
      const c = etat(src, actions, a.a, objets, 2), dx = e.x - c.x, dz = e.z - c.z, dist = Math.hypot(dx, dz), R = a.rayon_souffle ?? 18;
      if (dist >= R || dist < 0.01) continue;
      const f = 1 - dist / R, k = ease.sortie(borne((t - a.a) / 0.45));
      e.x += dx / dist * 6 * f * k; e.z += dz / dist * 3 * f * k; e.roulis += 0.35 * f * k * Math.sign(dz || 1);
      e.secousse = Math.max(e.secousse, Math.max(0, 1 - (t - a.a) * 2) * f);
      if (f > 0.35 && (e.brule < 0 || e.brule > a.a + 0.4)) e.brule = a.a + 0.4;
    }
  // REBOND après le choc (27/11) : celui qui percute recule d'1,5 m et pivote ; la cible est poussée d'1 m et pivote un peu
  for (const a of actions) {
    if (a.faire !== "heurter") continue;
    const ti = a.a + (a.d || 1); if (t < ti) continue;
    const k = ease.sortie(borne((t - ti) / 0.6)), signe = ((a.cible || "").length % 2 ? 1 : -1);
    if (a.objet === o.id) { e.x -= 1.5 * k; e.cap += 0.16 * k * signe; }
    if (a.cible === o.id) { e.x += 1.0 * k; e.cap -= 0.06 * k * signe; }
  }
  // percuté : son arrière s'écrase aussi
  for (const a of actions) if (a.faire === "heurter" && a.cible === o.id && t >= a.a + (a.d || 1))
    e.ecrase = Math.max(e.ecrase || 0, borne((t - a.a - (a.d || 1)) / 0.15) * 0.6);
  return e;
}

// ------------------------------------------------------------------ feu (particules dessinées, toujours les mêmes)
function feu(T) {
  // flamme : goutte allongée (blanc-jaune au cœur, orange, rouge), fumée sombre et douce, lueur ronde au sol
  const flamme = texture(T, 64, 128, (c, w, h) => {
    const g = c.createRadialGradient(32, 92, 2, 32, 80, 60);
    g.addColorStop(0, "rgba(255,250,210,1)"); g.addColorStop(0.25, "rgba(255,190,60,.95)"); g.addColorStop(0.55, "rgba(255,90,10,.6)"); g.addColorStop(1, "rgba(200,30,0,0)");
    c.fillStyle = g; c.beginPath(); c.moveTo(32, 4); c.bezierCurveTo(60, 50, 64, 120, 32, 124); c.bezierCurveTo(0, 120, 4, 50, 32, 4); c.fill(); });
  const fum = texture(T, 64, 64, (c) => { const g = c.createRadialGradient(32, 32, 0, 32, 32, 32); g.addColorStop(0, "rgba(30,30,34,.8)"); g.addColorStop(0.6, "rgba(40,40,46,.35)"); g.addColorStop(1, "rgba(40,40,46,0)"); c.fillStyle = g; c.fillRect(0, 0, 64, 64); });
  const lueur = texture(T, 64, 64, (c) => { const g = c.createRadialGradient(32, 32, 0, 32, 32, 32); g.addColorStop(0, "rgba(255,140,40,.9)"); g.addColorStop(1, "rgba(255,90,20,0)"); c.fillStyle = g; c.fillRect(0, 0, 64, 64); });
  return { flamme: new T.SpriteMaterial({ map: flamme, blending: T.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.85 }),
           fumee: new T.SpriteMaterial({ map: fum, depthWrite: false, transparent: true, opacity: 0.6 }),
           lueur: new T.MeshBasicMaterial({ map: lueur, blending: T.AdditiveBlending, depthWrite: false, transparent: true }) };
}

// ------------------------------------------------------------------ TÔLE CABOSSÉE (27/11, l'auteur : « les dégâts sur le
// véhicule sont inexistants ») : au choc, les points de la carrosserie proches de l'impact sont enfoncés dans le sens du
// coup (plus fort au centre), avec un peu de froissé. Calculé une seule fois, à l'instant du choc : même image partout.
function cabosser(T, g, point, sens, force, graine) {
  if (!g || g.userData.cabosse) return;
  g.userData.cabosse = true;
  g.updateMatrixWorld(true);
  const r = hasard(graine), R = 2.2 + force * 0.8, v = new T.Vector3();
  g.traverse(m => {
    if (!m.isMesh || !m.geometry?.attributes?.position) return;
    m.geometry = m.geometry.clone();              // (les modèles partagent leur forme : on ne cabosse que celui-ci)
    const pos = m.geometry.attributes.position, inv = new T.Matrix4().copy(m.matrixWorld).invert();
    const sensLocal = sens.clone().transformDirection(inv);
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i).applyMatrix4(m.matrixWorld);
      const d = v.distanceTo(point);
      if (d > R) continue;
      const k = Math.pow(1 - d / R, 2) * force;
      v.fromBufferAttribute(pos, i);
      v.addScaledVector(sensLocal, k * 0.9 / Math.max(1e-3, m.getWorldScale(new T.Vector3()).x));
      v.x += (r() - 0.5) * 0.12 * k; v.y += (r() - 0.5) * 0.12 * k; v.z += (r() - 0.5) * 0.12 * k;
      pos.setXYZ(i, v.x, v.y, v.z);
    }
    pos.needsUpdate = true; m.geometry.computeVertexNormals();
  });
}
// ÉCRASEMENT par sections (27/11, l'auteur : « les dégâts sont inexistants ») : nos modèles ont peu de points, enfoncer la
// surface ne se voyait pas. On tasse en accordéon toute la partie du véhicule côté impact (zone = 35 % de sa longueur) :
// elle se raccourcit de 60 %, se froisse (points décalés au hasard) et le capot remonte un peu.
function ecraser(T, g, versImpact, force, graine) {
  if (!g || g.userData.ecrase_) return;
  g.userData.ecrase_ = true;
  g.updateMatrixWorld(true);
  const bb = new T.Box3().setFromObject(g), centre = bb.getCenter(new T.Vector3()), r = hasard(graine), v = new T.Vector3();
  const dir = versImpact.clone().setY(0).normalize();
  let L = 0;                                       // demi-longueur de l'objet dans le sens du choc
  g.traverse(m => { if (!m.isMesh || !m.geometry?.attributes?.position) return; const p = m.geometry.attributes.position;
    for (let i = 0; i < p.count; i++) { v.fromBufferAttribute(p, i).applyMatrix4(m.matrixWorld); L = Math.max(L, v.clone().sub(centre).dot(dir)); } });
  const zone = Math.min(L * 0.7, 2 * L * 0.35 * force), debut = L - zone;
  g.traverse(m => {
    if (!m.isMesh || !m.geometry?.attributes?.position) return;
    m.geometry = m.geometry.clone();
    const pos = m.geometry.attributes.position, inv = new T.Matrix4().copy(m.matrixWorld).invert();
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i).applyMatrix4(m.matrixWorld);
      const s = v.clone().sub(centre).dot(dir);
      if (s <= debut) continue;
      const k = (s - debut) / Math.max(zone, 1e-3), recul = (s - debut) * 0.6;
      v.addScaledVector(dir, -recul);                                    // la partie avant recule (tassée)
      const b = (a2) => { const x = Math.sin(Math.round(v.x * 20) * 12.9898 + Math.round(v.y * 20) * 78.233 + Math.round(v.z * 20) * 37.719 + a2 + graine) * 43758.5453; return x - Math.floor(x) - 0.5; };
      const fx = b(1), fy = b(2), fz = b(3);                              // même endroit = même froissure (pas de fente)
      v.y += k * zone * 0.12 + fy * 0.18 * k;                              // capot qui remonte, tôle froissée
      v.x += fx * 0.22 * k; v.z += fz * 0.22 * k;
      v.applyMatrix4(inv); pos.setXYZ(i, v.x, v.y, v.z);
    }
    pos.needsUpdate = true; m.geometry.computeVertexNormals();
    if (m.material?.color) { m.material = m.material.clone(); m.material.color.multiplyScalar(0.92); }
  });
}
// masses en tonnes (ordre de grandeur) : qui encaisse le plus dans un choc
const MASSES = { moto: 0.2, personne: 0.08, voiture: 1.4, taxi: 1.4, police: 1.6, camionnette: 2.5, ambulance: 3.5, pompiers: 14,
                 camion: 12, citerne: 20, bus: 12, tracteur: 4, train: 400, tgv: 400, wagon_citerne: 60, avion: 60, helico: 5, bateau: 200 };

// RUPTURE d'une citerne percutée (27/11, l'auteur : « l'arrière doit subir d'énormes dégâts ») : trou noir au point d'impact,
// lambeaux de tôle arrachés et retournés vers l'extérieur, jet de carburant. Fixé à l'objet (il reste attaché s'il bouge).
function dechirer(T, scene, g, point, sens, graine) {
  // construit dans le monde (taille réelle en mètres), puis rattaché à l'objet sans changer d'échelle (attach)
  const r = hasard(graine), grp = new T.Group();
  g.updateMatrixWorld(true);
  const bb = new T.Box3().setFromObject(g), c = bb.getCenter(new T.Vector3()), t = bb.getSize(new T.Vector3());
  const cote = sens.clone().setY(0).normalize().negate();          // face percutée (côté d'où vient le choc)
  const ext = Math.abs(cote.x) * t.x / 2 + Math.abs(cote.z) * t.z / 2;
  // un rayon lancé depuis l'extérieur vers la citerne trouve le VRAI point de la tôle (et son orientation)
  const hauteur = bb.min.y + t.y * 0.62, depart = c.clone().addScaledVector(cote, ext + 3); depart.y = hauteur;
  const ray = new T.Raycaster(depart, cote.clone().negate(), 0, ext * 2 + 3);
  const touche = ray.intersectObject(g, true).find(h => h.face);
  if (!touche) return null;                                        // rien de sûr à dessiner : on n'invente pas
  const normale = touche.face.normal.clone().transformDirection(touche.object.matrixWorld).normalize();
  const centre = touche.point.clone().addScaledVector(normale, 0.03);
  const R = Math.min(0.8, t.y * 0.2);
  const trou = new T.Mesh(new T.CircleGeometry(R, 14), new T.MeshBasicMaterial({ color: 0x0b0b0b, side: T.DoubleSide }));
  trou.position.copy(centre); trou.lookAt(centre.clone().add(normale)); grp.add(trou);
  const tole = new T.MeshPhongMaterial({ color: 0xb9bec6, side: T.DoubleSide, shininess: 60 });
  for (let i = 0; i < 9; i++) {                    // lambeaux de tôle autour du trou, retournés vers l'extérieur
    const a = i / 9 * Math.PI * 2 + r() * 0.3, l = R * (0.6 + r() * 0.6);
    const tri = new T.BufferGeometry().setFromPoints([new T.Vector3(-R * 0.28, 0, 0), new T.Vector3(R * 0.28, 0, 0), new T.Vector3((r() - 0.5) * R * 0.2, l, 0)]);
    tri.computeVertexNormals(); const p = new T.Mesh(tri, tole);   // lambeau plat (tôle), pas un pique
    const piv = new T.Group(); piv.position.copy(centre); piv.quaternion.copy(trou.quaternion); grp.add(piv);
    p.position.set(Math.cos(a) * R, Math.sin(a) * R, 0); p.rotation.z = a - Math.PI / 2;   // pointe vers l'extérieur du trou
    p.rotateX(0.5 + r() * 0.5); piv.add(p);                         // et rabattue vers l'arrière
  }
  scene.add(grp); g.attach(grp);
  const jet = [];                                  // jet de carburant (gouttes sombres qui retombent)
  const cv = document.createElement("canvas"); cv.width = cv.height = 32; const cx = cv.getContext("2d");
  const gr = cx.createRadialGradient(16, 16, 0, 16, 16, 16); gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(0.6, "rgba(255,255,255,.7)"); gr.addColorStop(1, "rgba(255,255,255,0)");
  cx.fillStyle = gr; cx.fillRect(0, 0, 32, 32); const goutte = new T.CanvasTexture(cv);   // gouttes rondes, pas carrées
  for (let i = 0; i < 60; i++) { const sp = new T.Sprite(new T.SpriteMaterial({ map: goutte, color: 0x4a3414, transparent: true, opacity: 0.9, depthWrite: false }));
    sp.visible = false; scene.add(sp); jet.push({ sp, ph: r(), v: 3 + r() * 4, ec: (r() - 0.5) * 1.6, h: r() * 0.8 }); }
  return { jet, depart: centre.clone(), sens: normale.clone().setY(0).normalize().negate() };
}

function couleursDe(g) {
  const c = []; g?.traverse(m => { if (m.isMesh && m.material?.color) c.push("#" + m.material.color.getHexString()); });
  return c.length ? c : ["#d8d8d8", "#333333"];
}

// ------------------------------------------------------------------ VRAIE FRACTURE (three-pinata, MIT, 27/11)
// La pièce (citerne, cabine, mur…) est découpée en cellules de Voronoï : de vrais éclats de SA forme, faces de cassure
// sombres (métal / béton brûlé). Graine fixe = mêmes éclats dans chaque morceau de rendu. Échec (modèle non fermé) → false.
let PINATA = null;
export async function chargerFracture() {
  if (PINATA === null) { try { PINATA = await import("@dgreenheck/three-pinata"); } catch (e) { PINATA = false; } }
  return PINATA;
}
function fracturer(T, m, nombre, graine, pieces, scene, g, r, batiment) {
  if (!PINATA) return false;
  try {
    const geo = m.geometry.clone(); geo.applyMatrix4(m.matrixWorld);      // en coordonnées du monde
    if (!geo.attributes.normal) geo.computeVertexNormals();
    const mat = Array.isArray(m.material) ? m.material[0] : m.material;
    const interieur = new T.MeshLambertMaterial({ color: batiment ? 0x4a4540 : 0x2a2622 });
    const d = new PINATA.DestructibleMesh(geo, mat, interieur);
    const opt = new PINATA.FractureOptions({ fractureMethod: "voronoi", fragmentCount: nombre, voronoiOptions: { mode: "3D" }, seed: graine });
    const frags = d.fracture(opt);
    if (!frags || frags.length < 2) return false;
    for (const f of frags) {
      f.geometry.computeBoundingBox(); const c = new T.Vector3(); f.geometry.boundingBox.getCenter(c);
      f.geometry.translate(-c.x, -c.y, -c.z); f.position.copy(c);          // chaque éclat tourne autour de son propre centre
      f.castShadow = f.receiveShadow = true; f.userData.de = g; scene.add(f);
      pieces.push({ m: f, p0: f.position.clone(), q0: f.rotation.clone(), vole: batiment ? (c.y > 4 || r() < 0.3) : r() < 0.7 });
    }
    return true;
  } catch (e) { return false; }
}

// ------------------------------------------------------------------ DÉSINTÉGRATION (demande de l'auteur du 27/11 : « le camion
// est toujours intact » après l'explosion). À l'instant de l'explosion, les vraies pièces de l'objet (cabine, citerne, roues,
// châssis…) sont détachées ; les grosses pièces sont cassées en éclats de la même matière ; tout est projeté vers l'extérieur,
// tourne, retombe et reste au sol. Tout dépend seulement de t (même image à chaque rendu, morceaux rendus en parallèle).
function desintegrer(T, scene, g, o, etatExplosion, t, te, batiment, chute = false) {
  const d = g.userData;
  if (!d.morceaux) {
    // l'objet tel qu'il était à l'instant de l'explosion
    g.position.set(etatExplosion.x, etatExplosion.y, etatExplosion.z); g.rotation.set(etatExplosion.roulis, etatExplosion.cap, etatExplosion.tangage);
    g.updateMatrixWorld(true);
    const centre = new T.Vector3(); new T.Box3().setFromObject(g).getCenter(centre);
    const r = hasard((o.id || "x").length * 53 + 7), pieces = [];
    const maillages = []; g.traverse(m => { if (m.isMesh) maillages.push(m); });
    for (const m of maillages) {
      const bb = new T.Box3().setFromObject(m), taille = new T.Vector3(); bb.getSize(taille);
      const volume = taille.x * taille.y * taille.z;
      const haut = batiment ? bb.min.y > (new T.Box3().setFromObject(g).max.y) * 0.35 : true;
      if (!batiment && taille.y < 0.7 && taille.x > 3) continue;   // le châssis reste : l'épave noircie au sol
      if (volume > (batiment ? 30 : 3) && fracturer(T, m, batiment ? 22 : 12, (o.id || "x").length * 131 + maillages.indexOf(m), pieces, scene, g, r, batiment)) {
        m.visible = false;                       // vraie fracture (three-pinata) : la forme même de la pièce se fend en éclats
      } else if (volume > (batiment ? 30 : 3)) { // secours : éclats en forme de blocs (même couleur, même matière)
        const nx = Math.min(5, Math.max(2, Math.round(taille.x / (batiment ? 5 : 2.2)))), ny = batiment ? 3 : 2, nz = Math.min(4, Math.max(1, Math.round(taille.z / (batiment ? 5 : 1.6))));
        for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++) for (let k = 0; k < nz; k++) {
          const sx = taille.x / nx, sy = taille.y / ny, sz = taille.z / nz;
          const geo = new T.BoxGeometry(sx * (0.7 + r() * 0.5), sy * (0.6 + r() * 0.5), sz * (0.7 + r() * 0.5));
          const e = new T.Mesh(geo, Array.isArray(m.material) ? m.material[0] : m.material);
          e.position.set(bb.min.x + sx * (i + 0.5), bb.min.y + sy * (j + 0.5), bb.min.z + sz * (k + 0.5));
          e.rotation.set(r() * 0.4, r() * 0.4, r() * 0.4); scene.add(e); e.userData.de = g;
          const vole = batiment ? (j >= ny - 1 || r() < 0.25) : (j > 0 ? r() < 0.75 : r() < 0.3);   // le bas reste sur l'épave
          pieces.push({ m: e, p0: e.position.clone(), q0: e.rotation.clone(), vole });
        }
        m.visible = false;
      } else if (!batiment || haut) {          // petite pièce (roue, vitre, phare) : détachée telle quelle
        const p = new T.Vector3(), q = new T.Quaternion(), sc_ = new T.Vector3(); m.matrixWorld.decompose(p, q, sc_);
        scene.attach(m); m.userData.de = g; pieces.push({ m, p0: m.position.clone(), q0: m.rotation.clone(), vole: r() < 0.45 });
      }
    }
    for (const pc of pieces) {                 // vitesse : vers l'extérieur depuis le centre, vers le haut, au hasard
      const dir = pc.p0.clone().sub(centre); dir.y = Math.max(0.3, dir.y); dir.normalize();
      // explosion : projetées vers l'extérieur ; effondrement (séisme) : elles tombent presque sur place, en tas
      const force = chute ? 0.4 + r() * 1.6 : pc.vole ? (batiment ? 6 + r() * 12 : 4 + r() * 8) : 0.5 + r() * 1.5;
      pc.v = dir.multiplyScalar(force); pc.v.y = chute ? -r() * 2 : pc.v.y + (pc.vole ? 3 + r() * 7 : 0.8);
      pc.spin = [(r() - 0.5) * 9, (r() - 0.5) * 9, (r() - 0.5) * 9].map(x => x * (pc.vole ? 1 : 0.15));
      const bb = new T.Box3().setFromObject(pc.m); pc.demi = Math.max(0.1, (bb.max.y - bb.min.y) / 2);
    }
    d.morceaux = pieces;
    scene.userData.solides = null;             // de nouveaux éclats : la caméra doit aussi les éviter
  }
  const u = Math.max(0, t - te);
  for (const pc of d.morceaux) {
    // vol balistique jusqu'au sol, puis glisse un peu et s'arrête (reste au sol, couché)
    const tSol = (pc.v.y + Math.sqrt(pc.v.y * pc.v.y + 2 * 9.8 * Math.max(0, pc.p0.y - pc.demi))) / 9.8, tv = Math.min(u, tSol);
    const glisse = Math.max(0, Math.min(u - tSol, 0.6)) * (1 - Math.min(u - tSol, 0.6) / 1.2);
    pc.m.position.set(pc.p0.x + pc.v.x * (tv + glisse * 0.5), Math.max(pc.demi, pc.p0.y + pc.v.y * tv - 4.9 * tv * tv), pc.p0.z + pc.v.z * (tv + glisse * 0.5));
    const k = tv + glisse * 0.3;
    pc.m.rotation.set(pc.q0.x + pc.spin[0] * k, pc.q0.y + pc.spin[1] * k, pc.q0.z + pc.spin[2] * k);
    pc.m.visible = true;
    // noircit avec le feu (pas un immeuble qui s'effondre sans feu)
    if (!chute && pc.m.material?.color) { if (!pc.m.userData.brulee) { pc.m.material = pc.m.material.clone(); pc.m.userData.brulee = 1; }
      pc.m.material.color.lerp(new T.Color(0x1d1a18), borne(u / 5) * 0.06); }
  }
}

// ------------------------------------------------------------------ la scène
let QUARKS = null;                           // feu / fumée three.quarks (effets.js) ; indisponible = anciennes flammes
async function chargerQuarks() {
  if (QUARKS === null) { try { QUARKS = await import("./effets.js"); } catch (e) { console.log("three.quarks indisponible : " + e); QUARKS = false; } }
  return QUARKS;
}
export async function creer3d(sc, couche, T) {
  if ((sc.actions || []).some(a => a.faire === "exploser")) await chargerFracture();
  const avecFeu = (sc.actions || []).some(a => ["bruler", "exploser", "effondrer"].includes(a.faire)) && sc.quarks !== false;
  if (avecFeu) await chargerQuarks();
  await prechargerModeles([...(sc.objets || []).map(o => o.type), "immeuble", "gratte_ciel", "maison", "arbre", "voiture", "camion", "camionnette", "personne",
                           "bus", "residence", "magasin", "hopital", "banque", "feu_tricolore", "debris"]);
  const cv = el("canvas", "", couche); cv.width = W; cv.height = H; const cx = cv.getContext("2d");
  const scene = new T.Scene(); decor(T, scene, sc);
  // vue « maquette » vue d'en haut, sans perspective (comme les reconstitutions de bonnequestion.tv), sinon caméra classique
  const iso = sc.vue === "iso", HAUT_ISO = sc.iso_hauteur ?? 90;
  const camera = iso ? new T.OrthographicCamera(-HAUT_ISO * W / H / 2, HAUT_ISO * W / H / 2, HAUT_ISO / 2, -HAUT_ISO / 2, 0.5, 3000)
                     : new T.PerspectiveCamera(sc.focale ?? 40, W / H, 0.5, 3000);
  const objets = sc.objets || [], actions = sc.actions || [], MATS = feu(T);
  const groupes = {};
  for (const o of objets) {
    const g = modelePret(o.type) ? modele(T, o.type, o, (o.id || "").length * 7 + objets.indexOf(o))
      : (FABRIQUES[o.type] || FABRIQUES.voiture)(T, o);
    scene.add(g); groupes[o.id] = g;
    const ombre = new T.Mesh(new T.CircleGeometry(1, 24), new T.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.35, depthWrite: false }));
    ombre.rotation.x = -Math.PI / 2; ombre.position.y = 0.03; const ta = g.userData.taille || [4, 2, 2]; ombre.scale.set(ta[0] * 0.6, ta[2] * 0.75, 1); scene.add(ombre); g.userData.ombre = ombre;
    if (o.flou_vitesse) g.userData.flou = true;
  }
  // CIRCULATION : des véhicules roulent tout seuls sur les voies où la reconstitution ne se passe pas (la scène vit)
  const trafic = [];
  if (scene.userData.voies && sc.trafic !== false) {
    const { larg, n } = scene.userData.voies, rr = hasard((sc.graine || 5) * 31 + 7);
    const zObjets = objets.filter(o => !["batiment", "arbre", "muret", "mur"].includes(o.type)).map(o => o.z || 0);
    const COUL = ["#d9dde4", "#2d3436", "#c0392b", "#2980b9", "#f1c40f", "#7f8c8d", "#ecf0f1", "#16a085"];
    for (let v = 0; v < n; v++) {
      const z = -larg / 2 + (v + 0.5) * 3.6;
      // jamais à travers l'accident : ni sur une voie de la reconstitution, ni sur sa chaussée (autoroute : l'autre sens roule)
      if (zObjets.some(zo => Math.abs(zo - z) < 2.6 || (n > 2 && Math.sign(zo || -1) === Math.sign(z)))) continue;
      const sens = n > 2 ? (z < 0 ? 1 : -1) : (v ? -1 : 1);
      for (let k = 0; k < 4; k++) {
        const type = rr() < 0.15 ? "camion" : rr() < 0.15 ? "bus" : "voiture";
        const typeM = type === "bus" && !modelePret("bus") ? "camionnette" : type, n_ = Math.floor(rr() * 99);
        const g = modelePret(typeM) ? modele(T, typeM, {}, n_) : FABRIQUES[type](T, { couleur: COUL[Math.floor(rr() * COUL.length)] });
        g.rotation.y = sens > 0 ? 0 : Math.PI; scene.add(g);
        trafic.push({ g, z, sens, x0: -300 + rr() * 600, v: (sens > 0 ? 1 : -1) * (14 + rr() * 10) });
      }
    }
  }
  // flammes et fumée : un lot de particules par objet qui brûle
  const particules = {};
  for (const a of actions.filter(a => a.faire === "bruler" || a.faire === "exploser")) {
    const r = hasard(a.objet.length * 97 + 13), liste = [];
    for (let i = 0; i < (a.faire === "exploser" ? 50 : 60); i++) {
      const s = new T.Sprite(i % 3 ? MATS.flamme : MATS.fumee.clone()); scene.add(s);
      liste.push({ s, ph: r(), dx: (r() - 0.5), dz: (r() - 0.5), v: 0.6 + r() * 0.8, fumee: !(i % 3), taille: a.taille ?? 1 });
    }
    const fl = actions.find(x => x.faire === "deverser" && x.objet === a.objet);
    if (fl) for (let i = 0; i < 40; i++) {           // flammes basses sur toute la flaque
      const s = new T.Sprite(i % 4 ? MATS.flamme : MATS.fumee.clone()); scene.add(s);
      const ang = r() * 6.28, rr = Math.sqrt(r());
      liste.push({ s, ph: r(), dx: Math.cos(ang) * rr, dz: Math.sin(ang) * rr, v: 0.6 + r() * 0.8, fumee: !(i % 4), taille: 0.8, flaque: fl.rayon ?? 9 });
    }
    const sol_ = new T.Mesh(new T.PlaneGeometry(1, 1), MATS.lueur.clone()); sol_.rotation.x = -Math.PI / 2; scene.add(sol_);
    liste.push({ lueur: sol_ });
    particules[a.objet] = (particules[a.objet] || []).concat(liste);
  }
  // véhicules qui peuvent être atteints par le souffle d'une explosion : un petit feu prêt (il ne s'allume que s'ils sont touchés)
  if (actions.some(a => a.faire === "exploser"))
    for (const o of objets) {
      if (particules[o.id] || ["batiment", "entrepot", "immeuble", "maison", "batiment_officiel", "muret", "mur", "foule", "personne", "arbre", "avion", "helico"].includes(o.type)) continue;
      const r = hasard(o.id.length * 71 + 3), liste = [];
      for (let i = 0; i < 24; i++) { const s_ = new T.Sprite(i % 3 ? MATS.flamme : MATS.fumee.clone()); scene.add(s_);
        liste.push({ s: s_, ph: r(), dx: (r() - 0.5), dz: (r() - 0.5), v: 0.6 + r() * 0.8, fumee: !(i % 3), taille: 0.7 }); }
      particules[o.id] = liste;
    }
  // FEU ET FUMÉE three.quarks : chaque objet qui brûle (incendie, explosion, ou touché par le souffle)
  let avancerEffets = null;
  if (avecFeu && QUARKS) {
    const sources = [];
    for (const o of objets) {
      const fin = etat(o, actions, 1e4, objets);
      if (fin.effondreT != null && fin.brule < 0 && fin.explose < 0) {     // nuage de poussière grise
        const g = groupes[o.id], ta = g?.userData.taille || [10, 10, 10];
        sources.push({ debut: fin.effondreT + 0.3, taille: Math.max(1, Math.min(3, ta[0] / 8)), poussiere: true,
                       position: t => { const e = etat(o, actions, t, objets); return [e.x, 0.5, e.z]; } });
        continue;
      }
      const debut = fin.brule >= 0 ? fin.brule : fin.explose >= 0 ? fin.explose + 0.15 : -1;
      if (debut < 0 || ["foule", "personne"].includes(o.type)) continue;
      const g = groupes[o.id], ta = g?.userData.taille || [4, 2, 2];
      const taille = Math.max(0.7, Math.min(2.6, Math.max(ta[0], ta[2]) / 6));
      sources.push({ debut, taille, position: t => { const e = etat(o, actions, t, objets); return [e.x, Math.max(0, e.y) + 0.3, e.z]; } });
      for (const q of particules[o.id] || []) if (!q.lueur && !q.flaque) q.quarks = true;   // les anciennes flammes s'effacent
    }
    if (sources.length) avancerEffets = QUARKS.creerEffets(T, scene, sources, { flamme: MATS.flamme.map, fumee: MATS.fumee.map }, (sc.graine || 3) * 7919);
  }
  // CHOCS (heurter) : éclair, débris qui volent et retombent, caméra qui tremble (vidéo du Caire du 27/11 : « on ne voit pas l'accident »)
  const chocs = actions.filter(a => a.faire === "heurter").map((a, n) => {
    const r = hasard(97 + n * 13), debris = [];
    const teintes = [...couleursDe(groupes[a.objet]), ...couleursDe(groupes[a.cible])];
    // vraies pièces (pare-chocs, portière, roue, plaque : Kenney CC0) + éclats de carrosserie et de vitre (27/11 : les
    // débris partaient au ciel comme des confettis). Vitesse surtout DANS LE SENS DU CHOC, à peine vers le haut ; ils
    // glissent sur la route puis s'arrêtent.
    const pieces = ["debris-bumper", "debris-door", "debris-tire", "debris-plate-a"];
    for (let i = 0; i < 34; i++) {
      const verre = i % 3 === 0, piece = i < 4 && modelePret("debris");
      let m;
      if (piece) { m = modele(T, "debris", { variante: pieces[i], longueur: [1.8, 1.2, 0.7, 0.9][i] }, i); }
      else m = new T.Mesh(new T.BoxGeometry(verre ? 0.1 + r() * 0.15 : 0.15 + r() * 0.35, verre ? 0.02 : 0.04 + r() * 0.08, verre ? 0.08 + r() * 0.15 : 0.12 + r() * 0.3),
        verre ? new T.MeshPhongMaterial({ color: 0xcfe8ff, transparent: true, opacity: 0.85, shininess: 140 }) : lambert(T, teintes[Math.floor(r() * teintes.length)]));
      m.visible = false; scene.add(m);
      const avant = piece ? 3 + r() * 5 : 4 + r() * 9;                    // dans le sens du choc
      debris.push({ m, avant, cote: (r() - 0.5) * (piece ? 4 : 9), vy: piece ? 1 + r() * 2.5 : 0.8 + r() * 3.5,
                    rx: (r() - 0.5) * 12, ry: (r() - 0.5) * 12, piece });
    }
    const eclair = new T.Sprite(new T.SpriteMaterial({ map: MATS.lueur.map, blending: T.AdditiveBlending, depthWrite: false, transparent: true }));
    eclair.visible = false; scene.add(eclair);
    const typeDe = id => (objets.find(o => o.id === id) || {}).type;
    return { t: a.a + (a.d || 1), objet: a.objet, cible: a.cible, typeS: typeDe(a.objet), typeC: typeDe(a.cible), debris, eclair, n };
  });
  // FLAQUES (deverser) : le carburant s'étale sur la route ; s'il prend feu, les flammes couvrent toute la flaque
  const flaques = actions.filter(a => a.faire === "deverser").map(a => {
    const m = new T.Mesh(new T.CircleGeometry(1, 48), new T.MeshBasicMaterial({ color: 0x15120e, transparent: true, opacity: 0.85, depthWrite: false }));
    m.rotation.x = -Math.PI / 2; m.visible = false; scene.add(m);
    return { a, m, rayon: a.rayon ?? 9 };
  });
  // BOULES DE FEU (exploser) : sphère orange qui gonfle et s'éteint + onde de choc au sol
  const boules = actions.filter(a => a.faire === "exploser").map(a => {
    // (avant : une seule sphère en lumière additive → bulle pâle sur un sol clair, vidéo de l'Iowa du 27/11)
    // boules lumineuses aux bords doux (dégradé), qui palpitent : un disque plein faisait « dessin plat »
    const tex = (a, b) => texture(T, 128, 128, c => { const g = c.createRadialGradient(64, 64, 0, 64, 64, 64);
      g.addColorStop(0, a); g.addColorStop(0.45, b); g.addColorStop(1, "rgba(120,20,0,0)"); c.fillStyle = g; c.fillRect(0, 0, 128, 128); });
    const couches = [["rgba(255,250,220,1)", "rgba(255,200,80,.9)", 0.55], ["rgba(255,170,60,1)", "rgba(255,90,20,.85)", 0.8],
                     ["rgba(230,80,20,.95)", "rgba(140,30,10,.7)", 1.0]].flatMap(([a, b, k], n) => [0, 1, 2].map(i => {
      const m = new T.Sprite(new T.SpriteMaterial({ map: tex(a, b), transparent: true, depthWrite: false }));
      m.visible = false; scene.add(m); return { m, k: k * (1 - 0.12 * i), dx: (i - 1) * 0.35, dy: (i % 2) * 0.25, n };
    }));
    const o = new T.Mesh(new T.RingGeometry(0.9, 1, 64), new T.MeshBasicMaterial({ color: 0xffd9a0, transparent: true, depthWrite: false, side: T.DoubleSide }));
    o.rotation.x = -Math.PI / 2; o.visible = false; scene.add(o);
    const r = hasard(a.objet.length * 31 + 5), debris = [];
    for (let i = 0; i < 40; i++) { const m = new T.Mesh(new T.BoxGeometry(0.4 + r() * 1.2, 0.3 + r() * 0.6, 0.4 + r() * 1), lambert(T, ["#5a5550", "#8a9099", "#3a3632", "#a89f8c"][i % 4]));
      m.visible = false; scene.add(m); const ang = r() * 6.28; debris.push({ m, vx: Math.cos(ang) * (6 + r() * 16), vz: Math.sin(ang) * (6 + r() * 16), vy: 8 + r() * 16, rx: r() * 8 }); }
    return { a, couches, o, debris };
  });
  // JETS D'EAU (arroser) : gouttes bleutées en arc des pompiers vers le feu
  const jets = actions.filter(a => a.faire === "arroser" && a.cible).map(a => {
    const gouttes = Array.from({ length: 36 }, (_, i) => { const sp = new T.Sprite(new T.SpriteMaterial({ color: 0xbfe3ff, transparent: true, opacity: 0.8, depthWrite: false })); sp.visible = false; scene.add(sp); return { sp, ph: i / 36 }; });
    return { a, gouttes };
  });
  // anneaux jaunes au sol (« une voiture » entourée, comme dans les reconstitutions)
  const anneaux = (sc.reperes || []).filter(m => m.anneau !== false).map(m => {
    const a = new T.Mesh(new T.RingGeometry(1, 1.09, 64), new T.MeshBasicMaterial({ color: 0xffd600, transparent: true, depthWrite: false, side: T.DoubleSide }));
    a.rotation.x = -Math.PI / 2; a.position.y = 0.08; scene.add(a); return { a, m };
  });
  const etiquettes = (sc.reperes || []).map(m => { const e = el("div", "repere", couche, echapper(m.texte || "")); return e; });
  const cam = sc.camera?.length ? sc.camera : [{ a: 0, pos: [-45, 45, 55], cible: [0, 0, 0] }];   // jamais sans caméra
  const posCam = t => {                    // caméra : glisse d'un point à l'autre, et dérive toujours un peu
    let i = 0; while (i < cam.length - 1 && t >= cam[i + 1].a) i++;
    const A = cam[i], B = cam[Math.min(i + 1, cam.length - 1)], k = B === A ? 0 : ease.douce(prog(t, A.a, B.a - A.a));
    const suivre = o => { const g = groupes[o]; return g ? [g.position.x, g.position.y, g.position.z] : null; };
    const plus = (v, r) => r ? v.map((x, j) => x + r[j]) : v;
    const ca = plus((A.suivre && suivre(A.suivre)) || A.cible || [0, 0, 0], A.regard), cb = plus((B.suivre && suivre(B.suivre)) || B.cible || ca, B.regard);
    const pa = A.suivre && suivre(A.suivre) ? A.pos.map((v, j) => v + suivre(A.suivre)[j]) : A.pos;
    const pb = B.suivre && suivre(B.suivre) ? B.pos.map((v, j) => v + suivre(B.suivre)[j]) : B.pos;
    const d = 1 + 0.02 * Math.sin(t * 0.4);
    return { p: pa.map((v, j) => mix(v, pb[j], k) * (j === 1 ? 1 : d)), c: ca.map((v, j) => mix(v, cb[j], k)) };
  };
  // inondation, séisme, tempête : préparés une fois (actions « inonder », « trembler », « tempete »)
  const aIn = actions.find(a => a.faire === "inonder");
  const inondation = aIn ? { a: aIn.a, d: aIn.d || 6, hauteur: aIn.hauteur ?? 1.6,
    // eau bleu-gris trouble, qui brille et ondule : la couleur boue (vraie, mais orangée le soir) ne se lisait pas comme
    // de l'eau (avis de l'auteur du 27/11)
    plan: (() => { const tex = texture(T, 256, 256, (c, w, h) => { c.fillStyle = "#4f6f82"; c.fillRect(0, 0, w, h); const r = hasard(17);
                     for (let i = 0; i < 260; i++) { c.strokeStyle = `rgba(${r() < 0.5 ? "210,230,240" : "40,60,75"},${0.12 + r() * 0.18})`; c.lineWidth = 1 + r() * 2;
                       const x = r() * w, y = r() * h, l = 10 + r() * 30; c.beginPath(); c.moveTo(x, y); c.quadraticCurveTo(x + l / 2, y - 3, x + l, y); c.stroke(); } }, [60, 60]);
                   const m = new T.Mesh(new T.PlaneGeometry(900, 900), new T.MeshPhongMaterial({ map: tex, color: 0xffffff, transparent: true, opacity: 0.9,
                     shininess: 90, specular: 0x9fb6c4 }));
                   m.userData.tex = tex;
                   m.rotation.x = -Math.PI / 2; m.visible = false; scene.add(m); return m; })() } : null;
  const secousses = actions.filter(a => a.faire === "trembler");
  const aTe = actions.find(a => a.faire === "tempete");
  const tempete = aTe ? (() => { const n = 900, r = hasard(41), base = new Float32Array(n * 3), geo = new T.BufferGeometry();
    for (let i = 0; i < n; i++) { base[i * 3] = (r() - 0.5) * 120; base[i * 3 + 1] = r() * 40; base[i * 3 + 2] = (r() - 0.5) * 120; }
    geo.setAttribute("position", new T.BufferAttribute(new Float32Array(n * 6), 3));
    const l = new T.LineSegments(geo, new T.LineBasicMaterial({ color: 0xb8c8e0, transparent: true, opacity: 0.45 })); l.frustumCulled = false; l.visible = false; scene.add(l);
    return { a: aTe.a, force: aTe.force ?? 1, pluie: l, base }; })() : null;
  const groupesSuivis = t => {                  // l'objet filmé à cet instant (il ne « bouche » pas sa propre vue)
    let i = 0; while (i < cam.length - 1 && t >= cam[i + 1].a) i++;
    return [cam[i], cam[Math.min(i + 1, cam.length - 1)]].map(k => groupes[k.suivre]).filter(Boolean);
  };
  // un débris de l'objet filmé ne « bouche » pas la vue sur lui (il vole autour de lui au moment de l'explosion)
  const estDans = (m, gs) => gs.some(g => { if (m.userData.de === g) return true; let x = m; while (x) { if (x === g) return true; x = x.parent; } return false; });
  return (t, duree) => {
    for (const o of objets) {
      const g = groupes[o.id], e = etat(o, actions, t, objets);
      g.visible = e.visible; g.userData.ombre.visible = e.visible && e.y < 3;
      const sx = e.secousse ? Math.sin(t * 60) * 0.15 * e.secousse : 0;
      g.position.set(e.x + sx, e.y, e.z); g.rotation.set(e.roulis, e.cap, e.tangage);
      if (e.explose >= 0 && ["batiment", "entrepot", "immeuble", "maison"].includes(o.type))
        e.effondre = Math.max(e.effondre || 0, 0.55 * ease.sortie(prog(t, e.explose + 0.15, 0.8)));
      if (e.effondre != null) g.scale.y = 1 - 0.85 * e.effondre;
      g.userData.ombre.position.set(e.x, 0.03, e.z);
      for (const w of g.userData.roues || []) w.rotation.y = -e.distance / (g.userData.rayon || 0.4);
      if (g.userData.pale) g.userData.pale.rotation.y = t * 25;
      if (g.userData.anime) g.userData.anime(t);
      if (g.userData.eau) { const n = borne(prog(t, o.remplir_a ?? 0.4, o.remplir_duree ?? 2.2)) * (o.niveau ?? 1); const c = g.userData.cote; g.userData.eau.scale.y = Math.max(0.001, n); g.userData.eau.position.y = c * n / 2; }
      // explosion d'un véhicule ou d'un bâtiment : il se désintègre (pièces + éclats projetés), l'épave brûle
      // séisme : l'immeuble qui s'effondre tombe en morceaux, sur place
      if (e.effondreT != null && e.explose < 0 && t >= e.effondreT + 0.2 && ["batiment", "entrepot", "immeuble", "maison", "residence", "magasin", "hopital", "banque", "batiment_officiel"].includes(o.type)) {
        desintegrer(T, scene, g, o, g.userData.morceaux ? null : etat(o, actions, e.effondreT, objets), t, e.effondreT + 0.2, true, true);
        g.visible = false;
      }
      if (e.explose >= 0 && t >= e.explose && o.desintegrer !== false && !["foule", "personne"].includes(o.type))
        desintegrer(T, scene, g, o, g.userData.morceaux ? null : etat(o, actions, e.explose, objets), t, e.explose,
                    ["batiment", "entrepot", "immeuble", "maison", "batiment_officiel"].includes(o.type));
      // choc : l'avant de celui qui percute et l'arrière de celui qui est percuté s'écrasent un peu
      if (e.ecrase > 0) g.scale.x = 1 - 0.03 * e.ecrase;   // (l'écrasement réel est fait par « ecraser »)
      if (e.brule >= 0) g.traverse(m => { if (m.material?.color && !m.userData.brulee) { m.material = m.material.clone(); m.userData.brulee = 1; } if (m.userData.brulee) m.material.color.lerp(new T.Color(0x1d1a18), borne(prog(t, e.brule, 6)) * 0.08); });
      const ps = particules[o.id] || [];
      const debut = e.brule >= 0 ? e.brule : e.explose;
      for (const q of ps) {
        const actif = debut >= 0 && t >= debut, ta = g.userData.taille || [4, 2, 2], force = borne(prog(t, debut, 1.2));
        if (q.lueur) {                         // lueur orange qui palpite au sol sous le feu
          q.lueur.visible = actif; if (!actif) continue;
          const r = Math.max(ta[0], ta[2]) * 2.2 * force * (1 + 0.08 * Math.sin(t * 9) + 0.05 * Math.sin(t * 23));
          q.lueur.scale.set(r, r, 1); q.lueur.position.set(e.x, 0.1, e.z); q.lueur.material.opacity = 0.75 * force; continue;
        }
        const vie = q.fumee ? 3.2 : 1.1, age = ((t - debut) * q.v + q.ph * vie) % vie;
        q.s.visible = actif && !q.quarks;
        if (!actif) continue;
        const u = age / vie, vent = q.fumee ? u * u * 6 : 0;
        const hauteur = (q.fumee ? 22 : 5.5) * q.taille;
        if (q.flaque) q.s.position.set(e.x + q.dx * q.flaque * force + vent, 0.3 + u * hauteur * 0.5 * force, e.z + q.dz * q.flaque * force);
        else q.s.position.set(e.x + q.dx * ta[0] * 0.8 + vent, e.y + (q.fumee ? 3 : 0.4) + u * hauteur * force, e.z + q.dz * ta[2] * 0.9);
        const vacille = 1 + 0.25 * Math.sin(t * 17 + q.ph * 40);
        const k = (q.fumee ? mix(3, 12, u) : mix(2.6, 0.5, u) * vacille) * q.taille * force * (e.explose >= 0 && t - e.explose < 0.6 ? 2 : 1);
        q.s.scale.set(k * (q.fumee ? 1 : 0.7), k * (q.fumee ? 1 : 1.6), 1);
        q.s.material.rotation = q.fumee ? u * 2 + q.ph * 6 : 0;
      }
    }
    for (const c of trafic) {                 // ralentit puis s'arrête près d'un accident (feu, véhicule couché)
      let x = ((c.x0 + c.v * t) % 600 + 900) % 600 - 300;
      c.g.position.set(x, 0, c.z); for (const w of c.g.userData.roues || []) w.rotation.y = -c.v * t / 0.4;
    }
    if (scene.userData.eau) scene.userData.eau.position.y = -0.02 + Math.sin(t) * 0.05;

    let tremble = 0;
    for (const ch of chocs) {
      const dt = t - ch.t, g = groupes[ch.objet], ta = g?.userData.taille || [4, 2, 2];
      const px = g ? g.position.x + ta[0] * 0.5 : 0, pz = g ? g.position.z : 0;
      if (dt >= 0 && !ch.pos) ch.pos = [px, pz];
      if (dt >= 0 && !ch.cabosse) {               // la tôle des DEUX véhicules se cabosse au point d'impact
        ch.cabosse = true;
        const gc = groupes[ch.cible], point = new T.Vector3(ch.pos[0], 1.1, ch.pos[1]);
        const sens = gc ? new T.Vector3(gc.position.x - g.position.x, 0, gc.position.z - g.position.z).normalize() : new T.Vector3(1, 0, 0);
        // gravité selon les MASSES (27/11) : le plus léger encaisse le plus ; une citerne percutée se déchire toujours
        const mS = MASSES[ch.typeS] ?? 1.5, mC = MASSES[ch.typeC] ?? 1.5;
        const forceS = borne(Math.sqrt(mC / mS) * 0.8, 0.5, 1.4), forceC = borne(Math.sqrt(mS / mC) * 1.1, 0.35, 1.3);
        ecraser(T, g, sens, forceS, 307 + ch.n);                       // l'avant de celui qui percute se tasse
        ecraser(T, gc, sens.clone().negate(), ch.typeC === "citerne" ? Math.max(1.0, forceC) : forceC, 211 + ch.n);
        cabosser(T, gc, point, sens, ch.typeC === "citerne" ? 1.4 : 0.8, 213 + ch.n);
        if (ch.typeC === "citerne" && gc) ch.rupture = dechirer(T, scene, gc, point, sens, 401 + ch.n);
      }
      const [ix, iz] = ch.pos || [px, pz];
      ch.eclair.visible = dt >= 0 && dt < 0.5;
      if (ch.eclair.visible) { const k = 14 * (1 - dt / 0.5) + 4; ch.eclair.scale.set(k, k, 1); ch.eclair.position.set(ix, 1.5, iz); ch.eclair.material.opacity = 1 - dt / 0.5; }
      if (dt >= 0 && !ch.sens) {                   // sens du choc : de celui qui percute vers celui qui est percuté
        const gc = groupes[ch.cible];
        ch.sens = gc ? new T.Vector3(gc.position.x - g.position.x, 0, gc.position.z - g.position.z).normalize() : new T.Vector3(1, 0, 0);
        ch.lat = new T.Vector3(-ch.sens.z, 0, ch.sens.x);
      }
      for (const d of ch.debris) {
        d.m.visible = dt >= 0; if (dt < 0) continue;
        // petit vol (jusqu'au sol), puis glissade freinée, puis immobile
        const tVol = (d.vy + Math.sqrt(d.vy * d.vy + 2 * 9.8 * 0.9)) / 9.8, u = Math.min(dt, tVol);
        const glisse = Math.max(0, dt - tVol), g_ = Math.min(glisse, 0.7), dist = u + g_ * (1 - g_ / 1.4);
        const y = Math.max(d.piece ? 0.15 : 0.03, 1 + d.vy * u - 4.9 * u * u);
        d.m.position.set(ix + ch.sens.x * d.avant * dist + ch.lat.x * d.cote * dist, y, iz + ch.sens.z * d.avant * dist + ch.lat.z * d.cote * dist);
        const rot = u + g_ * 0.3;
        d.m.rotation.set(d.piece ? 0 : d.rx * rot, d.ry * rot, d.piece ? Math.PI / 2 * borne(u / tVol) : 0);
      }
      if (ch.rupture) for (const q of ch.rupture.jet) {   // le carburant gicle 3 s puis s'arrête
        const age = ((dt * 1.6 + q.ph) % 1), actif = dt >= 0 && dt < 3;
        q.sp.visible = actif; if (!actif) continue;
        const d = age * q.v, lat = new T.Vector3(-ch.rupture.sens.z, 0, ch.rupture.sens.x);
        q.sp.position.copy(ch.rupture.depart).addScaledVector(ch.rupture.sens, -d).addScaledVector(lat, q.ec * age);
        q.sp.position.y = Math.max(0.05, ch.rupture.depart.y - 0.3 + q.h * 0.4 + 1.2 * age - 4.9 * age * age);
        const k = 0.18 + age * 0.3; q.sp.scale.set(k, k, 1);
      }
      if (dt >= 0) tremble = Math.max(tremble, Math.max(0, 1 - dt * 1.6));
    }
    for (const f of flaques) {
      const g = groupes[f.a.objet], k = ease.sortie(prog(t, f.a.a, f.a.d || 3));
      f.m.visible = k > 0 && !!g; if (!f.m.visible) continue;
      f.m.scale.set(f.rayon * k, f.rayon * k * 0.8, 1); f.m.position.set(g.position.x, 0.05, g.position.z);
    }
    for (const x of boules) {
      const g = groupes[x.a.objet], dt = t - x.a.a, actif = dt >= 0 && dt < 2.6 && !!g;
      for (const d of x.debris) {                // débris projetés tout autour, qui retombent et restent au sol
        d.m.visible = dt >= 0 && !!g; if (!d.m.visible) continue;
        const u = Math.min(dt, (d.vy + Math.sqrt(d.vy * d.vy + 2 * 9.8 * 1.8)) / 9.8), y = Math.max(0.2, 2 + d.vy * u - 9.8 * u * u / 2);
        d.m.position.set(g.position.x + d.vx * u, y, g.position.z + d.vz * u); d.m.rotation.set(d.rx * u, d.rx * u * 0.7, 0);
      }
      x.o.visible = actif; for (const c of x.couches) c.m.visible = actif; if (!actif) continue;
      const ta = g.userData.taille || [10, 10, 10], R = (x.a.rayon ?? Math.max(10, ta[0] * 0.6)) * ease.sortie(borne(dt / 0.5));
      for (const c of x.couches) {                // cœur blanc-jaune, orange, rouge sombre qui monte et s'assombrit
        const k = 2 * R * c.k * (1 + 0.06 * Math.sin(t * 20 + c.k * 9 + c.dx * 7));
        c.m.scale.set(k, k * 0.9, 1); c.m.position.set(g.position.x + c.dx * R, k * 0.3 + c.dy * R + dt * 4 * c.k, g.position.z);
        c.m.material.opacity = Math.max(0, 0.95 - borne((dt - 0.4 * c.k) / 1.6)) * (c.k < 1 ? 1 - borne(dt / 1.2) : 1);
      }
      const o = 3 + dt * 30; x.o.scale.set(o, o, 1); x.o.position.set(g.position.x, 0.1, g.position.z); x.o.material.opacity = Math.max(0, 0.8 - dt * 0.45);
      tremble = Math.max(tremble, Math.max(0, 1.4 - dt * 1.2));
    }
    for (const j of jets) {
      const src = groupes[j.a.objet], dst = groupes[j.a.cible], actif = src && dst && t >= j.a.a;
      for (const q of j.gouttes) {
        q.sp.visible = !!actif; if (!actif) continue;
        const u = (q.ph + (t - j.a.a) * 0.9) % 1, A = src.position, B = dst.position, h = 2.5 + (src.userData.taille?.[1] || 2);
        q.sp.position.set(mix(A.x, B.x, u), h + Math.sin(Math.PI * u) * 6 - u * (h - 1.5), mix(A.z, B.z, u));
        const k = 0.5 + u * 1.4; q.sp.scale.set(k, k, 1); q.sp.material.opacity = 0.85 * (1 - u * 0.6);
      }
    }
    // SÉISME : tout tremble pendant la secousse, les bâtiments touchés s'effondrent (action « effondrer »)
    for (const q of secousses) if (t >= q.a && t < q.a + (q.d || 4)) tremble = Math.max(tremble, 1.6 * Math.sin(Math.PI * prog(t, q.a, q.d || 4)));
    const { p, c } = posCam(t);
    // INONDATION : l'eau monte dans la rue ; les véhicules flottent et dérivent quand elle dépasse leurs roues
    if (inondation) {
      const k = ease.douce(prog(t, inondation.a, inondation.d || 6)), h = mix(-0.3, inondation.hauteur ?? 1.6, k);
      inondation.plan.visible = k > 0; inondation.plan.position.y = h + Math.sin(t * 1.3) * 0.04;
      inondation.plan.userData.tex.offset.set(t * 0.012, t * 0.02);          // le courant fait bouger les vaguelettes
      for (const o of objets) {
        const g = groupes[o.id]; if (!g || !["voiture", "taxi", "camionnette", "police", "ambulance", "bus"].includes(o.type)) continue;
        if (h > 0.7) { const f = borne((h - 0.7) / 0.8); g.position.y = Math.max(g.position.y, h - 0.9); g.position.x += f * (t - inondation.a) * 0.6;
          g.rotation.y += Math.sin(t * 0.7 + o.id.length) * 0.15 * f; g.rotation.z = Math.sin(t * 1.1 + o.id.length) * 0.05 * f; }
      }
    }
    // TEMPÊTE : les arbres plient sous le vent, la pluie tombe en biais
    if (tempete) {
      const v = borne(prog(t, tempete.a, 1.5)) * (tempete.force ?? 1);
      for (const a of scene.userData.arbres || []) a.rotation.z = -v * (0.12 + 0.08 * Math.sin(t * 2.3 + a.position.x * 0.3));
      tempete.pluie.visible = v > 0;
      if (v > 0) { const pos = tempete.pluie.geometry.attributes.position; const n = pos.count / 2;
        for (let i = 0; i < n; i++) { const x0 = tempete.base[i * 3], y0 = tempete.base[i * 3 + 1], z0 = tempete.base[i * 3 + 2];
          const y = ((y0 - t * 38) % 40 + 40) % 40, x = x0 + c[0] - y * 0.35, z = z0 + c[2];
          pos.setXYZ(2 * i, x, y, z); pos.setXYZ(2 * i + 1, x + 0.5, y + 1.4, z); }
        pos.needsUpdate = true; }
    }
    if (!iso && !(cam.find(k => k.a <= t && k._cle === "interieur"))) p[1] = Math.max(p[1], c[1] + 2.2, 2.5);   // jamais au ras du sol
    const sol_ = scene.userData.soleil;
    if (sol_) {
      if (!scene.userData.ombresPretes) {        // une fois tout construit : ce qui est solide fait de l'ombre
        scene.traverse(m => { if (m.isMesh && !m.material?.transparent) { m.castShadow = true; m.receiveShadow = true; } });
        scene.userData.ombresPretes = true;
      }
      sol_.target.position.set(c[0], 0, c[2]); sol_.position.set(c[0] - 60, 120, c[2] + 40);
    }
    if (tremble > 0) { p[0] += Math.sin(t * 71) * 0.9 * tremble; p[1] += Math.sin(t * 53) * 0.7 * tremble; c[1] += Math.sin(t * 61) * 0.4 * tremble; }
    // la caméra ne traverse JAMAIS un mur, un hangar ou un débris (Iowa du 27/11 : images noires, caméra dans les éclats) :
    // si un objet solide est entre ce qu'on filme et la caméra, elle se place devant lui, un peu plus haut
    if (!iso && sc.anti_collision !== false) {
      const C = new T.Vector3(...c), P = new T.Vector3(...p), dir = P.clone().sub(C), dist = dir.length();
      if (dist > 2) {
        dir.normalize();
        const rc = scene.userData.rayon || (scene.userData.rayon = new T.Raycaster());
        rc.set(C, dir); rc.far = dist;
        const solides = scene.userData.solides || (scene.userData.solides = []);
        if (!solides.length) scene.traverse(m => { if (m.isMesh && !m.material?.transparent && m.geometry?.boundingSphere !== undefined) solides.push(m); });
        const obstacles = solides.filter(m => m.visible && !estDans(m, groupesSuivis(t)));
        const bouche = (q) => { const v = q.clone().sub(C), l = v.length(); rc.set(C, v.normalize()); rc.far = l;
                                return rc.intersectObjects(obstacles, false).find(x => x.distance > 1.5); };
        // vue bouchée : on MONTE d'abord (plan en plongée, comme un drone) ; on ne s'approche qu'en dernier recours
        // (avant : la caméra se collait au mur qui bouchait la vue, Iowa refaite du 27/11)
        if (bouche(P)) {
          // 1) tourner autour de ce qu'on filme (même distance, même hauteur) ; 2) monter ; 3) plongée en biais
          // (jamais pile au-dessus : la caméra ne saurait plus où est le haut → image cassée, Iowa refaite du 27/11)
          let libre = null;
          const tourner = a => { const v = P.clone().sub(C); const x = v.x * Math.cos(a) - v.z * Math.sin(a), z = v.x * Math.sin(a) + v.z * Math.cos(a);
                                 return new T.Vector3(C.x + x, P.y, C.z + z); };
          for (const a of [0.5, -0.5, 1.0, -1.0, 1.6, -1.6, 2.4, -2.4, Math.PI]) { const Q = tourner(a); if (!bouche(Q)) { libre = Q; break; } }
          for (const monte of [12, 25, 45]) { if (libre) break; const Q = P.clone(); Q.y += monte; if (!bouche(Q)) libre = Q; }
          if (!libre) { const Q = C.clone().add(new T.Vector3(dist * 0.35, Math.max(30, dist * 0.8), dist * 0.35)); libre = bouche(Q) ? null : Q; }
          if (libre) { p[0] = libre.x; p[1] = libre.y; p[2] = libre.z; }
          // sinon : on garde le plan prévu (voir à travers un débris vaut mieux que d'entrer dans la boule de feu, Iowa du 27/11)
        }
      }
    }
    if (iso) {                                // toujours le même angle (45°, en surplomb) ; on se rapproche doucement
      const z = mix(1, sc.iso_zoom ?? 1.25, ease.douce(prog(t, 0, Math.max(duree || 6, 1))));
      if (camera.zoom !== z) { camera.zoom = z; camera.updateProjectionMatrix(); }
      camera.position.set(c[0] - 140, c[1] + 150, c[2] + 140); camera.lookAt(...c);
    } else { camera.position.set(...p); camera.lookAt(...c); }
    camera.updateMatrixWorld();
    // anneaux et étiquettes qui suivent leur objet
    anneaux.forEach(({ a, m }) => { const g = groupes[m.objet]; if (!g) return; const v = prog(t, m.a ?? 0.5, 0.4); a.visible = v > 0 && t < (m.fin ?? (m.a ?? 0.5) + 3.5);   // l'anneau désigne, puis s'efface
      const ta = g.userData.taille || [4, 2, 2], r = Math.max(ta[0], ta[2]) * 0.6 * mix(1.5, 1, ease.sortie(v)); a.scale.set(r, r, 1); a.position.set(g.position.x, 0.08, g.position.z); a.material.opacity = v; });
    etiquettes.forEach((e, i) => {
      const m = sc.reperes[i], g = groupes[m.objet]; if (!g) return;
      const ta = g.userData.taille || [4, 2, 2], v = new T.Vector3(g.position.x, g.position.y + ta[1] + 1.2, g.position.z).project(camera);
      e.style.left = ((v.x + 1) / 2 * W) + "px"; e.style.top = ((1 - v.y) / 2 * H) + "px"; e.dataset.base = "translate(-14px,-50%)";
      if (m.fin != null && t >= m.fin) { e.style.opacity = 0; return; }
      apparition(e, t, m.a ?? 0.5);
    });
    if (avancerEffets) avancerEffets(t);
    const R = moteur(T); R.render(scene, camera);
    cx.clearRect(0, 0, W, H); cx.drawImage(R.domElement, 0, 0);
  };
}
