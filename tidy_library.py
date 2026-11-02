"""Repair titles/authors on already-built books, then rebuild the index."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from authors import AUTHORS  # noqa: E402
from build_books import OUT, rebuild_index, tidy_title  # noqa: E402


def main():
    for slug in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, slug, "book.json")
        if not os.path.isfile(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        d["title"] = tidy_title(d["title"])
        d["author"] = AUTHORS.get(slug, d.get("author") or "Unknown")
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    index = rebuild_index()
    for b in index:
        print(f"{b['title'][:42]:44} {b['author'][:24]:26} {b['level']:<12} {b['pageCount']:4}p")
    print(f"\n{len(index)} books")


if __name__ == "__main__":
    main()
