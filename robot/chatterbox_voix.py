"""Voix « homme français » : Chatterbox Multilingual (Resemble AI, licence MIT), lancé dans son propre espace Python.

Chatterbox a besoin de versions de bibliothèques qui gêneraient le reste du robot : il tourne donc à part (~/venv-chatterbox,
voir creer.yml) et ce fichier ne dépend que de lui. Il imite la voix de référence sons/voix/bernard.wav (lecteur « Bernard »
de LibriVox, enregistrement du domaine public, voir sons/LICENCES.md).

    python robot/chatterbox_voix.py travail.json
travail.json = {"reference": "…wav", "phrases": [{"texte": "…", "chemin": "…wav", "emotion": 0.5}, …]}
Le modèle est chargé UNE fois pour toutes les phrases de ce calcul ; robot/voix.py en lance plusieurs EN MÊME TEMPS, chacun
avec sa part des cœurs (CHATTERBOX_COEURS) et l'intensité de chaque phrase (« emotion » = exaggeration de Chatterbox).
"""
import json
import sys
import wave


def main():
    import numpy as np
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    travail = json.load(open(sys.argv[1], encoding="utf-8"))
    import os
    torch.set_num_threads(int(os.environ.get("CHATTERBOX_COEURS") or max(1, torch.get_num_threads())))
    modele = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    for i, p in enumerate(travail["phrases"]):
        son = modele.generate(p["texte"], language_id="fr", audio_prompt_path=travail["reference"],
                              exaggeration=float(p.get("emotion", 0.55)), cfg_weight=0.4, temperature=0.75)
        # (27/11 : intonation un peu plus vivante, débit plus posé et moins « mécanique » : cfg 0,5 → 0,4 ; temperature
        #  0,75 = moins d'à-coups d'une phrase à l'autre, conseils de réglage de Chatterbox Multilingual)
        x = son.squeeze(0).detach().cpu().numpy()
        with wave.open(p["chemin"], "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(modele.sr)
            w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
        print(f"phrase {i + 1}/{len(travail['phrases'])}", flush=True)


if __name__ == "__main__":
    main()
