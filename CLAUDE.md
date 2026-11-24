# Buzz Insolite (buzz-insolite)

Robot de vidéos TikTok « Buzz et insolite » : il repère les actualités françaises et européennes qui buzzent sur TikTok, écrit
une vidéo ORIGINALE sur le sujet (articles de presse + vraies images libres de droits + voix de synthèse) et la publie par Buffer.
Projet frère de `jt-auto` (@petitsdramas) et `grok-tiktok`. Le propriétaire est débutant : tout en français (code,
commentaires, commits, textes du site), explications simples, sans jargon.

## Choix du propriétaire (24/11/2026)
- **Tout gratuit** : GitHub Actions (dépôt public = minutes illimitées), IA gratuites (Mistral, Groq, Gemini, OpenRouter,
  mêmes clés que jt-auto), Piper (voix), Whisper (calage des mots), Pexels / NASA / Wikimedia (images), ffmpeg, Buffer gratuit.
  Ne jamais brancher un service payant.
- **Thème** : buzz et actualité insolite, France et Europe. Seuils du buzz : ≥ 500 000 vues, ≥ 10 000 j'aime, ≥ 1 000
  commentaires (réglables sur le site). « Rien à éviter » comme sujet, mais les règles légales restent (pas de nom de victime
  ni de mineur, présomption d'innocence, faits vérifiés) : `ecrire.REGLES_SUJET`.
- **Jamais la vidéo d'un autre compte** : on ne garde que le SUJET et les chiffres d'une vidéo virale ; les faits viennent de
  la presse, les images de banques libres. C'est ce qui rend la chaîne originale et payable par TikTok (Creator Rewards :
  vidéos de plus d'1 minute, `video.duree_min` 62 s).
- **Style validé sur l'essai « 1 an sur Mars »** : voix Piper « Tom » (`fr_FR-tom-medium`, length-scale 0,80, noise 0,75 /
  0,9), pauses de 0,18 s, silences coupés ; vraie vidéo nette au milieu + la même floutée derrière ; étiquette rouge
  « INSOLITE » + gros titre jaune en haut ; sous-titres karaoké Poppins (3 mots, le mot dit en jaune et grossi à 112 %, calé
  sur la voix par Whisper « small ») ; dernier écran « ET TOI ? dis-le en commentaire » ; crédits des images en bas.
- **Publication** : les deux modes au choix (`publication.mode` : « cocher » = le propriétaire coche « À publier » ; « auto » =
  les vidéos aux faits vérifiés vont directement dans la file) ; **2 vidéos par jour** (12:30 et 19:00 par défaut).
  Boutons « Publier maintenant » (Buffer, partage immédiat). Buffer est partagé avec @petitsdramas : le compte TikTok de la
  chaîne doit être écrit dans Réglages → Publication (`publication.compte`).
- Description : texte + question + 4 à 6 hashtags (2 du sujet, 2 des vidéos virales du même sujet, les fixes de la chaîne).

## Fonctionnement
- `robot/buzz.py` (buzz.yml, toutes les 2 h) : yt-dlp lit les comptes d'actualité suivis (`buzz.comptes`), garde les vidéos
  au-dessus des seuils, l'IA les regroupe par sujet → `docs/donnees/buzz.json` (statut nouveau / utilise / ignore / sans_source).
- `robot/principal.py` (creer.yml : bouton Créer, série 1-10, sujet du buzz ou sujet libre, création automatique lancée par la
  garde) : `sources.chercher` (flux RSS + Google Actualités, jamais de contournement d'un refus) → `ecrire.ecrire` (IA) →
  `ecrire.verifier` (2e IA d'un AUTRE fournisseur, phrases corrigées ou retirées) → `voix.dire` + `voix.mots_entendus` →
  `images.trouver` (Pexels vidéo → Pexels photo → NASA si sujet d'espace, début au tiers → Wikimedia, 4 s entre deux recherches)
  → `montage.monter` → Release `v-<id>` (adresse publique pour Buffer) → `docs/donnees/file.json` + miniature.
- `robot/publication_auto.py` (garde.yml, toutes les 15 min) : créneaux de publication et de création (valables 3 h).
  **Buffer est appelé UNE seule fois, AVANT `depot.enregistrer`** (qui peut se répéter) : sinon double publication.
- `robot/commande.py` (commande.yml) : ordres du site. `robot/avancement.py` : barre de progression (branche `avancement`).
- Site `docs/index.html` (GitHub Pages, main /docs) : onglets Buzz, Vidéos, Créer, Publication, Journal, Réglages ; clé
  GitHub fine-grained du navigateur (`bi_jeton`, droits Actions + Contents) ; mode démo sans données.
- Secrets : `BUFFER_API_KEY`, `PEXELS_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`.

## Avant d'envoyer
`python -m unittest discover -s tests` (aucun appel réseau ni IA ; ffmpeg nécessaire pour l'essai complet). Essai sans IA :
`SIMULATION=1 python -m robot.principal --libre "Essai"`. Site : servir `docs/` et l'ouvrir à 400 px de large.
