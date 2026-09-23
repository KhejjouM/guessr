# 🎯 Guessr

Jeu de devinettes façon GeoGuessr, multi-niches : **Sneakers · Montres · Motos · Voitures**.
Une photo apparaît ultra-zoomée et floutée, elle se dévoile progressivement — plus tu réponds
vite, plus tu scores.

## Lancer

```bash
python3 -m http.server 8642 --directory "$(dirname "$0")"
```

Puis http://localhost:8642. Fonctionne aussi en double-cliquant `index.html` (le contenu est
servi via `content.js`, pas un `fetch`, justement pour rester jouable en `file://`).

## Modèle

Chaque thème a sa partie gratuite et sa partie payante :

| | Gratuit | Premium |
|---|---|---|
| **Daily** | 1 défi par thème et par jour | idem |
| **Parties illimitées** | — | ✅ |
| **Mode Expert** | — | ✅ |

Le **daily est déterministe** : tout le monde reçoit le même tirage le même jour, donc les
scores sont comparables — c'est ce qui rend le partage intéressant. Le bouton « Partager »
copie une grille façon Wordle :

```
Guessr 👟 Sneakers #265 — 18 420 pts
🟩🟩🟨⬜🟩  🔥3
```

🟩 trouvé à la saisie · 🟨 trouvé au QCM · ⬜ raté

## Règles

- **5 manches**, **5000 pts max** par manche (plancher 800), **15 s** de chrono.
- **0 → 7,5 s** : saisie libre uniquement. Le *fuzzy matching* accepte le nom complet, le nom
  sans la marque (« countach » pour Lamborghini Countach) et tolère les fautes de frappe.
  Chaque essai raté coûte **−300 pts**.
- **7,5 s → 15 s** : un QCM de 6 choix apparaît (leurres de la même marque et de notoriété
  proche). La saisie reste possible et rapporte plus.
- Le daily entretient une **série** (🔥) tant que tu joues chaque jour.

## Contenu

Le pipeline (`tools/`) évite la recherche plein-texte, qui renvoie n'importe quoi — dans une
version précédente, « Bugatti Chiron » avait ramené une photo de son moteur, et
« Converse One Star » une boucle de ceinture médiévale. Il s'appuie sur deux sources
structurées :

- **Wikidata** (motos, voitures) — chaque modèle est une entité typée avec sa marque (P176)
  et son image canonique (P18). Le nombre de versions linguistiques sert de **mesure de
  notoriété** : une voiture présente dans 40 langues est iconique, une présente dans 2 rend
  le quiz injouable. On trie par notoriété et on coupe.
- **Catégories Wikimedia Commons** (sneakers, montres) — mal couverts par Wikidata, mais les
  catégories sont curées à la main. Seules les catégories **spécifiques à un modèle** sont
  utilisées ; une catégorie de marque mélangerait les modèles et casserait le label.

Cette notoriété alimente aussi les paliers : le daily pioche dans le haut du panier pour
rester accessible, le mode Expert ouvre tout le catalogue.

```bash
python3 tools/fetch_content.py          # récupère (reprend où il s'était arrêté)
python3 tools/build_content.py          # génère content.js + élague les orphelines
```

## Héberger / mettre à jour

Le jeu est publié via **GitHub Pages** (branche `main`, racine) :
👉 **https://khejjoum.github.io/guessr/**

Un `git push` sur `main` redéploie automatiquement (build ~1 min, puis propagation CDN).

⚠️ **Si tu modifies `game.js` ou `content.js`, incrémente le `?v=` des deux balises
`<script>` dans `index.html`.** Sans ça, les visiteurs déjà venus gardent l'ancien code
en cache et ne voient jamais la mise à jour.

## Limites connues

- **Les sneakers sont la niche la plus pauvre en contenu libre** : Wikimedia a des milliers
  de voitures mais seulement quelques photos par modèle de sneaker. Passer à l'échelle sur
  cette niche demanderait une autre source (licence payante ou partenariat).
- Le **login est une démo locale** (localStorage, hachage jouet) — ce n'est pas un système
  d'authentification sécurisé.
- Le **paywall est fictif** : n'importe quelle carte au bon format passe, aucun échange
  réseau, rien n'est débité. **N'entre jamais de vraie carte bancaire.**

## Crédits images

Photos issues de [Wikimedia Commons](https://commons.wikimedia.org), sous leurs licences
respectives. L'auteur et la licence de **chaque image** sont listés dans le jeu
(bouton « Crédits & licences ») — c'est ce qu'exige CC-BY.
