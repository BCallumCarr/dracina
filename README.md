# Reimagined Harry Potter Series

Each chapter file must start with `# Chapter N: Title`. Scene breaks are a lone `***` line.

## Build (local)

One-time tool install (pandoc + tectonic into `.tools/`, no Homebrew):

```bash
bash scripts/bootstrap_tools.sh
```

Build all four formats:

```bash
python3 scripts/build_book.py
```

Products land in `output/`:
- `Dracina-Book1.docx`
- `Dracina-Book1.epub`
- `Dracina-Book1.pdf`
- `Dracina-Book1-ElevenReader.epub`

Names never change, so re-uploading to a shared Proton folder replaces the file behind links already posted.

Tests:

```bash
python3 -m unittest discover -s tests -v
```

## CI

`.github/workflows/publish-books.yml` runs the same script on push to `main` when book/build paths change, on `workflow_dispatch`, and on `book*` tags. Artifacts upload for 90 days. Tags also attach the files to a GitHub Release.

Do not create the remote until the local build is proven.
