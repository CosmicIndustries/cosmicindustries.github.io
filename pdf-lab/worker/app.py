#!/usr/bin/env python3
"""Local-first, bounded PDF crawler and searchable document catalog."""
from __future__ import annotations
import asyncio, hashlib, json, os, re, sqlite3, time, uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag, unquote
from urllib.robotparser import RobotFileParser

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
robots_cache: dict[str, RobotFileParser] = {}

def connect():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS documents(
      id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, url TEXT NOT NULL,
      filename TEXT NOT NULL, title TEXT, path TEXT NOT NULL, bytes INTEGER NOT NULL,
      pages INTEGER, text TEXT NOT NULL, discovered_at TEXT NOT NULL)""")
    c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(id UNINDEXED, filename, title, url, body)")
    c.commit(); return c

def now(): return datetime.now(timezone.utc).isoformat()

class CrawlRequest(BaseModel):
    start_url: str
    filename_patterns: list[str] = Field(default_factory=lambda:["*.pdf"])
    content_query: str = ""
    depth: int = Field(default=3, ge=0, le=12)
    max_pages: int = Field(default=500, ge=1, le=5000)
    max_files: int = Field(default=250, ge=1, le=2000)
    max_bytes: int = Field(default=40_000_000, ge=1024, le=250_000_000)
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
    # Refuse localhost/private literal IP targets to reduce accidental SSRF.
    import ipaddress, socket
    try:
        ip=ipaddress.ip_address(p.hostname)
        if not ip.is_global: return False
    except ValueError:
        try:
            for info in socket.getaddrinfo(p.hostname, None):
                if not ipaddress.ip_address(info[4][0]).is_global: return False
        except socket.gaierror: return False
    return True

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
        rp=RobotFileParser(); rp.set_url(origin+"/robots.txt")
        try:
            r=await client.get(origin+"/robots.txt", timeout=8, headers={"User-Agent":UA})
            if r.status_code==200: rp.parse(r.text.splitlines())
            elif r.status_code in (401,403): rp.parse(["User-agent: *","Disallow: /"])
            else: rp.parse(["User-agent: *","Allow: /"])
        except Exception: rp.parse(["User-agent: *","Disallow: /"])
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

def extract_pdf(data):
    import io
    reader=PdfReader(io.BytesIO(data), strict=False)
    pages=[]; texts=[]
    for i,page in enumerate(reader.pages):
        t=page.extract_text() or ""; texts.append(t)
        for line_no,line in enumerate(t.splitlines(),1):
            if line.strip(): pages.append({"page":i+1,"line":line_no,"text":line[:500]})
    return "\n".join(texts),len(reader.pages),pages

def store_pdf(url, filename, data, title, text, pages):
    digest=hashlib.sha256(data).hexdigest(); path=FILES/(digest+".pdf")
    if not path.exists(): path.write_bytes(data)
    docid=str(uuid.uuid4())
    c=connect()
    existing=c.execute("SELECT id FROM documents WHERE sha256=?",(digest,)).fetchone()
    if existing: c.close(); return existing["id"],False
    c.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)",
      (docid,digest,url,filename,title,str(path),len(data),pages,text,now()))
    c.execute("INSERT INTO document_fts VALUES(?,?,?,?,?)",(docid,filename,title or "",url,text))
    c.commit(); c.close()
    return docid,True

async def crawl(jobid, cfg: CrawlRequest):
    j=jobs[jobid]; j["status"]="running"; j["started_at"]=now()
    def log(msg): j["log"].append(msg); j["log"]=j["log"][-200:]
    start=cfg.start_url.strip()
    if not valid_http(start): raise ValueError("Start URL must be a public http(s) URL; private, localhost and credential-bearing targets are refused.")
    root=urlparse(start).hostname
    queue=deque([(start,0)]); visited=set(); found=set(); stored=0; pages_seen=0
    limits=httpx.Limits(max_connections=8,max_keepalive_connections=4)
    async with httpx.AsyncClient(follow_redirects=False,limits=limits,headers={"User-Agent":UA}) as client:
      while queue and pages_seen<cfg.max_pages and len(found)<cfg.max_files:
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
                if length>cfg.max_bytes: continue
                if "pdf" in ctype or urlparse(url).path.lower().endswith(".pdf"):
                    chunks=[]; total=0
                    async for chunk in response.aiter_bytes():
                        total+=len(chunk)
                        if total>cfg.max_bytes: raise ValueError("file exceeds max_bytes")
                        chunks.append(chunk)
                    data=b"".join(chunks); name=unquote(Path(urlparse(url).path).name) or "document.pdf"
                    if not name.lower().endswith(".pdf"): name+=".pdf"
                    if not filename_matches(name,cfg.filename_patterns): continue
                    found.add(url); j["stats"]["pdfs_found"]+=1
                    try:
                        body,np,pagematches=extract_pdf(data)
                    except Exception as e:
                        j["stats"]["parse_errors"]+=1; log(f"PDF parse failed: {name}: {e}"); continue
                    if not query_matches(body,cfg.content_query): continue
                    if cfg.download_matches:
                        docid,new=store_pdf(url,name,data,name,body,np)
                        stored+=int(new)
                    else:
                        docid,new=None,False
                    j["stats"]["matches"]+=1
                    j["results"].append({"id":docid,"filename":name,"url":url,"pages":np,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"new":new,"snippets":[x for x in pagematches if query_matches(x["text"],cfg.content_query)][:8]})
                    log((("Stored " if new else "Already catalogued ") if cfg.download_matches else "Matched (download disabled) ")+name)
                elif "text/html" in ctype and level<cfg.depth:
                    data=await response.aread()
                    if len(data)>cfg.max_bytes: continue
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
    match_mode: str = Field(default="glob", pattern="^(glob|regex)$")
    max_results: int = Field(default=200, ge=1, le=2000)
    indexes: int = Field(default=2, ge=1, le=5)
    recursive: bool = False
    recursive_depth: int = Field(default=2, ge=0, le=3)
    max_pages: int = Field(default=30, ge=1, le=100)
    respect_robots: bool = True

class ImportURLsRequest(BaseModel):
    urls: list[str] = Field(default_factory=list, max_length=500)
    filename_patterns: list[str] = Field(default_factory=lambda:["*.pdf"])
    content_query: str = ""
    max_bytes: int = Field(default=40_000_000, ge=1024, le=250_000_000)
    respect_robots: bool = True

def normalize_glob(pattern):
    return pattern.strip().replace(r"\*", "*").replace(r"\?", "?").lower()

def glob_to_regex(pattern):
    """Translate URL glob: * stays within a path segment; ** crosses separators."""
    p=normalize_glob(pattern); out=[]; i=0
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
    return re.compile("^"+"".join(out)+"$",re.I)

def commoncrawl_query_pattern(pattern):
    p=pattern.lower()
    m=re.search(r"\.([a-z]{2,})(?:[./*]|$)",p)
    if m: return "*."+m.group(1)+"/*"
    host=re.search(r"https?://([^/]+)",p)
    if host and "*" not in host.group(1): return host.group(1)+"/*"
    raise ValueError("Global discovery needs a recognizable suffix (.edu/.gov/.org) or literal host.")

def url_matcher(pattern, mode):
    if mode=="regex":
        try: return re.compile(pattern,re.I)
        except re.error as e: raise HTTPException(400,"Invalid URL regular expression: "+str(e))
    return glob_to_regex(pattern)

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

@app.post("/api/discover")
async def discover_wildcard(req: WildcardDiscoveryRequest):
    pattern=req.url_pattern.strip()
    matcher=url_matcher(pattern,req.match_mode)
    cdx_pattern=commoncrawl_query_pattern(pattern)
    async with httpx.AsyncClient(timeout=30,headers={"User-Agent":UA}) as client:
        info=await client.get("https://index.commoncrawl.org/collinfo.json")
        info.raise_for_status()
        collections=info.json()[:req.indexes]
        results=[]; seen=set(); errors=[]
        for collection in collections:
            endpoint=collection.get("cdx-api")
            if not endpoint: continue
            try:
                r=await client.get(endpoint,params={"url":cdx_pattern,"output":"json","filter":"status:200","collapse":"urlkey","limit":str(min(req.max_results*10,10000))})
                if r.status_code==404: continue
                r.raise_for_status()
                for line in r.text.splitlines():
                    try: item=json.loads(line)
                    except Exception: continue
                    url=item.get("url","")
                    if not url or url in seen or not re.match(r"^https?://",url,re.I): continue
                    if not matcher.search(url): continue
                    seen.add(url)
                    results.append({"url":url,"timestamp":item.get("timestamp"),"mime":item.get("mime"),"status":item.get("status"),"collection":collection.get("id")})
                    if len(results)>=req.max_results: break
                if len(results)>=req.max_results: break
            except Exception as e: errors.append(collection.get("id","index")+": "+str(e)[:180])
        pages_crawled=0
        if req.recursive and req.recursive_depth>0 and len(results)<req.max_results:
            pages_crawled=await recursive_url_discovery(client,[x["url"] for x in results],matcher,req,results,seen,errors)
    return {"pattern":pattern,"match_mode":req.match_mode,"cdx_pattern":cdx_pattern,"results":results,"count":len(results),"indexes_checked":len(collections),"pages_crawled":pages_crawled,"errors":errors,"source":"Common Crawl URL index + bounded live recursive crawl" if req.recursive else "Common Crawl URL index; captures may be historical"}

@app.post("/api/import-urls")
async def import_discovered_urls(req: ImportURLsRequest):
    results=[]; errors=[]
    async with httpx.AsyncClient(follow_redirects=False,timeout=25,headers={"User-Agent":UA}) as client:
        for url in req.urls[:500]:
            try:
                if not valid_http(url): raise ValueError("URL is not a public http(s) target")
                if not await can_fetch(client,url,req.respect_robots): raise ValueError("Disallowed by robots.txt")
                async with client.stream("GET",url) as response:
                    if 300 <= response.status_code < 400 and response.headers.get("location"):
                        raise ValueError("Redirect not followed; add the final URL explicitly")
                    if response.status_code!=200: raise ValueError("HTTP "+str(response.status_code))
                    if not valid_http(str(response.url)): raise ValueError("Unsafe redirect target")
                    ctype=response.headers.get("content-type","").lower()
                    if "pdf" not in ctype and not urlparse(url).path.lower().endswith(".pdf"): raise ValueError("Not identified as a PDF")
                    length=int(response.headers.get("content-length","0") or 0)
                    if length>req.max_bytes: raise ValueError("PDF exceeds size limit")
                    chunks=[]; total=0
                    async for chunk in response.aiter_bytes():
                        total+=len(chunk)
                        if total>req.max_bytes: raise ValueError("PDF exceeds size limit")
                        chunks.append(chunk)
                    data=b"".join(chunks)
                name=unquote(Path(urlparse(url).path).name) or "document.pdf"
                if not name.lower().endswith(".pdf"): name+=".pdf"
                if not filename_matches(name,req.filename_patterns): continue
                body,np,pages=extract_pdf(data)
                if not query_matches(body,req.content_query): continue
                docid,new=store_pdf(url,name,data,name,body,np)
                results.append({"id":docid,"filename":name,"url":url,"pages":np,"bytes":len(data),"new":new})
            except Exception as e: errors.append({"url":url,"error":str(e)[:200]})
    return {"imported":len(results),"results":results,"errors":errors}


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

DEFAULT_PATHS = [
 "","files/","docs/","documents/","downloads/","publications/","reports/","research/",
 "resources/","manuals/","technical/","technical-reports/","archive/","archives/",
 "data/","datasets/","library/","media/","uploads/","assets/","content/",
 "annual-report.pdf","report.pdf","technical-report.pdf","manual.pdf","index.pdf",
 "documents/","files/","wp-content/uploads/","sites/default/files/"
]
DISCOVERY_TOOLS = ["ffuf","feroxbuster","dirsearch","gobuster","dirb","katana","hakrawler","gau","waybackurls","rg","ripgrep","pdftotext"]

@app.get("/api/tools")
def tool_inventory():
    import shutil
    return {"tools":[{"name":name,"available":shutil.which(name) is not None,"path":shutil.which(name)} for name in DISCOVERY_TOOLS],
            "native_engines":["Common Crawl CDX","bounded async path probe","HTML link crawler","PDF text regex grep","SQLite FTS5"]}

@app.post("/api/grep")
def intelligent_grep(req: GrepRequest):
    import fnmatch
    if not req.pattern.strip(): raise HTTPException(400,"Enter a grep expression.")
    try:
        flags=0 if req.case_sensitive else re.IGNORECASE
        expression=req.pattern if req.regex else re.escape(req.pattern)
        if req.whole_word: expression=r"\b(?:"+expression+r")\b"
        rx=re.compile(expression,flags)
    except re.error as e: raise HTTPException(400,"Invalid regular expression: "+str(e))
    c=connect()
    rows=c.execute("SELECT id,filename,title,url,text FROM documents ORDER BY discovered_at DESC").fetchall()
    c.close(); results=[]
    for row in rows:
        if not fnmatch.fnmatch(row["filename"].lower(),req.filename_pattern.lower()): continue
        lines=(row["text"] or "").splitlines()
        hits=[i for i,line in enumerate(lines) if rx.search(line)]
        if not hits: continue
        snippets=[]; used=set()
        for i in hits:
            lo=max(0,i-req.context_lines); hi=min(len(lines),i+req.context_lines+1)
            if any(k in used for k in range(lo,hi)): continue
            used.update(range(lo,hi))
            snippets.append({"line":i+1,"text":"\\n".join(f"{k+1}: {lines[k][:500]}" for k in range(lo,hi))})
            if len(snippets)>=12: break
        results.append({"id":row["id"],"filename":row["filename"],"title":row["title"],"url":row["url"],"hit_count":len(hits),"snippets":snippets})
        if len(results)>=req.limit: break
    return {"count":len(results),"results":results,"engine":"Python regex grep over extracted PDF text"}

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
            candidates.extend(p+("."+ext) for ext in extensions)
    candidates=list(dict.fromkeys(candidates))[:5000]
    sem=asyncio.Semaphore(req.concurrency); found=[]; errors=[]
    async with httpx.AsyncClient(follow_redirects=False,timeout=req.timeout,headers={"User-Agent":UA}) as client:
        async def probe(path):
            async with sem:
                url=urljoin(base,path)
                if not valid_http(url) or urlparse(url).hostname!=host: return
                if req.respect_robots and not await can_fetch(client,url,True): return
                try:
                    r=await client.head(url)
                    if r.status_code in (405,501):
                        async with client.stream("GET",url,headers={"Range":"bytes=0-0"}) as streamed:
                            status=streamed.status_code; headers=streamed.headers
                    else:
                        status=r.status_code; headers=r.headers
                    if status in (200,206,301,302,307,308,401,403):
                        found.append({"url":url,"status":status,"content_type":headers.get("content-type",""),"bytes":headers.get("content-length"),"interesting":status in (401,403)})
                except Exception as e: errors.append({"path":path,"error":str(e)[:120]})
        await asyncio.gather(*(probe(p) for p in candidates))
    found.sort(key=lambda x:(0 if x["url"].lower().endswith(".pdf") else 1,x["status"],x["url"]))
    return {"base_url":base,"tested":len(candidates),"count":len(found),"results":found,"errors":errors[:30],
            "engine":"bounded native ffuf-style wordlist probe","available_external_tools":tool_inventory()["tools"]}

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
def list_documents(q:str="",limit:int=200):
    c=connect()
    if q.strip():
        try:
            rows=c.execute("SELECT d.id,d.filename,d.title,d.url,d.bytes,d.pages,d.sha256,d.discovered_at FROM document_fts f JOIN documents d ON d.id=f.id WHERE document_fts MATCH ? ORDER BY rank LIMIT ?",(q, min(max(limit,1),500))).fetchall()
        except sqlite3.OperationalError:
            rows=c.execute("SELECT id,filename,title,url,bytes,pages,sha256,discovered_at FROM documents WHERE filename LIKE ? OR title LIKE ? OR text LIKE ? ORDER BY discovered_at DESC LIMIT ?",(f"%{q}%",f"%{q}%",f"%{q}%",min(max(limit,1),500))).fetchall()
    else:
        rows=c.execute("SELECT id,filename,title,url,bytes,pages,sha256,discovered_at FROM documents ORDER BY discovered_at DESC LIMIT ?",(min(max(limit,1),500),)).fetchall()
    c.close(); return [dict(x) for x in rows]

@app.get("/api/documents/{docid}/download")
def download_document(docid:str):
    c=connect(); row=c.execute("SELECT path,filename FROM documents WHERE id=?",(docid,)).fetchone(); c.close()
    if not row or not Path(row["path"]).is_file(): raise HTTPException(404,"Document not found")
    return FileResponse(row["path"],media_type="application/pdf",filename=row["filename"])

@app.post("/api/search")
def search_docs(req:SearchRequest):
    c=connect()
    rows=c.execute("SELECT id,filename,title,url,text FROM documents ORDER BY discovered_at DESC").fetchall()
    c.close(); results=[]
    for row in rows:
        if query_matches(row["text"],req.query):
            lines=[x.strip() for x in row["text"].splitlines() if x.strip() and query_matches(x,req.query)]
            results.append({"id":row["id"],"filename":row["filename"],"title":row["title"],"url":row["url"],"snippets":lines[:8]})
            if len(results)>=req.limit: break
    return results
