# Buzz Insolite (buzz-insolite)

**LANGUE OBLIGATOIRE : toujours répondre à l'auteur EN FRANÇAIS** (messages, explications, résumés, questions), sans exception, même après une reprise de conversation ou un résumé automatique (exigence de l'auteur du 27/11).

Robot de vidéos TikTok « Buzz et insolite » : il repère les actualités du monde entier qui buzzent sur TikTok, écrit
une vidéo ORIGINALE sur le sujet (articles de presse + vraies images libres de droits + voix de synthèse) et la publie par Buffer.
Projet frère de `jt-auto` (@petitsdramas) et `grok-tiktok`. Le propriétaire est débutant : tout en français (code,
commentaires, commits, textes du site), explications simples, sans jargon.

## Choix du propriétaire (24/11/2026)
- **Tout gratuit** : GitHub Actions (dépôt public = minutes illimitées), IA gratuites (Mistral, Groq, Gemini, OpenRouter,
  mêmes clés que jt-auto), Piper (voix), Whisper (calage des mots), Pexels / NASA / Wikimedia (images), ffmpeg, Buffer gratuit.
  Ne jamais brancher un service payant.
- **Thème** : buzz et actualité insolite du MONDE ENTIER (demande de l'auteur du 24/11 ; avant : France et Europe). 14 comptes
  internationaux ajoutés (bbcnews, cnn, dailymail, unilad, ladbible, washingtonpost, nytimes, cbsnews, skynews, abcnews, insider,
  aljazeeraenglish, reuters, foxnews ; theguardian illisible) ; l'IA donne titres en français + `mots_cles_en` ; presse en anglais
  (`sources.bing(langue="en")`) et vidéos libres cherchées aussi en anglais ; la vidéo reste en français. Seuils du buzz : ≥ 500 000 vues, ≥ 10 000 j'aime, ≥ 1 000
  commentaires (réglables sur le site). « Rien à éviter » comme sujet, mais les règles légales restent (pas de nom de victime
  ni de mineur, présomption d'innocence, faits vérifiés) : `ecrire.REGLES_SUJET`.
- **Courtes citations des vidéos d'origine** (choix de l'auteur du 25/11, après explication des risques ; remplace « jamais
  la vidéo d'un autre compte ») : `robot/citations.py` + `principal.placer_citations`. Extraits de 10 à 15 s des vidéos
  virales d'origine du sujet (`sujet["videos"]`, les plus vues d'abord, `video.citations_nombre` 5 au plus) : un par vidéo
  d'abord, puis d'autres passages des mêmes vidéos (autorisé par l'auteur le 25/11) sans que l'ensemble repris d'une vidéo
  dépasse la MOITIÉ de sa durée (`PART_TOTALE` ; une vidéo de 24 s = 1 extrait) ; 40 % de la vidéo par extrait au plus
  (10 s au moins ; vidéo de moins de 20 s non citée), moments où l'image bouge le plus, sans chevauchement (`moments`), son d'origine coupé, vidéo montrée en ENTIER (ni recadrée
  ni floutée : logo et encadré du journaliste visibles — l'auteur demandait de les flouter : REFUSÉ, cela cache la source),
  bandeau court « @compte » sous le titre (`calque(source=)`, raccourci à la demande de l'auteur du 25/11), crédit + preuve « courte citation ». Le 1er
  extrait sur l'accroche, les autres répartis ; scène trop courte prolongée par la suivante. Pas jugés par l'IA des
  images (c'est l'événement lui-même) ; gardés par « Refaire » (images). Vidéo entière jamais gardée. Le reste de la
  vidéo : notre texte, notre voix, les images libres.
  **Toutes les sources** (demande de l'auteur du 25/11) : le relevé du buzz garde TOUTES les vidéos lues sur les 28 comptes
  (`buzz.garder_videos_lues` → `docs/donnees/videos_lues.json`, 7 jours, même sous les seuils) ; `citations.videos_du_meme_evenement`
  y prend celles du MÊME événement (2 mots en commun, puis confirmation par l'IA `CONSIGNE_MEME_EVENEMENT` ; sans IA : 3 mots),
  12 vidéos au plus. **Images fixes de l'événement** (`images_fixes`, `video.citations_photos` 3) : tirées des vidéos d'origine
  hors des extraits (les vidéos trop courtes pour un extrait d'abord), montrées en entier avec le bandeau ; placement mêlé
  (2 extraits, 1 image…). Essai CAN : Brut + franceinfo (extraits), HugoDécrypte + 20 Minutes (images fixes).
  **Maximum d'extraits + photos de presse** (demande de l'auteur du 25/11) : `video.citations_nombre` 12 (1 à 15) ; les
  extraits vidéo sont répartis sur toutes les scènes possibles (le 1er en accroche), puis les images fixes meublent les
  scènes restantes : images tirées des vidéos d'origine, puis **photos des articles** (`sources.images_de_page` : og:image,
  twitter:image, grandes photos du corps de l'article ; `citations.photos_presse` : 600 px au moins, sans doublon d'agence
  par empreinte `_empreinte`, confirmées par l'IA qui voit `CONSIGNE_PHOTOS_PRESSE` ; bandeau et crédit « Photo : média »).
  **Sous-titres sur bandeau noir** pendant une citation (style ASS « B », `montage.karaoke`) : les vidéos d'origine ont leurs
  propres sous-titres incrustés au même endroit (vidéo CAN r9 du 25/11 : 12/12 écrans de l'événement — Al Jazeera, BBC,
  franceinfo — mais « sous-titre anglais illisible ») ; ligne des crédits sur fond sombre aussi.
  **Audit de la vidéo CAN r9 (25/11, demandé par l'auteur) et corrections** : hashtags « #c #a #n #2 » (chaîne de l'IA découpée
  en lettres → `ecrire.liste_hashtags`, 3 lettres au moins) ; « président sénégalais » pour le président de la FÉDÉRATION
  laissé par un modèle 20b → `CONSIGNE_VERIF` contrôle fonctions / dates / scores / contradictions, et 2e vérification par
  un autre fournisseur si le 1er est un petit modèle ; « Imaginez… / Dis-le » → tutoiement partout ; contrôle final : 12 tours
  (56 min) et l'accroche d'Al Jazeera remplacée par une photo Wikipédia à cause des sous-titres de la vidéo d'origine → un
  extrait n'est JAMAIS remplacé pour un texte (`CONSIGNE_FINALE` : les textes de la vidéo d'origine font partie de l'image) ;
  7 extraits sur 10 d'Al Jazeera (anglais) → comptes français d'abord (`COMPTES_FR`), 3 extraits par compte au plus
  (`PARCOMPTE_MAX`) ; Brut / BFM / HugoDécrypte refusés une fois par TikTok → 3 essais simples espacés (`telecharger`, jamais
  de contournement) ; même titre jaune sur 2 écrans de suite → affiché une fois.
  Durée : le contrôle final exige 61 s au moins (TikTok paie les vidéos de PLUS d'1 minute ; texte visé 62 s). Durée TikTok : `video.duree_min` 62 s.
- **Style validé sur l'essai « 1 an sur Mars »** : voix Piper « Tom » au départ (remplacée par Kokoro, voir plus bas), pauses de 0,18 s, silences coupés ; vraie vidéo nette au milieu + la même floutée derrière ; étiquette rouge
  « INSOLITE » + gros titre jaune en haut ; sous-titres karaoké Poppins (3 mots, le mot dit en jaune et grossi à 112 %, calé
  sur la voix par Whisper « small ») ; dernier écran « ET TOI ? dis-le en commentaire » ; crédits des images en bas.
- **Publication** : les deux modes au choix (`publication.mode` : « cocher » = le propriétaire coche « À publier » ; « auto » =
  les vidéos aux faits vérifiés vont directement dans la file) ; **2 vidéos par jour** (12:30 et 19:00 par défaut).
  Boutons « Publier maintenant » (Buffer, partage immédiat). Buffer est partagé avec @petitsdramas : le compte TikTok de la
  chaîne doit être écrit dans Réglages → Publication (`publication.compte`).
- Description : texte + question + 4 à 6 hashtags (2 du sujet, 2 des vidéos virales du même sujet, les fixes de la chaîne).

## Ajouts du 24/11/2026 (l'auteur : « ajoute tout »)
- **Voix Kokoro** (`voix.KOKORO`, Apache 2.0, kokoro-onnx, modèle téléchargé une fois depuis les releases GitHub de
  kokoro-onnx) : Piper jugé « très robotique » par l'auteur. Une seule voix française (femme, `kokoro-ff_siwis`) ; 3 voix d'homme
  d'autres langues qui parlent français aussi bien comprises par Whisper (essai du 24/11) : `kokoro-pm_alex`, `kokoro-em_alex`,
  `kokoro-am_fenrir`. Piper reste au choix. Vitesse Kokoro = 0,92 / `video.vitesse`.
- **Voix choisie par l'auteur le 24/11 (après comparaison) : homme français sans accent, Chatterbox Multilingual** (Resemble AI,
  MIT ; `voix.CHATTERBOX` = "chatterbox-bernard", défaut) qui imite sons/voix/bernard.wav (14 s de LibriVox, domaine public).
  Tourne dans son propre espace Python (`robot/chatterbox_voix.py`, ~/venv-chatterbox + modèle Hugging Face en cache dans
  creer.yml, `CHATTERBOX_PYTHON`) : ses bibliothèques gêneraient les autres. ~6 s de calcul par seconde de voix ; accéléré
  ×1,15 (atempo = 0,92 / `video.vitesse`) ; phrase comprise à moins de 75 % par Whisper = refaite une fois ; Chatterbox en
  panne = Kokoro femme pour la vidéo (`voix.preparer`). Kokoro (femme) aimée aussi ; les voix Kokoro d'homme ont un accent
  (refusées par l'auteur).
- **Logo de la chaîne : A** (choix de l'auteur du 24/11, `docs/marque/logo-a.png`, dessiné par `outils/logos.py`) : photo de
  profil TikTok, et en petit (130 px, rond, liseré blanc) en haut à droite de chaque écran des vidéos (`montage.calque`,
  `LOGO_XY`). Nom « Buzz Insolite », bio et conseils : `docs/marque/LISEZMOI.md` et Réglages → 🏪 Ma chaîne.
- **Carte animée** (`robot/carte.py`, `video.carte`) : 2e écran, zoom ×1 → ×4 sur le lieu de l'actu (champ "lieu" de l'IA),
  pays en rouge sombre, épingle ; frontières Natural Earth ; lieu trouvé par Photon puis Nominatim (qui répond 629 aux serveurs
  partagés), sinon "coordonnees" données par l'IA.
- **Bande son** (`robot/sons.py`, `video.musique`, `video.bruitages`) : musique libre (sons/musique, ACE-Step Apache 2.0, humeur
  « neutre / tension / joie » choisie par l'IA) très basse et qui s'efface sous la voix ; TOUS les bruitages COUPÉS par défaut le 24/11 (15 essais écoutés, aucun retenu : `video.bruitages` false) ; woosh entre les écrans COUPÉ (l'auteur ne l'aime pas, 24/11 ;
  `video.transitions`), ding sur les chiffres, « dun dun » sur la réponse d'un vrai / faux (sons/LICENCES.md).
- **Formats** (`ecrire.FORMATS`, entrée `format` de creer.yml) : « buzz », « vrai_faux » (affirmation, compte à rebours, réponse
  VRAI ! / FAUX ! en couleur, champ "reponse" jamais retiré par la vérification), « semaine » (3 meilleurs sujets des 7 jours,
  N°3 → N°1). Création automatique : 1 vidéo sur `creation.formats.vrai_faux` (3) en vrai / faux, « semaine » le dimanche au
  dernier créneau (`publication_auto.format_auto`).
- **Statistiques** (`robot/stats.py`, stats.yml toutes les 3 h, `publication.chaine` = pseudo TikTok de la chaîne) : vues /
  j'aime / commentaires de nos vidéos retrouvées (heure ±3 h + mots de la description), meilleures heures (2 vidéos par heure
  au moins), formats, musiques, hashtags qui marchent → stats.json, onglet 📊 Stats ; `publication.heures_auto` = publier aux
  meilleures heures.

- **Voix proposées sur le site** (demande de l'auteur du 25/11) : seulement les 2 voix non robotiques retenues — Homme
  (`chatterbox-bernard`, par défaut) et Femme (`kokoro-ff_siwis`). Les autres restent dans le code (secours) mais ne sont
  plus proposées.

## Contrôle qualité en 4 niveaux (demande de l'auteur du 24/11 : « comme l'autre projet », correction du seul passage fautif)
`robot/controle.py` (détail en tête du fichier) : 1. texte (`controle_texte` : faits par la 2e IA + règles, nombres en lettres
`robot/nombres.py`, durée estimée à 3,5 mots/s, seules les phrases fautives réécrites puis revérifiées) ; 2. voix (`voix.preparer` :
Whisper + voix qui traîne, phrase refaite) ; 3. images (`controle_images` : noir / flou mesurés, IA qui voit `ia.regarder_json`
Gemini → Mistral → Groq par paquets de 5 ; écran fautif = nouvelle image, sinon écran de texte) ; 4. vidéo finie
(`controle_video` : format, durée, son, écrans noirs, réécoute Whisper phrase par phrase, IA sur une image de chaque écran ;
`corriger_ecrans` + `montage.monter` qui ne refait que les écrans dont la signature a changé) ; 5. avant publication
(`verifier_et_envoyer`, `Refusee`). Bulletin + note /100 dans `controles` de chaque vidéo ; défaut grave restant = statut
« a_verifier » (jamais publiée automatiquement ; bouton « Publier quand même » = action `publier_force`).

**ZÉRO problème restant (exigence de l'auteur du 24/11)** : chaque problème reste « ouvert » dans le `Bulletin` jusqu'à ce que
la revérification du passage le trouve réglé (`ouvrir` / `fermer`, phrases repérées par `uid`) ; boucles jusqu'à zéro (texte
4 tours, images 5, vidéo finie 4 depuis le 25/11) avec une échelle de solutions dont la dernière marche à coup sûr : image → nouvelle
recherche → thème → écran de texte ; titre → raccourci → retiré ; voix → refaite → phrase simplifiée par l'IA → phrase retirée
(si la vidéo reste ≥ 62 s) ; phrase / accroche trop longue → coupée en deux ; question finale → question type ; vidéo trop
courte → phrases ajoutées, sinon sujet abandonné (LookupError). Note = 100 sans problème restant ; un contrôle impossible
(IA en panne après 3 essais espacés d'1 min) = « a_verifier ».

## Plus jamais une vidéo sans images (analyse de la vidéo des étoiles du 24/11)
Vidéo « Écoutez la naissance des étoiles ! » : 1 écran illustré sur 15, le reste en écrans de texte (fond bleu-violet), et
pourtant 100/100. Causes : l'IA des images rejetait de vraies images de nébuleuse (« ne colle pas à la phrase ») ; après 2
recherches ratées, l'échelle passait à l'écran de texte ; l'écran de texte comptait comme « réglé ». Corrections :
`CONSIGNE_IMAGES` accepte toute vraie image du sujet ou de son domaine ; `nouvelle_image` : recherche de l'IA → vraies vidéos
de l'entité → passages de réserve (`script["_reserve"]`, vidéos du sujet non utilisées) → thème (`entite_sujet`) → vraie image
d'un autre écran à un autre moment (`_image_deja_bonne`) → écran de texte seulement si la vidéo n'a AUCUNE image ;
`part_illustree` : moins de 70 % d'écrans illustrés = problème grave (« à vérifier », jamais 100/100) ; raisons de chaque
écran refusé écrites dans le journal.

- **Analyse des vidéos sans images du 24/11 au soir** (« Malaise… Macron », « Franco… », « Sénégal… », « Macron et l'A320 ») :
  faites par l'ANCIEN code (lancées avant la correction ci-dessus) ; en plus, YouTube refuse les serveurs de GitHub (« Sign in
  to confirm you're not a bot ») et seuls les 8 premiers candidats (tous YouTube) étaient essayés : PeerTube / Internet
  Archive jamais tentés. Corrigé : tous les candidats (10 essais au plus), YouTube écarté pour tout le passage dès son 1er
  refus (`images.YOUTUBE`). **Garanties** : `controle.avant_publication` refuse TOUJOURS (même « Publier quand même ») une
  vidéo avec moins de 70 % d'écrans illustrés (`ecrans_illustres` / `ecrans_total`) ; `principal.reparer_tout_de_suite` la
  refait aussitôt (images) ; la santé de la nuit refait les autres.

- **Analyse des vidéos refaites du 24/11 vers minuit** (« seulement des titres de presse ») : 1) tri par les mots trop faible
  (« can't » = « CAN », « 2025 ») → `_mots_sujet` sans nombres ni petits mots anglais (`MOTS_VIDES_EN`) + **tri des titres par
  une IA** (`filtrer_par_ia`, `CONSIGNE_TRI` : même événement / personne / lieu seulement) ; 2) PeerTube refusait (403) le
  téléchargement par yt-dlp → `telecharger_peertube` : fichier direct de l'API de l'instance, SEUL LE DÉBUT téléchargé puis
  coupé par ffmpeg (47 s de vidéo en 7 s) ; 3) titres de presse comptés comme images et recopiés → `part_illustree` ne les
  compte plus, `_image_deja_bonne` ne reprend qu'une image VALIDÉE par l'IA (`_valide`), vidéo d'abord, jamais un titre ;
  2 titres de presse au plus ; 4) mauvaise page Wikipédia (« Yosemite » pour Franco) → titre de la page vérifié.

## Composition des vidéos (demande de l'auteur du 25/11)
- **Surtout des morceaux de vraies vidéos de 5 à 10 s** : passages de 10 s (`images.PASSAGE`) ; un morceau couvre 1 ou 2
  phrases (`donner_clip` : la phrase suivante reçoit le même morceau avec `suite`, si les 2 phrases font ≤ 10,5 s estimées ;
  `montage.enchainer` fait reprendre la vidéo là où l'écran d'avant s'est arrêté). **Et des images fixes** : 1 écran sur 4
  (écrans 4, 8, 12…) prend la vraie photo Wikipédia de l'entité citée (`images.trouver_photo`), sinon une vidéo.
- **Scènes de 5 à 10 s** (demande de l'auteur du 25/11, remplace le « 1 ou 2 phrases ») : `principal.scenes_de` regroupe
  les phrases qui se suivent (3,5 mots/s) ; une scène = UN média (`donner` : 1re phrase + copies `suite` pour les autres),
  vraie vidéo qui continue (`montage.enchainer`) ou vraie photo (1 scène sur 4) ; `E["scenes"]` gardé pour les reprises.
- **Jamais de doublon** : `controle._image_deja_bonne` ne recopie plus une image ; il fait CONTINUER la scène d'avant (même
  vidéo, la suite) ou prend un passage jamais montré d'une vidéo validée (après tout ce qui a été vu de ce fichier).
- **Toutes les sources** : vidéos du sujet prises à tour de rôle dans chaque source (YouTube CC, PeerTube, Internet Archive,
  Vimeo, Commons), 5 au plus, titres copiés d'une source à l'autre essayés en dernier ; articles : 8 au plus,
  `sources.sans_doublons` (même lien, même titre ou 60 % des mots en commun = copie d'agence : le plus complet gardé),
  chaque article a sa part de place pour l'IA qui écrit (`ecrire._articles_texte`), consigne « rassemble les infos de tous
  les articles sans répéter ».
- **Bug corrigé le 25/11** : depuis l'ajout des vidéos d'entités, la recherche d'image (Wikipédia, Commons) ne se faisait plus
  que pour la DERNIÈRE phrase (boucle cassée) → écrans vides puis titres de presse. Chaque écran a de nouveau sa recherche.
- Site : le bulletin du contrôle qualité est toujours replié (demande de l'auteur du 25/11).

- **Analyse des vidéos refaites du 25/11 (0 vraie image sur 12 à 15 écrans)** : 1) les images trouvées étaient jugées
  « illisibles » sans raison connue (Wikimedia bloque le serveur de la session : pas reproductible ici) → tout fichier
  téléchargé est vérifié aussitôt (`images.lisible` : taille, page HTML, ffprobe) et jamais posé s'il est illisible ; la
  raison exacte est écrite dans le journal (`_image_de` donne l'erreur de ffmpeg) ; 2) Vimeo refuse le téléchargement sans
  compte (« only works when logged-in », même par son lecteur) → seules les vidéos dont l'auteur a permis le téléchargement
  (lien `download` de l'API officielle) sont prises (`fichier`, 300 Mo au plus) ; 3) beaucoup de sujets d'actu n'ont presque
  aucune vidéo libre de l'événement exact.

- **Cause des « image illisible » (25/11)** : la galerie Wikipédia donne souvent des PNG, enregistrés en « .jpg » ; sur les
  machines de GitHub, ffmpeg n'en tirait aucune image (sans message). `images.bonne_extension` renomme chaque fichier selon
  son VRAI contenu (PNG, JPEG, WebP, GIF, WebM, MP4). Cartes, logos, emblèmes, drapeaux, schémas de la galerie Wikipédia
  écartés (ce ne sont pas de vraies photos). YouTube mis de côté après 2 échecs quels qu'ils soient (« Video unavailable »).

- **Suite (25/11)** : même renommés, certains JPEG (CMYK…) restaient indécodables par ffmpeg → `images.photo_standard` rouvre
  CHAQUE photo avec Pillow et la réenregistre en JPEG RGB standard ; `lisible` décode vraiment une image. L'IA des images
  donne un `rapport` (exact / sujet / domaine / aucun) : seule « aucun » est refusée (un A320 en vol pour une phrase sur sa
  chaîne de montage = bon ; des chevaux pour une élève qui fait un malaise = refusé).

- **Fin des écrans vides (25/11)** : le contrôle lit les PHOTOS avec Pillow (`controle._image_de`) — ffmpeg n'en tirait
  rien sur GitHub, même d'un JPEG standard ; résultat : CAN 0 → 11 écrans sur 12, « Macron sauveur » 20/20 avec 3 vraies
  vidéos (PeerTube, Internet Archive). Une IA qui répond par une LISTE au lieu d'un objet faisait planter le contrôle des
  images (3 essais puis mode secours, vidéo « à vérifier ») → `ia._objet` range la liste sous les clés habituelles.

- **Deuxième avis (25/11)** : l'IA des images, enfin disponible, refusait encore de bonnes images (photo d'archive de l'équipe
  du Sénégal, manifestation antifasciste pour Franco) → CAN 11 → 7 écrans illustrés. `CONSIGNE_IMAGES` : archive / autre match /
  autre manifestation du même thème = « sujet » ou « domaine », doute = « domaine ». Avant l'écran de texte, `deuxieme_avis`
  remontre l'image refusée (`_rejetees`, copie `rejeteeNN-k.jpg`) avec une question large (lien même lointain) : gardée =
  `_garde_2e_avis`, plus rejugée, problème fermé.
- **IA qui voit « indisponible » (25/11)** : 3 vidéos sur 4 sans regard de l'IA (5 vidéos à la fois, Gemini en panne).
  4e fournisseur : OpenRouter, modèles gratuits qui voient les images (`_modeles_openrouter(vision=True)`) ; attente
  croissante (1, 2, 3, 4 min) ; la raison exacte est écrite dans le journal et dans le bulletin.

## Vitesse (analyse du 24/11 : vidéo GTA en 99 min, dont 86 min de voix Chatterbox)
- Voix refaite par le contrôle final : la phrase a déjà eu 2 essais à l'étape voix, donc mots simplifiés DÈS le 1er essai,
  phrase retirée au 3e (si la vidéo reste ≥ 62 s) ; avant : jusqu'à 7 essais identiques (~1 min de Chatterbox chacun).
- `CONSIGNE_FINALE` : le texte DANS l'image de fond (article, panneau) n'est pas un chevauchement ; titre déjà retiré et
  toujours un problème = l'image est changée (avant : 7 tours sans fin sur une carte « La presse en parle »).
- Contrôle final arrêté après 70 min de fabrication (2 tours au moins) : problèmes restants dans le bulletin, « à vérifier ».
- File commune : 5 vidéos en même temps au plus (`creation.paralleles`) ; les autres attendent leur tour ; le site affiche
  l'heure de fin prévue de chaque vidéo (`heuresDeFin` : temps restant, ou première place libérée + durée moyenne réelle).

## Barres fantômes (bug du 25/11 : « 11 vidéos en fabrication » pour 4 réelles)
Une fabrication ANNULÉE (ou tuée par GitHub) n'appelait jamais `avancement.finir` : sa barre restait « en_cours » jusqu'à
30 min sur le site. Corrigé : le site ne garde une barre « en cours » que si sa tâche GitHub tourne vraiment
(`tachesActives` : runs in_progress / queued de creer.yml) ; creer.yml a une étape `if: cancelled()` qui marque la barre
« annulee » (`python -m robot.avancement --annuler`), effacée au bout d'1 min.

## Améliorations choisies le 25/11 (liste de 30 : n° 1 à 6, 9, 10, 12, 13, 16, 17, 18, 21, 23, 25, 26, 27)
- **1. Moments forts** (`citations.notes_ia`, `CONSIGNE_MOMENTS`) : l'IA qui voit note 10 images de chaque vidéo d'origine
  (10 = l'action de l'événement, 0 = présentateur, plateau, titre) ; `moments(notes=)` choisit les passages les mieux notés,
  puis les changements de plan ; images fixes prises aux instants les mieux notés.
- **3. Coupes sur les plans** (`vision.scenes` : PySceneDetect, sinon ffmpeg ; `vision.caler_sur_plans`) : un extrait
  commence au début d'un plan et finit à la fin d'un plan (10 s au moins).
- **2. Recadrage sur les visages** (`vision.centre_visages`, OpenCV YuNet ; `montage.centre_cadrage` → `media["cx"]`) : vidéo
  ou photo HORIZONTALE recadrée sur le plus grand visage au lieu du milieu (MediaPipe récent ne détecte plus les visages sans
  modèle à part).
- **4. Photos agrandies** (`vision.agrandir`, OpenCV dnn_superres FSRCNN ×2, 0,3 s) : toute photo de moins de 1000 px, dans
  `images.photo_standard` (Real-ESRGAN demande une carte graphique). OpenCV 4 obligatoire (`opencv-contrib-python-headless<5` :
  OpenCV 5 ne lit plus les modèles .pb). Modèles en cache `~/.cache/buzz-modeles` (creer.yml). PySceneDetect est installé
  SANS ses dépendances (`--no-deps`, creer.yml / essai.yml) : il réclame `opencv-python` (OpenCV 5) qui écrasait l'OpenCV 4
  (essai de la nuit du 25/11 : « agrandissement impossible ») ; Dependabot ignore OpenCV 5. Les tests tournent toujours
  SANS `GITHUB_ACTIONS` (tests.yml, essai de la nuit) : sinon ils tentent d'envoyer sur GitHub (échec sur les PR de Dependabot).

- **5. Voix plus vivante** (`voix.emotion` → « exaggeration » de Chatterbox) : accroche 0,7, phrase qui s'exclame ou
  questionne 0,62, explications 0,5 (la voix choisie). **10. Tous les cœurs** (`voix.processus_voix`, `_chatterbox`) : les
  phrases sont réparties entre plusieurs calculs Chatterbox EN MÊME TEMPS (un par paire de cœurs ; `CHATTERBOX_PROCESSUS`,
  `CHATTERBOX_COEURS`), longues phrases réparties équitablement.
- **6. Orthographe** (`robot/langue.py`, LanguageTool public sans clé) : fautes de frappe évidentes corrigées directement,
  accords / conjugaisons corrigés par l'IA avec les remarques (la 1re suggestion de LanguageTool est parfois fausse) ; noms
  propres jamais touchés ; à la fin de l'étape « texte ».
- **9. Musiques** (`robot/musiques.py`, workflow « Musiques libres » à lancer à la main) : Openverse (API sans clé, licence
  CC0 seulement, surtout Freesound ; FreePD a fermé en 2025), 5 par ambiance, 40 s à 5 min, sans voix ni bruitage
  → `sons/musique/<ambiance>_ov_*.mp3` + `catalogue.json` (auteur, page, tempo mesuré) ; `sons.musique` choisit l'ambiance PUIS le rythme
  (`TEMPOS`) ; 2 ambiances de plus pour l'IA : « epique » et « emotion ».

- **12. uv** (astral-sh/setup-uv) dans tous les workflows : `uv pip install --system …`, pip en secours (`|| pip install …`) ;
  l'espace à part de Chatterbox garde pip (en cache). **13. Contrôle final** : 4 tours au plus (avant 12), et à partir du
  2e tour l'IA ne revoit que les écrans REFAITS (`controle_video(seulement=)`, comparaison des signatures `_sig`).

- **16. Essai de la nuit** (`robot/essai_nuit.py`, essai.yml à 01 h 47 UTC) : tests du code, voix d'homme (1 phrase),
  Whisper, téléchargement TikTok, OpenCV, LanguageTool, IA qui écrit, IA qui voit — sans publier ni ajouter de vidéo ;
  résultat `sante.json` → `essai_nuit` (onglet Santé), panne écrite dans le journal.
- **17. Versions figées** : `requirements.txt` (OpenCV, scenedetect… à la version essayée) + `.github/dependabot.yml`
  (chaque lundi, mises à jour proposées en « pull request », testées par tests.yml avant fusion par l'auteur ; yt-dlp
  toujours en dernière version, exprès).
- **18. Quotas des IA** (`ia.QUOTAS` : appels, refus 429, erreurs, restes annoncés par les en-têtes x-ratelimit) → fiche de
  chaque vidéo (`ia_quotas`) → `sante.quotas_ia` (24 h) → onglet Santé (🟠 = plus de 30 % de refus).

- **21. Tendances Google** (`sources.tendances_google` : flux officiel « Daily Search Trends » FR / US / GB, sans clé ;
  pytrends trop souvent refusé ; `en_tendance` : 2 mots en commun) : un sujet qui monte AUSSI sur Google a son score × 1,5
  et le badge 🔎 sur le site.
- **23. Séries** (`publication_auto.SERIES`, `serie_du_jour`, réglage `creation.series`) : 1re vidéo du lundi = « LE
  CHIFFRE DU LUNDI » (format chiffre), du vendredi = « VRAI OU FAUX DU VENDREDI » ; étiquette rouge à la place
  d'« INSOLITE » (`script["etiquette"]`) et hashtag de la série en tête.
- **25. Vidéos retirées** (`stats.main`) : une vidéo publiée vue en ligne puis disparue de la chaîne = 🚨 dans le journal,
  `retiree_le`, et les comptes cités dedans mis de côté 30 jours pour les extraits (`video.sources_a_risque`,
  `citations.videos_du_meme_evenement`).
- **26. gitleaks 8.30.0** (secrets.yml, empreinte vérifiée, `--redact`, `.gitleaks.toml` : règles habituelles + noms des
  secrets du robot) à chaque envoi ; à la main = tout l'historique (vérifié propre le 25/11).
- **27. Étiquette IA** : déjà en place (Buffer `isAiGenerated`, sinon mention écrite + alerte) ; badge sur le site
  (« 🤖 étiquette IA cochée » / « ⚠️ à cocher »).

- **Refaire le texte garde les extraits** (vidéo CAN r10 du 25/11 : texte corrigé mais extraits BBC / franceinfo perdus,
  remplacés par une statue, des timbres moldaves et des écrans de texte) : `refaire.preparer` (texte) range les extraits de
  l'ancienne version dans `script["_citations_reserve"]` ; `placer_citations` les repose d'abord sur les phrases nouvelles,
  puis complète par de nouveaux extraits (il ne s'arrête plus dès qu'un extrait existe déjà).
- **AUCUN extrait perdu** (exigence de l'auteur du 25/11) : chaque extrait vidéo trouvé est noté (`script["_citations_toutes"]`,
  archivé avec ses fichiers pour « Refaire ») ; étape « extraits » après le contrôle final : `controle.extraits_perdus` (extrait
  trouvé mais plus à l'écran alors qu'un écran montre autre chose) → `reposer_extraits` (écran de texte d'abord, puis titre
  de presse, puis photo / vidéo qui n'est pas de l'événement ; jamais la carte ni la question) → vidéo remontée, revérifiée
  (2 tours). Il en reste = problème GRAVE (« à vérifier ») et `avant_publication` refuse TOUJOURS (même « Publier quand
  même ») ; `extraits_perdus` dans la fiche, badge sur le site.
- **Règles de chaque vidéo** (`robot/regles.py`, étape « regles » après « extraits ») : extraits perdus, écran sans image,
  même passage deux fois, plus d'1 minute, 70 % illustrés, hashtags (3 à 10, mots entiers), tutoiement (citations entre
  guillemets exclues), dates / années présentes dans les articles (sinon corrigées par l'IA, ou l'année douteuse retirée),
  question finale, description. `reparer` ne corrige QUE les passages fautifs (voix refaite pour ces phrases seulement,
  seuls ces écrans remontés), puis TOUT est revérifié (2 tours) ; il reste une règle = grave, `regles_non_respectees`,
  jamais publiée (`avant_publication`), badge 📏 sur le site.
- **Caractères que la police n'a pas** (vidéo CAN r11 du 25/11, 100/100 mais « 1☒0 » sur 4 écrans : tiret insécable U+2011
  écrit par l'IA, absent de Poppins) : `montage.affichable` / `REMPLACER` (tirets ‐ ‑ ‒ − → « - », trait d'union conditionnel
  retiré) à TOUT texte dessiné (titres, sous-titres, crédits), `ecrire.normaliser` nettoie le texte de l'IA à la source,
  règle « caracteres » (regles.py) et rejeu (« 1‑0 » → « 1-0 »).
- **Analyse de la vidéo CAN r12 (25/11, 100/100) et corrections pour les suivantes** : accroche sur un homme de dos sur une
  plage → l'extrait le MIEUX NOTÉ par l'IA ouvre la vidéo (`note_ia` de chaque extrait, `_note_fenetre`) ; extraits d'un même
  compte collés → espacés (`placer_citations`) ; « 1-0 » redit dans 3 phrases et phrase administrative (« cette sanction a
  été prise, invoquant les articles… ») → consignes d'écriture et de vérification (un chiffre dit UNE fois, phrases simples) ;
  accroche « TAS REND LA VICTOIRE » → jamais de sigle dans l'accroche ; question avec tiret insécable → `affichable` sur la
  question et la description ; `categorie` vide → « actualite » par défaut. Non corrigé (choix) : nos sous-titres sur
  bandeau noir peuvent tomber près des sous-titres de la vidéo d'origine (leur place change d'un média à l'autre).
- **Analyse des vidéos du 25/11 après-midi** (CAN r13, Seattle, marées) et nouvelles règles : phrase absurde « 18 7 18 »
  (simplification de l'IA acceptée sans contrôle) → `controle.simplification_valable` / `phrase_absurde` + règle (phrase
  retirée) ; unités anglaises « 2,8 ft », « 20-30 ft », « 2,9 pieds » → règle « unites » (`regles.convertir_unites` :
  pieds, miles, livres, pouces, mph → m, km, kg, cm, km/h, sans IA) ; gros titres en anglais ou hors sujet (« CLOSED BEACHES »,
  « 10 SAILS ») → règle « titre » (`titre_hors_phrase` : chaque mot du titre doit être dans la phrase dite, sinon titre
  retiré) ; accroche « VAGUES MORTELLES EN COASTE » → règle « accroche » (LanguageTool, sinon les 4 premiers mots du titre) ;
  même photo de presse sur 3 écrans de suite → une image FIXE ne couvre qu'une phrase, les suivantes prennent d'autres
  images de l'événement. Vidéo Seattle : excellente (14/14 écrans de l'arrestation). Non corrigé : un nom en titre
  (« BOB FERGUSON ») peut s'afficher sur le visage d'une autre personne de l'extrait.
- **Problème d'une phrase retirée** (vidéo CAN r14 du 25/11 : la règle a retiré « 18 7 18 », mais son problème de voix
  restait ouvert → « à vérifier » à tort) : à la fin de l'étape « regles », tout problème ouvert dont la phrase n'existe plus
  est clos (« phrase retirée »).
- **Rejeu d'une vraie vidéo** (`tests/test_rejeu.py`, données réelles de la CAN r10 dans `tests/donnees/rejeu_can`, sans
  réseau ni IA, ~50 s, à chaque envoi) : les règles trouvent les défauts réels, la réparation ne touche que les passages
  fautifs, refaire le texte ne perd aucun extrait, le montage ne refait que les écrans changés. Il a trouvé dès sa 1re
  exécution 2 vrais défauts : son silencieux qui faisait planter le réglage du volume (`sons.niveau`), image sans crédit
  qui faisait planter le montage. **Toute modification doit garder ce rejeu au vert.**
- **Pas de déguisement en navigateur** (demande de l'auteur du 25/11, refusée) : les téléchargements d'extraits ne se font
  jamais passer pour Chrome quand TikTok refuse (contournement d'une protection anti-robots) ; simples nouveaux essais.

## Crédits des IA vérifiés AVANT chaque création (demande de l'auteur du 25/11, vidéos à 0/100)
Cause : 5 vidéos lancées en même temps à 16 h 30 → Mistral « You need a subscription » (402) à CHAQUE appel (111 essais perdus
par vidéo), OpenRouter « free-models-per-day », Groq et Gemini saturées → textes écrits / vérifiés par de petites IA de secours,
« phrases » qui n'étaient que des nombres (« 74 », « 2 », « 2026 », ajoutées par la réécriture pour allonger le texte), titres
en anglais, vidéos de 45 à 59 s. Corrections :
- `robot/credits.py` : `verifier()` essaie chaque IA (petite question texte, puis petite image) → il faut 2 IA qui écrivent
  (une écrit, une AUTRE vérifie) + 1 IA qui voit, et au plus `MAX_EN_MEME_TEMPS` (2) vidéos en fabrication ; raison lisible
  (abonnement nécessaire, limite du jour, trop de demandes). Job « plan » de creer.yml (clés des IA + GH_TOKEN) : pas bon =
  `mettre_en_attente` (garde.json → `en_attente`, une entrée par vidéo), aucune machine (`if: plan != '[]'`) ; une série
  plus grande que les places libres part en partie, le reste attend. Garde (toutes les 15 min, clés des IA) :
  `relancer_attente` lance la plus ancienne dès que la vérification passe (une par passage) ; créneaux automatiques vérifiés
  aussi. Site : « ⏸️ N création(s) en attente des IA gratuites » dans le cadre d'avancement.
- `ia._mort` : 401 / 402 / 403, « per-day », « billing », « subscription » = fournisseur entier mis de côté pour le passage.
- Phrases ajoutées ou réécrites par l'IA (`controle_texte`, allongement) et texte de l'IA (`ecrire.normaliser`) : jamais une
  phrase absurde (nombre seul), 5 vrais mots au moins pour un ajout.
- Règle « texte_non_verifie » : faits non vérifiés par une 2e IA (IA saturées) = revérifiés, sinon jamais publiée.
- LanguageTool ne touche JAMAIS une citation entre guillemets (« racli » devenu « racle » dans la vidéo GTA).
- Unités : « 30 pieds, soit 9 mètres » → « 9 mètres » (plus « 9 m, soit 9 mètres »).

## Prononciation des voix homme et femme (demande de l'auteur du 25/11, points 1, 2, 3, 4, 6)
`robot/prononciation.py`, appliqué JUSTE avant la voix (Chatterbox et Kokoro, `voix._preparer` ; les sous-titres restent bien
écrits ; la clé de la mémoire des voix suit le texte DIT : un mot corrigé = phrase redite) :
- 4. `mise_en_forme` : M. / Mme / n° / 1er / 2e, %, €, $, km/h, °C, &, vs, etc., heures (18h30) ; sigles épelés à la française
  (« ICE » → « i cé eu ») sauf `COMME_UN_MOT` (NASA, OTAN, FIFA, CAF…) ; chiffres romains laissés.
- 1. dictionnaire `docs/donnees/prononciation.json` (+ `BASE`) : mot → comment le dire ; 3. l'auteur ajoute / retire un
  mot sur le site (Réglages → 🗣️ Prononciation, ordre `prononciation`), ses mots (✍️) passent avant ceux du robot (🤖).
- 2. apprentissage : phrase mal comprise par Whisper (< 75 %) → `candidats` (noms propres, sigles, mots à l'allure
  étrangère, jamais un mot français courant) → `respeller` (IA aidée par 6. eSpeak-NG, déjà installé avec Kokoro :
  espeakng-loader + phonemizer ; secours `ipa_vers_francais`) → phrase redite ; gardé pour les vidéos suivantes
  (`enregistrer_appris`) seulement si la phrase est alors bien comprise.
- Mistral (25/11 au soir) : la nouvelle clé répond encore « You need a subscription » (402) : il faut ACTIVER le plan
  gratuit dans la console Mistral (une nouvelle clé ne suffit pas). Créations : doublons entre attente et santé évités
  (`sante.deja_en_refaire` lit aussi `en_attente`, `mettre_en_attente` sans doublon, refaire d'une vidéo disparue oublié).

## Boutons des vidéos (demande de l'auteur du 25/11 : « comme l'autre projet », jt-auto)
Interrupteurs `boutonsVideo` / `bascule` (classe `.btn.bascule`) : VIDES tant qu'ils ne sont pas activés (« ☐ À publier »,
« ☐ Écarter », « 🚀 Publier maintenant »), COLORÉS seulement une fois activés (« ✅ À publier · n° k dans la file » vert,
« 🛑 Écartée (toucher pour annuler) » rouge, « 📤 Publiée · date » bleu) ; toucher un interrupteur activé l'annule
(`retirer`). Juste après un appui : « ⏳ … » clignotant (`enAttente`, `envoyerBascule`) jusqu'à la confirmation du robot
(site relu à 20, 45, 75 et 120 s ; `oublierAttentes`), retour à l'état d'avant si l'ordre est refusé.

## Avancement en direct (demande de l'auteur du 25/11 : « mis à jour bien plus rapidement »)
Robot : envoi toutes les 5 s au plus (`avancement.INTERVALLE`) + signe de vie toutes les 15 s même au milieu d'une longue
étape (`_lancer_battement`, fil discret : temps écoulé et fin prévue à jour). Site : relecture toutes les 5 s pendant une
fabrication, 30 s sinon (une vidéo lancée ailleurs apparaît seule), 60 s onglet caché ; seuls les fichiers dont l'empreinte
`sha` a changé sont retéléchargés (`avCache`), tâches GitHub relues toutes les 30 s (`avTaches`) ; « mis à jour il y a X s ».

## Liens des vidéos d'origine (24/11 : « vidéo indisponible » sur TikTok)
Les liens étaient bons (34/34 vérifiés) : TikTok affiche « vidéo indisponible » sur téléphone hors de l'appli, sans compte,
ou pour une vidéo supprimée / réservée aux adultes. Le site ouvre maintenant la vidéo dans le LECTEUR OFFICIEL de TikTok
(`player/v1/<id>`, fenêtre `#lecteur`, sans appli ni compte), lien direct « Ouvrir dans TikTok » en secours ;
`buzz.verifier_liens` (chaque relevé, anciens sujets compris) : oEmbed 400/403/404 = `indisponible` (lien retiré), pseudo
de l'auteur corrigé. Une vidéo réservée aux adultes reste impossible à voir sans compte TikTok.

## Vitesse, suite (demande de l'auteur du 24/11)
- Calage des mots : Whisper de **Groq** d'abord (`voix._groq_mots`, whisper-large-v3-turbo, clé GROQ_API_KEY), Whisper local
  si Groq refuse (3 refus = local pour le reste du passage).
- **Mémoire des voix** (`voix.preparer(memoire=)`, dossier `memoire_voix` de la vidéo) : une phrase déjà dite à l'identique ET
  réussie n'est jamais refaite ; une phrase jugée mauvaise est oubliée (`voix.oublier`) avant d'être refaite.
- **Voix et images en même temps** (fil `fil_images` dans `fabriquer`) ; médias pris par les autres vidéos en construction
  écartés (`avancement.publier_medias` / `medias_des_autres`) : jamais deux vidéos avec les mêmes passages.
- **File après le texte** : toutes les machines d'une série démarrent (articles + texte), `attendre_son_tour` (champ `file` :
  attente / active) limite la partie lourde à `creation.paralleles` (5 par défaut) vidéos en même temps.
- Caches GitHub (pip, ffmpeg, voix, Whisper, Chatterbox) : **tout nouvel outil lourd doit avoir son cache** dans creer.yml.

## Qualité, suite (demande de l'auteur du 24/11)
- Son : -14 LUFS en DEUX passages (`sons.niveau`, mesure puis réglage linéaire) ; une seule musique par vidéo (`_musique`).
- **Coupes sur le rythme** : `sons.battements` (tempo par autocorrélation, temps et demi-temps) + `sons.caler_pauses` : le
  silence après chaque phrase (0,08 à 0,45 s, `p["_pause"]`) fait tomber l'écran suivant sur un temps de la musique.
- **Zones libres de TikTok** (`montage.ZONE_*`, `MARGE_COTES`) : logo et étiquette sous la loupe (y ≥ 160), textes à 130 px des
  bords, sous-titres au-dessus de la description (y < 1540), crédits juste sous les sous-titres (visibles : licences CC BY).
- **Accroche** (`principal.accroche`) : le 1er écran prend une vraie vidéo s'il n'en a pas. **Couverture** (`couverture_ms`,
  `thumbnailOffset` de Buffer) : 1er écran avec vraie image + gros titre. **Sources** : « Sources : … » sur le dernier écran
  (`sources_ecran`) et dans la description, avec les crédits des images (`publier.texte`).

## Thèmes, formats, sujets déjà traités (demande de l'auteur du 24/11)
- L'IA du buzz donne `categorie` (faits_divers, animaux, insolite…) et `ville_france` ; stats.json → `categories` ;
  `buzz.facteur_categorie` : score × (vues médianes du thème ÷ vues médianes de la chaîne), entre 0,6 et 1,8.
- Nouveaux formats (`ecrire.FORMATS`) : « chiffre » (le chiffre fou du jour), « monde60 » (4 actus du jour, `sujet_monde60`,
  samedi soir en automatique), « region » (près de chez toi : sujets avec `ville_france` d'abord). `MULTI` = formats à
  plusieurs sujets. Rotation automatique `publication_auto.format_auto` : vrai_faux 1/3, chiffre 1/5, region 1/7.
- `principal.deja_traite` : jamais un sujet mis en vidéo ces 7 derniers jours (même id ou `buzz.meme_sujet`).

## Refaire en corrigeant (demande de l'auteur du 24/11 : « ne pas recréer à l'identique une vidéo qui a un problème »)
`robot/refaire.py` + `principal.refaire_video` (creer.yml : entrées `refaire`, `etape`, `remarque` ; site : « 🔁 Refaire en
corrigeant » sur chaque vidéo). Chaque création range `travail-<id>.tar.gz` dans sa Release (texte complet, articles,
bulletin, `memoire_voix`, images et passages ; images non gardées au-delà de 400 Mo). Étapes : images (écrans du bulletin ou
« écran 3, 5 » de la remarque, sinon tous ; anciennes images INTERDITES via `deja`), voix (phrases signalées simplifiées,
sinon nouvelle prise ; mémoire oubliée), texte (`ecrire.refaire_texte` avec problèmes + remarque, phrases inchangées gardent
voix et image, contrôle des faits refait), tout (version nouvelle, autres images), auto (`etape_auto` d'après le bulletin).
Nouvel id `<id>-r<n>` qui remplace l'ancien dans file.json (ancienne Release supprimée).

## Santé du robot et réparations automatiques (demande de l'auteur du 24/11 : « s'autorépare sans mon aide »)
`robot/sante.py` (sante.yml : chaque nuit 03 h 17 UTC + bouton « 🩺 Vérifier maintenant » ; onglet 🩺 Santé, sante.json) :
IA, sources de vidéos libres, presse, Buffer, comptes TikTok, créations des 24 h, durée moyenne de chaque étape (`durees` de
chaque vidéo). Répare seul : comptes muets 3 contrôles de suite → pause 7 jours (`buzz.en_pause`) ; sujets réservés > 6 h ou en
échec → remis en jeu (échec : une fois) ; vidéos non publiées « à vérifier » ou dont l'IA trouve ≥ 2 images hors sujet sur 8
(`audit_video`) → REFAITES en corrigeant (`gh workflow run creer.yml -f refaire=…`), 2 fois au plus par vidéo, 3 par nuit.

## Vraies images du sujet (demande de l'auteur du 24/11 : « pas de bouts de vidéos au hasard pour meubler »)
Les vidéos des JT et agences (BFM, TF1, AFP…) ne sont JAMAIS reprises (droits, TikTok les reconnaît). À la place :
champ "entite" de chaque phrase (titre de l'article Wikipédia de la personne / du lieu / de l'objet) → `images.wikipedia_media`
(galerie de l'article Wikipédia FR, qui n'accepte que des images libres ; pauses si 429) ; écrans « LA PRESSE EN PARLE »
(`images.carte_presse` : vrai titre + nom du média, 3 au plus, sur les écrans restés sans vraie image) ; NASA / Wikimedia ;
banques d'images génériques (Pixabay, Pexels) COUPÉES (`video.images_generiques` false) ; sinon écran de texte.
L'IA qui contrôle les images refuse une image générique sans rapport réel.

## Sujets riches et vraies vidéos du sujet (demande de l'auteur du 24/11)
- **Seulement des sujets sans problème** : avant de commencer une vidéo, `principal.creer` lit les articles
  (`sources.chercher_large`, jusqu'à 6 articles) et exige `sources.assez_riche` : 3 médias DIFFÉRENTS avec un vrai article
  (≥ 600 caractères, hors Google / Wikipédia / descriptions TikTok) et 5 000 caractères en tout. Sinon le sujet n'est pas
  commencé (statut `sans_source`, « Pas assez d'articles ») et le suivant est pris ; si aucun ne passe, le plus riche est fait
  quand même. Les articles lus sont gardés (étape « articles » déjà faite) et réunis dans UNE vidéo.
- Scan du buzz : `s["medias"]` = nombre de médias qui en parlent (`sources.nombre_de_medias`, Bing) ; moins de 3 = score ÷ 4 ;
  affiché sur la carte du sujet (📰).
- **Vraies vidéos du sujet** (`images.videos_du_sujet`, `SOURCES_VIDEO`) : vidéos publiées par leur auteur sous licence libre
  permettant l'usage commercial et le montage (`licence_ok` : CC BY, CC BY-SA, CC0, domaine public ; jamais NC ni ND) sur
  YouTube (filtre CC + licence relue), PeerTube (Sepia Search), Internet Archive, Vimeo (clé gratuite facultative
  `VIMEO_TOKEN`, filtres CC-BY / CC-BY-SA / CC0) et Wikimedia Commons ; Dailymotion, Rumble, TikTok, Instagram : aucune
  licence libre possible, jamais repris ; au moins 2 mots du sujet
  dans le titre ; télés / agences / médias écartés par le nom (`MEDIAS_INTERDITS`). **Aucun refus pour un logo visible** (choix de l'auteur du
  24/11, après l'avertissement : une vidéo PeerTube « CC BY » de l'essai était un reportage France 24 remis en ligne ; ni
  contrôle des logos sur les vidéos, ni dans le contrôle des images). Découpées en passages de 6 s (`debut`),
  alternés entre vidéos, utilisées en PREMIER sur les écrans, crédit « Vidéo : auteur (source, licence) ».
  Ensuite, pour les écrans restants : vidéos libres de CHAQUE `entite` citée (6 au plus, `entites_faites`, `prefixe`, `deja` :
  jamais deux fois la même vidéo). Photos Wikipédia / Commons seulement en dernier recours (choix de l'auteur du 24/11 : des
  bouts de vraies vidéos collés l'un après l'autre).
- **Jamais repris** : vidéos TikTok et Instagram d'autres comptes (droits de leurs auteurs, contenu « non original » pour
  TikTok), vidéos des médias même citées (la courte citation ne couvre pas une vidéo qui illustre sans analyser). yt-dlp + deno
  installés dans creer.yml. YouTube qui refuse le serveur (429, « Sign in ») = on s'en passe, sans contournement. Les vidéos
  des JT et agences (droits réservés) restent interdites, même si elles sont dans l'article.

## Plusieurs machines en même temps (demande de l'auteur du 24/11)
creer.yml : job « plan » (`principal.planifier` : un sujet + des réserves PAR machine, réservés « en_cours » avec `reserve_le`,
libres de nouveau après 3 h ; réserves non utilisées rendues à la fin de `creer`) puis job « creer » en matrice (une vidéo par
machine, `MACHINE` = n°, `max-parallel` = `creation.paralleles`, 3 par défaut, 1 à 5 ; `fail-fast: false`). Identifiant de
vidéo suffixé par le n° de machine. Avancement : un fichier par machine `av-<run>-<machine>.json` sur la branche « avancement »
(`avancement._pousser` garde ceux des autres machines < 2 h) ; le site affiche une barre par vidéo.

**File d'attente commune** (demande de l'auteur du 24/11) : `avancement.attendre_son_tour` au début de chaque machine (toutes
séries confondues) : au plus `creation.paralleles` vidéos en même temps ; les autres s'inscrivent « en_attente » (heure de la
demande) sur la branche avancement et partent dans l'ordre (revérifié toutes les 30 s) ; machine muette 30 min (en cours) ou
3 min (en attente) = plantée, ignorée ; départ forcé après 200 min (job de 350 min). Le site affiche la file.

**Toujours 5 sujets** (demande de l'auteur du 24/11) : si les seuils en donnent moins, `buzz.relever` complète avec les vidéos
récentes les plus vues juste en dessous (« sous_seuils », score divisé par 2) ; doublons fusionnés (`buzz.sans_doublons`,
`meme_sujet` : 60 % des mots en commun) ; onglet Buzz : « 🏆 Les 5 sujets qui buzzent le plus » toujours visible (statut affiché).

## Analyse des erreurs du 24/11 (demande de l'auteur) et corrections
- Sujet abandonné « 8 phrases vérifiées » : la 2e IA retirait tout ce qui n'était pas mot pour mot dans les articles, et chaque
  revérification de TOUT le texte retirait d'autres phrases → `ecrire.verifier` CORRIGE (retire seulement si impossible),
  accepte transitions / questions / contexte évident, et `seulement=` : après une réécriture, seules les phrases nouvelles
  sont jugées ; 3 allers-retours « compléter puis vérifier » avant d'abandonner (`principal.fabriquer`).
- Plantage du contrôle des images (image d'une vidéo trop courte) → `controle._image_de` lit la 1re image, sinon écran fautif.
- Erreurs absentes du journal du site (effacées par le retour à la version en ligne) → `commun.A_ENVOYER` + `rejouer_journal`
  dans `depot.enregistrer` ; filtre « ⚠️ Problèmes seulement » dans l'onglet Journal.
- Modèles d'IA retirés (404 « does not exist / no longer available ») → `ia._MORTS`, plus réessayés pendant le passage.
- Préventif : Release créée en 3 essais (`depot.publier_release`), enregistrement en 10 essais, barre d'avancement 2 essais.

## Jamais d'abandon (exigence de l'auteur du 24/11 : « une vidéo en construction doit arriver à son terme et être sur le site »)
- Plus aucune LookupError : articles trop maigres → `sources.chercher_large` (autres recherches, contexte Wikipédia, descriptions
  des vidéos TikTok virales) ; texte trop court → contexte Wikipédia ajouté puis phrases ajoutées (5 tours) ; vidéo toujours
  courte → problème ouvert (« à vérifier »), la vidéo va au bout.
- **Étape qui plante = seule cette étape recommence** (demande de l'auteur du 24/11) : `principal.fabriquer` est découpée en
  étapes (`ETAPES` : articles, écriture, texte, voix, images, contrôle des images, montage, contrôle final, rangement) ; ce qui
  est fait est gardé dans `etat` (même identifiant de vidéo, même dossier). Une étape ratée est refaite seule (3 essais, 15 s),
  puis `creer` rappelle `fabriquer` avec le même `etat` (4 tentatives, 20 s ; la 4e en mode secours pour les étapes restantes :
  voix Kokoro, pas de regard de l'IA sur les images). Dans une étape : voix des phrases déjà dites, images déjà trouvées,
  écrans déjà montés et tour du contrôle final gardés ; `reprises` dans la fiche de la vidéo ; IA gratuites saturées → `avec_ia` attend 5 min (90 min max).
- La vidéo est toujours enregistrée sur le site ; un problème restant = statut « a_verifier » (publication automatique bloquée).

## Fonctionnement
- `robot/buzz.py` (buzz.yml, toutes les 2 h) : yt-dlp lit les comptes d'actualité suivis (`buzz.comptes`), garde les vidéos
  au-dessus des seuils, l'IA les regroupe par sujet → `docs/donnees/buzz.json` (statut nouveau / utilise / ignore / sans_source).
- `robot/principal.py` (creer.yml : bouton Créer, série 1-10, sujet du buzz ou sujet libre, création automatique lancée par la
  garde) : `sources.chercher` (flux RSS + Google Actualités, jamais de contournement d'un refus) → `ecrire.ecrire` (IA) →
  `ecrire.verifier` (2e IA d'un AUTRE fournisseur, phrases corrigées ou retirées) → `voix.dire` + `voix.mots_entendus` →
  `images.trouver` (Pexels vidéo → Pixabay vidéo → NASA si sujet d'espace, début au tiers → Wikimedia vidéo (480p transcodée) → Pexels / Pixabay / Wikimedia photo ; 4 s entre deux recherches Wikimedia ; clés Pexels suspendues au 24/11 : `PIXABAY_API_KEY` à la place)
  → `montage.monter` → Release `v-<id>` (adresse publique pour Buffer) → `docs/donnees/file.json` + miniature.
- `robot/publication_auto.py` (garde.yml, toutes les 15 min) : créneaux de publication et de création (valables 3 h).
  **Buffer est appelé UNE seule fois, AVANT `depot.enregistrer`** (qui peut se répéter) : sinon double publication.
- `robot/commande.py` (commande.yml) : ordres du site. `robot/avancement.py` : barre de progression (branche `avancement`).
- Site `docs/index.html` (GitHub Pages, main /docs) : onglets Buzz, Vidéos, Créer, Publication, Journal, Réglages ; clé
  GitHub fine-grained du navigateur (`bi_jeton`, droits Actions + Contents) ; mode démo sans données.
- **Réglages GitHub interdits depuis une session Claude** (proxy) : activer Pages et écrire les secrets se font à la main par
  l'auteur. Secrets : `BUFFER_API_KEY`, `CEREBRAS_API_KEY` / `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` / `ZAI_API_KEY` (facultatifs), `PEXELS_API_KEY` (facultatif), `PIXABAY_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `VIMEO_TOKEN` (facultatif).

## Vidéos invisibles sur le site (25/11 au soir)
3 vidéos fabriquées en même temps (Arche, Trump, GTA) avaient leur Release restée en BROUILLON sur GitHub : fichier
introuvable (404) pour le site et pour Buffer. `depot.publier_release` appelle maintenant `rendre_publique` (vérifie
`isDraft`, sinon `gh release edit --draft=false`, puis le lien de la vidéo doit répondre) ; la santé (`sante.reparer_brouillons`)
rend publiques chaque nuit les Releases restées en brouillon.

## Modèles d'IA de secours (25/11 au soir, demande de l'auteur)
Groq a retiré `llama-4-maverick` (404) et Gemini ne répondait plus : plus aucune IA qui voit. `ia.modeles(fournisseur, vision=)`
lit la liste OFFICIELLE des modèles de chaque fournisseur avec sa clé (`LISTES`, une fois par passage, `_EN_LIGNE`) : modèles
préférés (`FOURNISSEURS[...]["modeles"]`, `VISION`, listes allongées) encore publiés d'abord, puis jusqu'à 4 modèles de secours
du même fournisseur (`_secours_ok` : Gemini « flash », Mistral selon `capabilities.vision`, Groq « llama-4 / vision / -vl »
pour les images ; jamais embed / tts / whisper / guard…). Liste illisible = liste préférée telle quelle. OpenRouter : 8
modèles gratuits. La santé écrit dans son journal les modèles retenus pour chaque IA. Relevé du 25/11 : Groq n'a PLUS aucun
modèle qui voit (llama-4 retirés) ni llama-3.3-70b ; modèles Gemini qui DESSINENT (« -image ») écartés. Limite du jour :
Gemini et Groq la comptent PAR MODÈLE → seul le modèle épuisé est écarté (`_MORTS`) ; OpenRouter (limite commune) et
401 / 402 / 403 / abonnement → fournisseur entier mis de côté. Piège : le 429 de Gemini dit « check your plan and BILLING
details » → ce n'est PAS un abonnement (avant : tout Gemini écarté, plus aucune IA qui voit).

## Publier une vidéo « à vérifier » (25/11 au soir, demande de l'auteur)
- Les vidéos « à vérifier » ont aussi l'interrupteur « ☐ À publier » (`boutonsVideo`) : cochée, elle prend `force` = publiée
  « quand même » à son créneau (`publication_auto` → `verifier_et_envoyer(forcer=)`), la santé ne la refait plus ;
  « retirer » la remet « à vérifier ». Les garanties qui bloquent même « quand même » restent (images, extraits, règles).
- « Publier quand même » refusé pour « description vide » (vidéo de l'arche : la règle n'était pas vérifiée quand la
  description MANQUAIT) → `regles.verifier` reçoit toujours une chaîne ; `controle.description_secours` (titre 👀 + question)
  remplit une description vide au lieu de bloquer.
- Contrôle avant publication : le lien de la vidéo était testé par HEAD (GitHub répond 401 → TOUTES les publications
  refusées) → `controle.lien_en_ligne` lit le début du fichier.

## Audit complet en 4 passes (25/11 au soir, demande de l'auteur)
1. Code (ruff, ESLint du site, actionlint + shellcheck des 12 tâches) ; 2. en ligne (tâches des 24 h, site ouvert à 400 px
et 1300 px dans chaque onglet, chaque vidéo : Release, fichier, miniature, champs ; journal du robot) ; 3. logique
(publication, ordres du site, Buffer, enregistrement, santé, file d'attente) ; 4. tout revérifié (tests, site, tâches).
Trouvé et corrigé :
- **Réveils de GitHub sautés** : garde « toutes les 15 min » partie 3 fois en 24 h, buzz pas depuis 8 h → créneau de 19 h 00
  manqué. **Métronome** (`metronome.yml`) : tourne en continu (5 h 40, se relance seul ; secours chaque heure ; un seul à
  la fois), lance garde (15 min), buzz (2 h), stats (3 h) si leur dernier passage est trop ancien. Les cron restent en secours.
- `buzz.py` : `ecrire` = module d'écriture ET fonction d'enregistrement → `liste_hashtags` plantait, le buzz n'était plus
  regroupé par l'IA (« une vidéo = un sujet ») → module importé sous le nom `redaction`.
- Créations en attente : un « refaire » d'une vidéo que l'auteur a gardée (À publier, publiée, écartée, `force`) est
  oublié ; la santé ne refait plus une vidéo « À publier ».
- Buffer : pas de 2e envoi après une absence de réponse (double publication possible) ; « Publier maintenant » respecte `force`.
- Vérification des crédits : 5 modèles essayés par IA (limite du jour par modèle chez Gemini).
- Site : longs messages d'erreur (onglet Santé) qui débordaient sur téléphone → `overflow-wrap: anywhere`.
- Test `TestTousLesFichiers` : chaque fichier du robot est chargé (un fichier cassé que les autres tests n'utilisent pas
  passait inaperçu).

## NOUVEAU STYLE « 100 % fabriqué » (26/11, demande de l'auteur, d'après curioverse.actu et vudenhaut.fr)
Constat : nos 4 vidéos publiées restaient à 0 vue exactement (TikTok ne les montrait à personne) : elles reprenaient des
extraits d'autres comptes (BBC, franceinfo, Al Jazeera…), logos visibles = « contenu non original ». Les chaînes modèles ne
reprennent AUCUNE image : cartes animées, gros chiffres, étiquettes, reconstitutions 3D style maquette (curioverse : 186
vidéos en 6 semaines, médiane 908 vues ; alertes météo avec carte médiane 30 000, reconstitutions 3D jusqu'à 1,1 million).
30 images/s comme nous : la fluidité vient du mouvement doux permanent, pas du nombre d'images. Choix de l'auteur : TOUT
remplacer (plus aucun extrait), et tout faire (habillage, cartes, chiffres, 3D). Pas une copie exacte de curioverse (nom,
logo, mise en page) : même recette, notre identité (rouge et jaune du logo sur bleu nuit).
- `video.style` = "anime" (défaut ; Réglages → Style des vidéos) ou "classique" (ancien montage). En « anime » :
  pas de recherche d'images, pas de citations, pas de contrôle des images ; étape « images » = `realisation`.
- `robot/realisateur.py` : l'IA réalisatrice découpe les phrases en scènes (`CONSIGNE` : carte, chiffre, mot, frise, citation,
  barres, 3d, question) ; `valider` contrôle TOUT (chiffre présent dans le texte ou les articles, citation copiée des
  articles, objets / actions / décors 3D de la bibliothèque, lieux trouvés par `carte.trouver_lieu`, toutes les phrases
  couvertes dans l'ordre, la dernière = question) sinon scène sûre (`_secours` : 1er chiffre dit, ou mots forts) ;
  `pour_rendu` : numéros de phrases → secondes (voies → z, caméra qui suit l'objet principal, mention « Reconstitution 3D
  · illustration d'après <source> ») ; `rendre` lance `node robot/rendu/rendre.mjs`.
- `montage.monter_anime` : même voix, même musique (calée sur le rythme), même son -14 LUFS ; mots calés (`V.caler`) →
  sous-titres dessinés par la page ; rendu refait seulement si le storyboard change (`_sig_anime`).
- `robot/rendu/` : `page.html` (habillage : pastille BUZZ INSOLITE + lieu/date, gros titre qui rétrécit après l'accroche,
  logo rond, SOUS-TITRES SANS FOND NOIR : mot dit surligné en jaune, mots importants en jaune, mots à venir pâles ;
  mention et source en bas), `moteur.js` (charger / rendre(t) : rien ne dépend de l'horloge ; scènes carte (Mercator,
  départements Licence Ouverte, pays Natural Earth, zoom lent, pluie / neige / orage, flèche, repères), chiffre (compteur),
  frise, citation, question, barres, photo), `scenes3d.js` (Three.js r170 MIT : voiture, camion, citerne, bus, moto, avion,
  hélico, bateau, train, bâtiment, arbre, personne, muret, mur, cube d'eau ; décors autoroute, route, ville, mer, port,
  plage, piste, voie ferrée, campagne, studio ; actions avancer, heurter, changer_voie, tourner, se_coucher, brûler,
  exploser, tomber, voler, couler ; anneau jaune + étiquette qui suivent un objet ; feu et fumée en particules),
  `rendre.mjs` (Chromium sans écran via Playwright 1.63.0 `package.json`, capture JPEG → ffmpeg H.264 CRF 16, 30 i/s,
  morceaux en parallèle = un par paire de cœurs ; ~0,5 s par image sur un cœur). Workflows creer / tests / essai :
  setup-node 22 + `npm install --prefix robot/rendu` + `playwright install --with-deps chromium` (cache ~/.cache/ms-playwright).
- Contrôles adaptés : chaque phrase animée compte comme illustrée (`media.type` = "anime") ; `controle_video(anime=True)` :
  pas d'écrans noirs ni de regard de l'IA sur les images (on les dessine), voix / sous-titres / durée / format contrôlés ;
  refaire « images » = nouvelle réalisation (`animation` effacée), refaire « texte » = nouveau storyboard.
- Polices : Poppins Medium à Black (OFL). Données : `robot/rendu/geo/LICENCES.md`.
- **1re vraie vidéo (27/11, « Afghanistan : les noms des femmes effacés », 68 s, 100/100, 10 min de fabrication dont 6 min 44 de
  rendu)** : trop statique (7 scènes « mot » sur 13 = diapositives), titre sur 3 lignes qui chevauchait l'étiquette,
  « 21,70 » sans « millions », paragraphes en double avec les sous-titres. Corrigé : scènes `icone` (emoji géant Noto Color
  Emoji, police installée par les workflows), `document` (feuille + lignes + tampon), `calendrier` (page qui se retourne),
  `personnes` (proportion « 3 sur 10 ») ; « mot » 2 fois au plus, 5 types différents demandés ; textes sous un visuel ≤ 60
  signes ; `_unite_du_texte` (unité « millions / milliards / % » reprise de la phrase) ; secours = pictogramme selon les mots
  (`PICTOS`) ; titre ajusté sur 2 lignes (`TITRE_MAX`), jamais sous le logo ; étiquettes placées sous le titre.
- **2e vraie vidéo (27/11, « Parade Macy's reportée », 71 s, 100/100)** : manette 🎮 pour NBC (« jeu » dans « jeudi ») →
  pictogrammes par mots ENTIERS ; « PARMI BUZZ », « 5 novembre » 12 s sur des phrases sans rapport → secours = une scène
  par phrase, jamais une date ni une année comme chiffre, noms propres / sigles d'abord ; l'IA n'avait placé que 5 scènes
  pour 15 phrases → elle recommence si moins de 80 % des phrases sont placées (`_couvre`) ; phrases sur une « attaque
  iranienne au Qatar » (article financier mélangeant plusieurs actus) → `CONSIGNE_VERIF` : phrase HORS SUJET retirée même
  si elle est vraie.

## Nouveau style, version 2 : « au niveau de curioverse » (27/11, demande de l'auteur)
Constat après les 2 premières vidéos : nos scènes étaient des DIAPOSITIVES séparées sur fond vide ; chez curioverse et
vudenhaut, un DÉCOR (Terre vue du ciel ou maquette 3D) reste à l'écran et bouge en continu, les chiffres et étiquettes
s'affichent PAR-DESSUS. Refait ainsi :
- **Décor permanent** (`moteur.js`, `BASES` = carte, 3d, photo) : un décor reste jusqu'au décor suivant (`finDecor`) ;
  les encadrés (chiffre, icone, document, calendrier, personnes, frise, barres, citation, mot) passent par-dessus, le décor
  s'assombrit un peu (`voileDecor`) et ses étiquettes s'effacent. Voile sombre doux derrière un encadré (`voile`).
  Dégradés sombres en haut et en bas (`#voiles`) : titre et sous-titres toujours lisibles.
- **Carte satellite de la NASA** (domaine public) : Blue Marble (jour) ou lumières des villes VIIRS (nuit), tuiles GIBS
  EPSG:3857 niveau 8 au plus, servies par `rendre.mjs` (`/tuile/…`, cache `~/.cache/buzz-insolite/tuiles`) et TOUTES
  chargées avant la 1re image (`tuilesVisibles`, zoom au-dessus en secours) ; frontières et départements par-dessus.
  EOX Sentinel-2 cloudless ÉCARTÉ : licence commerciale payante exigée (même les années « CC BY » sont ambiguës).
- `realisateur.py` : consigne « décor + encadrés » (1re scène = décor, 1 à 3 décors, 3D pour un événement physique,
  `nuit`) ; `pour_rendu` ajoute une CARTE DU LIEU implicite sous le 1er encadré (`implicite`, zoom ×8 sur le lieu géocodé
  `anim["lieu"]`, nuit si les 1res phrases parlent de nuit / soir).
- **3D plus vivante** (`scenes3d.js`) : ciel en dégradé, trottoirs, lampadaires avec halo (sans vraies lumières : rendu
  rapide), immeubles variés avec toits, CIRCULATION automatique sur les voies libres (jamais sur la chaussée de l'accident).
- Bug : un lieu seul (un point) était pris pour « rien à montrer » → la carte ne zoomait pas.
- Feu refait (flamme allongée qui vacille, lueur orange au sol, fumée qui monte et s'élargit, véhicule qui noircit).
- **3e vraie vidéo (27/11, « Octogénaire défie la police à Tirana », 79 s, 100/100)** : carte satellite de l'Albanie sous
  tous les encadrés (mieux), mais 11 encadrés sur 14 (pictogrammes ratés « JARED », « D'ALIMENTER », élève 🧑‍🎓 deux fois),
  aucune 3D pour une manifestation, document qui chevauchait les sous-titres, et RENDU DE 26 MIN (filtre CSS
  `brightness` sur le décor : sans carte graphique il doublait le coût de chaque image). Corrigé : voile dessiné une seule
  fois (`voile`, plus de filtre) ; objets 3D `foule` (InstancedMesh, chacun sautille), `police` / `pompiers` / `ambulance`
  (`vehiculeUrgence` : gyrophares qui clignotent), `batiment_officiel` (colonnes, fronton, drapeau qui flotte) ; décor
  `place` (dalles, immeubles autour) ; `userData.anime(t)` appelé à chaque image ; consigne : les décors occupent au moins
  la moitié de la vidéo, « valeur » d'icône = des NOMS, chaque emoji une fois ; valeur commençant par « d' / le / la… » =
  pictogramme seul ; document plus court (640 px).

## Outils gratuits pour faire « exactement » comme curioverse (27/11, demande de l'auteur)
Recherche faite : aucune source publique sur la façon dont curioverse fabrique ses vidéos ; les briques gratuites retenues :
- **Vrais modèles 3D Kenney, CC0** (usage commercial permis) : `robot/rendu/modeles/` (8 Mo, `LISEZMOI.md`), copies
  officielles d'OpenGameArt (kenney.nl refuse le serveur de la session) : Car Kit (voitures, taxi, camionnette, camion,
  POLICE, AMBULANCE, POMPIERS, débris, cônes), City Kit Commercial / Suburban (immeubles, gratte-ciel, maisons), Mini
  Characters (personnes), Watercraft (bateaux, conteneurs), Train Kit, Nature Kit (arbres, palmiers, rochers). Chargés par
  `GLTFLoader` (`vendor/addons`, importmap `three/addons/`) ; `scenes3d.MODELES` : type → variantes, taille réelle (longueur
  ou hauteur), avant du véhicule tourné vers +x ; `prechargerModeles` avant la 1re image ; immeubles et arbres du décor en
  vrais modèles (sauf la nuit : fenêtres allumées dessinées) ; circulation en vrais modèles. Types sans modèle (citerne,
  bus, avion, hélico, grand cargo, foule, bâtiment officiel) gardent leur forme dessinée.
- **Vraies rues et vrais bâtiments du lieu** : OpenStreetMap via l'API Overpass (gratuite, attribution « © OpenStreetMap »)
  — bloqué depuis le réseau de la session (à faire et tester depuis GitHub).
- **Modèles de vidéo FIXES** (`robot/gabarits.py`, réglage `video.realisation` = "gabarit" par défaut, sinon l'IA
  réalisatrice) : l'IA n'EXTRAIT que des faits (`CONSIGNE` : type parmi `TYPES_EVENEMENT`, lieu, nuit, départements, pays,
  acteurs {id, type, rôle}, déroulé {phrase, qui, action, cible}, 3 chiffres, date, titre, source) ; le ROBOT compose
  (`composer`) : carte d'accroche → reconstitution 3D (`_scene_3d` : décor selon le type `DECOR`, acteurs placés sur les
  voies, secours qui arrivent de loin, foule + police + bâtiment officiel pour une manifestation, actions calées sur leur
  phrase, repères « rôle ») → encadrés chiffres / calendrier par-dessus (jamais phrase 1 ni dernière) → scène `suite`
  (rien par-dessus : la 3D réapparaît après un encadré) → carte « LE BILAN » → question. Météo / catastrophe : la carte
  tout du long (départements ou pays colorés, pluie, neige, orage). Contrôlé ensuite par `realisateur.valider` ;
  extraction impossible ou sans lieu → IA réalisatrice. Carte : un lieu précis = on plonge sur la ville, le pays reste
  coloré autour (`cadrer_zones` pour cadrer tout le pays). Ombres des grands pictogrammes retirées (trop lentes).

## Leçons de bonnequestion.tv (27/11, chaîne donnée par l'auteur)
284 vidéos en 7 semaines, médiane 51 000 vues, 102 au-dessus de 100 000 (jet en Floride 2 M, TGV Séville 1,2 M, Bataclan
1,1 M, A13 fermée 1 M). 72 à 116 s. Recette relevée image par image et reprise (sans copier nom, logo ni mise en page) :
- **Accroche = le moment le plus fort, tout de suite** (avion qui tombe, « 8 000 MÈTRES en une minute. »), dans un VISEUR
  (coins de caméra, « ● RECONSTITUTION · lieu · heure qui défile »), puis retour au début du récit. → `gabarits._accroche`
  (copie de la 3D, actions fortes `FORTS` sur la phrase 0, `accroche: true`), `#viseur` de page.html, `sb.viseur` / `viseur_heure`.
- **Horloge + chapitres** sous le titre (« ● 21:40 » + barre en étapes « 1/5 · L'ATTAQUE ») qui avancent avec le récit.
  → l'IA extrait `heures` (gabarits.CONSIGNE) ; `_heures` ne garde qu'une heure VRAIMENT dite dans SA phrase, dans l'ordre,
  2 au moins ; `sb.chrono` ; `#chrono` dans moteur.js. Consigne d'écriture : récit dans l'ordre avec les heures des articles.
- **Vue « maquette » isométrique** (Bataclan : salle, rue, foule vues d'en haut, sans perspective) → `vue: "iso"` dans
  scenes3d.js (caméra orthographique, même angle, zoom lent) pour manifestation, police / justice, incendie, explosion (`VUE_MAQUETTE`).
- **Instruments** : jauge de vitesse (aiguille, zone rouge au-delà de la limite) → type `jauge` (chiffre en km/h ou nœuds).
  Vus aussi (pas encore faits) : altimètre, message radio avec onde sonore, téléphone « appel entrant », compteur 6/11.
- Mention « Reconstitution · plan simplifié · positions approximatives » ; fin « ＋ ABONNE-TOI POUR LA SUITE » sur la question.
- Leurs cartes sont PLATES (terre crème, mer bleu clair, ou plan de rues sombre avec routes jaunes pour l'A13) : nos cartes
  satellite restent (curioverse) ; un plan de rues demanderait OpenStreetMap (Overpass, bloqué ici).
- Sujets : beaucoup de « service » au tutoiement (« Ta carte Revolut refusée ? », « par où passer », « tu as le droit de sortir ? »).

## Reconstitution COMPLÈTE des faits (27/11, l'auteur : « tu ne reconstitues pas entièrement les faits, va bien plus loin »)
- **Chaque étape DITE est montrée** : `gabarits._completer` lit chaque phrase (`MOTS_ACTIONS` : choc, se renverse, fuite de
  carburant, prend feu, explosion, chute, naufrage) et ajoute l'action oubliée par la petite IA ; un 2e véhicule est créé
  pour un choc ; secours (`SECOURS`) qui arrivent à leur phrase ; « 27 véhicules brûlent » / « propage » → **bouchon** de 6
  véhicules qui arrivent derrière puis prennent feu un à un (`_bouchon`, `retard`). Type d'événement déduit du texte si
  l'IA dit « autre » (`type_du_texte`, vidéo de l'Iowa du 27/11 : explosion classée « autre » → pictogrammes sur fond vide) ;
  lieu repris du texte ; IA en panne = recette d'après le texte seul. Explosion / incendie sans véhicule = un bâtiment.
- **Un plan par étape** (`realisateur.plans_camera`, `PLANS`) : la caméra COUPE vers le bon angle juste avant chaque action
  (choc de côté au ras du sol, renversement de face, flaque vue de haut, feu en plan large, secours), le plus fort d'abord
  à moments égaux, plans de 1,4 s au moins, recul selon la taille (`GRANDS`).
- **Effets** (scenes3d.js) : éclair + 28 débris qui volent et retombent + caméra qui tremble au choc ; flaque de carburant
  qui s'étale et brûle sur toute sa surface (`deverser`) ; boule de feu + onde de choc (`exploser`) ; anneaux 3,5 s.
- **Bug corrigé** : la voiture visait la place de DÉPART du camion (il avait avancé) → elle frappait le vide. `etat` calcule
  maintenant où se trouve la cible à l'instant du choc.
- Pendant la 3D, un chiffre devient une ÉTIQUETTE par-dessus (« 27 VÉHICULES ») au lieu d'un encadré qui cachait l'action ;
  la jauge de vitesse reste un encadré. Citerne redessinée (cabine orange, citerne brillante, bandes rouges, losange danger).

## Scénario de reconstitution PLAN PAR PLAN (27/11, l'auteur : « reconstitue exactement comme ça s'est passé, de A à Z »)
`robot/reconstitution.py` : une IA écrit le scénario comme un story-board (décor, moment, objets avec voie / position,
UN PLAN PAR PHRASE : actions, angle `cadre`, étiquette) ; `valider` garde seulement ce que la 3D sait faire (OBJETS, ACTIONS,
DECORS, CADRES), remet les plans dans l'ordre, jamais sur l'accroche ni la question, retire une étiquette au chiffre inventé.
`gabarits._appliquer_scenario` le transforme en acteurs / déroulé / `_cadres` / `_etiquettes` / `_decor`, puis `_completer`
ajoute ce que le texte raconte et que l'IA a oublié. `realisateur.plans_camera(..., cadres)` : les angles du scénario passent
avant les plans automatiques (`CADRES` : large, cote, face, dessus, suivi, interieur = vue du conducteur avec `regard`,
maquette). Nouvelles actions 3D : freiner, deraper (tête-à-queue), tonneau, effondrer, arroser (jets d'eau des pompiers),
fuir (personnes qui courent) ; sans destination, `distance` depuis l'endroit où l'objet se trouve. Nouveau décor `usine`
(hangars, cheminées, cuves, clôture), choisi pour une explosion / un incendie d'usine, d'entrepôt, de dépôt de munitions.
Limite honnête : la précision dépend des articles ; ce qui n'est pas dit reste simple (« positions approximatives »).
Workflows : dépôt apt de Microsoft retiré avant `playwright install --with-deps` (403 le 27/11 : création impossible).

- **Iowa refaite (27/11, 1re version : 55 s d'un immeuble immobile, explosion jamais montrée)** : « détonations » non reconnu ;
  explosion / incendie TOUJOURS montrés (`_completer` : boule de feu à la 1re phrase qui en parle, sinon phrase 2 ; fumée sur
  « nuage / fumée ») ; évacuation → foule qui s'enfuit ; dépôt / usine / munitions → objet `entrepot` (hangar à toit arrondi,
  panneau danger) au centre du décor `usine` ; boule de feu en 9 halos lumineux (jaune, orange, rouge), 40 débris, bâtiment
  qui s'affaisse et noircit ; bâtiments jamais sur la route ; pays coloré en voile léger quand on plonge sur une ville.

- **Iowa r2 (27/11)** : explosion enfin visible, mais tour de bureaux au lieu du dépôt, 2e moitié figée, carte noire et mauvais
  lieu. Corrigé : `_completer` montre aussi l'APRÈS (`APRES` : barrières de terre qui apparaissent, mousse / eau des pompiers,
  drone qui survole, experts qui prélèvent, police qui boucle) ; « Middletown, Iowa » cherché en ENTIER (« Middletown » seul =
  une autre ville) ; « soir » n'est plus la carte de nuit (presque noire au zoom 8) ; dans le décor usine, bâtiment = entrepôt ;
  muret / mur / arbre / taxi du scénario gardés ; vue maquette seulement si le scénario n'a pas choisi ses angles.

## Destruction réaliste (27/11, l'auteur : « le camion est toujours intact » après l'explosion)
`scenes3d.desintegrer` : à l'instant de l'explosion, les vraies pièces de l'objet sont détachées (`scene.attach`) ; les grosses
pièces (> 3 m³, bâtiment > 30 m³) sont cassées en éclats de la même matière ; vitesse vers l'extérieur + vers le haut, rotation,
vol balistique jusqu'au sol (`tSol`), petite glissade, puis immobiles ; le châssis reste (épave noircie qui brûle) ; un bâtiment
perd surtout son haut. Tout dépend de t seulement (état de l'objet recalculé à l'instant de l'explosion) : rendu en morceaux
parallèles identique. Souffle (`etat`, `rayon_souffle` 18 m) : ce qui est proche est repoussé, penche, tremble et prend feu
(petit feu préparé pour chaque véhicule s'il y a une explosion). Choc : l'avant du véhicule qui percute et l'arrière du
percuté s'écrasent (`ecrase`, échelle en longueur).

## Son, ombres et phonétique (27/11, recherche demandée par l'auteur)
- **Bruitages des reconstitutions** (`sons/reconstitution/`, tous CC0 d'OpenGameArt, détail dans `LICENCES.md`) :
  `realisateur.evenements_sonores(sb)` → choc à l'impact, explosion + débris qui retombent, feu qui crépite tant que la 3D
  est à l'écran, sirène à l'arrivée des secours ; `sons.mixer(effets=)` les place à l'instant exact (feu / sirène répétés
  puis effacés). Réglage `video.sons_reconstitution` (vrai par défaut ; différent de `bruitages`, coupés par l'auteur).
- **Ombres portées** (scenes3d.js) : soleil avec ombre douce 2048 px sur 120 m autour de ce qu'on filme ; tout objet solide
  fait et reçoit une ombre (`sc.ombres` false pour couper). Coût mesuré : rendu +30 %.
- **Phonétique** (`robot/phonetique.py`) : WikiPron (Wiktionnaire, CC BY-SA, 97 000 mots prononcés EN FRANÇAIS, noms propres
  étrangers compris) + Lexique 3.83 (CC BY-SA 4.0, 142 000 mots courants), téléchargés une fois (cache
  `~/.cache/buzz-phonetique`, creer.yml). `prononciation.respeller` part de la prononciation française du Wiktionnaire
  (avant : eSpeak anglais) ; `candidats` ne réécrit jamais un mot français courant.
- Caméra : vue du conducteur seulement depuis un véhicule ; décors denses (usine, ville, port) = caméra plus loin et plus
  haute ; étiquettes « PAS_DE_LEAD » (code / anglais) retirées.
- Pistes trouvées, pas encore branchées : three-pinata (MIT, vraie fracture Voronoï), three.quarks (particules), N8AO
  (ombre douce des coins), Quaternius / Poly Pizza (modèles CC0 plus détaillés), Kyutai TTS (CC BY 4.0, français, à
  tester sur processeur), DeepFilterNet (MIT/Apache, nettoyage de voix), dictionnaire MFA français (CC BY 4.0).

- **Iowa r4 (27/11, pire par endroits : images noires, blocs suspendus en l'air)** : le scénario plaçait 4 entrepôts au MÊME
  endroit (débris coincés dans les murs) et mettait le président et l'agence EPA sur place ; la caméra traversait tout ; la
  carte cherchait encore « Middletown » seul. Corrigé : `reconstitution.valider` espace les bâtiments (46 m) et les véhicules
  d'une même voie (9 m), écarte les personnes qui n'étaient pas sur place ; `scenes3d` : rayon de la cible vers la caméra
  (`Raycaster`) → si un objet solide coupe la vue, la caméra se place devant, plus haut (`sc.anti_collision` false pour
  couper) ; `realisateur.valider` cherche le lieu avec son nom COMPLET d'abord.

## Outils gratuits branchés (27/11, « fait le 2 »)
- **Vraie fracture** : three-pinata 2.0.1 (MIT, `vendor/three-pinata.es.js`, importmap `@dgreenheck/three-pinata`) dans
  `scenes3d.fracturer` : une grosse pièce qui explose est découpée en cellules de Voronoï de SA forme (12 éclats, bâtiment
  22), faces de cassure sombres, graine fixe (mêmes éclats dans chaque morceau de rendu) ; échec → éclats en blocs.
- **Feu et fumée en particules** : three.quarks 0.16.0 + quarks.core 0.16.0 (MIT ; les versions ≥ 0.17 exigent Three.js
  r182) dans `robot/rendu/effets.js` : flammes (260 particules, blanc-jaune → orange → rouge sombre), fumée qui gonfle et
  dérive au vent, étincelles. REPRODUCTIBLE : `Math.random` remplacé par une suite fixe (Mulberry32) pendant la simulation,
  rejouée depuis 0 par pas de 1/30 s jusqu'à l'image demandée ; chaque objet qui brûle (incendie, explosion, souffle) a sa
  source (`etat(o, actions, 1e4)` donne l'instant du feu) ; anciennes flammes masquées (`q.quarks`), flaque et lueur gardées.
  Coût mesuré : rendu +40 % sur un passage de feu. `sc.quarks` false pour couper.
- **Modèles Quaternius CC0** (`modeles/quaternius/`, `LICENCE.md`) : bus et car scolaire, feu tricolore, panneaux, hôpital,
  banque, résidences, magasin (types `bus`, `feu_tricolore`, `panneau`, `hopital`, `banque`, `magasin`, `residence`) ; les
  OBJ n'ayant pas de couleurs, elles sont données d'après le nom des pièces (vitres, phares…). Décor « ville » : quartier
  varié et feux tricolores tous les 60 m ; circulation avec de vrais bus.

## Corrections après Gizeh + carte blanche de l'auteur (27/11 au soir)
- **Voix** : la voix lit le texte ÉCRIT converti par le robot (`voix.preparer` : `p["voix"] = p["ecrit"]`) — l'IA avait écrit
  « trente-et-une morts » ; nombres accordés au genre du nom qui suit (`nombres._feminin`, genre des noms de Lexique 3.83,
  `phonetique.genre`, cache `phonetique-v2`) ; « 1,5 million » → « un million et demi » ; « 2-1 » / « 20-30 » → « à » ;
  mots à l'allure anglaise inconnus des dictionnaires réécrits AVANT la 1re prise (`prononciation._anglais`, eSpeak anglais ;
  un nom connu du Wiktionnaire est laissé : la voix le connaît) ; seuil Whisper 75 → 85 % (`voix.SEUIL_COMPRIS`).
- **Voix moins robot** : vitesse changée par Rubber Band (`voix._rubberband`, formants préservés) au lieu d'atempo
  (métallique) ; finition studio `voix.FINITION` (passe-haut 75 Hz, chaleur 180 Hz, présence 3,2 kHz, de-esser, compresseur
  doux) ; Chatterbox cfg_weight 0,4, temperature 0,75, émotion 0,55 / 0,65 / 0,72.
- **3D** : calendrier petit (280 px) à droite sous le logo, sans assombrir la scène ; « citerne » dans le texte = jamais un
  simple camion ; objet DÉJÀ en feu filmé en plan large (`_cam(feux=)`) ; caméra jamais à moins de 2,2 m au-dessus de la
  cible ; toujours la carte du lieu ; fumée plus légère.
- **Catastrophes en 3D** (`gabarits.NATURELS`, `_naturel`) : inondation (eau boueuse qui monte, véhicules qui flottent et
  dérivent, habitants évacués), séisme (secousse, immeubles qui s'effondrent EN TAS — `desintegrer(chute=true)` — avec
  nuage de poussière beige three.quarks), feu de forêt (décor `foret`, 7 arbres qui s'embrasent un à un, pompiers, bombardier
  d'eau), tempête (pluie en biais, arbres qui plient, arbre qui tombe). Reconnues dans le texte (`TYPE_MOTS`) même si l'IA
  dit « catastrophe naturelle » ou « météo ». Plans `inonder`, `trembler`, `effondrer`, `tempete`, `fuir` ; jamais sans
  caméra (`_cam` / `scenes3d`).

## Gizeh r2 et qualité 3D automatique (27/11 au soir)
Défauts vus par l'auteur : camion-citerne qui « s'élève » à 20 m (le scénario lui donnait `voler` sur « la fumée s'élève »),
voiture qui percute le vide (choc raconté À LA FIN, joué après l'incendie), dégâts invisibles. Corrigé pour toutes les vidéos :
- `reconstitution.valider` : `voler` / `tomber` seulement pour avion / hélico ; `gabarits._completer` : un choc raconté APRÈS
  que sa cible s'est renversée / a brûlé / explosé est remis AVANT (`_avant`), et dans la même phrase la cible ne prend feu
  qu'après l'impact (`retard` = durée du choc + 0,3 s) ; « s'effondre » / « chavire » = se renverse.
- Vrais dégâts au choc : `scenes3d.cabosser` enfonce la carrosserie autour du point d'impact (les deux véhicules, géométrie
  clonée, calculé une fois), 40 débris aux couleurs des deux véhicules (`couleursDe`) dont des éclats de vitre.
- Plans jamais figés plus de 6 s (`realisateur._cam` ajoute plan large / vu de dessus / rapproché).
- **IA qui regarde la reconstitution finie** (`controle._regarder_anime`, `CONSIGNE_3D` : objet qui flotte, caméra dans un
  objet, image vide, incohérence avec la phrase, texte qui cache l'action) → `controle.corriger_anime` : 1er tour plan large,
  2e tour actions de la phrase retirées (sauf feu / explosion), puis nouveau rendu ; 2 corrections au plus, le reste au bulletin.
- L'après d'un accident (`APRES`) : police pour l'enquête, engins qui déblaient, circulation qui reprend.

## PAUSE de l'ancien modèle (27/11, demande de l'auteur)
En attendant que le nouveau style soit validé : `publication.auto` et `creation.auto` = false (reglages.json) ; les 11
vidéos de l'ANCIEN style non publiées sont « écartées » (`ecartee_pause`, réversibles depuis le site) ; la santé de la nuit
ne refait plus aucune vidéo quand la création automatique est coupée. Les 4 vidéos publiées de l'ancien style ont été
supprimées de TikTok par l'auteur (0 vue) : `retiree_le` + `supprimee_par_auteur` (pas d'alerte, comptes non pénalisés).
Pour reprendre : remettre les deux réglages « auto » dans Réglages.

## IA de secours ajoutées (26/11, demande de l'auteur « n'as-tu pas trouvé d'autres IA de secours ? »)
Listes communautaires (awesome-free-llm-apis) relues ; retenues = gratuites, sans carte, usage commercial non interdit :
- **GitHub Models** (`github`) : jeton de la tâche (`GITHUB_MODELS_TOKEN: ${{ github.token }}`, permission `models: read`),
  AUCUNE clé à créer ; voit les images (gpt-4.1-mini, gpt-4o-mini) ; catalogue https://models.github.ai/catalog/models lu
  pour les secours (`supported_input_modalities`) ; limites par modèle et par jour.
- Facultatives, actives dès que l'auteur ajoute la clé gratuite : **Cerebras** (`CEREBRAS_API_KEY`, texte), **Cloudflare
  Workers AI** (`CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`, 10 000 neurones/jour, voit les images), **Z AI**
  (`ZAI_API_KEY`, GLM « flash », voit les images). `ia.a_cle(f)` (clé + n° de compte), `ia.VISION_ORDRE`.
- ÉCARTÉES : Cohere (usage NON commercial), NVIDIA NIM (prototypes seulement, production = licence payante), Kilo Code /
  Requesty (gardent et réutilisent les textes), petits services inconnus.

## Avant d'envoyer
`python -m unittest discover -s tests` (aucun appel réseau ni IA ; ffmpeg nécessaire pour l'essai complet). Essai sans IA :
`SIMULATION=1 python -m robot.principal --libre "Essai"`. ⚠️ Cet essai local écrit dans `docs/donnees` et `docs/miniatures` : `git checkout docs/ && git clean -fd docs/miniatures` AVANT d'envoyer (26/11 : une fausse vidéo d'essai est partie sur le site). Site : servir `docs/` et l'ouvrir à 400 px de large.
