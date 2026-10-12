#!/usr/bin/env python3
"""Build book products (docx, epub, pdf, ElevenReader epub) from Markdown."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Any language: a number, then an ASCII or full-width colon, then the title.
CHAPTER_HEADING = re.compile(r"^# [^\d\n]*\d+[^:：\n]*[:：]\s*\S.*$")
CHAPTER_FILE = re.compile(r"^\d{2}-.+\.md$")
SCENE_BREAK = re.compile(r"^(?:\*\*\*|\* \* \*|---)\s*$")
STEM_OK = re.compile(r"^[A-Za-z0-9._-]+$")
REQUIRED_META = ("stem", "title", "author", "language", "rights", "disclaimer")
DEFAULT_DISCLAIMER_TITLE = "Fanfiction Disclaimer"


class BuildError(Exception):
    """Raised when book metadata, chapters, or tools are invalid."""


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_book_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    data = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if ":" not in line:
            raise BuildError(f"{path}: bad line {line!r}")
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest == "|":
            block = []
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.startswith("  "):
                    block.append(nxt[2:])
                    i += 1
                    continue
                if nxt.startswith("\t"):
                    block.append(nxt[1:])
                    i += 1
                    continue
                if nxt.strip() == "":
                    if i + 1 < len(lines) and (
                        lines[i + 1].startswith("  ") or lines[i + 1].startswith("\t")
                    ):
                        block.append("")
                        i += 1
                        continue
                    break
                break
            data[key] = "\n".join(block).rstrip("\n")
            continue
        if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "\"'":
            rest = rest[1:-1]
        data[key] = rest
        i += 1
    missing = [k for k in REQUIRED_META if not data.get(k)]
    if missing:
        raise BuildError(f"{path}: missing {', '.join(missing)}")
    if not STEM_OK.match(data["stem"]):
        raise BuildError(f"{path}: stem must match {STEM_OK.pattern}")
    return data


def validate_chapter(path: Path, text: str) -> None:
    for line in text.splitlines():
        if not line.strip():
            continue
        if not CHAPTER_HEADING.match(line):
            raise BuildError(
                f"{path}: first content line must be '# Chapter N: Title'"
                " (translated headings are fine)"
            )
        return
    raise BuildError(f"{path}: file is empty")


def rewrite_scene_breaks(text: str, mode: str) -> str:
    # Raw HTML fences stop pandoc from turning "* * *" into nested lists.
    if mode == "reader":
        inner = '<p class="scene-gap">* * *</p>'
    elif mode == "elevenreader":
        inner = '<p class="scene-gap"></p>'
    else:
        raise BuildError(f"unknown scene mode {mode!r}")
    repl = "```{=html}\n" + inner + "\n```"
    out_lines = []
    for line in text.splitlines():
        if SCENE_BREAK.match(line):
            out_lines.append(repl)
        else:
            out_lines.append(line)
    ending = "\n" if text.endswith("\n") else ""
    return "\n".join(out_lines) + ending


def chapter_paths(book_dir: Path) -> list:
    chapters = book_dir / "chapters"
    if not chapters.is_dir():
        return []
    return sorted(
        p
        for p in chapters.iterdir()
        if p.is_file() and CHAPTER_FILE.match(p.name)
    )


def _first_executable(candidates) -> Path:
    for path in candidates:
        if path.is_file() and os.access(str(path), os.X_OK):
            return path
    raise FileNotFoundError


def resolve_pandoc(root: Path) -> Path:
    which = shutil.which("pandoc")
    if which:
        return Path(which)
    tools = root / ".tools"
    candidates = [
        tools / "pandoc" / "bin" / "pandoc",
        tools / "pandoc" / "pandoc",
    ]
    if tools.is_dir():
        candidates.extend(sorted(tools.glob("**/bin/pandoc")))
    try:
        return _first_executable(candidates)
    except FileNotFoundError as exc:
        raise BuildError(
            "pandoc not found. Run scripts/bootstrap_tools.sh once, then retry."
        ) from exc


def resolve_tectonic(root: Path) -> Path:
    which = shutil.which("tectonic")
    if which:
        return Path(which)
    tools = root / ".tools"
    candidates = [
        tools / "tectonic" / "tectonic",
        tools / "tectonic",
    ]
    if tools.is_dir():
        candidates.extend(sorted(tools.glob("**/tectonic")))
    try:
        return _first_executable(
            [c for c in candidates if c.name == "tectonic"]
        )
    except FileNotFoundError as exc:
        raise BuildError(
            "tectonic not found. Run scripts/bootstrap_tools.sh once, then retry."
        ) from exc


def discover_books(root: Path, only: Path = None) -> list:
    if only is not None:
        book_yaml = only / "book.yaml" if only.is_dir() else only
        if book_yaml.name != "book.yaml":
            book_yaml = only / "book.yaml"
        if not book_yaml.is_file():
            raise BuildError(f"book.yaml not found at {book_yaml}")
        return [book_yaml.parent]
    books_root = root / "books"
    if not books_root.is_dir():
        return []
    found = []
    for child in sorted(books_root.iterdir()):
        if (child / "book.yaml").is_file():
            found.append(child)
    return found


def compose_markdown(
    meta: dict, chapter_texts: list, mode: str, disclaimer: bool = True
) -> str:
    parts = []
    if disclaimer:
        title = meta.get("disclaimer_title", DEFAULT_DISCLAIMER_TITLE)
        parts += [f"# {title}", "", meta["disclaimer"].rstrip(), ""]
    for text in chapter_texts:
        parts.append(rewrite_scene_breaks(text.rstrip() + "\n", mode=mode).rstrip())
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def write_metadata_file(path: Path, meta: dict) -> None:
    # Pandoc metadata only. Keep unknown keys out of this file.
    text = (
        f'title: "{meta["title"]}"\n'
        f'author: "{meta["author"]}"\n'
        f'lang: {meta["language"]}\n'
        f'rights: "{meta["rights"]}"\n'
    )
    # EB Garamond has no CJK glyphs; xeCJK needs its own font for the PDF.
    if meta.get("cjk_font"):
        text += f'CJKmainfont: {meta["cjk_font"]}\n'
        if meta.get("cjk_italic_font"):
            text += f'CJKoptions: [ItalicFont={meta["cjk_italic_font"]}]\n'
    path.write_text(text, encoding="utf-8")


def run_pandoc(pandoc: Path, args: list, env: dict) -> None:
    cmd = [str(pandoc)] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise BuildError(f"pandoc failed ({proc.returncode}): {detail}")


def build_one_book(root: Path, book_dir: Path, out_dir: Path) -> list:
    meta = parse_book_yaml(book_dir / "book.yaml")
    files = chapter_paths(book_dir)
    if not files:
        print(f"skip {book_dir}: no chapter files", file=sys.stderr)
        return []

    chapter_texts = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        validate_chapter(path, text)
        chapter_texts.append(text)

    pandoc = resolve_pandoc(root)
    tectonic = resolve_tectonic(root)
    stem = meta["stem"]
    out_dir.mkdir(parents=True, exist_ok=True)

    reader_css = root / "styles" / "reader.css"
    eleven_css = root / "styles" / "elevenreader.css"
    print_tex = root / "styles" / "print.tex"
    print_yaml = root / "styles" / "print.yaml"
    for style in (reader_css, eleven_css, print_tex, print_yaml):
        if not style.is_file():
            raise BuildError(f"missing style file {style}")

    env = os.environ.copy()
    env["PATH"] = str(tectonic.parent) + os.pathsep + env.get("PATH", "")

    written = []
    with tempfile.TemporaryDirectory(prefix="dracina-build-") as tmp:
        tmp_path = Path(tmp)
        meta_file = tmp_path / "metadata.yaml"
        write_metadata_file(meta_file, meta)
        # Body text goes before \tableofcontents only via include-before.
        disclaimer_md = tmp_path / "disclaimer.md"
        disclaimer_md.write_text(
            f"# {meta.get('disclaimer_title', DEFAULT_DISCLAIMER_TITLE)}"
            " {.unnumbered .unlisted}\n\n"
            + meta["disclaimer"].rstrip()
            + "\n",
            encoding="utf-8",
        )
        disclaimer_tex = tmp_path / "disclaimer.tex"
        run_pandoc(
            pandoc,
            [
                str(disclaimer_md),
                "-t",
                "latex",
                "--top-level-division=chapter",
                "-o",
                str(disclaimer_tex),
            ],
            env=env,
        )
        disclaimer_tex.write_text(
            "{\\raggedright\n"
            + disclaimer_tex.read_text(encoding="utf-8")
            + "\\par}\n",
            encoding="utf-8",
        )

        reader_md = tmp_path / "reader.md"
        eleven_md = tmp_path / "eleven.md"
        print_md = tmp_path / "print.md"
        reader_md.write_text(
            compose_markdown(meta, chapter_texts, mode="reader"), encoding="utf-8"
        )
        eleven_md.write_text(
            compose_markdown(meta, chapter_texts, mode="elevenreader"),
            encoding="utf-8",
        )
        print_md.write_text(
            compose_markdown(meta, chapter_texts, mode="reader", disclaimer=False),
            encoding="utf-8",
        )

        targets = [
            (
                reader_md,
                out_dir / f"{stem}.docx",
                ["--metadata-file", str(meta_file)],
            ),
            (
                reader_md,
                out_dir / f"{stem}.epub",
                [
                    "--metadata-file",
                    str(meta_file),
                    "--css",
                    str(reader_css),
                    "--split-level=1",
                    "--toc",
                ],
            ),
            (
                print_md,
                out_dir / f"{stem}.pdf",
                [
                    "--metadata-file",
                    str(meta_file),
                    "--metadata-file",
                    str(print_yaml),
                    "--include-in-header",
                    str(print_tex),
                    "--include-before-body",
                    str(disclaimer_tex),
                    "--top-level-division=chapter",
                    "--pdf-engine",
                    str(tectonic),
                ],
            ),
            (
                eleven_md,
                out_dir / f"{stem}-ElevenReader.epub",
                [
                    "--metadata-file",
                    str(meta_file),
                    "--css",
                    str(eleven_css),
                    "--split-level=1",
                    "--toc",
                ],
            ),
        ]
        for src, dest, extra in targets:
            run_pandoc(pandoc, [str(src), "-o", str(dest)] + extra, env=env)
            written.append(dest)
            print(f"wrote {dest}")
    return written


def build_all(root: Path, out_dir: Path, only: Path = None) -> list:
    books = discover_books(root, only=only)
    written = []
    for book_dir in books:
        written.extend(build_one_book(root, book_dir, out_dir))
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="repo root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output directory (default: <root>/output)",
    )
    parser.add_argument(
        "--book",
        type=Path,
        default=None,
        help="optional single book directory containing book.yaml",
    )
    args = parser.parse_args(argv)
    root = (args.root or repo_root_from_script()).resolve()
    out_dir = (args.out or (root / "output")).resolve()
    only = args.book.resolve() if args.book else None
    try:
        written = build_all(root=root, out_dir=out_dir, only=only)
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not written:
        print("no book products written", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
