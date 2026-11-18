#!/usr/bin/env python3
"""Local-first, bounded PDF crawler and searchable document catalog."""
from __future__ import annotations
import asyncio, hashlib, json, os, re, sqlite3, time, uuid, shutil, subprocess, traceback, mimetypes, tempfile, zipfile
from functools import lru_cache
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag, unquote
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pypdf import PdfReader

ROOT = Path(os.environ.get("PDF_LAB_HOME", Path(__file__).parent / "data")).resolve()
FILES = ROOT / "documents"
DB = ROOT / "catalog.sqlite3"
ROOT.mkdir(parents=True, exist_ok=True); FILES.mkdir(parents=True, exist_ok=True)
UA = "CosmicPDFLab/1.0 (+local research crawler)"
app = FastAPI(title="Cosmic PDF Lab Worker", version="1.0.0")
PDF_LAB_PAGE = Path(__file__).resolve().parent.parent / "index.html"

@app.get("/", include_in_schema=False)
def serve_pdf_lab():
    if not PDF_LAB_PAGE.is_file():
        raise HTTPException(404, "PDF Lab interface not found beside the worker.")
    return FileResponse(PDF_LAB_PAGE, media_type="text/html")
app.add_middleware(CORSMiddleware, allow_origins=["https://cosmicindustries.github.io","http://127.0.0.1:5500","http://localhost:5500"], allow_methods=["*"], allow_headers=["*"])
jobs: dict[str, dict] = {}
job_tasks: dict[str, asyncio.Task] = {}
fuzz_jobs: dict[str, dict] = {}
fuzz_job_tasks: dict[str, asyncio.Task] = {}
import_jobs: dict[str, dict] = {}
robots_cache: dict[str, RobotFileParser] = {}
robots_locks: dict[str, asyncio.Lock] = {}
host_validation_cache: dict[str, tuple[float, bool]] = {}

def _roman_value(value):
    value=(value or "").upper()
    values={"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
    total=0; previous=0
    for char in reversed(value):
        current=values.get(char,0)
        total += -current if current<previous else current
        previous=max(previous,current)
    return total or None


def derive_document_metadata(url, filename, title, text=""):
    """Extract a document series and explicit year/chapter/part/edition markers."""
    host=(urlparse(url).hostname or "").lower().removeprefix("www.")
    raw=" ".join([str(title or ""),Path(filename).stem]).strip()
    year_match=re.search(r"(?<!\d)(?:19|20)\d{2}(?!\d)",raw)
    year=int(year_match.group(0)) if year_match else None

    def find_unit(label):
        match=re.search(rf"\b(?:{label})\s*[-_.:#]?\s*(\d{{1,3}}|[ivxlcdm]+)\b",raw,re.I)
        if not match:return None
        value=match.group(1)
        return int(value) if value.isdigit() else _roman_value(value)

    chapter=find_unit("chapter|chap|ch")
    part=find_unit("part|pt|unit|module|lesson|volume|vol")
    edition_match=re.search(
        r"\b(?:(\d+(?:st|nd|rd|th)?)\s+edition|edition\s*(\d+)|rev(?:ision)?\s*([A-Z0-9.]+)|v(?:ersion)?\s*([0-9]+(?:\.[0-9]+)*))\b",
        raw,re.I
    )
    edition=next((x for x in edition_match.groups() if x),None) if edition_match else None

    series=re.sub(r"(?<!\d)(?:19|20)\d{2}(?!\d)"," ",raw)
    series=re.sub(
        r"\b(?:chapter|chap|ch|part|pt|unit|module|lesson|volume|vol)\s*[-_.:#]?\s*(?:\d{1,3}|[ivxlcdm]+)\b",
        " ",series,flags=re.I
    )
    series=re.sub(
        r"\b(?:(?:\d+(?:st|nd|rd|th)\s+)?edition|edition\s*\d+|rev(?:ision)?\s*[A-Z0-9.]+|v(?:ersion)?\s*[0-9]+(?:\.[0-9]+)*)\b",
        " ",series,flags=re.I
    )
    series=re.sub(r"\b(final|copy|draft|updated|revised)\b"," ",series,flags=re.I)
    series=re.sub(r"[_\-.]+"," ",series)
    series=re.sub(r"\s+"," ",series).strip(" -_")
    if len(series)<4:series=Path(filename).stem
    normalized=re.sub(r"[^a-z0-9]+"," ",series.casefold()).strip()
    series_key=(host+"::"+normalized) if host else normalized
    version_bits=[]
    if year:version_bits.append(str(year))
    if chapter is not None:version_bits.append("Chapter "+str(chapter))
    if part is not None:version_bits.append("Part "+str(part))
    if edition:version_bits.append("Edition "+edition)
    return {
        "domain":host,"series_key":series_key,"series_title":series,
        "year":year,"chapter":chapter,"part":part,"edition":edition,
        "version_label":" · ".join(version_bits) or "Unversioned",
    }


def normalize_document_url(url):
    parts=urlsplit((url or "").strip())
    host=(parts.hostname or "").lower()
    port=parts.port
    netloc=host+(f":{port}" if port and not ((parts.scheme=="https" and port==443) or (parts.scheme=="http" and port==80)) else "")
    return urlunsplit((parts.scheme.lower(),netloc,parts.path or "/",parts.query,""))


def document_duplicate_key(text, metadata):
    """Detect same-content duplicates but keep different years/chapters/parts."""
    normalized=re.sub(r"\s+"," ",(text or "").casefold()).strip()
    if len(normalized)<160:return None
    version=(metadata.get("year"),metadata.get("chapter"),metadata.get("part"),metadata.get("edition"))
    payload=normalized+chr(31)+json.dumps(version,separators=(",",":"))
    return hashlib.sha256(payload.encode("utf-8","ignore")).hexdigest()


def connect():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS documents(
      id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, url TEXT NOT NULL,
      filename TEXT NOT NULL, title TEXT, path TEXT NOT NULL, bytes INTEGER NOT NULL,
      pages INTEGER, text TEXT NOT NULL, discovered_at TEXT NOT NULL)""")
    c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(id UNINDEXED, filename, title, url, body)")
    # Porter stemming and Unicode diacritic folding improve recall for variants such
    # as fly/flying/flights while keeping the original text unchanged.
    c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS document_fts_linguistic
                 USING fts5(id UNINDEXED, filename, title, url, body,
                 tokenize='porter unicode61 remove_diacritics 2')""")
    c.execute("CREATE TABLE IF NOT EXISTS pdf_lab_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    c.execute("""CREATE TABLE IF NOT EXISTS document_metadata(
      doc_id TEXT PRIMARY KEY, domain TEXT, series_key TEXT, series_title TEXT,
      year INTEGER, chapter INTEGER, part INTEGER, edition TEXT,
      version_label TEXT, duplicate_key TEXT UNIQUE)""")
    metadata_migrated=c.execute("SELECT value FROM pdf_lab_meta WHERE key='document_metadata_v1'").fetchone()
    if not metadata_migrated:
        for row in c.execute("SELECT id,url,filename,title,text FROM documents").fetchall():
            metadata=derive_document_metadata(row["url"],row["filename"],row["title"],row["text"])
            duplicate_key=document_duplicate_key(row["text"],metadata)
            try:
                c.execute(
                    "INSERT OR IGNORE INTO document_metadata"
                    "(doc_id,domain,series_key,series_title,year,chapter,part,edition,version_label,duplicate_key) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (row["id"],metadata["domain"],metadata["series_key"],metadata["series_title"],
                     metadata["year"],metadata["chapter"],metadata["part"],metadata["edition"],
                     metadata["version_label"],duplicate_key)
                )
            except sqlite3.IntegrityError:
                pass
        c.execute("INSERT INTO pdf_lab_meta(key,value) VALUES('document_metadata_v1','done')")
    migrated=c.execute("SELECT value FROM pdf_lab_meta WHERE key='linguistic_fts_v1'").fetchone()
    if not migrated:
        c.execute("""INSERT INTO document_fts_linguistic(id,filename,title,url,body)
                     SELECT id,filename,title,url,text FROM documents""")
        c.execute("INSERT INTO pdf_lab_meta(key,value) VALUES('linguistic_fts_v1','done')")
    c.commit(); return c

def now(): return datetime.now(timezone.utc).isoformat()

class CrawlRequest(BaseModel):
    start_url: str
    filename_patterns: list[str] = Field(default_factory=lambda:["*.pdf","*.pptx","*.ppt","*.docx","*.doc","*.xlsx","*.xls","*.odp","*.odt","*.ods"])
    content_query: str = ""
    depth: int = Field(default=3, ge=0, le=12)
    max_pages: int = Field(default=0, ge=0)
    max_files: int = Field(default=0, ge=0)
    max_bytes: int = Field(default=0, ge=0)
    delay_seconds: float = Field(default=0.5, ge=0.1, le=30)
    same_domain: bool = True
    allow_domains: list[str] = Field(default_factory=list)
    respect_robots: bool = True
    download_matches: bool = True

class SearchRequest(BaseModel):
    query: str = ""
    limit: int = Field(default=100, ge=1, le=500)

def valid_http(url):
    p=urlparse(url)
    if p.scheme not in ("http","https") or not p.hostname: return False
    if p.username or p.password: return False
    import ipaddress, socket
    host=p.hostname.lower().rstrip(".")
    cached=host_validation_cache.get(host)
    if cached and time.monotonic()-cached[0] < 60:
        return cached[1]
    try:
        ip=ipaddress.ip_address(host)
        safe=ip.is_global
    except ValueError:
        try:
            addresses=socket.getaddrinfo(host,None)
            safe=bool(addresses) and all(ipaddress.ip_address(info[4][0]).is_global for info in addresses)
        except (socket.gaierror, ValueError):
            safe=False
    host_validation_cache[host]=(time.monotonic(),safe)
    return safe

def domain_allowed(host, root_host, allow, same):
    host=(host or "").lower().rstrip(".")
    root_host=(root_host or "").lower().rstrip(".")
    allowed={x.lower().strip().rstrip(".") for x in allow if x.strip()}
    if host==root_host: return True
    if same and host.endswith("."+root_host): return True
    if any(host==x or host.endswith("."+x) for x in allowed): return True
    return False

async def can_fetch(client, url, respect):
    if not respect: return True
    p=urlparse(url); origin=f"{p.scheme}://{p.netloc}"
    rp=robots_cache.get(origin)
    if rp is None:
        lock=robots_locks.setdefault(origin,asyncio.Lock())
        async with lock:
            rp=robots_cache.get(origin)
            if rp is None:
                rp=RobotFileParser(); rp.set_url(origin+"/robots.txt")
                try:
                    r=await client.get(origin+"/robots.txt", timeout=8, headers={"User-Agent":UA})
                    if r.status_code==200: rp.parse(r.text.splitlines())
                    elif r.status_code in (401,403): rp.parse(["User-agent: *","Disallow: /"])
                    else: rp.parse(["User-agent: *","Allow: /"])
                except Exception:
                    # Fail closed on robots retrieval errors.
                    rp.parse(["User-agent: *","Disallow: /"])
                robots_cache[origin]=rp
    return rp.can_fetch(UA,url)

def filename_matches(name, patterns):
    import fnmatch
    pats=patterns or ["*.pdf"]
    return any(fnmatch.fnmatch(name.lower(),p.lower()) for p in pats)

def query_matches(text, query):
    """Simple boolean expression: quoted phrases, AND, OR, NOT, parentheses."""
    if not query.strip(): return True
    tokens=re.findall(r'"[^"]+"|\(|\)|\bAND\b|\bOR\b|\bNOT\b|[^\s()]+',query,flags=re.I)
    if not tokens: return True
    # Shunting-yard to postfix; implicit AND between adjacent operands.
    out=[]; ops=[]; prec={"OR":1,"AND":2,"NOT":3}
    expanded=[]
    for i,t in enumerate(tokens):
        if i and (tokens[i-1]==")" or (tokens[i-1] not in ("AND","OR","NOT","(") and tokens[i-1]!="(")) and (t=="(" or t.upper()=="NOT" or (t not in (")","AND","OR"))):
            expanded.append("AND")
        expanded.append(t)
    tokens=expanded
    for t in tokens:
        u=t.upper()
        if t=="(": ops.append(t)
        elif t==")":
            while ops and ops[-1]!="(": out.append(ops.pop())
            if ops: ops.pop()
        elif u in prec:
            while ops and ops[-1]!="(" and prec.get(ops[-1],0)>=prec[u]: out.append(ops.pop())
            ops.append(u)
        else: out.append(t.strip('"').lower())
    while ops: out.append(ops.pop())
    stack=[]
    for t in out:
        if t=="NOT":
            if not stack: return False
            stack.append(not stack.pop())
        elif t in ("AND","OR"):
            if len(stack)<2: return False
            b=stack.pop(); a=stack.pop(); stack.append(a and b if t=="AND" else a or b)
        else: stack.append(t in text.lower())
    return len(stack)==1 and bool(stack[0])

def is_pdf_signature(data):
    """Accept a PDF header near byte zero, but not a header embedded in an HTML page."""
    prefix=(data or b"")[:1024]
    match=re.match(rb"^(?:\xef\xbb\xbf)?[ \t\r\n\x00]*%PDF-[0-9]\.[0-9]",prefix)
    return bool(match)


SUPPORTED_FORMATS = ("pdf","pptx","ppt","docx","doc","xlsx","xls","odp","odt","ods")
OFFICE_ZIP_FORMATS = {"pptx","docx","xlsx","odp","odt","ods"}
LEGACY_OFFICE_FORMATS = {"ppt","doc","xls"}
DOCUMENT_MIME = {
    "pdf":"application/pdf",
    "pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "ppt":"application/vnd.ms-powerpoint",
    "docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc":"application/msword",
    "xlsx":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls":"application/vnd.ms-excel",
    "odp":"application/vnd.oasis.opendocument.presentation",
    "odt":"application/vnd.oasis.opendocument.text",
    "ods":"application/vnd.oasis.opendocument.spreadsheet",
}


def document_format(value):
    suffix=Path(urlparse(value).path).suffix.lower().lstrip(".")
    return suffix if suffix in SUPPORTED_FORMATS else ""


def is_document_candidate(url, content_type):
    """Identify URLs/MIME types for supported PDF and office document formats."""
    ext=document_format(url)
    mime=(content_type or "").split(";",1)[0].strip().lower()
    return bool(ext in SUPPORTED_FORMATS or mime in set(DOCUMENT_MIME.values())
                or mime in {"application/octet-stream","binary/octet-stream"})


def is_pdf_candidate(url, content_type):
    """Backward-compatible PDF candidate helper."""
    mime=(content_type or "").split(";",1)[0].strip().lower()
    return (document_format(url)=="pdf" or "pdf" in mime
            or mime in {"application/octet-stream","binary/octet-stream"})


def document_signature_probe(data, filename, content_type=""):
    """Fast ranged-response signature check; full container validation occurs at import."""
    ext=Path(filename).suffix.lower().lstrip(".")
    prefix=(data or b"")[:1024]
    if ext=="pdf":
        return is_pdf_signature(prefix)
    if ext in OFFICE_ZIP_FORMATS:
        return prefix.startswith(b"PK\x03\x04")
    if ext in LEGACY_OFFICE_FORMATS:
        return prefix.startswith(bytes.fromhex("D0CF11E0A1B11AE1"))
    mime=(content_type or "").lower()
    return bool("officedocument" in mime or "opendocument" in mime)


def validate_document_signature(data, filename):
    """Validate a supported file's real signature and Office container markers."""
    ext=Path(filename).suffix.lower().lstrip(".")
    if ext not in SUPPORTED_FORMATS:
        raise ValueError("Unsupported document format: ."+(ext or "(none)"))
    if ext=="pdf":
        if not is_pdf_signature(data):
            raise ValueError("Invalid PDF: missing %PDF- signature.")
        return
    if ext in OFFICE_ZIP_FORMATS:
        try:
            with zipfile.ZipFile(__import__("io").BytesIO(data)) as archive:
                names=set(archive.namelist())
                expected={
                    "pptx":{"ppt/presentation.xml"},
                    "docx":{"word/document.xml"},
                    "xlsx":{"xl/workbook.xml"},
                    "odp":{"content.xml","mimetype"},
                    "odt":{"content.xml","mimetype"},
                    "ods":{"content.xml","mimetype"},
                }[ext]
                if not expected.issubset(names):
                    raise ValueError("ZIP container does not contain the expected "+ext.upper()+" document structure.")
                if len(names)>5000 or sum(x.file_size for x in archive.infolist())>100_000_000:
                    raise ValueError("Office archive exceeds safe extraction limits.")
        except zipfile.BadZipFile as exc:
            raise ValueError("Office document is not a valid ZIP container.") from exc
        return
    if ext in LEGACY_OFFICE_FORMATS:
        if not (data or b"").startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
            raise ValueError("Legacy Office file is missing the OLE compound-document signature.")
        return




def extract_pdf(data):
    import io
    if not is_pdf_signature(data):
        raise ValueError("Invalid PDF: missing %PDF- file signature in the first 1,024 bytes.")
    reader=PdfReader(io.BytesIO(data), strict=False)
    pages=[]; texts=[]
    for i,page in enumerate(reader.pages):
        t=page.extract_text() or ""; texts.append(t)
        for line_no,line in enumerate(t.splitlines(),1):
            if line.strip(): pages.append({"page":i+1,"line":line_no,"text":line[:500]})
    return "\n".join(texts),len(reader.pages),pages

def _xml_paragraph_text(xml_bytes):
    root=ET.fromstring(xml_bytes)
    output=[]
    for paragraph in root.iter():
        if paragraph.tag.rsplit("}",1)[-1] not in ("p","h","si","is"):
            continue
        parts=[node.text or "" for node in paragraph.iter()
               if node.tag.rsplit("}",1)[-1] in ("t","tab")]
        value="".join(parts).strip()
        if value:
            output.append(value)
    return output


def _extract_ooxml(data, ext):
    import io
    lines=[]; page_records=[]
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos=archive.infolist()
        if len(infos)>5000 or sum(x.file_size for x in infos)>100_000_000:
            raise ValueError("Office archive exceeds safe extraction limits.")
        names=set(archive.namelist())
        if ext=="pptx":
            slide_names=sorted(
                (n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml",n)),
                key=lambda n:int(re.search(r"slide(\d+)",n).group(1))
            )
            if not slide_names:
                raise ValueError("Presentation contains no readable slides.")
            for number,name in enumerate(slide_names,1):
                paragraphs=_xml_paragraph_text(archive.read(name))
                text="\n".join(paragraphs)
                lines.append(f"[Slide {number}]\n{text}")
                page_records.append({"page":number,"line":1,"text":text[:500]})
        elif ext=="docx":
            if "word/document.xml" not in names:
                raise ValueError("Word document body is missing.")
            paragraphs=_xml_paragraph_text(archive.read("word/document.xml"))
            for part in sorted(n for n in names if re.fullmatch(r"word/(header|footer)\d+\.xml",n)):
                paragraphs.extend(_xml_paragraph_text(archive.read(part)))
            lines.extend(paragraphs)
            page_records=[{"page":1,"line":i+1,"text":p[:500]} for i,p in enumerate(paragraphs)]
            return "\n".join(lines),None,page_records
        elif ext=="xlsx":
            shared=[]
            if "xl/sharedStrings.xml" in names:
                root=ET.fromstring(archive.read("xl/sharedStrings.xml"))
                for si in root:
                    shared.append("".join(node.text or "" for node in si.iter()
                                          if node.tag.rsplit("}",1)[-1]=="t"))
            sheets=sorted((n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml",n)),
                          key=lambda n:int(re.search(r"sheet(\d+)",n).group(1)))
            for number,name in enumerate(sheets,1):
                root=ET.fromstring(archive.read(name)); rows=[]
                for row in root.iter():
                    if row.tag.rsplit("}",1)[-1]!="row":continue
                    values=[]
                    for cell in row:
                        if cell.tag.rsplit("}",1)[-1]!="c":continue
                        cell_type=cell.attrib.get("t","")
                        value_node=next((x for x in cell if x.tag.rsplit("}",1)[-1]=="v"),None)
                        value=value_node.text if value_node is not None else ""
                        if cell_type=="s" and value.isdigit() and int(value)<len(shared):
                            value=shared[int(value)]
                        elif cell_type=="inlineStr":
                            value="".join(x.text or "" for x in cell.iter()
                                          if x.tag.rsplit("}",1)[-1]=="t")
                        if value: values.append(value)
                    if values: rows.append(" | ".join(values))
                text="\n".join(rows)
                lines.append(f"[Sheet {number}]\n{text}")
                page_records.append({"page":number,"line":1,"text":text[:500]})
        else:
            if "content.xml" not in names:
                raise ValueError("OpenDocument content.xml is missing.")
            paragraphs=_xml_paragraph_text(archive.read("content.xml"))
            # ODF paragraphs include table-cell text, making a useful flattened reader.
            lines.extend(paragraphs)
            page_records=[{"page":1,"line":i+1,"text":p[:500]} for i,p in enumerate(paragraphs)]
    body="\\n\\n".join(x for x in lines if x.strip())
    count=max(1,len(page_records))
    return body,count,page_records


def _extract_legacy_office(data, filename):
    office=shutil.which("libreoffice") or shutil.which("soffice")
    if not office:
        raise ValueError("Legacy Office format requires LibreOffice (soffice) on the worker machine.")
    with tempfile.TemporaryDirectory(prefix="pdf-lab-office-") as tmp:
        src=Path(tmp)/(Path(filename).name or "document.bin")
        src.write_bytes(data)
        converted=subprocess.run(
            [office,"--headless","--convert-to","pdf","--outdir",tmp,str(src)],
            capture_output=True,text=True,timeout=60,check=False
        )
        target=Path(tmp)/(src.stem+".pdf")
        if converted.returncode!=0 or not target.is_file():
            detail=(converted.stderr or converted.stdout or "LibreOffice conversion failed")[:240]
            raise ValueError("Legacy Office conversion failed: "+detail)
        return extract_pdf(target.read_bytes())


def extract_document(data, filename):
    """Extract searchable text from PDF, OOXML and OpenDocument formats."""
    ext=Path(filename).suffix.lower().lstrip(".")
    validate_document_signature(data,filename)
    if ext=="pdf":
        return extract_pdf(data)
    if ext in OFFICE_ZIP_FORMATS:
        return _extract_ooxml(data,ext)
    if ext in LEGACY_OFFICE_FORMATS:
        return _extract_legacy_office(data,filename)
    raise ValueError("Unsupported document format: ."+ext)


def store_document(url, filename, data, title, text, pages):
    digest=hashlib.sha256(data).hexdigest()
    ext=Path(filename).suffix.lower() or ".bin"
    path=FILES/(digest+ext)
    if not path.exists(): path.write_bytes(data)
    c=connect()
    existing=c.execute("SELECT id FROM documents WHERE sha256=?",(digest,)).fetchone()
    if existing:
        c.close()
        return existing["id"],False
    docid=str(uuid.uuid4())
    c.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)",
      (docid,digest,url,filename,title,str(path),len(data),pages,text,now()))
    c.execute("INSERT INTO document_fts VALUES(?,?,?,?,?)",(docid,filename,title or "",url,text))
    c.execute("INSERT INTO document_fts_linguistic VALUES(?,?,?,?,?)",(docid,filename,title or "",url,text))
    c.commit();c.close()
    return docid,True


def store_pdf(url, filename, data, title, text, pages):
    return store_document(url,filename,data,title,text,pages)

async def crawl(jobid, cfg: CrawlRequest):
    j=jobs[jobid]; j["status"]="running"; j["started_at"]=now()
    def log(msg): j["log"].append(msg); j["log"]=j["log"][-200:]
    start=cfg.start_url.strip()
    if not valid_http(start): raise ValueError("Start URL must be a public http(s) URL; private, localhost and credential-bearing targets are refused.")
    root=urlparse(start).hostname
    queue=deque([(start,0)]); visited=set(); found=set(); stored=0; pages_seen=0
    limits=httpx.Limits(max_connections=8,max_keepalive_connections=4)
    async with httpx.AsyncClient(follow_redirects=False,limits=limits,headers={"User-Agent":UA}) as client:
      while queue and (not cfg.max_pages or pages_seen<cfg.max_pages) and (not cfg.max_files or len(found)<cfg.max_files):
        url,level=queue.popleft(); url=urldefrag(url)[0]
        if url in visited: continue
        visited.add(url)
        if not valid_http(url): continue
        host=urlparse(url).hostname
        if not domain_allowed(host,root,cfg.allow_domains,cfg.same_domain): continue
        if not await can_fetch(client,url,cfg.respect_robots):
            j["stats"]["robots_blocked"]+=1; continue
        try:
            async with client.stream("GET",url,timeout=20) as response:
                if 300 <= response.status_code < 400 and response.headers.get("location"):
                    target=urljoin(url,response.headers["location"])
                    if valid_http(target) and domain_allowed(urlparse(target).hostname,root,cfg.allow_domains,cfg.same_domain):
                        queue.append((target,level))
                    continue
                if response.status_code!=200: continue
                if not valid_http(str(response.url)): continue
                ctype=response.headers.get("content-type","").lower()
                length=int(response.headers.get("content-length","0") or 0)
                if cfg.max_bytes and length>cfg.max_bytes: continue
                if is_document_candidate(url,ctype):
                    chunks=[]; total=0
                    async for chunk in response.aiter_bytes():
                        total+=len(chunk)
                        if cfg.max_bytes and total>cfg.max_bytes: raise ValueError("file exceeds max_bytes")
                        chunks.append(chunk)
                    data=b"".join(chunks)
                    name=unquote(Path(urlparse(url).path).name) or "document"
                    ext=document_format(name)
                    if not ext:
                        ext=next((x for x in SUPPORTED_FORMATS if DOCUMENT_MIME.get(x,"") in ctype),"")
                        if ext:name+="."+ext
                    if not ext or not filename_matches(name,cfg.filename_patterns): continue
                    found.add(url); j["stats"]["pdfs_found"]+=1
                    try:
                        validate_document_signature(data,name)
                        body,np,pagematches=extract_document(data,name)
                    except Exception as e:
                        j["stats"]["parse_errors"]+=1; log(f"Document parse failed: {name}: {e}"); continue
                    if not query_matches(body,cfg.content_query): continue
                    if cfg.download_matches:
                        docid,new=store_document(url,name,data,name,body,np)
                        stored+=int(new)
                    else:
                        docid,new=None,False
                    j["stats"]["matches"]+=1
                    j["results"].append({"id":docid,"filename":name,"url":url,"pages":np,"bytes":len(data),"format":ext,"sha256":hashlib.sha256(data).hexdigest(),"new":new,"snippets":[x for x in pagematches if query_matches(x["text"],cfg.content_query)][:8]})
                    log((("Stored " if new else "Already catalogued ") if cfg.download_matches else "Matched (download disabled) ")+name)
                elif "text/html" in ctype and level<cfg.depth:
                    data=await response.aread()
                    if cfg.max_bytes and len(data)>cfg.max_bytes: continue
                    soup=BeautifulSoup(data,"html.parser")
                    pages_seen+=1; j["stats"]["pages_visited"]=pages_seen
                    for a in soup.select("a[href]"):
                        nxt=urljoin(str(response.url),a.get("href",""))
                        nxt=urldefrag(nxt)[0]
                        if not valid_http(nxt): continue
                        nh=urlparse(nxt).hostname
                        if not domain_allowed(nh,root,cfg.allow_domains,cfg.same_domain): continue
                        if nxt not in visited: queue.append((nxt,level+1))
        except Exception as e:
            j["stats"]["request_errors"]+=1; log(f"Skipped {url}: {str(e)[:160]}")
        j["stats"]["queue_remaining"]=len(queue); j["stats"]["urls_visited"]=len(visited)
        await asyncio.sleep(cfg.delay_seconds)
    j["status"]="completed"; j["finished_at"]=now()
    log(f"Finished: {pages_seen} HTML pages, {j['stats']['pdfs_found']} PDF candidates, {j['stats']['matches']} content matches, {stored} new files stored.")


class WildcardDiscoveryRequest(BaseModel):
    url_pattern: str
    content_query: str = ""
    extensions: list[str] = Field(default_factory=lambda:["pdf","pptx","ppt","docx","doc","xlsx","xls","odp","odt","ods"])
    match_mode: str = Field(default="glob", pattern="^(glob|regex)$")
    max_results: int = Field(default=0, ge=0)
    indexes: int = Field(default=0, ge=0)
    recursive: bool = False
    recursive_depth: int = Field(default=2, ge=0, le=3)
    max_pages: int = Field(default=0, ge=0)
    respect_robots: bool = True

class ArchiveImportSource(BaseModel):
    original_url: str
    archive_file_url: str
    title: str = ""


class ImportURLsRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)
    archive_sources: list[ArchiveImportSource] = Field(default_factory=list)
    filename_patterns: list[str] = Field(default_factory=lambda:["*.pdf","*.pptx","*.ppt","*.docx","*.doc","*.xlsx","*.xls","*.odp","*.odt","*.ods"])
    content_query: str = ""
    max_bytes: int = Field(default=0, ge=0)
    respect_robots: bool = True


def import_source_targets(original_url, archive_file_url=None):
    """Try the live original first and its exact archived binary second."""
    targets=[]
    for target in (original_url,archive_file_url):
        if target and target not in targets:
            targets.append(target)
    return targets

def normalize_glob(pattern):
    return pattern.strip().replace(r"\*", "*").replace(r"\?", "?").lower()

def glob_to_regex(pattern):
    """Translate URL glob: * stays within a path segment; ** crosses separators.

    Bare host/path patterns such as *.edu/**/*.pdf are matched against absolute
    URLs by implicitly adding the HTTP(S) scheme.
    """
    p=normalize_glob(pattern)
    prefix = "" if re.match(r"^https?://",p,re.I) else r"https?://"
    out=[prefix]; i=0
    while i<len(p):
        ch=p[i]
        if ch=="*":
            if i+1<len(p) and p[i+1]=="*":
                i+=2
                if i<len(p) and p[i]=="/":
                    out.append("(?:.*/)?"); i+=1
                else: out.append(".*")
                continue
            out.append("[^/]*")
        elif ch=="?": out.append("[^/]")
        else: out.append(re.escape(ch))
        i+=1
    return re.compile("^"+"".join(out)+r"(?:[?#].*)?$",re.I)

def commoncrawl_query_pattern(pattern, mode="glob"):
    """Derive a narrow CDX prefix query; exact semantics are enforced locally."""
    p=pattern.lower()
    if mode=="regex":
        # Recover a literal hostname/TLD from common anchored or unanchored URL regexes.
        host=re.search(r"https?://.*?(\\.[a-z]{2,})(?:/|$)",p)
        if host: return "*"+host.group(1)+"/*"
        literal=re.search(r"https?://([a-z0-9.-]+)",p)
        if literal: return literal.group(1)+"/*"
        raise ValueError("Regex discovery needs a recognizable URL host or suffix, e.g. ^https://[^/]+\\\\.edu/...")
    # Query just the URL prefix that exists before the first wildcard in the host/path.
    literal=re.sub(r"[*?].*$","",p)
    m=re.search(r"https?://([^/]+)",literal)
    if m and m.group(1) and "." in m.group(1):
        host=m.group(1)
        if not host.startswith("."): return host+"/*"
    tld=re.search(r"\.([a-z]{2,})",p)
    if tld: return "*."+tld.group(1)+"/*"
    raise ValueError("Global discovery needs a recognizable suffix (.edu/.gov/.org) or literal host.")

def url_matcher(pattern, mode):
    if mode=="regex":
        try: return re.compile(pattern,re.I)
        except re.error as e: raise HTTPException(400,"Invalid URL regular expression: "+str(e))
    return glob_to_regex(pattern)

def cdx_query_candidates(pattern, mode):
    """Build a CDX query that narrows by host suffix and, where possible, file extension."""
    if mode=="regex":
        return [commoncrawl_query_pattern(pattern,mode)]
    p=normalize_glob(pattern)
    # A literal hostname is the strongest CDX narrowing.
    host=re.search(r"https?://([^/]+)",p)
    if host and not any(ch in host.group(1) for ch in "*?"):
        return [host.group(1)+"/*"]
    # Keep .edu PDF discovery focused on PDF-looking URL paths. The returned URLs are
    # still checked against the user's complete glob locally, so this is only a
    # candidate-generation optimization, not a change to matching semantics.
    edu=re.search(r"\.edu(?:/|$)",p)
    if edu:
        # Partition the broad .edu wildcard by the first hostname character.
        # CDX's * wildcard spans the remainder of the URL, including nested paths.
        # The local matcher below still enforces the user's full ** glob.
        buckets=list("0123456789abcdefghijklmnopqrstuvwxyz")
        extension="*.pdf" if re.search(r"\.pdf$",p) else "*"
        return [ch+"*.edu/"+extension for ch in buckets]
    # Other recognizable TLDs use a broad suffix query; local matching enforces the glob.
    tld=re.search(r"\.([a-z]{2,})(?:/|$)",p)
    if not tld:
        return [commoncrawl_query_pattern(pattern,mode)]
    return ["*."+tld.group(1)+"/*"]

async def recursive_url_discovery(client, seeds, matcher, req, results, seen, errors):
    """Bounded same-host crawl from up to five discovered host roots."""
    roots=[]
    for seed in seeds:
        p=urlparse(seed); root=f"{p.scheme}://{p.netloc}/"
        if root not in roots: roots.append(root)
        if len(roots)>=5: break
    queue=deque((root,0) for root in roots); visited=set(); pages=0
    while queue and pages<req.max_pages and len(results)<req.max_results:
        url,depth=queue.popleft()
        if url in visited or depth>req.recursive_depth: continue
        visited.add(url)
        if not valid_http(url): continue
        try:
            if not await can_fetch(client,url,req.respect_robots): continue
            async with client.stream("GET",url,timeout=15) as response:
                if response.status_code!=200 or "text/html" not in response.headers.get("content-type","").lower(): continue
                if not valid_http(str(response.url)): continue
                data=await response.aread()
            if len(data)>2_000_000: continue
            pages+=1
            soup=BeautifulSoup(data,"html.parser")
            for link in soup.select("a[href]"):
                target=urldefrag(urljoin(url,link.get("href","")))[0]
                if not valid_http(target) or urlparse(target).netloc.lower()!=urlparse(url).netloc.lower(): continue
                if matcher.search(target):
                    if target not in seen:
                        seen.add(target); results.append({"url":target,"timestamp":None,"mime":None,"status":"live-crawl","collection":"recursive-live"})
                        if len(results)>=req.max_results: break
                elif depth<req.recursive_depth and "?" not in target:
                    if target not in visited and not urlparse(target).path.lower().endswith((".jpg",".png",".gif",".zip",".mp4")):
                        queue.append((target,depth+1))
        except Exception as e:
            errors.append("recursive "+url+": "+str(e)[:140])
    return pages

def wayback_query_patterns(pattern, mode):
    """Map supported URL globs/regexes to a bounded Wayback CDX domain/prefix query."""
    p=pattern.lower()
    literal=re.search(r"https?://([^/]+)",p)
    if literal and not any(ch in literal.group(1) for ch in "*?[]"):
        return [literal.group(1)+"/*"]
    tld=re.search(r"\.([a-z]{2,})(?:/|$)",p)
    if not tld:
        raise ValueError("Wayback fallback needs a recognizable TLD or literal hostname.")
    return ["*."+tld.group(1)+"/*"]


def parse_wayback_cdx_payload(payload):
    """Normalize Wayback CDX JSON's header-row format into dictionaries."""
    if isinstance(payload,list) and payload:
        header=payload[0] if isinstance(payload[0],list) else None
        if header:
            return [dict(zip(header,values)) for values in payload[1:] if isinstance(values,list)]
        return [item for item in payload if isinstance(item,dict)]
    if isinstance(payload,dict):
        return [payload]
    return []


def arquivo_query_patterns(pattern, mode):
    """Build a broad but bounded Arquivo.pt CDX query; exact matching stays local."""
    p=pattern.lower()
    literal=re.search(r"https?://([^/]+)",p)
    if literal and not any(ch in literal.group(1) for ch in "*?[]"):
        return [literal.group(1)+"/*"]
    tld=None
    if mode=="regex":
        tld=re.search(r"\\\.([a-z]{2,})",p) or re.search(r"\.([a-z]{2,})(?:/|$)",p)
    else:
        tld=re.search(r"\.([a-z]{2,})(?:/|$)",p)
    if not tld:
        raise ValueError("Arquivo.pt discovery needs a recognizable TLD (such as .edu/.gov) or literal hostname.")
    # CDX interprets *.tld as a domain match, including hosts below that TLD.
    return ["*."+tld.group(1)]


def parse_arquivo_cdx_payload(payload):
    """Parse Arquivo.pt's output=json format (NDJSON, one object per line)."""
    if isinstance(payload, (dict, list)):
        if isinstance(payload, dict):
            return [payload]
        return [item for item in payload if isinstance(item, dict)]
    text_payload=str(payload or "").strip()
    if not text_payload:
        return []
    try:
        decoded=json.loads(text_payload)
        if isinstance(decoded, dict):
            return [decoded]
        if isinstance(decoded, list):
            return [item for item in decoded if isinstance(item, dict)]
    except (json.JSONDecodeError, TypeError):
        pass
    rows=[]
    for line in text_payload.splitlines():
        try:
            item=json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item,dict):
            rows.append(item)
    return rows


def arquivo_text_query(query):
    """Translate supported PDF Lab terms into Arquivo.pt's full-text syntax.

    Arquivo.pt supports required terms, quoted phrases, and '-' exclusions.
    Its API does not implement this worker's OR/NOT/parenthesis grammar.
    """
    value=(query or "").strip()
    if not value:
        return None
    tokens=re.findall(r'"[^"]+"|[()]|\S+',value)
    for token in tokens:
        quoted=token.startswith('"') and token.endswith('"')
        if not quoted and (token in ("(",")") or token.upper() in ("OR","NOT")):
            return None
    # Arquivo.pt treats separate terms as AND; retain the AND word inside
    # quoted phrases and remove only standalone Boolean AND operators.
    tokens=[token for token in tokens if token.startswith('"') or token.upper()!="AND"]
    value=" ".join(tokens).strip()
    return value or None


def clean_archive_text(value, max_chars=1200):
    """Convert archive HTML fragments/entities into safe, readable plain text."""
    if value is None:
        return None
    cleaned=BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    cleaned=re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned)>max_chars:
        cleaned=cleaned[:max_chars].rsplit(" ",1)[0]+" …"
    return cleaned or None


async def arquivo_text_discovery(client, query, pattern, mode, matcher, max_results, errors):
    """Search archived PDF contents by terms and URL scope."""
    if not (query or "").strip():
        return [],0,"not-run"
    normalized=arquivo_text_query(query)
    if not normalized:
        return [],0,"skipped"
    try:
        site_patterns=arquivo_query_patterns(pattern,mode)
        site_scope=",".join(site_patterns)
        # TextSearch accepts a host/path prefix, not the CDX trailing wildcard.
        if site_scope.endswith("/*"):
            site_scope=site_scope[:-1]
        params=[
            ("q",normalized),("type","pdf"),("siteSearch",site_scope),
            ("maxItems",str(min(max_results,500))),
            ("dedupField","url"),("dedupValue","1"),
            ("fields","title,originalURL,linkToArchive,tstamp,mimeType,snippet,linkToOriginalFile"),
        ]
        response=await client.get(
            "https://arquivo.pt/textsearch",params=params,
            timeout=httpx.Timeout(20.0,connect=8.0),
        )
        response.raise_for_status()
        payload=response.json()
        records=payload.get("response_items",[]) if isinstance(payload,dict) else []
        found=[]; seen=set()
        for item in records:
            if not isinstance(item,dict):
                continue
            url=item.get("originalURL") or ""
            if not url or url in seen or not re.match(r"^https?://",url,re.I):
                continue
            if not matcher.search(url):
                continue
            seen.add(url)
            found.append({
                "url":url,"timestamp":item.get("tstamp"),
                "mime":item.get("mimeType"),"status":None,
                "collection":"arquivo-textsearch",
                "title":clean_archive_text(item.get("title"),400),
                "snippet":clean_archive_text(item.get("snippet"),1200),
                "archive_url":item.get("linkToArchive"),
                "archive_file_url":item.get("linkToOriginalFile"),
                "query_match":True,
            })
            if len(found)>=max_results:
                break
        return found,1,("results" if found else "empty")
    except Exception as exc:
        errors.append("Arquivo.pt full-text: "+type(exc).__name__+": "+str(exc)[:160])
        return [],0,"unavailable"


def discovery_sort_key(item):
    is_pdf=(str(item.get("mime") or "").lower()=="application/pdf" or
            urlparse(item["url"]).path.lower().endswith(".pdf"))
    stamp=str(item.get("timestamp") or "")
    # Common Crawl uses YYYYMMDD; Wayback uses YYYYMMDDhhmmss.
    # Right-pad to a common precision, then sort newest first.
    stamp_number=int(stamp.ljust(14,"0")) if stamp.isdigit() else 0
    source_priority={"commoncrawl":0,"arquivo-textsearch":1,"arquivo-cdx":2,"wayback-cdx":3}.get(item.get("collection"),4)
    return (0 if item.get("query_match") else 1, 0 if is_pdf else 1, -stamp_number, source_priority, item["url"].casefold())


async def wayback_discovery(client, pattern, mode, matcher, max_results, errors):
    """Retrieve archived URL candidates from Internet Archive CDX; exact-match locally."""
    endpoint="https://web.archive.org/cdx/search/cdx"
    queries=wayback_query_patterns(pattern,mode)
    found=[]; seen=set(); pages_fetched=0
    for qpattern in queries:
        try:
            params=[
                ("url",qpattern),("output","json"),("fl","timestamp,original,mimetype,statuscode"),
                ("filter","statuscode:200"),("collapse","urlkey"),("limit",str(min(max_results*3,2000))),
            ]
            if re.search(r"\.pdf$",pattern,re.I):
                params.append(("filter",r"original:.*\.pdf([?#].*)?$"))
            response=await client.get(endpoint,params=params,timeout=httpx.Timeout(18.0,connect=6.0))
            response.raise_for_status()
            pages_fetched+=1
            payload=response.json()
            records=parse_wayback_cdx_payload(payload)
            for item in records:
                url=item.get("original") or item.get("url") or ""
                if not url or url in seen or not re.match(r"^https?://",url,re.I): continue
                if not matcher.search(url): continue
                seen.add(url)
                found.append({
                    "url":url,"timestamp":item.get("timestamp"),
                    "mime":item.get("mimetype") or item.get("mime"),
                    "status":item.get("statuscode") or item.get("status"),
                    "collection":"wayback-cdx",
                })
                if len(found)>=max_results: break
        except Exception as exc:
            errors.append("Wayback CDX "+qpattern+": "+type(exc).__name__+": "+str(exc)[:160])
    return found,pages_fetched


async def arquivo_discovery(client, pattern, mode, matcher, max_results, errors):
    """Supplement URL discovery with Arquivo.pt's independent CDX archive."""
    endpoint="https://arquivo.pt/wayback/cdx"
    queries=arquivo_query_patterns(pattern,mode)
    found=[]; seen=set(); requests_made=0
    for qpattern in queries:
        params=[
            ("url",qpattern),("output","json"),
            ("fields","url,timestamp,mime,status"),
            ("limit",str(min(max(200,max_results*20),2000))),
            ("filter","=status:200"),
        ]
        # Narrow archived captures to PDF-looking URLs before applying the exact
        # user glob locally. This keeps broad TLD scans useful under the API cap.
        if re.search(r"\.pdf(?:$|[?#])",pattern,re.I):
            params.append(("filter",r"~url:.*\.pdf([?#].*)?$"))
        last_error=None
        for attempt in range(2):
            try:
                response=await client.get(
                    endpoint,params=params,
                    timeout=httpx.Timeout(20.0,connect=8.0),
                )
                if response.status_code==429:
                    retry_after=response.headers.get("Retry-After","2")
                    try: delay=min(max(float(retry_after),1.0),15.0)
                    except ValueError: delay=2.0
                    if attempt==0:
                        await asyncio.sleep(delay)
                        continue
                response.raise_for_status()
                requests_made+=1
                for item in parse_arquivo_cdx_payload(response.text):
                    url=item.get("url") or item.get("original") or ""
                    if not url or url in seen or not re.match(r"^https?://",url,re.I):
                        continue
                    if not matcher.search(url):
                        continue
                    seen.add(url)
                    found.append({
                        "url":url,"timestamp":item.get("timestamp"),
                        "mime":item.get("mime") or item.get("mimetype"),
                        "status":item.get("status") or item.get("statuscode"),
                        "collection":"arquivo-cdx",
                    })
                    if len(found)>=max_results:
                        break
                break
            except (httpx.TimeoutException,httpx.TransportError,httpx.HTTPStatusError,ValueError) as exc:
                last_error=exc
                if attempt==0 and isinstance(exc,(httpx.TimeoutException,httpx.TransportError)):
                    await asyncio.sleep(1.0)
                    continue
                break
        if last_error:
            errors.append("Arquivo.pt CDX "+qpattern+": "+type(last_error).__name__+": "+str(last_error)[:160])
        if len(found)>=max_results:
            break
    return found,requests_made


@app.post("/api/discover")
async def discover_wildcard(req: WildcardDiscoveryRequest):
    pattern=req.url_pattern.strip()
    matcher=url_matcher(pattern,req.match_mode)
    result_limit=req.max_results or 10000
    try:
        query_patterns=cdx_query_candidates(pattern,req.match_mode)
    except ValueError as exc:
        raise HTTPException(400,detail=str(exc))
    results=[]; seen=set(); errors=[]; queried=[]; pages_fetched=0
    pages_crawled=0; page_limit_reached=False
    providers={"commoncrawl":"not-run","arquivo-textsearch":"not-run","arquivo":"not-run","wayback":"not-run"}
    timeout=httpx.Timeout(22.0,connect=6.0)
    async with httpx.AsyncClient(timeout=timeout,headers={"User-Agent":UA},limits=httpx.Limits(max_connections=12,max_keepalive_connections=6)) as client:
        # When a plain-term/phrase query is supplied, search archived PDF text
        # before falling back to URL-only CDX results.
        if len(results)<result_limit and "pdf" in {x.lower().lstrip(".") for x in req.extensions}:
            text_results,text_requests,text_state=await arquivo_text_discovery(
                client,req.content_query,pattern,req.match_mode,matcher,
                result_limit-len(results),errors
            )
            pages_fetched+=text_requests
            providers["arquivo-textsearch"]=text_state
            for item in text_results:
                if item["url"] not in seen:
                    seen.add(item["url"]); results.append(item)

        collections=[]
        try:
            info=await client.get("https://index.commoncrawl.org/collinfo.json",timeout=httpx.Timeout(12.0,connect=5.0))
            info.raise_for_status()
            collection_data=info.json()
            if not isinstance(collection_data,list):
                raise ValueError("Common Crawl collection list was not a JSON array")
            collections=collection_data if req.indexes==0 else collection_data[:req.indexes]
            providers["commoncrawl"]="available"
        except Exception as exc:
            providers["commoncrawl"]="unavailable"
            errors.append("Common Crawl collection list: "+type(exc).__name__+": "+str(exc)[:180])

        async def cdx_get(endpoint, params):
            last_error=None
            for attempt in range(2):
                try:
                    response=await client.get(endpoint,params=params,timeout=timeout)
                    # Rate limiting or overload should stop this provider's run;
                    # retrying a blocked IP immediately only adds load.
                    if response.status_code in (429,503):
                        raise RuntimeError("HTTP "+str(response.status_code)+"; stopping Common Crawl queries for this run")
                    if response.status_code in (500,502,504):
                        last_error=RuntimeError("HTTP "+str(response.status_code))
                        if attempt==0:
                            await asyncio.sleep(2.0)
                            continue
                    response.raise_for_status()
                    return response
                except (httpx.TimeoutException,httpx.TransportError) as exc:
                    last_error=exc
                    if attempt==0:
                        await asyncio.sleep(2.0)
                        continue
            raise RuntimeError("CDX request failed: "+str(last_error)[:140])

        commoncrawl_abort=False
        for collection in collections:
            endpoint=collection.get("cdx-api")
            if not endpoint: continue
            for query_index,cdx_pattern in enumerate(query_patterns):
                if len(results)>=result_limit or commoncrawl_abort: break
                try:
                    # One bounded response per host shard. The old pageSize=1
                    # loop could issue dozens of calls for a single shard.
                    params={
                        "url":cdx_pattern,"output":"json","filter":"status:200",
                        "collapse":"urlkey","limit":str(min(result_limit,2000)),
                        "fl":"url,timestamp,mime,status",
                    }
                    response=await cdx_get(endpoint,params)
                    pages_fetched+=1
                    queried.append(collection.get("id","index")+":"+cdx_pattern)
                    for line in response.text.splitlines():
                        try: item=json.loads(line)
                        except Exception: continue
                        url=item.get("url","")
                        if not url or url in seen or not re.match(r"^https?://",url,re.I): continue
                        if not matcher.search(url): continue
                        seen.add(url)
                        results.append({"url":url,"timestamp":item.get("timestamp"),"mime":item.get("mime"),
                                        "status":item.get("status"),"collection":"commoncrawl"})
                        if len(results)>=result_limit: break
                except Exception as exc:
                    message="Common Crawl "+str(collection.get("id","index"))+" "+cdx_pattern+": "+type(exc).__name__+": "+str(exc)[:160]
                    errors.append(message)
                    detail=str(exc).lower()
                    if ("cdx request failed" in detail or "http 429" in detail or "http 503" in detail
                            or isinstance(exc,(httpx.TimeoutException,httpx.TransportError))
                            or isinstance(exc,httpx.HTTPStatusError)):
                        commoncrawl_abort=True
                        break
                if query_index+1<len(query_patterns) and len(results)<result_limit and not commoncrawl_abort:
                    # Common Crawl asks clients to space CDX requests and avoid
                    # concurrent calls from the same IP.
                    await asyncio.sleep(1.05)
            if len(results)>=result_limit or commoncrawl_abort: break

        commoncrawl_count=sum(1 for item in results if item.get("collection")=="commoncrawl")
        commoncrawl_errors=any(error.startswith("Common Crawl ") for error in errors)
        if commoncrawl_count:
            providers["commoncrawl"]="results"
        elif commoncrawl_errors:
            providers["commoncrawl"]="unavailable"
        elif collections:
            providers["commoncrawl"]="empty"
        # Arquivo.pt is an independent CDX source and is queried before Wayback.
        # It is a supplement, not a complete mirror of the global web.
        if len(results)<result_limit:
            try:
                arquivo_results,arquivo_requests=await arquivo_discovery(
                    client,pattern,req.match_mode,matcher,result_limit-len(results),errors
                )
                pages_fetched+=arquivo_requests
                for item in arquivo_results:
                    if item["url"] not in seen:
                        seen.add(item["url"]); results.append(item)
                providers["arquivo"]="results" if arquivo_results else ("empty" if arquivo_requests else "unavailable")
            except Exception as exc:
                providers["arquivo"]="unavailable"
                errors.append("Arquivo.pt CDX: "+type(exc).__name__+": "+str(exc)[:160])

        # Internet Archive Wayback remains the final independent fallback.
        if len(results)<result_limit:
            try:
                wayback_results,wayback_pages=await wayback_discovery(
                    client,pattern,req.match_mode,matcher,result_limit-len(results),errors
                )
                pages_fetched+=wayback_pages
                for item in wayback_results:
                    if item["url"] not in seen:
                        seen.add(item["url"]); results.append(item)
                providers["wayback"]="results" if wayback_results else ("empty" if wayback_pages else "unavailable")
            except Exception as exc:
                providers["wayback"]="unavailable"
                errors.append("Wayback CDX: "+type(exc).__name__+": "+str(exc)[:160])

        if req.recursive and req.recursive_depth>0 and len(results)<result_limit:
            before=len(results)
            pages_crawled=await recursive_url_discovery(client,[x["url"] for x in results],matcher,req,results,seen,errors)
            if len(results)>before: providers["live-recursive"]="results"
            else: providers["live-recursive"]="empty"

    # Distinguish genuine archive full-text hits from URL-only candidates.
    # URL indexes cannot prove a document contains the requested search terms;
    # the import step still applies the full local Boolean content expression.
    if req.content_query.strip():
        for item in results:
            item["query_verified"]=bool(item.get("query_match"))
    allowed_extensions={x.lower().lstrip(".") for x in req.extensions if re.fullmatch(r"[A-Za-z0-9]{1,8}",x.lstrip("."))}
    if allowed_extensions:
        results=[item for item in results
                 if Path(urlparse(item["url"]).path).suffix.lower().lstrip(".") in allowed_extensions]
    # Verified keyword hits first, then PDFs, then newest archive capture.
    results.sort(key=discovery_sort_key)
    source_names=[name for name,state in providers.items() if state=="results"]
    return {
        "pattern":pattern,"match_mode":req.match_mode,"cdx_patterns":query_patterns,
        "queries_succeeded":queried,"pages_fetched":pages_fetched,"results":results,"count":len(results),
        "indexes_checked":len(collections),"pages_crawled":pages_crawled,"errors":errors,
        "providers":providers,"degraded":bool(errors),"partial":bool(errors) or page_limit_reached,
        "page_limit_reached":page_limit_reached,
        "source":" + ".join(source_names) if source_names else "No external index returned results; local tools remain available",
    }


@app.post("/api/import-urls")
async def import_discovered_urls(req: ImportURLsRequest):
    sem=asyncio.Semaphore(6)
    extract_sem=asyncio.Semaphore(4)
    async with httpx.AsyncClient(follow_redirects=False,timeout=25,
            headers={"User-Agent":UA},limits=httpx.Limits(max_connections=8,max_keepalive_connections=6)) as client:
        async def download_document(target_url, expected_filename):
            if not valid_http(target_url):
                raise ValueError("URL is not a public http(s) target")
            async with sem:
                if not await can_fetch(client,target_url,req.respect_robots):
                    raise ValueError("Disallowed by robots.txt")
                async with client.stream("GET",target_url) as response:
                    if 300 <= response.status_code < 400 and response.headers.get("location"):
                        raise ValueError("Redirect not followed; add the final URL explicitly")
                    if response.status_code!=200:
                        raise ValueError("HTTP "+str(response.status_code))
                    if not valid_http(str(response.url)):
                        raise ValueError("Unsafe redirect target")
                    length=int(response.headers.get("content-length","0") or 0)
                    if req.max_bytes and length>req.max_bytes:
                        raise ValueError("Document exceeds configured size limit")
                    chunks=[]; total=0
                    async for chunk in response.aiter_bytes():
                        total+=len(chunk)
                        if req.max_bytes and total>req.max_bytes:
                            raise ValueError("Document exceeds configured size limit")
                        chunks.append(chunk)
                    data=b"".join(chunks)
                    validate_document_signature(data,expected_filename)
                    return data

        async def import_one_core(url, archive_file_url=None, title=""):
            # Determine the document extension before fetching so the binary
            # validator knows which file signature/container structure to require.
            name=unquote(Path(urlparse(url).path).name) or "document"
            if not document_format(name):
                if archive_file_url:
                    name+=".pdf"
                else:
                    return None,{"url":url,"error":"URL has no supported document extension; use a direct .pdf/.pptx/.docx/.xlsx/etc. URL."}
            attempts=[]
            data=None
            download_url=None
            for target in import_source_targets(url,archive_file_url):
                try:
                    data=await download_document(target,name)
                    download_url=target
                    break
                except Exception as exc:
                    attempts.append({"url":target,"error":str(exc)[:200]})
            if data is None:
                if len(attempts)>1:
                    reason="Live URL failed: "+attempts[0]["error"]+"; archived copy failed: "+attempts[1]["error"]
                else:
                    reason=attempts[0]["error"] if attempts else "No import source was supplied"
                return None,{"url":url,"error":reason,"attempts":attempts}

            # Keep the original source filename, not the archive replay endpoint name.
            if not filename_matches(name,req.filename_patterns):
                return None,{"url":url,"error":"Excluded: filename did not match the selected glob(s).","excluded":True}
            try:
                async with extract_sem:
                    body,np,pages=await asyncio.to_thread(extract_document,data,name)
            except Exception as exc:
                return None,{"url":url,"error":"Verified document could not be extracted: "+str(exc)[:160]}
            if not query_matches(body,req.content_query):
                return None,{"url":url,"error":"Excluded: extracted PDF text did not match the content expression.","excluded":True}

            document_title=clean_archive_text(title,400) or name
            docid,new=store_document(download_url,name,data,document_title,body,np)
            return {
                "id":docid,"filename":name,"title":document_title,
                "url":url,"download_url":download_url,
                "retrieved_from_archive":download_url!=url,
                "format":document_format(name),"pages":np,"bytes":len(data),"new":new,
            },None

        job_id=str(uuid.uuid4())
        planned=len(req.urls[:500])+len(req.archive_sources[:500])
        import_jobs[job_id]={
            "id":job_id,"type":"import","status":"running","created_at":now(),
            "stats":{"planned":planned,"started":0,"finished":0,"stored":0,"errors":0,"excluded":0},
        }

        async def import_one(url,archive_file_url=None,title=""):
            stats=import_jobs[job_id]["stats"]
            stats["started"]+=1
            try:
                item,error=await import_one_core(url,archive_file_url,title)
                if item:
                    stats["stored"]+=1
                elif error and error.get("excluded"):
                    stats["excluded"]+=1
                elif error:
                    stats["errors"]+=1
                return item,error
            finally:
                stats["finished"]+=1

        tasks=[]
        tasks.extend(import_one(url) for url in req.urls[:500])
        tasks.extend(
            import_one(source.original_url,source.archive_file_url,source.title)
            for source in req.archive_sources[:500]
        )
        pairs=await asyncio.gather(*tasks)
    results=[item for item,error in pairs if item]
    outcomes=[error for item,error in pairs if error]
    errors=[item for item in outcomes if not item.get("excluded")]
    excluded=[item for item in outcomes if item.get("excluded")]
    import_jobs[job_id]["status"]="completed"
    import_jobs[job_id]["finished_at"]=now()
    import_jobs[job_id]["stats"]["imported"]=len(results)
    return {"job_id":job_id,"imported":len(results),"results":results,"errors":errors,"excluded":excluded}




class GrepRequest(BaseModel):
    pattern: str
    regex: bool = True
    case_sensitive: bool = False
    whole_word: bool = False
    context_lines: int = Field(default=2, ge=0, le=10)
    limit: int = Field(default=200, ge=1, le=1000)
    filename_pattern: str = "*.pdf"

class PathDiscoveryRequest(BaseModel):
    base_url: str
    paths: list[str] = Field(default_factory=list, max_length=3000)
    extensions: list[str] = Field(default_factory=lambda:["pdf"])
    concurrency: int = Field(default=12, ge=1, le=40)
    timeout: float = Field(default=8, ge=2, le=30)
    respect_robots: bool = True

class IndexedFuzzRequest(BaseModel):
    seed_urls: list[str] = Field(default_factory=list, max_length=2000)
    paths: list[str] = Field(default_factory=list, max_length=1000)
    extensions: list[str] = Field(default_factory=lambda:["pdf"])
    concurrency: int = Field(default=24, ge=1, le=40)
    timeout: float = Field(default=5, ge=2, le=30)
    max_probes: int = Field(default=800, ge=1, le=8000)
    respect_robots: bool = True

DEFAULT_PATHS = [
 "","files/","docs/","documents/","downloads/","publications/","reports/","research/",
 "resources/","manuals/","technical/","technical-reports/","archive/","archives/",
 "data/","datasets/","library/","media/","uploads/","assets/","content/",
 "annual-report.pdf","report.pdf","technical-report.pdf","manual.pdf","index.pdf",
 "documents/","files/","wp-content/uploads/","sites/default/files/"
]
DISCOVERY_TOOLS = ["ffuf","feroxbuster","dirsearch","gobuster","dirb","katana","hakrawler","gau","waybackurls","rg","ripgrep","pdftotext","libreoffice","soffice"]

@app.get("/api/tools")
def tool_inventory():
    import shutil
    return {"tools":[{"name":name,"available":shutil.which(name) is not None,"path":shutil.which(name)} for name in DISCOVERY_TOOLS],
            "native_engines":["Common Crawl CDX with Wayback fallback","bounded concurrent indexed-host fuzzer","bounded async path probe","HTML link crawler","concurrent ripgrep with page-aware memoized extraction","SQLite FTS5 Porter stemming + BM25 ranking"]}


@lru_cache(maxsize=32)
def cached_pdf_page_lines(path,mtime_ns,size):
    reader=PdfReader(path,strict=False)
    records=[]
    for page_no,page in enumerate(reader.pages,1):
        page_text=page.extract_text() or ""
        for line_no,line in enumerate(page_text.splitlines(),1):
            if line.strip():
                records.append((page_no,line_no,line[:4000]))
    return tuple(records)


def grep_one_document(row,req,rx,rg):
    import fnmatch
    if not fnmatch.fnmatch(row["filename"].lower(),req.filename_pattern.lower()): return None
    try:
        stat=Path(row["path"]).stat()
        records=cached_pdf_page_lines(row["path"],stat.st_mtime_ns,stat.st_size)
    except Exception:
        return None
    if not records: return None
    hit_indexes=[]; engine="Python regex fallback"
    if rg:
        payload="".join(f"{page}\t{line}\t{text}\n" for page,line,text in records)
        cmd=[rg,"--json","--line-number","--color","never","--text"]
        if not req.regex: cmd.append("--fixed-strings")
        if not req.case_sensitive: cmd.append("--ignore-case")
        if req.whole_word: cmd.append("--word-regexp")
        cmd.extend(["-e",req.pattern,"-"])
        try:
            proc=subprocess.run(cmd,input=payload,text=True,capture_output=True,timeout=20,check=False)
            if proc.returncode not in (0,1):
                raise RuntimeError(proc.stderr.strip() or f"rg exited {proc.returncode}")
            for raw in proc.stdout.splitlines():
                try:
                    event=json.loads(raw)
                    if event.get("type")!="match": continue
                    n=event.get("data",{}).get("line_number")
                    if n and 1<=n<=len(records): hit_indexes.append(n-1)
                except (ValueError,TypeError):
                    continue
            engine="ripgrep"
        except (OSError,subprocess.SubprocessError,RuntimeError):
            hit_indexes=[i for i,x in enumerate(records) if rx.search(x[2])]
    else:
        hit_indexes=[i for i,x in enumerate(records) if rx.search(x[2])]
    if not hit_indexes: return None

    snippets=[]; used=set(); matched_pages=set()
    for idx in hit_indexes:
        page_no,line_no,_=records[idx]
        matched_pages.add(page_no)
        lo=max(0,idx-req.context_lines); hi=min(len(records),idx+req.context_lines+1)
        # Do not let snippets cross PDF page boundaries.
        while lo<idx and records[lo][0]!=page_no: lo+=1
        while hi>idx+1 and records[hi-1][0]!=page_no: hi-=1
        if any(k in used for k in range(lo,hi)): continue
        used.update(range(lo,hi))
        snippets.append({"page":page_no,"line":line_no,
            "text":"\n".join(f"{records[k][1]}: {records[k][2][:500]}" for k in range(lo,hi))})
        if len(snippets)>=12: break
    return {
        "id":row["id"],"filename":row["filename"],"title":row["title"],"url":row["url"],
        "hit_count":len(hit_indexes),"pages":sorted(matched_pages),"snippets":snippets,"engine":engine,
    }


@app.post("/api/grep")
async def intelligent_grep(req: GrepRequest):
    if not req.pattern.strip(): raise HTTPException(400,"Enter a grep expression.")
    try:
        flags=0 if req.case_sensitive else re.IGNORECASE
        expression=req.pattern if req.regex else re.escape(req.pattern)
        if req.whole_word: expression=r"\b(?:"+expression+r")\b"
        rx=re.compile(expression,flags)
    except re.error as e: raise HTTPException(400,"Invalid regular expression: "+str(e))
    c=connect()
    rows=[dict(x) for x in c.execute("SELECT id,filename,title,url,path FROM documents ORDER BY discovered_at DESC").fetchall()]
    c.close()
    rg=shutil.which("rg")
    sem=asyncio.Semaphore(4)
    async def search_one(row):
        async with sem:
            return await asyncio.to_thread(grep_one_document,row,req,rx,rg)
    searched=await asyncio.gather(*(search_one(row) for row in rows))
    results=[x for x in searched if x]
    # Deterministic relevance order: more hits first, then earlier hit pages, then title.
    results.sort(key=lambda x:(-x["hit_count"],x["pages"][0] if x["pages"] else 10**9,x["filename"].casefold()))
    results=results[:req.limit]
    return {"count":len(results),"results":results,
            "engine":"concurrent ripgrep with memoized page-aware PDF extraction" if rg else "concurrent Python regex with memoized page-aware PDF extraction"}

@app.post("/api/discover-paths")
async def discover_paths(req: PathDiscoveryRequest):
    base=req.base_url.strip().rstrip("/")+"/"
    if not valid_http(base): raise HTTPException(400,"Base URL must be a public http(s) address.")
    host=urlparse(base).hostname
    paths=list(dict.fromkeys((req.paths or DEFAULT_PATHS)[:3000]))
    extensions=[x.lower().lstrip(".") for x in req.extensions if re.fullmatch(r"[A-Za-z0-9]{1,8}",x.lstrip("."))]
    candidates=[]
    for p in paths:
        p=p.strip().lstrip("/")
        if not p: continue
        candidates.append(p)
        if not Path(p).suffix:
            candidates.extend(p+"."+ext for ext in extensions)
    candidates=list(dict.fromkeys(candidates))[:5000]
    found=[]; errors=[]; checked=0
    host_sem=asyncio.Semaphore(min(req.concurrency,4))
    request_gate=asyncio.Lock()
    last_request=0.0
    async with httpx.AsyncClient(follow_redirects=False,timeout=req.timeout,
            headers={"User-Agent":UA},limits=httpx.Limits(max_connections=req.concurrency,max_keepalive_connections=req.concurrency)) as client:
        async def probe(path):
            nonlocal checked,last_request
            url=urljoin(base,path)
            if not valid_http(url) or urlparse(url).hostname!=host: return
            if req.respect_robots and not await can_fetch(client,url,True): return
            async with host_sem:
                # Pace requests to the one target host even when several workers are active.
                async with request_gate:
                    wait=max(0.0,0.20-(time.monotonic()-last_request))
                    if wait: await asyncio.sleep(wait)
                    last_request=time.monotonic()
                try:
                    r=await client.head(url)
                    if r.status_code in (405,501):
                        async with client.stream("GET",url,headers={"Range":"bytes=0-0"}) as streamed:
                            status=streamed.status_code; headers=streamed.headers
                    else:
                        status=r.status_code; headers=r.headers
                    checked+=1
                    if status in (200,206,301,302,307,308,401,403):
                        found.append({"url":url,"status":status,"content_type":headers.get("content-type",""),
                                      "bytes":headers.get("content-length"),"interesting":status in (401,403)})
                except Exception as exc:
                    errors.append({"path":path,"error":str(exc)[:120]})
        queue=asyncio.Queue()
        for path in candidates: queue.put_nowait(path)
        async def worker():
            while True:
                try: path=queue.get_nowait()
                except asyncio.QueueEmpty: return
                try: await probe(path)
                finally: queue.task_done()
        await asyncio.gather(*(worker() for _ in range(min(req.concurrency,len(candidates)))))
    found.sort(key=lambda x:(
        0 if x["url"].lower().endswith(".pdf") or "pdf" in x["content_type"].lower() else 1,
        0 if x["status"] in (200,206) else 1,
        x["url"].casefold(),
    ))
    return {"base_url":base,"tested":checked,"planned":len(candidates),"count":len(found),"results":found,"errors":errors[:30],
            "engine":"bounded fixed-worker same-host path probe","available_external_tools":tool_inventory()["tools"]}


def response_fingerprint(status, headers):
    """Comparable metadata from a HEAD response."""
    h={str(k).lower():str(v).strip() for k,v in dict(headers or {}).items()}
    return {
        "status":int(status),
        "mime":h.get("content-type","").split(";",1)[0].strip().lower(),
        "length":h.get("content-length",""),
        "etag":h.get("etag","").strip(),
        "last_modified":h.get("last-modified","").strip(),
    }


def is_soft_404_response(status, headers, baseline):
    """Detect hosts that return the same HTTP-200 HTML page for unknown paths."""
    if not baseline:
        return False
    current=response_fingerprint(status,headers)
    if current["status"] not in (200,206) or baseline.get("status") not in (200,206):
        return False
    if current["mime"] not in ("text/html","application/xhtml+xml"):
        return False
    if current["mime"]!=baseline.get("mime"):
        return False
    if current["etag"] and baseline.get("etag"):
        return current["etag"]==baseline["etag"]
    if current["length"] and baseline.get("length"):
        return current["length"]==baseline["length"]
    if current["last_modified"] and baseline.get("last_modified"):
        return current["last_modified"]==baseline["last_modified"]
    return False


def build_index_fuzz_plan(req: IndexedFuzzRequest):
    """Validate seeds and create a bounded, evenly distributed probe plan."""
    if not req.seed_urls:
        raise HTTPException(400,"Supply URL candidates from an index search first.")
    origins={}
    invalid=0
    for seed in req.seed_urls:
        seed=seed.strip()
        if not valid_http(seed):
            invalid+=1
            continue
        parsed=urlparse(seed)
        origin=f"{parsed.scheme}://{parsed.netloc}"
        origins.setdefault(origin,[]).append(seed)
    if not origins:
        raise HTTPException(400,"No valid public HTTP(S) index URLs were supplied.")

    word_paths=req.paths or DEFAULT_PATHS
    extensions=[x.lower().lstrip(".") for x in req.extensions
                if re.fullmatch(r"[A-Za-z0-9]{1,8}",x.lstrip("."))]
    clean_paths=[]
    for raw in word_paths:
        p=raw.strip().replace("\\","/").lstrip("/")
        if not p or "://" in p or any(part==".." for part in p.split("/")) or p.startswith("?"):
            continue
        clean_paths.append(p)
        # Directory entries should be probed as directories, not turned into
        # meaningless paths such as "documents/.pdf".
        if not p.endswith("/") and not Path(p).suffix:
            clean_paths.extend(p+"."+ext for ext in extensions)
    clean_paths=list(dict.fromkeys(clean_paths))[:1500]

    probe_jobs=[]; seen=set()
    origin_items=list(origins.items())
    base_budget,extra_budget=divmod(req.max_probes,len(origin_items))
    for origin_index,(origin,seeds) in enumerate(origin_items):
        host_budget=base_budget+(1 if origin_index<extra_budget else 0)
        if host_budget<1:
            continue
        host_added=0
        # Test the exact archived/indexed candidates first; they are stronger
        # evidence than synthetic wordlist guesses and were previously omitted.
        for seed in seeds:
            if seed not in seen and host_added<host_budget:
                seen.add(seed)
                probe_jobs.append((seed,origin,seed))
                host_added+=1
        directories={"/"}
        for seed in seeds:
            parts=[x for x in urlparse(seed).path.split("/") if x]
            if parts and "." in parts[-1]:
                parts=parts[:-1]
            prefix=[]
            for part in parts:
                prefix.append(part)
                directories.add("/"+"/".join(prefix)+"/")
        ordered_dirs=sorted(directories,key=lambda x:(0 if x!="/" else 1,x.count("/"),x))
        for directory in ordered_dirs:
            for path in clean_paths:
                url=origin+directory+path
                if url not in seen:
                    seen.add(url)
                    probe_jobs.append((url,origin,seeds[0]))
                    host_added+=1
                if host_added>=host_budget:
                    break
            if host_added>=host_budget:
                break

    return {
        "origins":origins,
        "invalid_seeds":invalid,
        "probe_jobs":probe_jobs,
    }


async def run_indexed_fuzz_job(job_id: str, req: IndexedFuzzRequest, plan: dict):
    """Execute a fuzzer job while publishing progress and partial results."""
    job=fuzz_jobs[job_id]
    origins=plan["origins"]
    probe_jobs=plan["probe_jobs"]
    sem=asyncio.Semaphore(req.concurrency)
    origin_semaphores={origin:asyncio.Semaphore(2) for origin in origins}
    origin_gates={origin:asyncio.Lock() for origin in origins}
    origin_last_request={origin:0.0 for origin in origins}
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=req.timeout,
        headers={"User-Agent":UA},
        limits=httpx.Limits(max_connections=req.concurrency,max_keepalive_connections=req.concurrency),
    ) as client:
        async def get_baseline(origin):
            marker=urljoin(origin+"/","/.cosmic-pdf-lab-missing-"+job_id+".pdf")
            try:
                if not await can_fetch(client,marker,req.respect_robots):
                    return None
                response=await client.head(marker)
                return response_fingerprint(response.status_code,response.headers)
            except Exception:
                return None

        baseline_pairs=await asyncio.gather(*(get_baseline(origin) for origin in origins))
        baselines=dict(zip(origins.keys(),baseline_pairs))

        async def probe(item):
            url,origin,seed=item
            stats=job["stats"]
            async with sem,origin_semaphores[origin]:
                try:
                    if not valid_http(url) or urlparse(url).netloc.lower()!=urlparse(origin).netloc.lower():
                        stats["skipped"]+=1
                        return
                    if not await can_fetch(client,url,req.respect_robots):
                        stats["robots_blocked"]+=1
                        stats["skipped"]+=1
                        return
                    async with origin_gates[origin]:
                        wait=max(0.0,0.30-(time.monotonic()-origin_last_request[origin]))
                        if wait:
                            await asyncio.sleep(wait)
                        origin_last_request[origin]=time.monotonic()
                    response=await client.head(url)
                    status=response.status_code
                    headers=response.headers
                    candidate_document=is_document_candidate(url,headers.get("content-type",""))
                    ext=document_format(url)
                    document_verified=False
                    pdf_verified=False
                    # Metadata/extension are hints only. Verify signatures using a
                    # bounded ranged read before declaring a candidate importable.
                    if status in (405,501) or (status in (200,206) and candidate_document):
                        async with client.stream("GET",url,headers={"Range":"bytes=0-1023"}) as streamed:
                            status=streamed.status_code
                            headers=streamed.headers
                            prefix=bytearray()
                            if status in (200,206):
                                async for chunk in streamed.aiter_bytes():
                                    remaining=1024-len(prefix)
                                    if remaining>0:
                                        prefix.extend(chunk[:remaining])
                                    if len(prefix)>=1024:
                                        break
                            probe_name=Path(urlparse(url).path).name or ("document."+ext if ext else "document")
                            document_verified=document_signature_probe(bytes(prefix),probe_name,headers.get("content-type",""))
                            pdf_verified=(ext=="pdf" and is_pdf_signature(bytes(prefix)))
                    stats["tested"]+=1
                    if is_soft_404_response(status,headers,baselines.get(origin)):
                        stats["soft_404s"]+=1
                        return
                    if status in (200,206,301,302,307,308,401,403):
                        result={
                            "url":url,
                            "status":status,
                            "content_type":headers.get("content-type",""),
                            "bytes":headers.get("content-length"),
                            "interesting":status in (401,403),
                            "seed_url":seed,
                            "host":urlparse(origin).hostname,
                            "is_pdf":pdf_verified,
                            "is_document":document_verified,
                            "document_format":ext or "unknown",
                            "pdf_verified":pdf_verified,
                        }
                        job["results"].append(result)
                        stats["found"]=len(job["results"])
                        stats["pdfs"]=sum(1 for result in job["results"] if result.get("is_pdf"))
                        stats["documents"]=sum(1 for result in job["results"] if result.get("is_document"))
                except Exception as exc:
                    stats["errors"]+=1
                    if len(job["errors"])<100:
                        job["errors"].append({"url":url,"error":str(exc)[:160]})
                finally:
                    stats["finished"]+=1

        queue=asyncio.Queue()
        for item in probe_jobs:
            queue.put_nowait(item)

        async def worker():
            while True:
                try:
                    item=queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    await probe(item)
                finally:
                    queue.task_done()

        await asyncio.gather(*(worker() for _ in range(min(req.concurrency,len(probe_jobs)))))

    job["results"].sort(key=lambda x:(
        0 if x["is_pdf"] else 1,
        0 if x["status"] in (200,206) else 1,
        0 if x["interesting"] else 1,
        x["url"].casefold(),
    ))
    stats=job["stats"]
    stats["hosts_checked"]=len(origins)
    stats["seeds_used"]=sum(len(v) for v in origins.values())
    stats["invalid_seeds"]=plan["invalid_seeds"]
    job["status"]="completed"
    job["finished_at"]=now()


@app.post("/api/fuzz-indexes")
async def fuzz_indexed_hosts(req: IndexedFuzzRequest):
    """Queue indexed-host fuzzing and return an ID immediately for progress polling."""
    plan=build_index_fuzz_plan(req)
    job_id=str(uuid.uuid4())
    planned=len(plan["probe_jobs"])
    fuzz_jobs[job_id]={
        "id":job_id,
        "status":"queued",
        "created_at":now(),
        "stats":{
            "planned":planned,
            "started":0,
            "finished":0,
            "tested":0,
            "found":0,
            "pdfs":0,
            "documents":0,
            "soft_404s":0,
            "errors":0,
            "skipped":0,
            "robots_blocked":0,
            "hosts_checked":len(plan["origins"]),
            "seeds_used":sum(len(v) for v in plan["origins"].values()),
            "invalid_seeds":plan["invalid_seeds"],
        },
        "results":[],
        "errors":[],
    }

    async def run():
        fuzz_jobs[job_id]["status"]="running"
        fuzz_jobs[job_id]["started_at"]=now()
        try:
            await run_indexed_fuzz_job(job_id,req,plan)
        except Exception as exc:
            fuzz_jobs[job_id]["status"]="failed"
            fuzz_jobs[job_id]["error"]=str(exc)[:240]
            fuzz_jobs[job_id]["finished_at"]=now()

    fuzz_job_tasks[job_id]=asyncio.create_task(run())
    return {
        "id":job_id,
        "status":fuzz_jobs[job_id]["status"],
        "stats":fuzz_jobs[job_id]["stats"],
    }


@app.get("/api/fuzz-indexes/{job_id}")
def get_index_fuzz_job(job_id: str):
    """Return live fuzzer progress and any paths discovered so far."""
    if job_id not in fuzz_jobs:
        raise HTTPException(404,"Unknown fuzzer job")
    return fuzz_jobs[job_id]



@app.get("/api/health")
def health():
    c=connect(); count=c.execute("SELECT COUNT(*) n FROM documents").fetchone()["n"]; c.close()
    return {"ok":True,"service":"Cosmic PDF Lab Worker","version":"1.0.0","documents":count,"data_dir":str(ROOT)}

@app.post("/api/jobs")
async def create_job(cfg:CrawlRequest):
    jid=str(uuid.uuid4())
    jobs[jid]={"id":jid,"status":"queued","created_at":now(),"config":cfg.model_dump(),"stats":{"pages_visited":0,"urls_visited":0,"pdfs_found":0,"matches":0,"robots_blocked":0,"request_errors":0,"parse_errors":0,"queue_remaining":0},"results":[],"log":[]}
    async def run():
        try: await crawl(jid,cfg)
        except Exception as e: jobs[jid]["status"]="failed"; jobs[jid]["error"]=str(e); jobs[jid]["finished_at"]=now()
    job_tasks[jid]=asyncio.create_task(run())
    return jobs[jid]

@app.get("/api/jobs/{jobid}")
def get_job(jobid:str):
    if jobid not in jobs: raise HTTPException(404,"Unknown job")
    return jobs[jobid]

@app.get("/api/documents")
def list_documents(q:str="",limit:int=200,format:str=""):
    c=connect()
    capped=min(max(limit,1),500)
    if q.strip():
        try:
            rows=c.execute(
                "SELECT d.id,d.filename,d.title,d.url,d.bytes,d.pages,d.sha256,d.discovered_at "
                "FROM document_fts_linguistic f JOIN documents d ON d.id=f.id "
                "WHERE document_fts_linguistic MATCH ? ORDER BY rank LIMIT ?",
                (q,capped*3)
            ).fetchall()
        except sqlite3.OperationalError:
            rows=c.execute(
                "SELECT id,filename,title,url,bytes,pages,sha256,discovered_at FROM documents "
                "WHERE filename LIKE ? OR title LIKE ? OR text LIKE ? ORDER BY discovered_at DESC LIMIT ?",
                (f"%{q}%",f"%{q}%",f"%{q}%",capped*3)
            ).fetchall()
    else:
        rows=c.execute(
            "SELECT id,filename,title,url,bytes,pages,sha256,discovered_at FROM documents ORDER BY discovered_at DESC LIMIT ?",
            (capped*3,)
        ).fetchall()
    c.close()
    output=[]
    for row in rows:
        item=dict(row)
        item["format"]=Path(item["filename"]).suffix.lower().lstrip(".") or "unknown"
        item["mime"]=mimetypes.guess_type(item["filename"])[0] or "application/octet-stream"
        item["indexed"]=True
        if format and item["format"]!=format.lower().lstrip("."):
            continue
        output.append(item)
        if len(output)>=capped:break
    return output


def document_row(docid):
    c=connect()
    row=c.execute("SELECT id,path,filename,title,url,bytes,pages,sha256,discovered_at,text FROM documents WHERE id=?",(docid,)).fetchone()
    c.close()
    if not row or not Path(row["path"]).is_file():
        raise HTTPException(404,"Document not found")
    return dict(row)


@app.get("/api/documents/{docid}/content")
def document_content(docid:str):
    row=document_row(docid)
    ext=Path(row["filename"]).suffix.lower().lstrip(".")
    return {
        "id":row["id"],"filename":row["filename"],"title":row["title"],
        "url":row["url"],"bytes":row["bytes"],"pages":row["pages"],
        "sha256":row["sha256"],"discovered_at":row["discovered_at"],
        "format":ext,"mime":mimetypes.guess_type(row["filename"])[0] or "application/octet-stream",
        "text":(row["text"] or "")[:2_000_000],
        "truncated":len(row["text"] or "")>2_000_000,
    }


@app.get("/api/documents/{docid}/download")
def download_document(docid:str):
    row=document_row(docid)
    mime=mimetypes.guess_type(row["filename"])[0] or "application/octet-stream"
    return FileResponse(row["path"],media_type=mime,filename=row["filename"])


@app.get("/api/documents/{docid}/view")
def view_document(docid:str):
    row=document_row(docid)
    mime=mimetypes.guess_type(row["filename"])[0] or "application/octet-stream"
    return FileResponse(
        row["path"],media_type=mime,
        headers={"Content-Disposition":"inline"}
    )


@app.get("/api/worker/status")
def worker_status():
    c=connect()
    count=int(c.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
    storage_bytes=int(c.execute("SELECT COALESCE(SUM(bytes),0) FROM documents").fetchone()[0])
    rows=c.execute("SELECT filename,COUNT(*) AS n FROM documents GROUP BY filename").fetchall()
    c.close()
    formats={}
    for row in rows:
        ext=Path(row["filename"]).suffix.lower().lstrip(".") or "unknown"
        formats[ext]=formats.get(ext,0)+int(row["n"])
    combined=[]
    for kind,source in (("crawl",jobs),("fuzzer",fuzz_jobs),("import",import_jobs)):
        for item in source.values():
            combined.append({
                "id":item.get("id"),"type":kind,"status":item.get("status"),
                "created_at":item.get("created_at"),"started_at":item.get("started_at"),
                "finished_at":item.get("finished_at"),"stats":item.get("stats",{}),
                "config":item.get("config",{}) if kind=="crawl" else {},
                "error":item.get("error"),
            })
    combined.sort(key=lambda x:x.get("created_at",""),reverse=True)
    active=[x for x in combined if x.get("status") in ("queued","running")]
    return {
        "ok":True,"service":"Cosmic PDF Lab Worker",
        "documents":count,"storage_bytes":storage_bytes,
        "formats":formats,"active_jobs":active[:10],"recent_jobs":combined[:8],
        "data_dir":str(ROOT),
        "tools":{"libreoffice":bool(shutil.which("libreoffice") or shutil.which("soffice")),
                 "ripgrep":bool(shutil.which("rg"))},
    }


@app.post("/api/search")
def search_docs(req:SearchRequest):
    c=connect()
    query=req.query.strip()
    try:
        if not query:
            rows=c.execute("""SELECT id,filename,title,url,bytes,pages,discovered_at
                              FROM documents ORDER BY discovered_at DESC LIMIT ?""",(req.limit,)).fetchall()
            out=[{**dict(row),"score":0.0,"snippets":[]} for row in rows]
        else:
            rows=c.execute("""
                SELECT d.id,d.filename,d.title,d.url,d.bytes,d.pages,d.discovered_at,
                       bm25(document_fts_linguistic,0.0,5.0,2.0,0.25,1.0) AS rank,
                       snippet(document_fts_linguistic,4,'[',']',' … ',18) AS excerpt
                FROM document_fts_linguistic
                JOIN documents d ON d.id=document_fts_linguistic.id
                WHERE document_fts_linguistic MATCH ?
                ORDER BY rank ASC, d.filename COLLATE NOCASE ASC
                LIMIT ?
            """,(query,req.limit)).fetchall()
            out=[{**{k:row[k] for k in ("id","filename","title","url","bytes","pages","discovered_at")},
                  "score":float(-row["rank"]),"snippets":[row["excerpt"]] if row["excerpt"] else []} for row in rows]
    except sqlite3.OperationalError:
        # Retain tolerant literal/boolean matching if a user enters non-FTS syntax.
        c.close()
        c=connect()
        rows=c.execute("SELECT id,filename,title,url,bytes,pages,discovered_at,text FROM documents ORDER BY discovered_at DESC").fetchall()
        tokens=[t for t in re.findall(r"[\w'-]+",query.casefold()) if t not in {"and","or","not"}]
        fallback=[]
        for row in rows:
            body=(row["text"] or "").casefold()
            if query_matches(body,query):
                score=sum(body.count(t) for t in tokens)
                fallback.append((score,row))
        fallback.sort(key=lambda item:(-item[0],item[1]["filename"].casefold()))
        out=[{**{k:row[k] for k in ("id","filename","title","url","bytes","pages","discovered_at")},
              "score":float(score),"snippets":[line[:500] for line in (row["text"] or "").splitlines() if query_matches(line,query)][:8]}
             for score,row in fallback[:req.limit]]
    c.close()
    return out

