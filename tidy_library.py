"""Repair titles/authors, regenerate text-book covers, and trim Gutenberg front matter."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from authors import AUTHORS  # noqa: E402
from build_books import OUT, make_cover, rebuild_index, tidy_title  # noqa: E402

LEGAL = re.compile(
    r"(e-?text prepared by|project gutenberg|produced by|transcribed from|"
    r"copyright|all rights reserved|this ebook is for the use)",
    re.I,
)
TOC = re.compile(r"^(contents|illustrations|list of illustrations)\b", re.I)


def junk(text, title, author):
    """True if this leading page is boilerplate rather than story."""
    t = text.strip()
    low = t.lower()
    if not t:
        return True
    if LEGAL.search(t) and len(t) < 700:
        return True
    if TOC.match(low) and len(t) < 1400:
        return True
    # a title page repeats the title and little else
    if len(t) < 320 and title.lower()[:26] in low:
        return True
    if len(t) < 220 and author.lower() in low and len(author) > 4:
        return True
    # contents lists: many ALL-CAPS runs in a short block
    caps = len(re.findall(r"\b[A-Z][A-Z' -]{3,}\b", t))
    if len(t) < 1600 and caps >= 6:
        return True
    return False


def main():
    for slug in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, slug, "book.json")
        if not os.path.isfile(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        title = tidy_title(d["title"])
        title = title.replace("Winnie-the-pooh", "Winnie-the-Pooh").replace(
            "Looking-glass", "Looking-Glass"
        )
        author = AUTHORS.get(slug, d.get("author") or "")
        if not author or author == "Unknown":
            author = "Anonymous"

        dropped = 0
        while dropped < 8 and d["pages"]:
            first = d["pages"][0]
            if first.get("image"):
                # keep the first illustrated page, but clean its text
                if dropped == 0 and junk(first.get("text", ""), title, author):
                    first["text"] = ""
                    dropped += 1
                break
            if junk(first.get("text", ""), title, author):
                d["pages"].pop(0)
                dropped += 1
            else:
                break

        d["title"] = title
        d["author"] = author

        n_img = len([x for x in d["pages"] if x.get("image")])
        if n_img == 0:
            make_cover(os.path.join(OUT, slug, "cover.jpg"), title, author, abs(hash(slug)) % 97)
            d["cover"] = "cover.jpg"

        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if dropped:
            print(f"  {slug}: trimmed {dropped} boilerplate page(s)")

    index = rebuild_index()
    total_words = sum(b["words"] for b in index)
    print(f"\n{len(index)} books, {total_words:,} words")
    for b in index:
        print(f"  {b['title'][:40]:42} {b['author'][:20]:22} {b['level']:<12} {b['pageCount']:4}p")


if __name__ == "__main__":
    main()
