#!/usr/bin/env bash
# (28/11) Aperçu 3D du site : copie le CODE du moteur de rendu (léger) dans docs/rendu/, servi par GitHub Pages. Les modèles
# 3D, polices et cartes (lourds) ne sont pas copiés : l'aperçu les lit directement sur GitHub (raw.githubusercontent.com).
set -eu
cd "$(dirname "$0")/.."
mkdir -p docs/rendu
rm -rf docs/rendu/vendor
cp robot/rendu/page.html robot/rendu/moteur.js robot/rendu/scenes3d.js robot/rendu/effets.js docs/rendu/
cp -r robot/rendu/vendor docs/rendu/vendor
echo "moteur copié dans docs/rendu"
