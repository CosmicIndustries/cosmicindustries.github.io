"""Regression tests for PDF Lab URL discovery, ranking, and linguistic search."""
from __future__ import annotations
import os
import tempfile
import unittest
import uuid
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
