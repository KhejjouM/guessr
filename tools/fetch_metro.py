#!/usr/bin/env python3
"""
Génère le thème « Métro » : le tracé des réseaux, sans aucun nom.

Pourquoi générer plutôt que récupérer des plans existants : tous les plans de métro
portent les noms des stations, et « Châtelet » ou « Times Square » donnent la ville
en une seconde. En dessinant nous-mêmes depuis OpenStreetMap, il n'y a aucun texte
par construction — juste la forme du réseau et les couleurs officielles des lignes.

Sortie : un SVG par ville (léger, net à tous les zooms) + les entrées content.json.
Données © contributeurs OpenStreetMap, sous licence ODbL.
"""

import json, math, os, re, time, unicodedata, urllib.parse, urllib.request

UA = "GuessrMetroBot/1.0 (https://github.com/KhejjouM/guessr; local dev)"
# L'instance principale limite agressivement. On tourne sur les miroirs publics
# plutôt que de marteler le même serveur.
ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "images", "metro")
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".raw")

SIZE = 1000          # plus grande dimension du viewBox
PAD = 45             # marge intérieure
BG = "#0d0c16"
CLIP_LO, CLIP_HI = 0.005, 0.995   # ne coupe que les vrais points aberrants : les
                                  # extrémités (branche d'Epping, ligne 14…) font
                                  # partie de ce qui rend un réseau reconnaissable
MIN_LUMA = 0.22      # en dessous, une ligne (la Northern noire…) disparaît sur le fond

# (nom, pays, latitude, longitude, rayon en degrés, notoriété)
CITIES = [
    ("Paris",             "France",      48.8566,   2.3522, 0.22, 99),
    ("Londres",           "Royaume-Uni", 51.5074,  -0.1278, 0.35, 98),
    ("New York",          "États-Unis",  40.7128, -74.0060, 0.30, 97),
    ("Tokyo",             "Japon",       35.6762, 139.6503, 0.30, 95),
    ("Moscou",            "Russie",      55.7558,  37.6173, 0.35, 94),
    ("Berlin",            "Allemagne",   52.5200,  13.4050, 0.25, 92),
    ("Madrid",            "Espagne",     40.4168,  -3.7038, 0.25, 90),
    ("Barcelone",         "Espagne",     41.3851,   2.1734, 0.20, 89),
    ("Séoul",             "Corée du Sud",37.5665, 126.9780, 0.35, 87),
    ("Mexico",            "Mexique",     19.4326, -99.1332, 0.25, 85),
    ("Shanghai",          "Chine",       31.2304, 121.4737, 0.35, 84),
    ("Pékin",             "Chine",       39.9042, 116.4074, 0.35, 83),
    ("Hong Kong",         "Chine",       22.3193, 114.1694, 0.22, 81),
    ("Singapour",         "Singapour",    1.3521, 103.8198, 0.22, 80),
    ("Montréal",          "Canada",      45.5017, -73.5673, 0.20, 78),
    ("Chicago",           "États-Unis",  41.8781, -87.6298, 0.25, 77),
    ("Washington",        "États-Unis",  38.9072, -77.0369, 0.30, 76),
    ("Rome",              "Italie",      41.9028,  12.4964, 0.22, 75),
    ("Milan",             "Italie",      45.4642,   9.1900, 0.20, 74),
    ("Vienne",            "Autriche",    48.2082,  16.3738, 0.18, 72),
    ("Lisbonne",          "Portugal",    38.7223,  -9.1393, 0.15, 71),
    ("Amsterdam",         "Pays-Bas",    52.3676,   4.9041, 0.15, 70),
    ("Bruxelles",         "Belgique",    50.8503,   4.3517, 0.15, 69),
    ("Munich",            "Allemagne",   48.1351,  11.5820, 0.22, 68),
    ("Stockholm",         "Suède",       59.3293,  18.0686, 0.25, 67),
    ("Prague",            "Tchéquie",    50.0755,  14.4378, 0.15, 66),
    ("Athènes",           "Grèce",       37.9838,  23.7275, 0.22, 65),
    ("Istanbul",          "Turquie",     41.0082,  28.9784, 0.30, 64),
    ("Lyon",              "France",      45.7640,   4.8357, 0.12, 62),
    ("Marseille",         "France",      43.2965,   5.3698, 0.12, 60),
    ("Delhi",             "Inde",        28.6139,  77.2090, 0.35, 58),
    ("São Paulo",         "Brésil",     -23.5505, -46.6333, 0.25, 56),
    ("Buenos Aires",      "Argentine",  -34.6037, -58.3816, 0.15, 55),
    ("Santiago",          "Chili",      -33.4489, -70.6693, 0.20, 54),
    ("Toronto",           "Canada",      43.6532, -79.3832, 0.22, 52),
    ("Osaka",             "Japon",       34.6937, 135.5023, 0.22, 50),
    ("Taipei",            "Taïwan",      25.0330, 121.5654, 0.22, 48),
    ("Varsovie",          "Pologne",     52.2297,  21.0122, 0.18, 46),
    ("Budapest",          "Hongrie",     47.4979,  19.0402, 0.15, 44),
    ("Copenhague",        "Danemark",    55.6761,  12.5683, 0.15, 42),
    ("Helsinki",          "Finlande",    60.1699,  24.9384, 0.22, 40),
    ("Oslo",              "Norvège",     59.9139,  10.7522, 0.18, 38),
    ("Bucarest",          "Roumanie",    44.4268,  26.1025, 0.15, 36),
    ("Kyiv",              "Ukraine",     50.4501,  30.5234, 0.18, 34),
    ("Saint-Pétersbourg", "Russie",      59.9311,  30.3609, 0.25, 32),
    ("Le Caire",          "Égypte",      30.0444,  31.2357, 0.22, 30),
    ("Bangkok",           "Thaïlande",   13.7563, 100.5018, 0.25, 28),
    ("Kuala Lumpur",      "Malaisie",     3.1390, 101.6869, 0.22, 26),
    ("Dubaï",             "Émirats",     25.2048,  55.2708, 0.25, 24),
    ("Naples",            "Italie",      40.8518,  14.2681, 0.15, 22),
]

# Palette de secours quand OSM ne donne pas la couleur officielle de la ligne
FALLBACK = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4",
            "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080", "#9a6324"]


def slug(s):
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def overpass(query, cache_key):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, cache_key + ".json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    data = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(6):
        endpoint = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            req = urllib.request.Request(endpoint, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=100) as r:
                out = json.load(r)
            if not out.get("elements"):
                raise ValueError("réponse vide")
            with open(path, "w") as f:
                json.dump(out, f)
            return out
        except Exception as e:
            host = endpoint.split("/")[2]
            wait = 12 + 25 * (attempt // len(ENDPOINTS))
            print(f"      … {host}: {type(e).__name__}, miroir suivant dans {wait}s", flush=True)
            time.sleep(wait)
    return None


def fetch_city(name, lat, lon, rad):
    bbox = f"{lat-rad},{lon-rad*1.6},{lat+rad},{lon+rad*1.6}"
    q = f'[out:json][timeout:180];relation["route"="subway"]({bbox});out geom;'
    return overpass(q, "metro_" + slug(name))


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0
    i = min(len(sorted_vals) - 1, max(0, int(p * (len(sorted_vals) - 1))))
    return sorted_vals[i]


def ensure_contrast(hex_colour):
    """Éclaircit les lignes trop sombres : la Northern Line est officiellement noire,
    invisible sur un fond sombre."""
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) < 6:
        return hex_colour
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if luma >= MIN_LUMA:
        return "#" + h[:6]
    # mélange vers le blanc jusqu'à passer le seuil
    t = (MIN_LUMA - luma) / max(1e-6, 1 - luma)
    t = min(0.85, t + 0.15)
    r, g, b = (c + (1 - c) * t for c in (r, g, b))
    return "#%02x%02x%02x" % tuple(round(c * 255) for c in (r, g, b))


def drop_orphans(strokes):
    """Retire les petits tronçons isolés loin du réseau. OSM en contient souvent
    (bouts de voie de garage, tracés en projet) : ils n'apportent rien au jeu mais
    étirent le cadrage et rétrécissent le réseau utile."""
    cents = []
    for _, pts in strokes:
        cents.append((sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)))
    mid_lat = sorted(c[0] for c in cents)[len(cents) // 2]
    mid_lon = sorted(c[1] for c in cents)[len(cents) // 2]
    dists = [math.hypot(c[0] - mid_lat, (c[1] - mid_lon) * 0.7) for c in cents]
    median = sorted(dists)[len(dists) // 2] or 1e-9
    kept = [s for s, d in zip(strokes, dists) if not (d > 3.5 * median and len(s[1]) < 25)]
    return kept or strokes


def build_svg(name, elements):
    """Projette les géométries et rend le réseau en SVG, sans aucun texte."""
    seen_ways = set()
    strokes = []          # (couleur, [(lat, lon), …])
    palette_idx = 0
    colour_by_ref = {}

    for rel in elements:
        tags = rel.get("tags", {})
        ref = tags.get("ref") or tags.get("name") or str(rel.get("id"))
        colour = tags.get("colour") or tags.get("color")
        if colour and not re.fullmatch(r"#[0-9A-Fa-f]{3,8}", colour):
            colour = None
        if not colour:
            if ref not in colour_by_ref:
                colour_by_ref[ref] = FALLBACK[palette_idx % len(FALLBACK)]
                palette_idx += 1
            colour = colour_by_ref[ref]

        for m in rel.get("members", []):
            if m.get("type") != "way":
                continue
            geom = m.get("geometry")
            if not geom or len(geom) < 2:
                continue
            wid = m.get("ref")
            # les deux sens d'une même ligne partagent les mêmes ways : on ne
            # dessine chaque tronçon qu'une fois
            if wid in seen_ways:
                continue
            seen_ways.add(wid)
            strokes.append((colour, [(p["lat"], p["lon"]) for p in geom]))

    if not strokes:
        return None, 0

    strokes = drop_orphans(strokes)
    if not strokes:
        return None, 0

    lats = [p[0] for _, pts in strokes for p in pts]
    lons = [p[1] for _, pts in strokes for p in pts]
    mean_lat = sum(lats) / len(lats)
    kx = math.cos(math.radians(mean_lat))

    xs = sorted(l * kx for l in lons)
    ys = sorted(-l for l in lats)
    x0, x1 = percentile(xs, CLIP_LO), percentile(xs, CLIP_HI)
    y0, y1 = percentile(ys, CLIP_LO), percentile(ys, CLIP_HI)
    span_x, span_y = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)

    # viewBox à la forme du réseau : un cadre carré laisserait un réseau large
    # comme Londres flotter au milieu de deux grosses bandes vides.
    scale = (SIZE - 2 * PAD) / max(span_x, span_y)
    w = round(span_x * scale + 2 * PAD)
    h = round(span_y * scale + 2 * PAD)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    def project(lat, lon):
        x = (lon * kx - cx) * scale + w / 2
        y = (-lat - cy) * scale + h / 2
        return round(x, 1), round(y, 1)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="{BG}"/>',
        '<g fill="none" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" opacity="0.95">',
    ]
    for colour, pts in strokes:
        proj = [project(la, lo) for la, lo in pts]
        proj = decimate(proj)
        if len(proj) < 2:
            continue
        d = " ".join(f"{x},{y}" for x, y in proj)
        parts.append(f'<polyline points="{d}" stroke="{ensure_contrast(colour)}"/>')
    parts.append("</g></svg>")
    return "\n".join(parts), len(strokes)


def decimate(points, min_dist=1.4):
    """OSM donne une précision métrique, inutile à l'échelle d'affichage. On retire les
    points trop rapprochés : même tracé, fichier bien plus léger."""
    if len(points) < 3:
        return points
    out = [points[0]]
    for p in points[1:-1]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= min_dist:
            out.append(p)
    out.append(points[-1])
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    items = []
    for name, country, lat, lon, rad, fame in CITIES:
        sid = slug(name)
        dest = os.path.join(OUT_DIR, sid + ".svg")
        if os.path.exists(dest) and os.path.getsize(dest) > 2000:
            print(f"  = {name} (déjà généré)", flush=True)
        else:
            print(f"  · {name} …", flush=True)
            data = fetch_city(name, lat, lon, rad)
            if not data:
                print(f"    ✗ {name} — pas de réponse Overpass", flush=True)
                continue
            svg, n = build_svg(name, data.get("elements", []))
            if not svg or n < 8:
                print(f"    ✗ {name} — réseau trop maigre ({n} tronçons)", flush=True)
                continue
            with open(dest, "w") as f:
                f.write(svg)
            print(f"    ✓ {name} — {n} tronçons, {os.path.getsize(dest)//1024} Ko", flush=True)
            time.sleep(8)   # on reste poli avec l'API publique

        if os.path.exists(dest):
            items.append({
                "id": sid, "name": name, "brand": country, "fame": fame, "ext": "svg",
                "credit": {
                    "file": sid + ".svg",
                    "author": "Tracé généré à partir des données OpenStreetMap",
                    "license": "ODbL — © contributeurs OpenStreetMap",
                    "source": "https://www.openstreetmap.org/copyright",
                },
            })

    path = os.path.join(ROOT, "content.json")
    content = json.load(open(path)) if os.path.exists(path) else {}
    content["metro"] = items
    with open(path, "w") as f:
        json.dump(content, f, ensure_ascii=False, indent=1)
    print(f"\n{len(items)} villes générées")


if __name__ == "__main__":
    main()
