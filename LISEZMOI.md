# 🔥 Buzz Insolite

Robot gratuit qui fabrique des vidéos TikTok sur les actualités françaises et européennes qui buzzent.

## Mise en route (une seule fois)
1. **Secrets** (Settings → Secrets and variables → Actions → New repository secret) : recopie depuis jt-auto
   `BUFFER_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, et ajoute `PEXELS_API_KEY`
   (clé gratuite sur pexels.com/api).
2. **Site** : Settings → Pages → Source « Deploy from a branch » → branche `main`, dossier `/docs` → Save.
   Le site sera sur https://tiranno06.github.io/buzz-insolite/
3. **Buffer** : relie le compte TikTok de la chaîne (publish.buffer.com → Channels → Connect → TikTok).
4. Sur le site : ⚙️ Réglages → colle ta clé GitHub, écris le nom du compte TikTok de Buffer, « Tester Buffer », enregistre.
5. 🔥 Buzz → « Chercher maintenant », puis ➕ Créer → « Lancer la série ».
