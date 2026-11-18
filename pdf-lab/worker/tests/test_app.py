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

    def test_institution_seeds_include_mit_uga_and_middle_georgia(self):
        self.assertIn("mit.edu", worker.INSTITUTION_DOMAIN_SEEDS)
        self.assertIn("uga.edu", worker.INSTITUTION_DOMAIN_SEEDS)
        self.assertIn("mga.edu", worker.INSTITUTION_DOMAIN_SEEDS)

    def test_fuzzer_can_start_from_domains_without_existing_url_seeds(self):
        req = worker.IndexedFuzzRequest(
            seed_urls=[],
            institution_domains=["mit.edu", "mga.edu"],
            paths=["manual.pdf"],
            extensions=["pdf"],
            max_probes=0,
        )
        with patch.object(worker, "valid_http", return_value=True):
            plan = worker.build_index_fuzz_plan(req)
        self.assertEqual(len(plan["origins"]), 2)
        self.assertIn("https://mit.edu", plan["origins"])
        self.assertIn("https://mga.edu", plan["origins"])
        self.assertIn("https://mit.edu/", plan["origins"]["https://mit.edu"])
        self.assertIn("https://mga.edu/", plan["origins"]["https://mga.edu"])
        self.assertTrue(any(x[0] == "https://mit.edu/manual.pdf" for x in plan["probe_jobs"]))
        self.assertTrue(any(x[0] == "https://mga.edu/manual.pdf" for x in plan["probe_jobs"]))

    def test_unlimited_probe_budget_keeps_all_generated_paths(self):
        req = worker.IndexedFuzzRequest(
            seed_urls=["https://example.edu/files/known.pdf"],
            institution_domains=[],
            paths=["manual.pdf", "syllabus.pdf", "catalog.pdf"],
            extensions=["pdf"],
            max_probes=0,
        )
        with patch.object(worker, "valid_http", return_value=True):
            plan = worker.build_index_fuzz_plan(req)
        urls = [item[0] for item in plan["probe_jobs"]]
        self.assertIn("https://example.edu/manual.pdf", urls)
        self.assertIn("https://example.edu/syllabus.pdf", urls)
        self.assertIn("https://example.edu/catalog.pdf", urls)

    def test_version_metadata_splits_years_and_chapters(self):
        body = "A sufficiently long extracted aircraft systems chapter " * 8
        first = worker.derive_document_metadata(
            "https://mit.edu/flight/manual-2022-chapter-1.pdf",
            "manual-2022-chapter-1.pdf",
            "Flight Training Manual 2022 Chapter 1",
            body,
        )
        next_year = worker.derive_document_metadata(
            "https://mit.edu/flight/manual-2023-chapter-1.pdf",
            "manual-2023-chapter-1.pdf",
            "Flight Training Manual 2023 Chapter 1",
            body,
        )
        next_chapter = worker.derive_document_metadata(
            "https://mit.edu/flight/manual-2022-chapter-2.pdf",
            "manual-2022-chapter-2.pdf",
            "Flight Training Manual 2022 Chapter 2",
            body,
        )
        self.assertEqual(first["year"], 2022)
        self.assertEqual(first["chapter"], 1)
        self.assertEqual(next_year["year"], 2023)
        self.assertEqual(next_chapter["chapter"], 2)
        self.assertEqual(first["series_title"], next_year["series_title"])
        self.assertNotEqual(
            worker.document_duplicate_key(body, first),
            worker.document_duplicate_key(body, next_year),
        )
        self.assertNotEqual(
            worker.document_duplicate_key(body, first),
            worker.document_duplicate_key(body, next_chapter),
        )

    def test_version_metadata_can_read_year_and_chapter_from_title_page_text(self):
        metadata = worker.derive_document_metadata(
            "https://mga.edu/aviation/manuals/pa28.pdf",
            "pa28.pdf",
            "PA-28 Warrior Flight Manual",
            "Middle Georgia State University | 2024 Edition | Chapter 3 | Aircraft Systems",
        )
        self.assertEqual(metadata["domain"], "mga.edu")
        self.assertEqual(metadata["year"], 2024)
        self.assertEqual(metadata["chapter"], 3)
        self.assertEqual(metadata["series_title"], "PA 28 Warrior Flight Manual")

    def test_identical_binary_keeps_distinct_year_versions_but_skips_same_version(self):
        body = "Flight training procedures and aircraft limitations " * 10
        binary = b"same exact PDF binary payload"
        first_id, first_new = worker.store_document(
            "https://mga.edu/aviation/flight-manual-2022.pdf",
            "flight-manual-2022.pdf", binary,
            "Flight Manual 2022", body, 20,
        )
        second_id, second_new = worker.store_document(
            "https://mga.edu/archive/flight-manual-2023.pdf",
            "flight-manual-2023.pdf", binary,
            "Flight Manual 2023", body, 20,
        )
        repeat_id, repeat_new = worker.store_document(
            "https://mga.edu/other/flight-manual-2023.pdf",
            "flight-manual-2023.pdf", binary,
            "Flight Manual 2023", body, 20,
        )
        self.assertTrue(first_new)
        self.assertTrue(second_new)
        self.assertNotEqual(first_id, second_id)
        self.assertFalse(repeat_new)
        self.assertEqual(second_id, repeat_id)
        rows = self.conn.execute(
            "SELECT d.sha256,m.year FROM documents d "
            "JOIN document_metadata m ON m.doc_id=d.id WHERE d.sha256=? ORDER BY m.year",
            (worker.hashlib.sha256(binary).hexdigest(),),
        ).fetchall()
        self.assertEqual([row["year"] for row in rows], [2022, 2023])

    def test_store_document_skips_same_version_text_duplicate(self):
        body = "Aircraft operating limitations and procedures. " * 12
        data_a = b"document bytes with different metadata A"
        data_b = b"document bytes with different metadata B"
        first_id, first_new = worker.store_document(
            "https://mit.edu/course/flight-manual-2022-chapter-1.pdf",
            "flight-manual-2022-chapter-1.pdf", data_a,
            "Flight Manual 2022 Chapter 1", body, 1,
        )
        second_id, second_new = worker.store_document(
            "https://www.mit.edu/archive/flight-manual-2022-chapter-1.pdf",
            "flight-manual-2022-chapter-1.pdf", data_b,
            "Flight Manual 2022 Chapter 1", body, 1,
        )
        other_id, other_new = worker.store_document(
            "https://mit.edu/course/flight-manual-2023-chapter-1.pdf",
            "flight-manual-2023-chapter-1.pdf", data_b+b"new-year",
            "Flight Manual 2023 Chapter 1", body, 1,
        )
        self.assertTrue(first_new)
        self.assertFalse(second_new)
        self.assertEqual(first_id, second_id)
        self.assertTrue(other_new)
        self.assertNotEqual(first_id, other_id)

    def test_zero_means_unlimited_for_discovery_and_file_size(self):
        wildcard = worker.WildcardDiscoveryRequest(
            url_pattern="*.edu/**/*.pdf", max_results=0, indexes=0
        )
        imported = worker.ImportURLsRequest(max_bytes=0)
        crawl = worker.CrawlRequest(start_url="https://example.edu/", max_bytes=0, max_files=0, max_pages=0)
        self.assertEqual(wildcard.max_results, 0)
        self.assertEqual(wildcard.indexes, 0)
        self.assertEqual(imported.max_bytes, 0)
        self.assertEqual(crawl.max_bytes, 0)
        self.assertEqual(crawl.max_files, 0)
        self.assertEqual(crawl.max_pages, 0)

    def test_document_url_normalization_removes_fragment_and_host_case(self):
        self.assertEqual(
            worker.normalize_document_url("HTTPS://WWW.MIT.EDU/manual.pdf#page=4"),
            "https://www.mit.edu/manual.pdf",
        )

    def test_metadata_migration_rewrites_archive_urls_without_losing_document(self):
        body = "Aviation training reference and aircraft systems procedures " * 8
        doc_id, created = worker.store_document(
            "https://mga.edu/aviation/pa28-manual-2024.pdf",
            "pa28-manual-2024.pdf",
            b"migration-archive-source-binary",
            "PA-28 Manual 2024",
            body,
            10,
        )
        self.assertTrue(created)
        replay = (
            "https://arquivo.pt/noFrame/replay/20260101010101id_/"
            "https://mga.edu/aviation/pa28-manual-2024.pdf"
        )
        self.conn.execute("UPDATE documents SET url=? WHERE id=?", (replay, doc_id))
        self.conn.execute("UPDATE document_fts SET url=? WHERE id=?", (replay, doc_id))
        self.conn.execute("UPDATE document_fts_linguistic SET url=? WHERE id=?", (replay, doc_id))
        self.conn.execute("DELETE FROM pdf_lab_meta WHERE key='document_metadata_v4'")
        self.conn.commit()
        self.conn.close()

        self.conn = worker.connect()
        row = self.conn.execute(
            "SELECT d.url,m.domain,m.year FROM documents d "
            "JOIN document_metadata m ON m.doc_id=d.id WHERE d.id=?",
            (doc_id,),
        ).fetchone()
        self.assertEqual(row["url"], "https://mga.edu/aviation/pa28-manual-2024.pdf")
        self.assertEqual(row["domain"], "mga.edu")
        self.assertEqual(row["year"], 2024)

    def test_canonical_document_url_unwraps_arquivo_replay(self):
        replay = (
            "https://arquivo.pt/noFrame/replay/20260101010101id_/"
            "https://aviation.example.edu/courses/flight-manual.pdf"
        )
        self.assertEqual(
            worker.canonical_document_url(replay),
            "https://aviation.example.edu/courses/flight-manual.pdf",
        )

    def test_canonical_document_url_unwraps_wayback_replay(self):
        replay = (
            "https://web.archive.org/web/20260101010101id_/"
            "https://library.example.edu/manuals/warrior.pdf"
        )
        self.assertEqual(
            worker.canonical_document_url(replay),
            "https://library.example.edu/manuals/warrior.pdf",
        )

    def test_metadata_domain_uses_original_archive_source_host(self):
        replay = (
            "https://arquivo.pt/noFrame/replay/20260101010101id_/"
            "https://aviation.example.edu/courses/flight-manual-2024-chapter-2.pdf"
        )
        metadata = worker.derive_document_metadata(
            replay,
            "flight-manual-2024-chapter-2.pdf",
            "Flight Manual 2024 Chapter 2",
        )
        self.assertEqual(metadata["domain"], "aviation.example.edu")
        self.assertEqual(metadata["year"], 2024)
        self.assertEqual(metadata["chapter"], 2)

    def test_local_index_seeds_return_original_source_urls(self):
        body = "Aviation systems and flight training procedures " * 8
        worker.store_document(
            "https://arquivo.pt/noFrame/replay/20260101010101id_/"
            "https://mga.edu/aviation/flight-manual.pdf",
            "flight-manual.pdf",
            b"local-index-seed-binary",
            "Flight Manual",
            body,
            12,
        )
        seeds = worker.local_index_seed_urls(["pdf"])
        self.assertIn("https://mga.edu/aviation/flight-manual.pdf", seeds)
        self.assertFalse(any("arquivo.pt" in url for url in seeds))

    def test_adjacent_version_filenames_generate_year_chapter_and_part_siblings(self):
        variants = worker.adjacent_version_filenames("flight-manual-2024-chapter-3-part-2.pdf")
        self.assertIn("flight-manual-2023-chapter-3-part-2.pdf", variants)
        self.assertIn("flight-manual-2025-chapter-3-part-2.pdf", variants)
        self.assertIn("flight-manual-2024-chapter-2-part-2.pdf", variants)
        self.assertIn("flight-manual-2024-chapter-4-part-2.pdf", variants)
        self.assertIn("flight-manual-2024-chapter-3-part-1.pdf", variants)
        self.assertIn("flight-manual-2024-chapter-3-part-3.pdf", variants)

    def test_fuzzer_plan_probes_adjacent_indexed_chapters(self):
        req = worker.IndexedFuzzRequest(
            seed_urls=["https://mga.edu/aviation/flight-manual-2024-chapter-2.pdf"],
            institution_domains=[],
            paths=[],
            extensions=["pdf"],
            max_probes=0,
        )
        with patch.object(worker, "valid_http", return_value=True):
            plan = worker.build_index_fuzz_plan(req)
        urls = {item[0] for item in plan["probe_jobs"]}
        self.assertIn(
            "https://mga.edu/aviation/flight-manual-2024-chapter-1.pdf",
            urls,
        )
        self.assertIn(
            "https://mga.edu/aviation/flight-manual-2024-chapter-3.pdf",
            urls,
        )

    def test_index_fuzz_plan_distributes_budget_across_hosts(self):
        req = worker.IndexedFuzzRequest(
            seed_urls=[
                "https://one.example.edu/docs/handbook.pdf",
                "https://two.example.edu/library/course.pdf",
            ],
            paths=["docs/", "manual"],
            extensions=["pdf"],
            institution_domains=[],
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
            seed_urls=[seed], institution_domains=[], paths=["manual"], extensions=["pdf"], max_probes=5
        )
        with patch.object(worker, "valid_http", return_value=True):
            plan = worker.build_index_fuzz_plan(req)
        self.assertIn((seed, "https://example.edu", seed), plan["probe_jobs"])

    def test_index_fuzz_job_plan_rejects_empty_seed_list(self):
        req = worker.IndexedFuzzRequest(seed_urls=[], institution_domains=[])
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
