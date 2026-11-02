"""Regenerate covers for text-only books and trim duplicate front matter."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from authors import AUTHORS  # noqa: E402
from build_books import OUT, make_cover, rebuild_index  # noqa: E402

FRONT_HINTS = re.compile(r"^(contents|illustrations|chapter|by\s)", re.I)


def is_front_matter(text, title, author):
    t = text.strip()
    if len(t) > 700:
        return False
    low = t.lower()
    if title.lower()[:24] in low and len(t) < 420:
        return True
    if author and author.lower() in low and len(t) < 320:
        return True
    if FRONT_HINTS.match(low) and len(t) < 260:
        return True
    return False


def main():
    for slug in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, slug, "book.json")
        if not os.path.isfile(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        n_img = len([x for x in d["pages"] if x.get("image")])
        author = AUTHORS.get(slug, d.get("author"))

        if n_img == 0:
            # strip leading repeated title / contents pages
            dropped = 0
            while dropped < 6 and d["pages"]:
                first = d["pages"][0]
                if is_front_matter(first.get("text", ""), d["title"], author):
                    d["pages"].pop(0)
                    dropped += 1
                else:
                    break
            if dropped:
                print(f"  {slug}: trimmed {dropped} front matter pages")

        d["author"] = author
        cover_path = os.path.join(OUT, slug, "cover.jpg")
        if n_img == 0:
            make_cover(cover_path, d["title"], author, abs(hash(slug)) % 97)
            d["cover"] = "cover.jpg"
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    index = rebuild_index()
    print(f"\n{len(index)} books, covers refreshed")


if __name__ == "__main__":
    main()
