# Buzz Insolite (buzz-insolite)

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
4 tours, images 5, vidéo finie 12) avec une échelle de solutions dont la dernière marche à coup sûr : image → nouvelle
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
  l'auteur. Secrets : `BUFFER_API_KEY`, `PEXELS_API_KEY` (facultatif), `PIXABAY_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `VIMEO_TOKEN` (facultatif).

## Avant d'envoyer
`python -m unittest discover -s tests` (aucun appel réseau ni IA ; ffmpeg nécessaire pour l'essai complet). Essai sans IA :
`SIMULATION=1 python -m robot.principal --libre "Essai"`. Site : servir `docs/` et l'ouvrir à 400 px de large.
