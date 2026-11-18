"""Regression tests for PDF Lab URL discovery, ranking, and linguistic search."""
from __future__ import annotations
import os
import tempfile
import unittest
import uuid
from unittest.mock import patch
from pathlib import Path

# Keep tests isolated from a developer's real PDF library.
_TEST_HOME = tempfile.mkdtemp(prefix="pdf-lab-tests-")
os.environ["PDF_LAB_HOME"] = _TEST_HOME

import app as worker  # noqa: E402


class PDFLabCoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = worker.connect()

    def tearDown(self):
        self.conn.close()

    def test_pptx_extraction_reads_slide_text(self):
        import io, zipfile
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("ppt/presentation.xml", "<p:presentation xmlns:p='p'/>")
            archive.writestr(
                "ppt/slides/slide1.xml",
                "<p:sld xmlns:p='p' xmlns:a='a'><a:p><a:r><a:t>Aircraft performance</a:t></a:r></a:p></p:sld>",
            )
            archive.writestr(
                "ppt/slides/slide2.xml",
                "<p:sld xmlns:p='p' xmlns:a='a'><a:p><a:r><a:t>Flight planning</a:t></a:r></a:p></p:sld>",
            )
        text, pages, records = worker.extract_document(payload.getvalue(), "aviation.pptx")
        self.assertEqual(pages, 2)
        self.assertIn("[Slide 1]", text)
        self.assertIn("Aircraft performance", text)
        self.assertIn("[Slide 2]", text)
        self.assertEqual(len(records), 2)

    def test_docx_extraction_reads_paragraphs(self):
        import io, zipfile
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "word/document.xml",
                "<w:document xmlns:w='w'><w:body>"
                "<w:p><w:r><w:t>Aircraft systems</w:t></w:r></w:p>"
                "<w:p><w:r><w:t>Maintenance procedures</w:t></w:r></w:p>"
                "</w:body></w:document>",
            )
        text, pages, records = worker.extract_document(payload.getvalue(), "systems.docx")
        self.assertIsNone(pages)
        self.assertIn("Aircraft systems", text)
        self.assertIn("Maintenance procedures", text)
        self.assertEqual(len(records), 2)

    def test_xlsx_extraction_reads_shared_strings(self):
        import io, zipfile
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", "<workbook/>")
            archive.writestr(
                "xl/sharedStrings.xml",
                "<sst xmlns='x'><si><t>Aircraft</t></si><si><t>Hours</t></si></sst>",
            )
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                "<worksheet xmlns='x'><sheetData><row>"
                "<c r='A1' t='s'><v>0</v></c><c r='B1' t='s'><v>1</v></c>"
                "</row></sheetData></worksheet>",
            )
        text, pages, records = worker.extract_document(payload.getvalue(), "flight-hours.xlsx")
        self.assertEqual(pages, 1)
        self.assertIn("Aircraft | Hours", text)
        self.assertEqual(len(records), 1)

    def test_store_document_preserves_original_format_extension(self):
        import io, zipfile
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", "<w:document xmlns:w='w'><w:body/></w:document>")
        body, pages, _ = worker.extract_document(payload.getvalue(), "briefing.docx")
        doc_id, created = worker.store_document(
            "https://example.edu/briefing.docx", "briefing.docx",
            payload.getvalue(), "Briefing", body, pages,
        )
        row = self.conn.execute("SELECT path,filename FROM documents WHERE id=?", (doc_id,)).fetchone()
        self.assertTrue(created)
        self.assertEqual(row["filename"], "briefing.docx")
        self.assertTrue(row["path"].endswith(".docx"))

    def test_archive_import_source_falls_back_after_live_url(self):
        original = "https://example.edu/handbook.pdf"
        archived = (
            "https://arquivo.pt/noFrame/replay/"
            "20260101010101id_/https://example.edu/handbook.pdf"
        )
        source = worker.ArchiveImportSource(
            original_url=original,
            archive_file_url=archived,
            title="Aviation handbook",
        )
        self.assertEqual(
            worker.import_source_targets(source.original_url, source.archive_file_url),
            [original, archived],
        )
        request = worker.ImportURLsRequest(archive_sources=[source])
        self.assertEqual(request.archive_sources[0].title, "Aviation handbook")

    def test_pdf_candidate_includes_generic_binary_responses(self):
        self.assertTrue(worker.is_pdf_candidate("https://example.edu/scan.pdf", "text/html"))
        self.assertTrue(worker.is_pdf_candidate("https://example.edu/download?id=9", "application/pdf"))
        self.assertTrue(worker.is_pdf_candidate("https://example.edu/download?id=9", "application/octet-stream"))
        self.assertFalse(worker.is_pdf_candidate("https://example.edu/course", "text/html"))

    def test_pdf_signature_detects_real_pdf_header(self):
        self.assertTrue(worker.is_pdf_signature(b"%PDF-1.7\nbinary"))
        self.assertTrue(worker.is_pdf_signature(b"%PDF-1.4" + b"x" * 1016))
        self.assertFalse(worker.is_pdf_signature(b"<!doctype html><html>not a pdf</html>"))
        self.assertFalse(worker.is_pdf_signature(b""))

    def test_recursive_edu_glob_matches_arbitrary_depth_and_query(self):
        matcher = worker.glob_to_regex("*.edu/**/*.pdf")
        self.assertTrue(matcher.search("https://example.edu/course.pdf"))
        self.assertTrue(matcher.search("https://www.example.edu/a/b/c/course.pdf"))
        self.assertTrue(matcher.search("https://library.example.edu/docs/handbook.pdf?download=1"))
        self.assertFalse(matcher.search("https://example.com/docs/course.pdf"))
        self.assertFalse(matcher.search("https://example.edu/docs/course.html"))

    def test_wayback_domain_query_for_edu(self):
        self.assertEqual(worker.wayback_query_patterns("*.edu/**/*.pdf", "glob"), ["*.edu/*"])

    def test_wayback_json_header_rows_are_normalized(self):
        payload = [
            ["urlkey", "timestamp", "original", "mimetype", "statuscode"],
            ["edu,example)/report.pdf", "20261118010101",
             "https://example.edu/report.pdf", "application/pdf", "200"],
        ]
        rows = worker.parse_wayback_cdx_payload(payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["original"], "https://example.edu/report.pdf")
        self.assertEqual(rows[0]["statuscode"], "200")

    def test_arquivo_tld_query_targets_domain_suffix(self):
        self.assertEqual(worker.arquivo_query_patterns("*.edu/**/*.pdf", "glob"), ["*.edu"])
        self.assertEqual(worker.arquivo_query_patterns("*.gov/**/manual.pdf", "glob"), ["*.gov"])
        self.assertEqual(
            worker.arquivo_query_patterns("https://library.example.edu/**/*.pdf", "glob"),
            ["library.example.edu/*"],
        )

    def test_arquivo_regex_suffix_query(self):
        self.assertEqual(
            worker.arquivo_query_patterns(r"^https://[^/]+\.edu/.+\.pdf$", "regex"),
            ["*.edu"],
        )

    def test_arquivo_text_query_translation(self):
        self.assertEqual(worker.arquivo_text_query("aviation AND aircraft"), "aviation aircraft")
        self.assertEqual(worker.arquivo_text_query('"flight control"'), '"flight control"')
        self.assertEqual(worker.arquivo_text_query('"flight AND control"'), '"flight AND control"')
        self.assertIsNone(worker.arquivo_text_query("aviation OR helicopter"))
        self.assertIsNone(worker.arquivo_text_query("aviation NOT obsolete"))

    def test_archive_html_fragments_are_cleaned(self):
        self.assertEqual(
            worker.clean_archive_text(
                'For <em>aviation</em> &amp; flight <span class="ellipsis">systems</span>'
            ),
            "For aviation & flight systems",
        )
        self.assertEqual(worker.clean_archive_text("<b></b>"), None)
        self.assertEqual(worker.clean_archive_text(None), None)

    def test_arquivo_json_lines_are_normalized(self):
        payload = (
            '{"url":"https://example.edu/report.pdf","timestamp":"20261118010101",'
            '"mime":"application/pdf","status":"200"}\n'
            '{"url":"https://example.edu/handbook.pdf","timestamp":"20251118010101",'
            '"mime":"application/pdf","status":"200"}'
        )
        rows = worker.parse_arquivo_cdx_payload(payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["url"], "https://example.edu/report.pdf")
        self.assertEqual(rows[1]["mime"], "application/pdf")

    def test_soft_404_classifier_detects_generic_200_html_fallback(self):
        baseline = worker.response_fingerprint(
            200, {"content-type": "text/html; charset=UTF-8", "content-length": "4182"}
        )
        self.assertTrue(worker.is_soft_404_response(
            200, {"content-type": "text/html", "content-length": "4182"}, baseline
        ))
        self.assertFalse(worker.is_soft_404_response(
            200, {"content-type": "application/pdf", "content-length": "4182"}, baseline
        ))
        self.assertFalse(worker.is_soft_404_response(
            404, {"content-type": "text/html", "content-length": "4182"}, baseline
        ))

    def test_pdf_parser_rejects_html_before_pypdf(self):
        with self.assertRaisesRegex(ValueError, "missing %PDF-"):
            worker.extract_pdf(b"<!DOCTYPE html><html>not a PDF</html>")

    def test_index_fuzz_plan_distributes_budget_across_hosts(self):
        req = worker.IndexedFuzzRequest(
            seed_urls=[
                "https://one.example.edu/docs/handbook.pdf",
                "https://two.example.edu/library/course.pdf",
            ],
            paths=["docs/", "manual"],
            extensions=["pdf"],
            max_probes=10,
        )
        with patch.object(worker, "valid_http", return_value=True):
            plan = worker.build_index_fuzz_plan(req)
        urls = [item[0] for item in plan["probe_jobs"]]
        self.assertEqual(len(plan["origins"]), 2)
        self.assertLessEqual(len(urls), 10)
        self.assertTrue(any(url == "https://one.example.edu/docs/docs/" for url in urls))
        self.assertTrue(any(url == "https://one.example.edu/docs/manual.pdf" for url in urls))
        self.assertFalse(any("/docs/.pdf" in url for url in urls))

    def test_index_fuzz_plan_includes_original_seed_urls(self):
        seed = "https://example.edu/docs/aviation-handbook.pdf"
        req = worker.IndexedFuzzRequest(
            seed_urls=[seed], paths=["manual"], extensions=["pdf"], max_probes=5
        )
        with patch.object(worker, "valid_http", return_value=True):
            plan = worker.build_index_fuzz_plan(req)
        self.assertIn((seed, "https://example.edu", seed), plan["probe_jobs"])

    def test_index_fuzz_job_plan_rejects_empty_seed_list(self):
        req = worker.IndexedFuzzRequest(seed_urls=[])
        with self.assertRaises(worker.HTTPException):
            worker.build_index_fuzz_plan(req)

    def test_discovery_sort_prioritizes_verified_keyword_hits(self):
        items = [
            {"url": "https://example.edu/new.pdf", "mime": "application/pdf",
             "timestamp": "20261118010101", "collection": "commoncrawl"},
            {"url": "https://example.edu/match.pdf", "mime": "application/pdf",
             "timestamp": "20240101000000", "collection": "arquivo-textsearch",
             "query_match": True},
        ]
        items.sort(key=worker.discovery_sort_key)
        self.assertEqual(items[0]["url"], "https://example.edu/match.pdf")

    def test_discovery_sort_prefers_pdf_then_newest_capture(self):
        items = [
            {"url": "https://example.edu/old.pdf", "mime": "application/pdf",
             "timestamp": "20240101", "collection": "commoncrawl"},
            {"url": "https://example.edu/new.pdf", "mime": "application/pdf",
             "timestamp": "20261118010101", "collection": "wayback-cdx"},
            {"url": "https://example.edu/new.html", "mime": "text/html",
             "timestamp": "20261118010101", "collection": "wayback-cdx"},
        ]
        items.sort(key=worker.discovery_sort_key)
        self.assertEqual(items[0]["url"], "https://example.edu/new.pdf")
        self.assertEqual(items[1]["url"], "https://example.edu/old.pdf")
        self.assertEqual(items[2]["url"], "https://example.edu/new.html")

    def test_boolean_content_expression(self):
        body = "Flight control systems use an aircraft autopilot."
        self.assertTrue(worker.query_matches(body, '"flight control" AND autopilot'))
        self.assertTrue(worker.query_matches(body, "autopilot OR glider"))
        self.assertFalse(worker.query_matches(body, "autopilot AND NOT aircraft"))
        self.assertFalse(worker.query_matches(body, "helicopter"))

    def test_private_literal_target_is_rejected(self):
        self.assertFalse(worker.valid_http("http://127.0.0.1/private.pdf"))
        self.assertFalse(worker.valid_http("http://192.168.1.1/"))

    def test_porter_index_matches_english_word_forms(self):
        doc_id = str(uuid.uuid4())
        digest = uuid.uuid4().hex
        values = (
            doc_id, digest, "https://example.edu/corrected.pdf", "corrected.pdf",
            "Corrected report", str(Path(_TEST_HOME) / "corrected.pdf"),
            1234, 1, "The system was corrected after testing.", worker.now(),
        )
        self.conn.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)", values)
        self.conn.execute(
            "INSERT INTO document_fts VALUES(?,?,?,?,?)",
            (doc_id, "corrected.pdf", "Corrected report",
             "https://example.edu/corrected.pdf", "The system was corrected after testing."),
        )
        self.conn.execute(
            "INSERT INTO document_fts_linguistic VALUES(?,?,?,?,?)",
            (doc_id, "corrected.pdf", "Corrected report",
             "https://example.edu/corrected.pdf", "The system was corrected after testing."),
        )
        match = self.conn.execute(
            "SELECT id FROM document_fts_linguistic "
            "WHERE document_fts_linguistic MATCH ?",
            ("correction",),
        ).fetchone()
        self.assertIsNotNone(match)
        self.assertEqual(match["id"], doc_id)

    def test_bm25_ranking_function_is_available(self):
        self.conn.execute(
            "INSERT INTO document_fts_linguistic(id,filename,title,url,body) "
            "VALUES(?,?,?,?,?)",
            ("ranking-smoke", "flight.pdf", "Flight systems",
             "https://example.edu/flight.pdf", "flight flight controls"),
        )
        row = self.conn.execute(
            "SELECT bm25(document_fts_linguistic,0.0,5.0,2.0,0.25,1.0) AS score "
            "FROM document_fts_linguistic "
            "WHERE document_fts_linguistic MATCH ?",
            ("flight",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertIsInstance(row["score"], float)


if __name__ == "__main__":
    unittest.main()
