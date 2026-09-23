#!/usr/bin/env python3
"""
Transforme content.json en content.js consommable par le jeu.

Pourquoi un .js et pas le .json : un <script src> fonctionne en file://, alors qu'un
fetch() sur un fichier local est bloqué par CORS. Le jeu reste donc jouable en
double-cliquant index.html, sans serveur.

Au passage : on retire les items dont l'image manque, et on supprime les images
orphelines laissées par d'anciens runs.
"""

import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "images")

with open(os.path.join(ROOT, "content.json")) as f:
    content = json.load(f)

clean, referenced = {}, set()
for theme, items in content.items():
    kept = []
    for it in items:
        path = os.path.join(IMG_DIR, theme, it["id"] + "." + it.get("ext", "jpg"))
        if os.path.exists(path) and os.path.getsize(path) > 2000:
            kept.append(it)
            referenced.add(os.path.relpath(path, ROOT))
        else:
            print(f"  - image manquante, item retiré : {theme}/{it['id']}")
    if kept:
        clean[theme] = kept

# Élagage des images orphelines, thème par thème. On ignore les dossiers absents de
# content.json : ce sont des thèmes en cours de génération, pas des orphelins.
removed = 0
for theme in os.listdir(IMG_DIR):
    tdir = os.path.join(IMG_DIR, theme)
    if not os.path.isdir(tdir) or theme not in content:
        continue
    for fn in os.listdir(tdir):
        rel = os.path.relpath(os.path.join(tdir, fn), ROOT)
        if rel not in referenced:
            os.remove(os.path.join(ROOT, rel))
            removed += 1

with open(os.path.join(ROOT, "content.json"), "w") as f:
    json.dump(clean, f, ensure_ascii=False, indent=1)

with open(os.path.join(ROOT, "content.js"), "w") as f:
    f.write("/* Généré par tools/build_content.py — ne pas éditer à la main. */\n")
    f.write("window.GUESSR_CONTENT = ")
    json.dump(clean, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")

names = {t: len({i["name"] for i in v}) for t, v in clean.items()}
print(f"\n{removed} image(s) orpheline(s) supprimée(s)")
print("photos :", {t: len(v) for t, v in clean.items()})
print("modèles distincts :", names)
