"""Build the reading library from Project Gutenberg public-domain books.

For each Gutenberg ID: download the illustrated HTML, extract text + illustrations
in document order, split into readable pages, and write
public/books/<slug>/book.json plus page images and a cover.

Books whose Gutenberg edition has no interior illustrations still get built:
the text is paginated and a typographic cover is generated with Pillow.
"""
import io
import json
import os
import re
import sys
import urllib.request

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "public", "books")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BookShelfBuilder/1.0"}

MAX_CHARS = 620          # characters of text per page
MIN_IMG = 110            # ignore images smaller than this on either side

BOOKS = [
    ("peter-rabbit", 14838, "Grade 3-4"),
    ("benjamin-bunny", 14407, "Grade 3-4"),
    ("squirrel-nutkin", 14872, "Grade 3-4"),
    ("jemima-puddle-duck", 14814, "Grade 3-4"),
    ("tom-kitten", 14837, "Grade 3-4"),
    ("jeremy-fisher", 15077, "Grade 3-4"),
    ("mrs-tiggy-winkle", 15137, "Grade 3-4"),
    ("flopsy-bunnies", 14220, "Grade 3-4"),
    ("two-bad-mice", 45264, "Grade 3-4"),
    ("mrs-tittlemouse", 17089, "Grade 3-4"),
    ("miss-moppet", 14848, "Grade 3-4"),
    ("ginger-and-pickles", 14877, "Grade 3-4"),
    ("tailor-of-gloucester", 14868, "Grade 4"),
    ("pie-and-the-patty-pan", 15234, "Grade 4"),
    ("mr-tod", 19805, "Grade 4"),
    ("samuel-whiskers", 15575, "Grade 4"),
    ("childs-picture-book", 36755, "Picture book"),
    ("wizard-of-oz", 55, "Grade 4-5"),
    ("doctor-dolittle", 501, "Grade 4-5"),
    ("just-so-stories", 2781, "Grade 4-6"),
    ("five-children-and-it", 778, "Grade 5-6"),
    ("secret-garden", 113, "Grade 5-6"),
    ("pinocchio", 500, "Grade 5"),
    ("treasure-seekers", 770, "Grade 5"),
    ("book-of-dragons", 23661, "Grade 5"),
    ("peter-pan", 16, "Grade 6"),
    ("alice-in-wonderland", 11, "Grade 6"),
    ("railway-children", 1874, "Grade 6"),
    ("phoenix-and-carpet", 836, "Grade 6"),
    ("enchanted-castle", 34219, "Grade 6"),
    ("black-beauty", 271, "Grade 6"),
    ("wind-in-the-willows", 289, "Grade 6-7"),
    ("anne-of-green-gables", 45, "Grade 6-7"),
    ("jungle-book", 236, "Grade 7"),
    ("looking-glass", 12, "Grade 7"),
    ("treasure-island", 120, "Grade 7-8"),
]

PALETTE = [
    ((0x2E, 0x6B, 0x4F), (0x8F, 0xD4, 0x8E)),
    ((0x1F, 0x4E, 0x79), (0x7F, 0xC8, 0xE8)),
    ((0x6B, 0x3F, 0x8E), (0xD3, 0xA5, 0xE8)),
    ((0x8A, 0x4B, 0x1F), (0xF0, 0xB2, 0x7A)),
    ((0x7A, 0x1F, 0x3D), (0xF2, 0x9E, 0xB2)),
    ((0x1F, 0x6B, 0x6B), (0x8E, 0xE0, 0xD4)),
]


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def clean(text):
    text = text.replace("\u00ad", "").replace("\u2019", "'")
    return re.sub(r"\s+", " ", text).strip()


def tidy_title(t):
    t = re.sub(r"^The Project Gutenberg eBook of\s*", "", t, flags=re.I)
    t = re.sub(r"\s*\|\s*Project Gutenberg\s*$", "", t, flags=re.I)
    t = re.sub(r"^The Project Gutenberg eBook:\s*", "", t, flags=re.I)
    t = re.sub(r",?\s*by\s+[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*){0,3}\.?$", "", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip().rstrip(".")


def tidy_author(a):
    a = re.sub(r"\s*,?\s*by\s+[A-Z][\w.\s'-]+\.?$", "", a).strip()
    a = re.sub(r"\s+", " ", a).strip().rstrip(".")
    return a or "Unknown"


def split_sentences(text, limit):
    """Split text into chunks of at most `limit` chars on sentence boundaries."""
    if len(text) <= limit:
        return [text]
    parts = re.split(r"(?<=[.!?])\s+", text)
    chunks, buf = [], ""
    for s in parts:
        if not buf:
            buf = s
        elif len(buf) + 1 + len(s) <= limit:
            buf += " " + s
        else:
            chunks.append(buf)
            buf = s
    if buf:
        chunks.append(buf)
    # anything still oversized gets hard-wrapped
    out = []
    for c in chunks:
        while len(c) > limit * 1.6:
            out.append(c[: int(limit * 1.6)].rsplit(" ", 1)[0])
            c = c[int(limit * 1.6):].lstrip()
        if c:
            out.append(c)
    return out


def make_cover(path, title, author, seed):
    W, H = 800, 1100
    c1, c2 = PALETTE[seed % len(PALETTE)]
    img = Image.new("RGB", (W, H), c1)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line(
            [(0, y), (W, y)],
            fill=(
                int(c1[0] + (c2[0] - c1[0]) * t),
                int(c1[1] + (c2[1] - c1[1]) * t),
                int(c1[2] + (c2[2] - c1[2]) * t),
            ),
        )
    def font(size, bold=False):
        for name in (["georgiab.ttf", "arialbd.ttf"] if bold else ["georgia.ttf", "arial.ttf"]):
            for base in (r"C:\Windows\Fonts", "/usr/share/fonts/truetype/dejavu"):
                p = os.path.join(base, name)
                if os.path.exists(p):
                    try:
                        return ImageFont.truetype(p, size)
                    except Exception:
                        pass
        return ImageFont.load_default()

    ft, fa = font(74, True), font(38)
    words, lines, line = title.split(), [], ""
    for w in words:
        test = (line + " " + w).strip()
        if d.textlength(test, font=ft) > W - 120:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)

    y = 250
    for ln in lines[:8]:
        d.text(((W - d.textlength(ln, font=ft)) / 2, y), ln, font=ft, fill=(255, 255, 255))
        y += 86
    y += 60
    d.line([(W / 2 - 70, y), (W / 2 + 70, y)], fill=(255, 255, 255), width=4)
    y += 40
    a = author.upper()
    d.text(((W - d.textlength(a, font=fa)) / 2, y), a, font=fa, fill=(255, 255, 255))
    img.save(path, "JPEG", quality=90, optimize=True)


def build(slug, gid, level="Grade 4-6"):
    base = f"https://www.gutenberg.org/cache/epub/{gid}/"
    try:
        raw = fetch(base + f"pg{gid}-images.html")
    except Exception as e:
        print(f"  SKIP {slug}: {e}")
        return False

    soup = BeautifulSoup(raw, "lxml")

    title = author = None
    for meta in soup.find_all("meta"):
        n = meta.get("name")
        if n == "title" and not title:
            title = meta.get("content")
        if n == "author" and not author:
            author = meta.get("content")
    if not title:
        t = soup.find("title")
        title = t.get_text() if t else slug
    title = tidy_title(clean(title))
    author = tidy_author(clean(author or ""))

    head = soup.find(id="pg-header")
    if head:
        head.decompose()
    for marker in soup.find_all(string=re.compile(r"\*\*\* END OF THE PROJECT GUTENBERG", re.I)):
        node = marker.parent
        while node is not None:
            nxt = node.find_next_sibling()
            node.decompose()
            node = nxt
        break

    blocks = soup.select("img, p, h1, h2, h3, h4, h5, blockquote, li")

    book_dir = os.path.join(OUT, slug)
    os.makedirs(book_dir, exist_ok=True)
    for f in os.listdir(book_dir):
        os.remove(os.path.join(book_dir, f))

    pages = []
    buf = []
    pending_img = None
    seen = set()
    saved = 0

    def flush(img=None):
        nonlocal buf
        text = " ".join(buf).strip()
        if img or text:
            pages.append({"image": img, "text": text})
        buf = []

    def save_image(src):
        nonlocal saved
        if not src or src in seen:
            return None
        seen.add(src)
        url = src if src.startswith("http") else base + src.lstrip("./")
        try:
            blob = fetch(url)
            im = Image.open(io.BytesIO(blob))
            if im.width < MIN_IMG or im.height < MIN_IMG:
                return None
            saved += 1
            name = f"p{saved:03d}.jpg"
            im = im.convert("RGB")
            im.thumbnail((1400, 1400), Image.LANCZOS)
            im.save(os.path.join(book_dir, name), "JPEG", quality=86, optimize=True)
            return name
        except Exception:
            return None

    for el in blocks:
        if el.name == "img":
            name = save_image(el.get("src"))
            if name:
                flush(pending_img)
                pending_img = name
                continue
        txt = clean(el.get_text(" "))
        if len(txt) < 2:
            continue
        for chunk in split_sentences(txt, MAX_CHARS):
            buf.append(chunk)
            if sum(len(b) for b in buf) >= MAX_CHARS:
                buf = [" ".join(buf)]
                flush(pending_img)
                pending_img = None
    flush(pending_img)

    pages = [p for p in pages if p["image"] or len(p["text"]) > 1]
    if not pages:
        print(f"  SKIP {slug}: no content")
        return False

    # a lone cover.jpg is the book cover, not a page
    cover = None
    if len(pages) == 1 and pages[0]["text"]:
        pages[0]["image"] = None
    imgs = [p["image"] for p in pages if p["image"]]
    if imgs:
        cover = imgs[0]
        im = Image.open(os.path.join(book_dir, cover)).convert("RGB")
        im.thumbnail((900, 1200), Image.LANCZOS)
        im.save(os.path.join(book_dir, "cover.jpg"), "JPEG", quality=88, optimize=True)
        cover = "cover.jpg"
    if not cover:
        make_cover(os.path.join(book_dir, "cover.jpg"), title, author, gid)
        cover = "cover.jpg"

    data = {
        "id": slug,
        "title": title,
        "author": author,
        "cover": cover,
        "level": level,
        "source": f"Project Gutenberg eBook #{gid}. Public domain in the United States.",
        "pages": pages,
    }
    with open(os.path.join(book_dir, "book.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    words = sum(len(p["text"].split()) for p in pages)
    print(f"  OK {slug}: {len(pages)} pages, {len(imgs)} images, {words} words, '{title}'")
    return True


def rebuild_index():
    index = []
    for slug in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, slug, "book.json")
        if not os.path.isfile(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        words = sum(len(x["text"].split()) for x in d["pages"])
        index.append({
            "id": d["id"],
            "title": d["title"],
            "author": d["author"],
            "cover": f"books/{d['id']}/{d.get('cover') or 'cover.jpg'}",
            "level": d.get("level", "Grade 4-6"),
            "pageCount": len(d["pages"]),
            "words": words,
        })
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    return index


def main():
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for slug, gid, level in BOOKS:
        if only and slug not in only:
            continue
        print(f"[{slug}] #{gid}", flush=True)
        build(slug, gid, level)
    index = rebuild_index()
    print(f"\nLibrary: {len(index)} books -> public/books/index.json")


if __name__ == "__main__":
    main()
