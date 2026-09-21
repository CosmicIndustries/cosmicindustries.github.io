#!/usr/bin/env python3
"""Harvest authoritative scientific catalog metadata into Fort Knowledge JSONL.
Standard library only. Discovery metadata is stored; source payloads are not copied.
"""

from __future__ import annotations
import argparse, hashlib, json, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "harvest" / "sources.json"
OUT = ROOT / "catalog" / "harvested.jsonl"
REPORT = ROOT / "catalog" / "harvest-report.json"
UA = "FortKnowledge-ScientificAtlas-Harvester/1.0"

def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def first(*values):
    for value in values:
        if value is not None and str(value).strip():
            return value
    return ""

def norm_title(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())

def canon(value):
    value = str(value or "").strip()
    if not value:
        return ""
    p = urllib.parse.urlsplit(value)
    if not p.scheme or not p.netloc:
        return value
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/") or "/", "", ""))

def fetch_json(url):
    req = urllib.request.Request(url, headers={"Accept":"application/json","User-Agent":UA})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))

def items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data","items","results","entry"):
            if isinstance(payload.get(key), list):
                return payload[key]
        feed = payload.get("feed")
        if isinstance(feed, dict) and isinstance(feed.get("entry"), list):
            return feed["entry"]
    return []

def make_record(source_id, title, domain, identifier, url, summary):
    title = str(title or "").strip()
    identifier = str(identifier or "").strip()
    url = canon(url)
    rid = hashlib.sha256(f"{source_id}|{identifier}|{url}|{title}".encode()).hexdigest()[:20]
    return {
        "id": rid,
        "title": title or identifier or url or "Untitled catalog record",
        "domain": domain or "unknown",
        "record_type": "catalog-record",
        "evidence_class": "CATALOG_METADATA",
        "priority": 0.5,
        "discovery_potential": 0.7,
        "accessibility_risk": 0.25,
        "status": "DISCOVERED",
        "summary": str(summary or "").strip(),
        "what_to_recover": "Inspect the source catalog record; capture the underlying dataset, version, documentation, and preservation metadata.",
        "validation_note": "Catalog presence establishes discoverability and provenance, not scientific validity.",
        "last_verified": datetime.now(timezone.utc).date().isoformat(),
        "source_registry": source_id,
        "source_identifier": identifier,
        "source_url": url,
        "harvested_at": now()
    }

def harvest_datacite(cfg):
    q = dict(cfg["query"])
    cursor = "1"
    count = 0
    while cursor and count < cfg["max_records"]:
        q["page[cursor]"] = cursor
        payload = fetch_json(cfg["endpoint"] + "?" + urllib.parse.urlencode(q))
        rows = items(payload)
        for row in rows:
            a = row.get("attributes", {}) if isinstance(row, dict) else {}
            title = next((x.get("title") for x in a.get("titles",[]) if x.get("title")), "")
            doi = first(row.get("id"), a.get("doi"))
            landing = first(a.get("url"), f"https://doi.org/{doi}" if doi else "")
            desc = " ".join(x.get("description","") for x in a.get("descriptions",[])[:2] if isinstance(x,dict))
            rec = make_record(cfg["id"], title, a.get("types",{}).get("resourceTypeGeneral","dataset"), doi, landing, desc)
            rec.update({
                "publisher": a.get("publisher",""),
                "publication_year": a.get("publicationYear"),
                "subjects": [x.get("subject","") for x in a.get("subjects",[]) if isinstance(x,dict)][:25],
                "content_identifier": doi
            })
            yield rec
            count += 1
            if count >= cfg["max_records"]:
                break
        nxt = payload.get("links",{}).get("next") if isinstance(payload,dict) else ""
        cursor = ""
        if nxt:
            cursor = urllib.parse.parse_qs(urllib.parse.urlsplit(nxt).query).get("page[cursor]",[""])[0]
        time.sleep(cfg.get("rate_delay_seconds",0.2))

def harvest_nasa(cfg):
    q = dict(cfg["query"])
    page = 1
    count = 0
    while count < cfg["max_records"]:
        q["page_num"] = page
        payload = fetch_json(cfg["endpoint"] + "?" + urllib.parse.urlencode(q))
        rows = items(payload)
        if not rows:
            break
        for row in rows:
            umm = row.get("umm", row) if isinstance(row,dict) else {}
            meta = row.get("meta",{}) if isinstance(row,dict) else {}
            title = first(umm.get("EntryTitle"), umm.get("ShortName"), meta.get("native-id"))
            concept = first(meta.get("concept-id"), row.get("concept-id"))
            doi_obj = umm.get("DOI",{})
            doi = first(doi_obj.get("DOI"), doi_obj.get("DOIName")) if isinstance(doi_obj,dict) else ""
            url = first(
                f"https://cmr.earthdata.nasa.gov/search/concepts/{concept}" if concept else "",
                f"https://doi.org/{doi}" if doi else ""
            )
            rec = make_record(cfg["id"], title, "earth-science", concept or doi, url, umm.get("Abstract",""))
            rec.update({
                "content_identifier": doi or concept,
                "version": umm.get("Version"),
                "science_keywords": umm.get("ScienceKeywords",[]),
                "data_centers": umm.get("DataCenters",[]),
                "temporal_extent": umm.get("TemporalExtents",[])
            })
            yield rec
            count += 1
            if count >= cfg["max_records"]:
                break
        if len(rows) < int(q["page_size"]):
            break
        page += 1
        time.sleep(cfg.get("rate_delay_seconds",0.2))

def harvest_usgs(cfg):
    offset = 0
    page_size = int(cfg["query"]["max"])
    count = 0
    while count < cfg["max_records"]:
        params = [("q",cfg["query"].get("q","")),("format","json"),("max",min(page_size,cfg["max_records"]-count)),("offset",offset)]
        for f in cfg["query"].get("filter",[]):
            params.append(("filter",f))
        payload = fetch_json(cfg["endpoint"] + "?" + urllib.parse.urlencode(params))
        rows = items(payload)
        if not rows:
            break
        for row in rows:
            item_id = first(row.get("id"), row.get("itemId"))
            link = row.get("link",{}) if isinstance(row.get("link"),dict) else {}
            url = first(link.get("url"), f"https://www.sciencebase.gov/catalog/item/{item_id}" if item_id else "")
            rec = make_record(cfg["id"], first(row.get("title"),row.get("name")), "earth-science", item_id, url, first(row.get("body"),row.get("description")))
            rec.update({
                "system_type": row.get("systemType"),
                "browse_category": row.get("browseCategory"),
                "tags": row.get("tags",[]),
                "identifiers": row.get("identifiers",[])
            })
            yield rec
            count += 1
            if count >= cfg["max_records"]:
                break
        offset += len(rows)
        if len(rows) < page_size:
            break
        time.sleep(cfg.get("rate_delay_seconds",0.2))

def harvest_ncei(cfg):
    offset = 0
    page_size = int(cfg["query"]["limit"])
    count = 0
    while count < cfg["max_records"]:
        params = {"limit":min(page_size,cfg["max_records"]-count),"offset":offset}
        payload = fetch_json(cfg["endpoint"] + "?" + urllib.parse.urlencode(params))
        rows = items(payload)
        if not rows:
            break
        for row in rows:
            ident = first(row.get("id"),row.get("uid"),row.get("dataset"))
            rec = make_record(cfg["id"], first(row.get("name"),row.get("title"),row.get("dataset")), "climate-and-environment", ident, first(row.get("url"),row.get("link")), first(row.get("description"),row.get("abstract")))
            rec.update({
                "available": row.get("available"),
                "dataset_code": row.get("dataset"),
                "mindate": row.get("mindate"),
                "maxdate": row.get("maxdate")
            })
            yield rec
            count += 1
            if count >= cfg["max_records"]:
                break
        offset += len(rows)
        if len(rows) < page_size:
            break
        time.sleep(cfg.get("rate_delay_seconds",0.2))

HARVESTERS = {
    "datacite-datasets": harvest_datacite,
    "nasa-cmr-collections": harvest_nasa,
    "usgs-sciencebase-data-releases": harvest_usgs,
    "noaa-ncei-search": harvest_ncei
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", dest="source_ids")
    args = parser.parse_args()

    cfg = json.loads(SOURCES.read_text(encoding="utf-8"))
    wanted = set(args.source_ids or [s["id"] for s in cfg["sources"]])
    raw = []
    errors = []
    for source in cfg["sources"]:
        if source["id"] not in wanted:
            continue
        try:
            raw.extend(HARVESTERS[source["id"]](source))
        except Exception as exc:
            errors.append({"source":source["id"],"error":repr(exc),"time":now()})

    deduped = {}
    for rec in raw:
        key = (rec.get("source_registry"),rec.get("source_identifier") or rec.get("source_url") or norm_title(rec.get("title")))
        if key not in deduped:
            deduped[key] = rec

    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("w",encoding="utf-8") as fh:
        for rec in sorted(deduped.values(), key=lambda x:(x.get("source_registry",""),x.get("title",""))):
            fh.write(json.dumps(rec,ensure_ascii=False,sort_keys=True) + "\n")

    report = {
        "harvested_at":now(),
        "records_seen":len(raw),
        "records_written":len(deduped),
        "duplicates_removed":len(raw)-len(deduped),
        "errors":errors,
        "sources":sorted({r["source_registry"] for r in deduped.values()})
    }
    REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 1 if errors and not deduped else 0

if __name__ == "__main__":
    raise SystemExit(main())
