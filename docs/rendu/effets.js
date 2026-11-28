// Feu et fumée réalistes avec three.quarks (MIT, version 0.16 compatible Three.js r170), demande de l'auteur du 27/11.
// Des centaines de particules : flammes qui montent en tourbillonnant et changent de couleur (blanc-jaune → orange → rouge
// sombre), fumée épaisse qui gonfle, monte et dérive avec le vent, étincelles. three.quarks tire ses particules au hasard :
// pour que chaque morceau de la vidéo (rendus en parallèle) montre EXACTEMENT le même feu, le hasard est remplacé par une
// suite fixe et la simulation est rejouée depuis le début, par pas de 1/30 s, jusqu'à l'instant demandé.
import { BatchedRenderer, ParticleSystem, RenderMode } from "three.quarks";
import { ConstantValue, IntervalValue, ConstantColor, ConeEmitter, SphereEmitter, ColorOverLife, SizeOverLife, Gradient,
         PiecewiseBezier, Bezier, ApplyForce, Vector3 as V3, Vector4 as V4 } from "quarks.core";

const PAS = 1 / 30;

function suite(graine) {                     // nombres « au hasard » toujours les mêmes (Mulberry32)
  let a = graine >>> 0;
  return () => { a = (a + 0x6D2B79F5) >>> 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

function feu(T, tex, taille) {
  return new ParticleSystem({
    duration: 1, looping: true, worldSpace: true, maxParticle: 260,
    startLife: new IntervalValue(0.5, 1.1), startSpeed: new IntervalValue(2.5 * taille, 5.5 * taille),
    startSize: new IntervalValue(1.6 * taille, 3.4 * taille), startRotation: new IntervalValue(0, 6.28),
    startColor: new ConstantColor(new V4(1, 1, 1, 1)), emissionOverTime: new ConstantValue(110),
    shape: new ConeEmitter({ radius: 1.6 * taille, angle: 0.25 }),
    material: new T.MeshBasicMaterial({ map: tex, blending: T.AdditiveBlending, transparent: true, depthWrite: false }),
    renderMode: RenderMode.BillBoard,
    behaviors: [
      new ColorOverLife(new Gradient([[new V3(1, 0.95, 0.7), 0], [new V3(1, 0.55, 0.12), 0.35], [new V3(0.75, 0.16, 0.03), 0.75], [new V3(0.2, 0.05, 0.02), 1]],
                                     [[0.9, 0], [0.85, 0.5], [0, 1]])),
      new SizeOverLife(new PiecewiseBezier([[new Bezier(0.7, 1.0, 0.8, 0.25), 0]])),
      new ApplyForce(new V3(0.15, 1, 0), new ConstantValue(3 * taille)),
    ],
  });
}

function fumee(T, tex, taille) {
  return new ParticleSystem({
    duration: 1, looping: true, worldSpace: true, maxParticle: 220,
    startLife: new IntervalValue(2.8, 4.5), startSpeed: new IntervalValue(2 * taille, 4 * taille),
    startSize: new IntervalValue(2.4 * taille, 4 * taille), startRotation: new IntervalValue(0, 6.28),
    startColor: new ConstantColor(new V4(1, 1, 1, 1)), emissionOverTime: new ConstantValue(28),
    shape: new ConeEmitter({ radius: 1.8 * taille, angle: 0.35 }),
    material: new T.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }),
    renderMode: RenderMode.BillBoard,
    behaviors: [
      new ColorOverLife(new Gradient([[new V3(0.32, 0.29, 0.27), 0], [new V3(0.16, 0.15, 0.15), 0.4], [new V3(0.35, 0.35, 0.36), 1]],
                                     [[0, 0], [0.5, 0.12], [0.32, 0.6], [0, 1]])),   // plus légère : elle cachait la scène (Gizeh, 27/11)
      new SizeOverLife(new PiecewiseBezier([[new Bezier(0.6, 1.2, 1.9, 2.6), 0]])),
      new ApplyForce(new V3(1, 0.35, 0.2), new ConstantValue(1.6 * taille)),         // le vent emporte la fumée
    ],
  });
}

let TEX_POUSSIERE = null;
function texturePoussiere(T) {                // nuage doux et CLAIR (la texture de fumée, sombre, donnait une poussière noire)
  if (!TEX_POUSSIERE) {
    const c = document.createElement("canvas"); c.width = c.height = 64; const x = c.getContext("2d");
    const g = x.createRadialGradient(32, 32, 0, 32, 32, 32); g.addColorStop(0, "rgba(255,255,255,.9)"); g.addColorStop(0.55, "rgba(255,255,255,.4)"); g.addColorStop(1, "rgba(255,255,255,0)");
    x.fillStyle = g; x.fillRect(0, 0, 64, 64); TEX_POUSSIERE = new T.CanvasTexture(c);
  }
  return TEX_POUSSIERE;
}

function poussiere(T, tex, taille) {           // nuage de poussière grise d'un immeuble qui s'effondre
  return new ParticleSystem({
    duration: 1, looping: true, worldSpace: true, maxParticle: 200,
    startLife: new IntervalValue(2.5, 4), startSpeed: new IntervalValue(3 * taille, 7 * taille),
    startSize: new IntervalValue(3 * taille, 6 * taille), startRotation: new IntervalValue(0, 6.28),
    startColor: new ConstantColor(new V4(1, 1, 1, 1)), emissionOverTime: new ConstantValue(45),
    shape: new ConeEmitter({ radius: 4 * taille, angle: 1.2 }),
    material: new T.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }),
    renderMode: RenderMode.BillBoard,
    behaviors: [new ColorOverLife(new Gradient([[new V3(0.75, 0.7, 0.62), 0], [new V3(0.62, 0.6, 0.56), 1]], [[0, 0], [0.75, 0.15], [0, 1]])),
                new SizeOverLife(new PiecewiseBezier([[new Bezier(0.6, 1.3, 2, 2.6), 0]])),
                new ApplyForce(new V3(0.6, 0.15, 0.3), new ConstantValue(1.2))],
  });
}

function etincelles(T, tex, taille) {
  return new ParticleSystem({
    duration: 1, looping: true, worldSpace: true, maxParticle: 120,
    startLife: new IntervalValue(0.8, 1.8), startSpeed: new IntervalValue(5 * taille, 11 * taille),
    startSize: new IntervalValue(0.15, 0.4), startColor: new ConstantColor(new V4(1, 0.75, 0.3, 1)),
    emissionOverTime: new ConstantValue(28), shape: new SphereEmitter({ radius: 1.2 * taille, arc: 6.283, thickness: 1 }),
    material: new T.MeshBasicMaterial({ map: tex, blending: T.AdditiveBlending, transparent: true, depthWrite: false }),
    renderMode: RenderMode.BillBoard,
    behaviors: [new ApplyForce(new V3(0, -1, 0), new ConstantValue(6)),
                new ColorOverLife(new Gradient([[new V3(1, 0.9, 0.5), 0], [new V3(1, 0.4, 0.1), 1]], [[1, 0], [0, 1]]))],
  });
}

// sources : [{ debut, taille, position: t => [x, y, z] }] ; renvoie avancer(t) à appeler avant chaque image
export function creerEffets(T, scene, sources, textures, graine = 7) {
  const lot = new BatchedRenderer(); scene.add(lot);
  const hasardFixe = suite(graine);
  let tSim = 0;
  const actifs = [];
  return t => {
    if (t < tSim - 1e-6) return;               // on ne revient jamais en arrière (les images avancent toujours)
    const vrai = Math.random; Math.random = hasardFixe;
    try {
      while (tSim + PAS <= t + 1e-6) {
        tSim += PAS;
        for (const s of sources) {
          if (!s.systemes && tSim >= s.debut) {   // le feu prend à son instant (même pas de temps dans chaque morceau)
            const k = s.taille || 1;
            s.systemes = s.poussiere ? [poussiere(T, texturePoussiere(T), k)]
              : [fumee(T, textures.fumee, k), feu(T, textures.flamme, k), etincelles(T, textures.flamme, k)];
            for (const ps of s.systemes) { lot.addSystem(ps); scene.add(ps.emitter); ps.emitter.rotation.x = -Math.PI / 2; }
            actifs.push(s);
          }
        }
        for (const s of actifs) {
          // EXTINCTION (28/11) : à l'instant prévu, les flammes et les étincelles baissent en 3 s puis cessent ; la fumée
          // devient légère (l'épave fume encore) puis s'arrête 12 s plus tard
          if (s.fin != null && tSim >= s.fin && !s.poussiere) {
            const k = Math.max(0, 1 - (tSim - s.fin) / 3), [fum, fl, et] = s.systemes;
            const etape = Math.round(k * 10);
            if (etape !== s.etapeExt) {
              s.etapeExt = etape;
              fl.emissionOverTime = new ConstantValue(110 * k);
              et.emissionOverTime = new ConstantValue(28 * k * k);
              fum.emissionOverTime = new ConstantValue(tSim - s.fin > 12 ? 0 : 28 * (0.3 + 0.7 * k));
            }
            if (!s.fumeeFinie && tSim - s.fin > 12) { s.fumeeFinie = true; fum.emissionOverTime = new ConstantValue(0); fum.endEmit(); }
            // (essai du 28/11 : des braises orange restaient allumées malgré un débit nul) : les systèmes éteints sont retirés
            if (!s.flammesFinies && tSim - s.fin > 3) { s.flammesFinies = true; fl.endEmit(); et.endEmit(); }
            if (!s.flammesRetirees && tSim - s.fin > 4.5) { s.flammesRetirees = true; lot.deleteSystem(fl); lot.deleteSystem(et); }
            if (!s.fumeeRetiree && tSim - s.fin > 20) { s.fumeeRetiree = true; lot.deleteSystem(fum); }
          }
          // l'objet est ENLEVÉ (route rouverte, Gizeh r5 du 28/11) : sa fumée et ses flammes disparaissent avec lui
          if (s.disparait != null && tSim >= s.disparait && !s.toutRetire) {
            s.toutRetire = s.flammesRetirees = s.fumeeRetiree = s.fumeeFinie = s.flammesFinies = true; s.etapeExt = -1;
            for (const ps of s.systemes) { try { ps.endEmit(); lot.deleteSystem(ps); } catch (e) { /* déjà retiré */ } }
          }
          const [x, y, z] = s.position(tSim);
          s.systemes.forEach((ps, i) => ps.emitter.position.set(x, y + (i === 0 ? 2.5 * (s.taille || 1) : 0.3), z));
        }
        lot.update(PAS);
      }
    } finally { Math.random = vrai; }
  };
}
