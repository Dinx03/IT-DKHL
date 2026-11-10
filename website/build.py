"""Assemble the site from shared partials, then bundle for Claude Artifacts.

    py build.py

Sources live in src/. Every page shares the same sprite, header and footer, so
they exist once and get stitched in at build time — duplicating them across pages
is how the two copies quietly drift apart.

Outputs (all generated — do not hand-edit):
    index.html            home page
    products.html         product catalogue
    dist/ona-healthy.html home page as one self-contained file, for Artifacts
    dist/products.html    catalogue as one self-contained file

Images under assets/img/ are linked normally in the real pages and embedded as
data URIs in the bundles, because an Artifact cannot load files beside it.
"""
import base64
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"
DIST = ROOT / "dist"

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Trirong:ital,wght@0,200;0,300;0,400;0,500;1,300'
    '&family=IBM+Plex+Sans+Thai:wght@200;300;400;500;600;700'
    '&family=IBM+Plex+Mono:wght@400;500'
    '&family=Playfair+Display:ital,wght@0,400;0,500;0,600;1,400'
    '&family=Poppins:wght@300;400;500;600'
    '&display=swap" rel="stylesheet">'
)

DESCRIPTION = (
    "ONA Healthy สวนมะเขือเทศปลอดสารพิษ อำเภอพิชัย จังหวัดอุตรดิตถ์ "
    "ปลูก สกัด และบรรจุในที่เดียว"
)

PAGES = [
    # source body,            output page,      <title>,                    bundle name
    ("page-home.html",     "index.html",    "ONA Healthy Estate",           "ona-healthy.html"),
    ("page-products.html", "products.html", "Products · ONA Healthy",       "products.html"),
    ("page-knowledge.html", "knowledge.html", "Tomato & Products · ONA Healthy", "knowledge.html"),
]

IMG_SRC = re.compile(r'src="(assets/img/[^"]+)"')
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".svg": "image/svg+xml"}


def read(name):
    p = SRC / name
    if not p.exists():
        sys.exit(f"missing partial: {p}")
    return p.read_text(encoding="utf-8").rstrip()


def inline_images(html):
    def to_data_uri(m):
        p = ROOT / m.group(1)
        if not p.exists():
            sys.exit(f"missing image: {p}")
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        return f'src="data:{MIME[p.suffix.lower()]};base64,{data}"'
    return IMG_SRC.sub(to_data_uri, html)


sprite = read("sprite.html")
header = read("header.html")
footer = read("footer.html")
css = (ROOT / "assets" / "css" / "style.css").read_text(encoding="utf-8").rstrip()
js = (ROOT / "assets" / "js" / "main.js").read_text(encoding="utf-8").rstrip()

DIST.mkdir(exist_ok=True)

for body_file, page_out, title, bundle_name in PAGES:
    body = read(body_file)
    parts = [sprite, header, body, footer]

    # --- the real page: links out to the shared stylesheet and script ---
    page = f"""<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{DESCRIPTION}">
  {FONTS}
  <link rel="stylesheet" href="assets/css/style.css">
</head>
<body>

{chr(10).join(parts)}

<script src="assets/js/main.js"></script>
</body>
</html>
"""
    (ROOT / page_out).write_text(page, encoding="utf-8")

    # --- the Artifact bundle: one file, no doctype/html/head/body of its own ---
    bundle = inline_images("\n".join([
        f"<title>{title}</title>",
        FONTS,
        "",
        "<style>", css, "</style>",
        "",
        *parts,
        "",
        "<script>", js, "</script>",
        "",
    ]))
    (DIST / bundle_name).write_text(bundle, encoding="utf-8")

    print(f"{page_out:<14} {len(page):>8,}   dist/{bundle_name:<18} {len(bundle):>8,}")

print(f"\nshared: sprite {len(sprite):,} | header {len(header):,} | footer {len(footer):,}"
      f" | css {len(css):,} | js {len(js):,}")
