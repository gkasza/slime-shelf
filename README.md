# Slime Shelf

A scroll and read picture book shelf, built for a tablet. Tap a book, scroll down, and read the words while you look at the pictures on the same screen.

## What is inside

**The app** (`public/`)

- Shelf of book covers with reading level tags and a progress bar on each book
- Scroll reader: every page shows its picture and its text together, in book order
- Remembers where she stopped, and offers a Continue reading card on the shelf
- Text size buttons and a night mode
- Works offline after the first visit, and installs to a tablet home screen as an app
- Add your own book: pick page photos or scans, order them by filename, and the book appears on the shelf. Those pages are stored on the device only, never uploaded.
- Deep links: `#book/<id>` opens a book, `#book/<id>/<page>` opens it at a page

**The library** (`public/books/`)

36 illustrated books, all public domain in the United States, downloaded from Project Gutenberg and rebuilt into page-by-page books with their original illustrations:

- Picture books and early readers: the Beatrix Potter tales, The Child's Picture Book
- Stretch shelf for a strong reader: The Wonderful Wizard of Oz, The Story of Doctor Dolittle, The Jungle Book, Treasure Island, The Secret Garden, Peter Pan, Alice in Wonderland, Through the Looking Glass, The Wind in the Willows, Anne of Green Gables, Black Beauty, Five Children and It, The Phoenix and the Carpet, The Enchanted Castle, The Railway Children, The Book of Dragons, Just So Stories, Pinocchio, The Story of the Treasure Seekers

## Rebuilding the library

```bash
pip install beautifulsoup4 lxml pillow
python build_books.py            # rebuild every book
python build_books.py wizard-of-oz   # rebuild just one
python fix_covers.py             # refresh generated covers
python tidy_library.py           # repair titles and authors, rebuild index
```

To add a book, add its Gutenberg id and reading level to `BOOKS` in `build_books.py`, then run it with that slug.

## Deploying

Static site, no build step. On Vercel the output directory is `public`.

```bash
npx vercel --prod
```

## Rights

The app code is yours. The bundled texts and illustrations are public domain in the United States, sourced from Project Gutenberg, and each book records its source id in `book.json`. Books still in copyright, such as the My Pet Slime series, are not included and are not downloadable through this app.
