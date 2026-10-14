<img width="478" height="238" alt="Dracina Malfoy" src="https://github.com/user-attachments/assets/d43694e5-3d1c-46c4-b59a-4ec3b9feeb24" />

# Harry Potter and the Girl with Green Eyes

A fanfiction series. Book 1: *Harry Potter and the Mirror of Erised*.

<img width="565" height="245" alt="image" src="https://github.com/user-attachments/assets/989f601e-ce6a-4bc0-91a1-310f7f0dbeed" />

---

Key points on what makes this rewritten series different to others:

- Dracina is a rich, deep character with complex motives (not just the bully Draco in female form, or a mix between Hermione and Draco)
- Harry is more broken, darker, dangerous, vengeful 
- Slytherin/Crabbe/Goyle/Lucius etc. are all less "comically bad/bullies/villainous" and are more substantial

Any and all feedback welcome - maybe we can open source a phenomenal story here

## Read it

Download the latest PDF, EPUB or DOCX from [Releases](../../releases/tag/latest), in English, Russian, Spanish or Chinese.

## Join in

Open an [issue](../../issues/new) to talk, or a pull request to put forward a change. See [CONTRIBUTING](CONTRIBUTING.md).

## Fork your own and build it yourself

Chapters live in `books/<book>/chapters/`. Each chapter file starts with `# Chapter N: Title`. A scene break is a single `***` or `---` line.

Install pandoc and tectonic into `.tools/` once (no Homebrew):

```bash
bash scripts/bootstrap_tools.sh
```

Build every book in every format into `output/`:

```bash
python3 scripts/build_book.py
```

Run the tests:

```bash
PATH="$PWD/.tools/pandoc/bin:$PWD/.tools/tectonic:$PATH" python3 -m unittest discover -s tests -v
```

## CI

`.github/workflows/publish-books.yml` builds on every push to `main` that touches books or build files. It runs on `book*` tags and by hand too. Each build replaces the [latest release](../../releases/tag/latest).

## Licence

Story text is CC BY-NC-SA 4.0. Code is MIT. See [LICENSE](LICENSE). Harry Potter belongs to J. K. Rowling. This is non-profit fanfiction.
