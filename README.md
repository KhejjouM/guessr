# 🎯 Guessr

Jeu de devinettes façon GeoGuessr, en local. 4 thèmes : **Sneakers, Moto, Montre, Voiture**.
Une photo apparaît ultra-zoomée et floutée, elle se dévoile — plus tu réponds vite, plus tu scores.

## Lancer le jeu

```bash
python3 -m http.server 8642 --directory "$(dirname "$0")"
```

Puis ouvrir http://localhost:8642 (marche aussi en double-cliquant `index.html`).

## Règles

- **5 manches** par partie, **5000 pts max** par manche (plancher 800), **15 s** chrono.
- **Phase 1 (0 → 7,5 s)** : saisie libre uniquement. Tape le nom du modèle
  (les surnoms marchent : « aj1 », « af1 », « 2cv », « f40 », « sub »…).
  Chaque essai raté = **−300 pts** de pénalité sur la manche.
- **Phase 2 (7,5 s → fin)** : un QCM de **6 choix** apparaît (leurres de la même
  marque en priorité). La saisie reste possible.
- Mauvaise réponse au QCM ou temps écoulé = **0 pt**, la manche s'arrête.
- Record par thème sauvegardé sur ton compte.

## Comptes & Premium (démo)

- **Login local** : comptes stockés dans le `localStorage` du navigateur,
  rien ne part sur internet (le « hachage » du mot de passe est un jouet, pas de la vraie sécurité).
- **Paywall fictif** : le thème Sneakers est gratuit ; Moto, Montre et Voiture demandent
  « Premium ». N'importe quelle carte au bon format passe (ex : `4242 4242 4242 4242`,
  expiration future, CVC 3 chiffres). **Aucun paiement réel, aucun échange réseau —
  n'entre jamais une vraie carte.**

## Contenu

55 photos libres de droits (Wikimedia Commons), toutes vérifiées :

| Thème | Modèles |
|---|---|
| 👟 Sneakers (19) | Jordan 1 & 4, AF1, SB Dunk, Air Max 1/90/97, Cortez, Blazer, Chuck Taylor, Superstar, Stan Smith, Samba, Yeezy 350, Old Skool, NB 574, Puma Suede, Reebok Classic, Gel-Lyte III |
| 🏍️ Moto (12) | Fat Boy, Panigale, Ninja, Gold Wing, YZF-R1, R 1200 GS, Bonneville, Vespa, Duke, Hayabusa, Bullet, Indian Chief |
| ⌚ Montre (12) | Submariner, Daytona, Speedmaster, Seamaster, Royal Oak, Nautilus, Tank, F-91W, G-Shock, Apple Watch, Swatch, Monaco |
| 🚗 Voiture (12) | 911, F40, Countach, 2CV, New Beetle, Mini, Model S, Mustang, 205 GTI, 300 SL, DeLorean, Chiron |

## Ajouter un modèle

1. Déposer la photo dans `images/<theme>/<id>.jpg`
2. Ajouter dans le tableau `THEMES` de `index.html` :
   `{ id:"mon_id", name:"Nom affiché", brand:"Marque", aliases:["surnom1","surnom2"] }`

## Crédits images

Toutes les photos proviennent de [Wikimedia Commons](https://commons.wikimedia.org) et restent
sous leurs licences libres respectives (CC BY / CC BY-SA / domaine public selon le fichier).
Projet de démo sans usage commercial.

## Pistes v3

- Classement multi-joueurs (nécessite un vrai backend)
- Streaks / multiplicateurs, mode chrono global
- Indices payants (dévoiler la marque contre des points)
