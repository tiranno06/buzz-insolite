// Scènes 3D des vidéos « 100 % fabriquées » : reconstitutions simples (style maquette, comme curioverse.actu) et objets de
// comparaison (cube d'eau…). Tout est construit ici avec des formes simples : aucune image ni modèle 3D d'ailleurs.
// Une scène décrit : un décor, des objets (id, type, position), des actions dans le temps, une caméra, des repères.
// Les actions sont rejouées depuis le début à chaque image : la même seconde donne toujours la même image.
import { ZONE, borne, prog, ease, mix, hasard, el, echapper, couleur, apparition } from "./moteur.js";

const W = 1080, H = 1920;
let RENDU = null;                         // un seul moteur WebGL pour toutes les scènes (le navigateur en limite le nombre)
function moteur(THREE) {
  if (!RENDU) {
    RENDU = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, alpha: true });
    RENDU.setPixelRatio(1); RENDU.setSize(W, H, false);
    RENDU.outputColorSpace = THREE.SRGBColorSpace;
    RENDU.toneMapping = THREE.ACESFilmicToneMapping; RENDU.toneMappingExposure = 1.05;
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
    const cab = boite(T, 2.4, 2.6, 2.5, lambert(T, o.couleur || "#f2f2f2")); cab.position.set(4.6, 1.9, 0); g.add(cab);
    const vit = boite(T, 0.1, 1.0, 2.2, lambert(T, "#26303f")); vit.position.set(5.82, 2.5, 0); g.add(vit);
    const cu = new T.Mesh(new T.CylinderGeometry(1.25, 1.25, 8.6, 24), new T.MeshLambertMaterial({ color: 0xe7ebf0 }));
    cu.rotation.z = Math.PI / 2; cu.position.set(-1.2, 2.25, 0); g.add(cu);
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

// ------------------------------------------------------------------ décors
function decor(T, scene, sc) {
  const d = sc.decor || "autoroute", nuit = (sc.moment || "soir") !== "jour";
  const ciel = { jour: [0x9cc9ff, 0xdfeeff], soir: [0x1d2a4a, 0x3b4f7a], nuit: [0x070b16, 0x141d33] }[sc.moment || "soir"];
  // ciel en dégradé (horizon plus clair) et brume : la profondeur d'une vraie maquette filmée
  const degrade = { jour: ["#5d9be0", "#cfe4ff"], soir: ["#0f1a33", "#4a5d8c"], nuit: ["#03060f", "#1a2442"] }[sc.moment || "soir"];
  scene.background = texture(T, 4, 256, (c, w, h) => { const g = c.createLinearGradient(0, 0, 0, h); g.addColorStop(0, degrade[0]); g.addColorStop(0.75, degrade[1]); g.addColorStop(1, degrade[1]); c.fillStyle = g; c.fillRect(0, 0, w, h); });
  scene.background.wrapS = scene.background.wrapT = T.ClampToEdgeWrapping; scene.background.repeat.set(1, 1);
  scene.fog = new T.Fog(ciel[1], 140, sc.brouillard || 480);
  scene.add(new T.HemisphereLight(nuit ? 0x8fa6d6 : 0xffffff, nuit ? 0x1a1f2b : 0x6d6a5f, nuit ? 1.1 : 1.6));
  const soleil = new T.DirectionalLight(nuit ? 0xb7c7ff : 0xffffff, nuit ? 1.2 : 2.2); soleil.position.set(-60, 120, 40); scene.add(soleil);
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
      const b = FABRIQUES.batiment(T, { hauteur: r() < 0.15 ? 40 + r() * 30 : 8 + r() * 26, largeur: 9 + r() * 10, profondeur: 9 + r() * 8,
                                        graine: Math.floor(r() * 99), nuit });
      b.position.set(x, 0, cote * (larg / 2 + 12 + r() * 10) + (cote > 0 ? 25 : 0)); if (cote > 0) b.scale.y = 0.5; scene.add(b);
    }
    if (d === "route") for (let x = -300; x < 300; x += 8 + r() * 14) for (const cote of [-1, 1]) { const a = FABRIQUES.arbre(T, {}); a.position.set(x, 0, cote * (larg / 2 + 4 + r() * 20)); scene.add(a); }
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
    scene.userData.voies = { larg, n: voies };
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
  } else sol(0x3a4a35);                  // campagne
}

// ------------------------------------------------------------------ état des objets à l'instant t (actions rejouées)
function etat(o, actions, t, objets) {
  const e = { x: o.x || 0, y: o.y || 0, z: o.z || 0, cap: (o.cap || 0) * Math.PI / 180, roulis: 0, tangage: 0, brule: -1, visible: o.a == null || t >= o.a, distance: 0, explose: -1, secousse: 0 };
  for (const a of actions.filter(a => a.objet === o.id).sort((p, q) => p.a - q.a)) {
    if (t < a.a) break;
    const d = a.d || 1, p = prog(t, a.a, d), k = a.faire === "avancer" || a.faire === "changer_voie" ? p : ease.douce(p);
    if (["avancer", "heurter", "changer_voie", "tomber", "voler"].includes(a.faire)) {
      let [vx, vz] = a.vers || [e.x, e.z];
      if (a.faire === "heurter" && a.cible) { const c = objets.find(x => x.id === a.cible); if (c) { vx = (c.x || 0) - (a.ecart ?? 6); vz = c.z || 0; } }
      const vy = a.faire === "tomber" ? (a.vers?.[2] ?? 0) : a.faire === "voler" ? (a.vers?.[2] ?? e.y) : e.y;
      const ax = e.x, az = e.z, ay = e.y;
      e.x = mix(ax, vx, k); e.z = mix(az, vz, k); e.y = mix(ay, vy, a.faire === "tomber" ? p * p : k);
      e.distance += Math.hypot(vx - ax, vz - az) * k;
      if (a.faire === "tomber") e.tangage = mix(0, (a.angle ?? -35) * Math.PI / 180, ease.sortie(p));
      if (a.faire === "heurter") e.secousse = Math.max(e.secousse, p >= 1 ? Math.max(0, 1 - (t - a.a - d) * 2.5) : 0);
    }
    if (a.faire === "tourner") e.cap += (a.angle || 90) * Math.PI / 180 * k;
    if (a.faire === "se_coucher") { e.roulis = (a.angle ?? 90) * Math.PI / 180 * ease.sortie(p); e.y += 0.6 * Math.sin(Math.PI * p); }
    if (a.faire === "couler") { e.roulis = (a.angle ?? 25) * Math.PI / 180 * k; e.y = mix(e.y, -(a.profondeur ?? 6), k); }
    if (a.faire === "bruler" && e.brule < 0) e.brule = a.a;
    if (a.faire === "exploser" && e.explose < 0) e.explose = a.a;
    if (a.faire === "disparaitre") e.visible = t < a.a;
    if (a.faire === "apparaitre") e.visible = true;
  }
  return e;
}

// ------------------------------------------------------------------ feu (particules dessinées, toujours les mêmes)
function feu(T) {
  const tex = texture(T, 64, 64, (c) => { const g = c.createRadialGradient(32, 32, 0, 32, 32, 32); g.addColorStop(0, "rgba(255,240,180,1)"); g.addColorStop(0.35, "rgba(255,140,30,.9)"); g.addColorStop(1, "rgba(255,60,0,0)"); c.fillStyle = g; c.fillRect(0, 0, 64, 64); });
  const fum = texture(T, 64, 64, (c) => { const g = c.createRadialGradient(32, 32, 0, 32, 32, 32); g.addColorStop(0, "rgba(40,40,45,.75)"); g.addColorStop(1, "rgba(40,40,45,0)"); c.fillStyle = g; c.fillRect(0, 0, 64, 64); });
  return { flamme: new T.SpriteMaterial({ map: tex, blending: T.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.55 }), fumee: new T.SpriteMaterial({ map: fum, depthWrite: false, transparent: true, opacity: 0.5 }) };
}

// ------------------------------------------------------------------ la scène
export async function creer3d(sc, couche, T) {
  const cv = el("canvas", "", couche); cv.width = W; cv.height = H; const cx = cv.getContext("2d");
  const scene = new T.Scene(); decor(T, scene, sc);
  const camera = new T.PerspectiveCamera(sc.focale ?? 40, W / H, 0.5, 3000);
  const objets = sc.objets || [], actions = sc.actions || [], MATS = feu(T);
  const groupes = {};
  for (const o of objets) {
    const g = (FABRIQUES[o.type] || FABRIQUES.voiture)(T, o); scene.add(g); groupes[o.id] = g;
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
        const g = FABRIQUES[type](T, { couleur: COUL[Math.floor(rr() * COUL.length)] }); g.rotation.y = sens > 0 ? 0 : Math.PI; scene.add(g);
        trafic.push({ g, z, sens, x0: -300 + rr() * 600, v: (sens > 0 ? 1 : -1) * (14 + rr() * 10) });
      }
    }
  }
  // flammes et fumée : un lot de particules par objet qui brûle
  const particules = {};
  for (const a of actions.filter(a => a.faire === "bruler" || a.faire === "exploser")) {
    const r = hasard(a.objet.length * 97 + 13), liste = [];
    for (let i = 0; i < (a.faire === "exploser" ? 50 : 60); i++) {
      const s = new T.Sprite(i % 3 ? MATS.flamme : MATS.fumee); scene.add(s);
      liste.push({ s, ph: r(), dx: (r() - 0.5), dz: (r() - 0.5), v: 0.6 + r() * 0.8, fumee: !(i % 3), taille: a.taille ?? 1 });
    }
    particules[a.objet] = (particules[a.objet] || []).concat(liste);
  }
  // anneaux jaunes au sol (« une voiture » entourée, comme dans les reconstitutions)
  const anneaux = (sc.reperes || []).filter(m => m.anneau !== false).map(m => {
    const a = new T.Mesh(new T.RingGeometry(1, 1.09, 64), new T.MeshBasicMaterial({ color: 0xffd600, transparent: true, depthWrite: false, side: T.DoubleSide }));
    a.rotation.x = -Math.PI / 2; a.position.y = 0.08; scene.add(a); return { a, m };
  });
  const etiquettes = (sc.reperes || []).map(m => { const e = el("div", "repere", couche, echapper(m.texte || "")); return e; });
  const cam = sc.camera || [{ a: 0, pos: [-45, 45, 55], cible: [0, 0, 0] }];
  const posCam = t => {                    // caméra : glisse d'un point à l'autre, et dérive toujours un peu
    let i = 0; while (i < cam.length - 1 && t >= cam[i + 1].a) i++;
    const A = cam[i], B = cam[Math.min(i + 1, cam.length - 1)], k = B === A ? 0 : ease.douce(prog(t, A.a, B.a - A.a));
    const suivre = o => { const g = groupes[o]; return g ? [g.position.x, g.position.y, g.position.z] : null; };
    const ca = (A.suivre && suivre(A.suivre)) || A.cible || [0, 0, 0], cb = (B.suivre && suivre(B.suivre)) || B.cible || ca;
    const pa = A.suivre && suivre(A.suivre) ? A.pos.map((v, j) => v + suivre(A.suivre)[j]) : A.pos;
    const pb = B.suivre && suivre(B.suivre) ? B.pos.map((v, j) => v + suivre(B.suivre)[j]) : B.pos;
    const d = 1 + 0.02 * Math.sin(t * 0.4);
    return { p: pa.map((v, j) => mix(v, pb[j], k) * (j === 1 ? 1 : d)), c: ca.map((v, j) => mix(v, cb[j], k)) };
  };
  return (t, duree) => {
    for (const o of objets) {
      const g = groupes[o.id], e = etat(o, actions, t, objets);
      g.visible = e.visible; g.userData.ombre.visible = e.visible && e.y < 3;
      const sx = e.secousse ? Math.sin(t * 60) * 0.15 * e.secousse : 0;
      g.position.set(e.x + sx, e.y, e.z); g.rotation.set(e.roulis, e.cap, e.tangage);
      g.userData.ombre.position.set(e.x, 0.03, e.z);
      for (const w of g.userData.roues || []) w.rotation.y = -e.distance / (g.userData.rayon || 0.4);
      if (g.userData.pale) g.userData.pale.rotation.y = t * 25;
      if (g.userData.eau) { const n = borne(prog(t, o.remplir_a ?? 0.4, o.remplir_duree ?? 2.2)) * (o.niveau ?? 1); const c = g.userData.cote; g.userData.eau.scale.y = Math.max(0.001, n); g.userData.eau.position.y = c * n / 2; }
      if (e.brule >= 0) g.traverse(m => { if (m.material?.color && !m.userData.brulee) { m.material = m.material.clone(); m.userData.brulee = 1; } if (m.userData.brulee) m.material.color.lerp(new T.Color(0x1d1a18), borne(prog(t, e.brule, 6)) * 0.08); });
      const ps = particules[o.id] || [];
      const debut = e.brule >= 0 ? e.brule : e.explose;
      for (const q of ps) {
        const vie = 1.6, age = ((t - debut) * q.v + q.ph * vie) % vie, actif = debut >= 0 && t >= debut;
        q.s.visible = actif;
        if (!actif) continue;
        const force = borne(prog(t, debut, 1.2)), ta = g.userData.taille || [4, 2, 2], u = age / vie;
        const hauteur = (q.fumee ? 16 : 6) * q.taille;
        q.s.position.set(e.x + q.dx * ta[0] * 0.7, e.y + 0.6 + u * hauteur * force, e.z + q.dz * ta[2] * 0.9);
        const k = (q.fumee ? mix(2.5, 9, u) : mix(2.2, 0.4, u)) * q.taille * force * (e.explose >= 0 && t - e.explose < 0.6 ? 2 : 1);
        q.s.scale.set(k, k * (q.fumee ? 1 : 1.5), 1);
      }
    }
    for (const c of trafic) {                 // ralentit puis s'arrête près d'un accident (feu, véhicule couché)
      let x = ((c.x0 + c.v * t) % 600 + 900) % 600 - 300;
      c.g.position.set(x, 0, c.z); for (const w of c.g.userData.roues || []) w.rotation.y = -c.v * t / 0.4;
    }
    if (scene.userData.eau) scene.userData.eau.position.y = -0.02 + Math.sin(t) * 0.05;
    const { p, c } = posCam(t);
    camera.position.set(...p); camera.lookAt(...c);
    camera.updateMatrixWorld();
    // anneaux et étiquettes qui suivent leur objet
    anneaux.forEach(({ a, m }) => { const g = groupes[m.objet]; if (!g) return; const v = prog(t, m.a ?? 0.5, 0.4); a.visible = v > 0 && (m.fin == null || t < m.fin);
      const ta = g.userData.taille || [4, 2, 2], r = Math.max(ta[0], ta[2]) * 0.6 * mix(1.5, 1, ease.sortie(v)); a.scale.set(r, r, 1); a.position.set(g.position.x, 0.08, g.position.z); a.material.opacity = v; });
    etiquettes.forEach((e, i) => {
      const m = sc.reperes[i], g = groupes[m.objet]; if (!g) return;
      const ta = g.userData.taille || [4, 2, 2], v = new T.Vector3(g.position.x, g.position.y + ta[1] + 1.2, g.position.z).project(camera);
      e.style.left = ((v.x + 1) / 2 * W) + "px"; e.style.top = ((1 - v.y) / 2 * H) + "px"; e.dataset.base = "translate(-14px,-50%)";
      if (m.fin != null && t >= m.fin) { e.style.opacity = 0; return; }
      apparition(e, t, m.a ?? 0.5);
    });
    const R = moteur(T); R.render(scene, camera);
    cx.clearRect(0, 0, W, H); cx.drawImage(R.domElement, 0, 0);
  };
}
