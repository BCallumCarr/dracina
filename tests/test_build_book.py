#!/usr/bin/env python3
"""Tests for scripts/build_book.py."""

from __future__ import annotations

import importlib.util
import re
import shutil
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build_book.py"


def pdf_text(pdf: Path) -> bytes:
    data = pdf.read_bytes()
    blob = data
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        try:
            blob += zlib.decompress(m.group(1))
        except zlib.error:
            pass
    return blob


def load_build_book():
    spec = importlib.util.spec_from_file_location("build_book", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_book"] = module
    spec.loader.exec_module(module)
    return module


class ParseYamlTests(unittest.TestCase):
    def test_parses_required_fields_and_disclaimer_block(self):
        bb = load_build_book()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "book.yaml"
            path.write_text(
                'stem: Dracina-Book1\n'
                'title: "Dracina Malfoy, Book 1"\n'
                'author: "Brad"\n'
                "language: en-GB\n"
                'rights: "Non-profit fanfiction."\n'
                "disclaimer: |\n"
                "  Line one.\n"
                "  Line two.\n",
                encoding="utf-8",
            )
            meta = bb.parse_book_yaml(path)
        self.assertEqual(meta["stem"], "Dracina-Book1")
        self.assertEqual(meta["title"], "Dracina Malfoy, Book 1")
        self.assertEqual(meta["author"], "Brad")
        self.assertEqual(meta["language"], "en-GB")
        self.assertEqual(meta["rights"], "Non-profit fanfiction.")
        self.assertEqual(meta["disclaimer"], "Line one.\nLine two.")


class ValidateChapterTests(unittest.TestCase):
    def test_rejects_chapter_without_heading(self):
        bb = load_build_book()
        with self.assertRaises(bb.BuildError):
            bb.validate_chapter(
                Path("01-bad.md"),
                "Harry walked into the shop.\n",
            )

    def test_accepts_translated_chapter_heading(self):
        bb = load_build_book()
        bb.validate_chapter(
            Path("01-ok.md"),
            "# Глава 1: Случайная встреча\n\nТекст.\n",
        )

    def test_accepts_chinese_chapter_heading(self):
        bb = load_build_book()
        bb.validate_chapter(Path("01-ok.md"), "# 第1章：偶遇\n\n正文。\n")

    def test_accepts_chapter_heading(self):
        bb = load_build_book()
        bb.validate_chapter(
            Path("01-ok.md"),
            "# Chapter 1: Scaffold Sample\n\nBody text.\n",
        )


class SceneBreakTests(unittest.TestCase):
    def test_reader_mode_keeps_visible_break(self):
        bb = load_build_book()
        out = bb.rewrite_scene_breaks("A\n\n***\n\nB\n", mode="reader")
        self.assertIn("* * *", out)
        self.assertIn("{=html}", out)
        self.assertNotIn("***\n", out)

    def test_elevenreader_mode_uses_empty_paragraph(self):
        bb = load_build_book()
        out = bb.rewrite_scene_breaks("A\n\n* * *\n\nB\n", mode="elevenreader")
        self.assertIn('<p class="scene-gap"></p>', out)
        self.assertIn("{=html}", out)
        self.assertNotIn("* * *", out)


class ComposeMarkdownTests(unittest.TestCase):
    def test_disclaimer_can_be_left_out_for_print_front_matter(self):
        bb = load_build_book()
        meta = {"disclaimer": "Not affiliated."}
        chapters = ["# Chapter 1: One\n\nBody.\n"]
        with_it = bb.compose_markdown(meta, chapters, mode="reader")
        without = bb.compose_markdown(
            meta, chapters, mode="reader", disclaimer=False
        )
        self.assertIn("Not affiliated.", with_it)
        self.assertNotIn("Not affiliated.", without)
        self.assertTrue(without.startswith("# Chapter 1: One"))

    def test_disclaimer_title_comes_from_book_metadata(self):
        bb = load_build_book()
        meta = {"disclaimer": "Text.", "disclaimer_title": "Отказ от прав"}
        out = bb.compose_markdown(meta, ["# Глава 1: Один\n"], mode="reader")
        self.assertTrue(out.startswith("# Отказ от прав\n"))


class MetadataFileTests(unittest.TestCase):
    def _write(self, meta):
        bb = load_build_book()
        base = {"title": "T", "author": "A", "language": "zh-Hans", "rights": "R"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.yaml"
            bb.write_metadata_file(path, {**base, **meta})
            return path.read_text(encoding="utf-8")

    def test_cjk_fonts_are_passed_to_pandoc(self):
        out = self._write(
            {"cjk_font": "FandolSong-Regular.otf", "cjk_italic_font": "FandolKai-Regular.otf"}
        )
        self.assertIn("CJKmainfont: FandolSong-Regular.otf\n", out)
        self.assertIn("CJKoptions: [ItalicFont=FandolKai-Regular.otf]\n", out)

    def test_no_cjk_keys_without_cjk_font(self):
        self.assertNotIn("CJK", self._write({}))


class BuildBookIntegrationTests(unittest.TestCase):
    def test_empty_chapters_exits_without_output_files(self):
        bb = load_build_book()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            book = root / "books" / "book1"
            (book / "chapters").mkdir(parents=True)
            (book / "book.yaml").write_text(
                'stem: Dracina-Book1\n'
                'title: "Dracina Malfoy, Book 1"\n'
                'author: "Brad"\n'
                "language: en-GB\n"
                'rights: "rights"\n'
                "disclaimer: |\n"
                "  Disclaimer text.\n",
                encoding="utf-8",
            )
            (root / "styles").mkdir()
            (root / "styles" / "reader.css").write_text("body{}", encoding="utf-8")
            (root / "styles" / "elevenreader.css").write_text(
                "body{}", encoding="utf-8"
            )
            out = root / "output"
            written = bb.build_all(root=root, out_dir=out)
            self.assertEqual(written, [])
            self.assertFalse(out.exists() and any(out.iterdir()))

    def test_build_writes_four_formats_with_elevenreader_rules(self):
        bb = load_build_book()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            book = root / "books" / "book1"
            chapters = book / "chapters"
            chapters.mkdir(parents=True)
            (book / "book.yaml").write_text(
                'stem: Dracina-Book1\n'
                'title: "Dracina Malfoy, Book 1"\n'
                'author: "Brad"\n'
                "language: en-GB\n"
                'rights: "Non-profit fanfiction."\n'
                "disclaimer: |\n"
                "  This is a non-profit, unofficial work of fanfiction.\n",
                encoding="utf-8",
            )
            (chapters / "01-scaffold-sample.md").write_text(
                "# Chapter 1: Scaffold Sample\n\n"
                "This chapter is a build sample.\n\n"
                "***\n\n"
                "Second scene for the silent break.\n",
                encoding="utf-8",
            )
            styles = root / "styles"
            styles.mkdir()
            (styles / "reader.css").write_text(
                'body{font-family:Georgia,serif;}\n'
                "p{text-indent:1.2em;}\n"
                "h1+p{text-indent:0;}\n"
                "p.scene-gap{text-align:center;text-indent:0;}\n",
                encoding="utf-8",
            )
            (styles / "elevenreader.css").write_text(
                'body{font-family:Georgia,serif;}\n'
                "p{text-indent:0;}\n"
                "p.scene-gap{margin:1.2em 0;}\n",
                encoding="utf-8",
            )
            for name in ("print.tex", "print.yaml"):
                shutil.copy(REPO / "styles" / name, styles / name)
            out = root / "output"
            written = bb.build_all(root=root, out_dir=out)
            names = sorted(p.name for p in written)
            self.assertEqual(
                names,
                [
                    "Dracina-Book1-ElevenReader.epub",
                    "Dracina-Book1.docx",
                    "Dracina-Book1.epub",
                    "Dracina-Book1.pdf",
                ],
            )
            self.assertTrue(any(n.endswith(".docx") for n in names))
            self.assertTrue(any(n.endswith(".pdf") for n in names))
            self.assertTrue(
                any(n.endswith(".epub") and "ElevenReader" not in n for n in names)
            )
            self.assertTrue(any(n.endswith("-ElevenReader.epub") for n in names))

            er = next(p for p in written if p.name.endswith("-ElevenReader.epub"))
            with zipfile.ZipFile(er) as zf:
                xhtml = [
                    n
                    for n in zf.namelist()
                    if n.endswith((".xhtml", ".html", ".htm"))
                ]
                blob = b"".join(zf.read(n) for n in xhtml)
            self.assertIn(b"Fanfiction Disclaimer", blob)
            self.assertIn(b"Chapter 1: Scaffold Sample", blob)
            self.assertIn(b'class="scene-gap"', blob)
            self.assertNotIn(b"<img", blob.lower())
            self.assertNotIn(b"* * *", blob)

            reader = next(
                p
                for p in written
                if p.suffix == ".epub" and "ElevenReader" not in p.name
            )
            with zipfile.ZipFile(reader) as zf:
                reader_blob = b"".join(
                    zf.read(n)
                    for n in zf.namelist()
                    if n.endswith((".xhtml", ".html", ".htm"))
                )
            self.assertIn(b"* * *", reader_blob)
            self.assertNotIn(b"<ul>", reader_blob)

            pdf = next(p for p in written if p.suffix == ".pdf")
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))
            pdf_blob = pdf_text(pdf)
            self.assertIn(b"/MediaBox[0 0 396 612]", pdf_blob)
            self.assertIn(b"EBGaramond", pdf_blob)

            docx = next(p for p in written if p.suffix == ".docx")
            with zipfile.ZipFile(docx) as zf:
                xml = zf.read("word/document.xml")
            self.assertIn(b"Scaffold Sample", xml)


if __name__ == "__main__":
    unittest.main()
