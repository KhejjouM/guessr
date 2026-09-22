#!/usr/bin/env python3
"""
Pipeline de contenu Guessr.

Objectif : remplacer la recherche plein-texte (qui renvoie n'importe quoi) par des
sources STRUCTURÉES, et ne garder que des modèles réellement reconnaissables.

Deux sources :
  1. Wikidata (voiture, moto) — chaque modèle est une entité typée, avec sa marque
     (P176), son image canonique (P18) et son nombre de versions linguistiques.
  2. Catégories Wikimedia Commons (sneakers, montres) — mal couverts par Wikidata,
     mais les catégories Commons sont curées à la main, donc fiables.

L'astuce qualité : le nombre de sitelinks Wikidata est un excellent proxy de
notoriété. Une voiture présente dans 40 langues est iconique ; une présente dans 2
rend le quiz injouable. On trie par notoriété et on coupe — ça donne aussi les
paliers de difficulté gratuitement.

Sortie : content.json (modèles + attribution des images) et les images téléchargées.
"""

import json, os, re, sys, time, unicodedata, urllib.parse, urllib.request

UA = "GuessrContentBot/1.0 (https://github.com/KhejjouM/guessr; local dev)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "images")
RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".raw")
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Wikidata est parfois en rate-limit agressif (1 req/min). On espace, et on met en
# cache le brut sur disque pour ne jamais rejouer une requête déjà réussie.
SPARQL_GAP = 65


def get_json(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def sparql(query, cache_key):
    os.makedirs(RAW_DIR, exist_ok=True)
    cache = os.path.join(RAW_DIR, cache_key + ".json")
    if os.path.exists(cache):
        with open(cache) as f:
            return json.load(f)
    url = SPARQL_ENDPOINT + "?format=json&query=" + urllib.parse.quote(query)
    for attempt in range(6):
        try:
            data = get_json(url)["results"]["bindings"]
            with open(cache, "w") as f:
                json.dump(data, f)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = SPARQL_GAP * (attempt + 1)
                print(f"    rate-limited, pause {wait}s…", flush=True)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"SPARQL échoué pour {cache_key}")


# ---------------------------------------------------------------- Wikidata

WIKIDATA_THEMES = {
    "voiture": {"class": "wd:Q3231690", "take": 90},   # automobile model
    "moto":    {"class": "wd:Q23866334", "take": 60},  # motorcycle model
}

SPARQL_TEMPLATE = """
SELECT ?item ?itemLabel ?brandLabel ?img ?sitelinks WHERE {{
  ?item wdt:P31/wdt:P279* {cls} ;
        wdt:P18 ?img ;
        wdt:P176 ?brand ;
        wikibase:sitelinks ?sitelinks .
  FILTER(?sitelinks >= 8)
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,en". }}
}}
ORDER BY DESC(?sitelinks)
LIMIT 400
"""


def clean_label(s):
    s = re.sub(r"\s*\([^)]*\)", "", s)          # retire les désambiguïsations
    return re.sub(r"\s+", " ", s).strip()


def looks_unlabeled(s):
    return bool(re.fullmatch(r"Q\d+", s.strip()))


def from_wikidata(theme, cfg):
    print(f"  [{theme}] requête Wikidata…", flush=True)
    rows = sparql(SPARQL_TEMPLATE.format(cls=cfg["class"]), f"wd_{theme}")
    print(f"  [{theme}] {len(rows)} entités brutes", flush=True)

    items, seen_names, seen_imgs = [], set(), set()
    for r in rows:
        name = clean_label(r["itemLabel"]["value"])
        brand = clean_label(r["brandLabel"]["value"])
        img = r["img"]["value"]
        if looks_unlabeled(name) or looks_unlabeled(brand):
            continue
        if len(name) < 3 or len(name) > 40:
            continue
        key = name.lower()
        if key in seen_names or img in seen_imgs:
            continue
        # Un quiz a besoin que la marque soit devinable à partir du nom OU distincte :
        # on garde tout, mais on note la marque pour générer des leurres crédibles.
        seen_names.add(key)
        seen_imgs.add(img)
        items.append({
            "name": name,
            "brand": brand,
            "sitelinks": int(r["sitelinks"]["value"]),
            "commons_file": urllib.parse.unquote(img.rsplit("/", 1)[-1]),
        })
        if len(items) >= cfg["take"]:
            break
    return items


# ---------------------------------------------- Commons (sneakers, montres)
# Wikidata couvre mal ces deux niches. Les catégories Commons, elles, sont curées :
# Category:Nike Air Jordan 1 ne contient que des Air Jordan 1.

COMMONS_THEMES = {
    # Catégories vérifiées une par une : seules les catégories SPÉCIFIQUES À UN MODÈLE
    # sont utilisables. Une catégorie de marque ("Nike trainers") mélange les modèles
    # et casserait le label.
    # Le 4e champ est la notoriété (0-100). Elle décide de ce qui entre dans le daily
    # gratuit (le haut du panier, reconnaissable par tous) et de ce qui reste réservé
    # au mode Expert. Sans ça, le daily pourrait demander de distinguer une Air Jordan 2
    # d'une Air Jordan 8 — infaisable, même pour un passionné.
    "sneakers": [
        ("Air Jordan 1",            "Nike",     "Category:Air Jordan 1",            98),
        ("Nike Air Force 1",        "Nike",     "Category:Nike Air Force",          96),
        ("Converse Chuck Taylor",   "Converse", "Category:Chuck Taylor All-Stars",  95),
        ("Adidas Stan Smith",       "Adidas",   "Category:Adidas Stan Smith",       93),
        ("Adidas Superstar",        "Adidas",   "Category:Adidas Superstar",        92),
        ("Adidas Samba",            "Adidas",   "Category:Adidas Samba",            90),
        ("Yeezy Boost",             "Adidas",   "Category:Yeezy",                   88),
        ("Nike Air Max 97",         "Nike",     "Category:Nike Air Max 97",         82),
        ("Air Jordan 4",            "Nike",     "Category:Air Jordan 4",            80),
        ("Adidas Gazelle",          "Adidas",   "Category:Adidas Gazelle",          76),
        ("Air Jordan 11",           "Nike",     "Category:Air Jordan 11",           72),
        ("Air Jordan 3",            "Nike",     "Category:Air Jordan 3",            70),
        ("Nike Air Max 270",        "Nike",     "Category:Nike Air Max 270",        66),
        ("Vans Authentic",          "Vans",     "Category:Vans Authentic",          64),
        # --- à partir d'ici : réservé au mode Expert ---
        ("Nike Kobe",               "Nike",     "Category:Nike Kobe shoes",         48),
        ("Asics Gel-Lyte III",      "Asics",    "Category:Asics Gel-Lyte III",      44),
        ("Air Jordan 5",            "Nike",     "Category:Air Jordan 5",            40),
        ("Air Jordan 12",           "Nike",     "Category:Air Jordan 12",           34),
        ("Nike Shox",               "Nike",     "Category:Nike Shox",               30),
        ("Air Jordan 13",           "Nike",     "Category:Air Jordan 13",           26),
        ("Air Jordan 2",            "Nike",     "Category:Air Jordan 2",            22),
        ("Air Jordan 8",            "Nike",     "Category:Air Jordan 8",            18),
        ("Nike Mag",                "Nike",     "Category:Nike Mag",                14),
    ],
    "montre": [
        ("Apple Watch",             "Apple",          "Category:Apple Watch",             98),
        ("Casio G-Shock",           "Casio",          "Category:G-Shock",                 95),
        ("Rolex Submariner",        "Rolex",          "Category:Rolex Submariner",        94),
        ("Casio F-91W",             "Casio",          "Category:Casio F-91W",             92),
        ("Swatch",                  "Swatch",         "Category:Swatch watches",          90),
        ("Omega Speedmaster",       "Omega",          "Category:Omega Speedmaster",       86),
        ("Rolex Daytona",           "Rolex",          "Category:Rolex Daytona",           84),
        ("Cartier Tank",            "Cartier",        "Category:Cartier Tank",            80),
        ("Audemars Piguet Royal Oak","Audemars Piguet","Category:Audemars Piguet",         78),
        ("Omega Seamaster",         "Omega",          "Category:Omega Seamaster",         74),
        ("Rolex Datejust",          "Rolex",          "Category:Rolex Datejust",          70),
        ("Patek Philippe Nautilus", "Patek Philippe", "Category:Patek Philippe watches",  66),
        # --- à partir d'ici : réservé au mode Expert ---
        ("TAG Heuer Monaco",        "TAG Heuer",      "Category:TAG Heuer Monaco",        48),
        ("Seiko 5",                 "Seiko",          "Category:Seiko watches",           44),
        ("Breitling Navitimer",     "Breitling",      "Category:Breitling watches",       38),
        ("Tissot",                  "Tissot",         "Category:Tissot watches",          32),
        ("IWC Portugieser",         "IWC",            "Category:IWC watches",             26),
    ],
}


def commons_category_files(category, limit=40):
    url = (COMMONS_API + "?action=query&format=json&generator=categorymembers"
           f"&gcmtitle={urllib.parse.quote(category)}&gcmtype=file&gcmlimit={limit}"
           "&prop=imageinfo&iiprop=url|mime|size|extmetadata&iiurlwidth=1280")
    try:
        data = get_json(url)
    except Exception as e:
        print(f"      ! {category}: {e}", flush=True)
        return []
    pages = data.get("query", {}).get("pages", {})
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if (ii.get("width") or 0) < 640:
            continue
        out.append({
            "commons_file": p["title"].replace("File:", ""),
            "url": ii.get("thumburl") or ii.get("url"),
            "meta": ii.get("extmetadata", {}),
        })
    return out


# ------------------------------------------------- attribution + download

def file_metadata(commons_file):
    """Récupère URL + licence + auteur : obligatoire pour respecter CC-BY."""
    url = (COMMONS_API + "?action=query&format=json&titles="
           + urllib.parse.quote("File:" + commons_file)
           + "&prop=imageinfo&iiprop=url|mime|size|extmetadata&iiurlwidth=1280")
    data = get_json(url)
    for p in data.get("query", {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        if not ii:
            continue
        return {"url": ii.get("thumburl") or ii.get("url"), "meta": ii.get("extmetadata", {})}
    return None


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def attribution(commons_file, meta):
    return {
        "file": commons_file,
        "author": strip_html(meta.get("Artist", {}).get("value", ""))[:120] or "Inconnu",
        "license": strip_html(meta.get("LicenseShortName", {}).get("value", "")) or "Voir Commons",
        "source": "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(commons_file),
    }


def slug(s):
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 5000:
        return True
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=90) as r, open(dest, "wb") as f:
            f.write(r.read())
        return os.path.getsize(dest) > 5000
    except Exception as e:
        print(f"      ! download {url}: {e}", flush=True)
        return False


# ------------------------------------------------------------------ main

def main():
    themes = sys.argv[1:] or ["sneakers", "montre", "moto", "voiture"]
    out_path = os.path.join(ROOT, "content.json")
    content = {}
    if os.path.exists(out_path):
        with open(out_path) as f:
            content = json.load(f)

    for theme in themes:
        print(f"\n=== {theme} ===", flush=True)
        os.makedirs(os.path.join(IMG_DIR, theme), exist_ok=True)
        items = []

        if theme in WIKIDATA_THEMES:
            for it in from_wikidata(theme, WIKIDATA_THEMES[theme]):
                info = file_metadata(it["commons_file"])
                if not info or not info["url"]:
                    continue
                sid = slug(it["name"])
                dest = os.path.join(IMG_DIR, theme, sid + ".jpg")
                if not download(info["url"], dest):
                    continue
                items.append({
                    "id": sid, "name": it["name"], "brand": it["brand"],
                    "fame": it["sitelinks"],
                    "credit": attribution(it["commons_file"], info["meta"]),
                })
                print(f"    ✓ {it['name']} ({it['brand']}, {it['sitelinks']} langues)", flush=True)
                time.sleep(0.3)

        elif theme in COMMONS_THEMES:
            for name, brand, category, fame in COMMONS_THEMES[theme]:
                files = commons_category_files(category)
                if not files:
                    print(f"    ✗ {name} — catégorie vide", flush=True)
                    continue
                # plusieurs photos par modèle = plus de variété en mode illimité
                kept = 0
                for f in files:
                    if kept >= 5:
                        break
                    sid = slug(name) + ("" if kept == 0 else f"_{kept+1}")
                    dest = os.path.join(IMG_DIR, theme, sid + ".jpg")
                    if not download(f["url"], dest):
                        continue
                    items.append({
                        "id": sid, "name": name, "brand": brand, "fame": fame,
                        "credit": attribution(f["commons_file"], f["meta"]),
                    })
                    kept += 1
                print(f"    ✓ {name} — {kept} photo(s)", flush=True)
                time.sleep(0.3)

        content[theme] = items
        with open(out_path, "w") as f:
            json.dump(content, f, ensure_ascii=False, indent=1)
        print(f"  → {len(items)} items pour {theme}", flush=True)

    print("\nTotal :", {k: len(v) for k, v in content.items()}, flush=True)


if __name__ == "__main__":
    main()
