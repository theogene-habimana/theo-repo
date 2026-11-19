#!/usr/bin/env python3
import argparse
import csv
import html
import json
import logging
import os
import re
import sys
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import requests

SEC = "https://www.sec.gov"
DATA = "https://data.sec.gov"
TICKERS_URL = f"{SEC}/files/company_tickers.json"
SUBMISSIONS_URL = f"{DATA}/submissions/CIK{{cik}}.json"

SENTENCE_OUTPUT = "sentence_level_cyber_disclosures.csv"
SUMMARY_OUTPUT = "file_level_summary.csv"
AUDIT_OUTPUT = "optional_keyword_audit.csv"
LOG_FILE = "cyber_extraction_log.txt"

DEFAULT_START_YEAR = 1990
DEFAULT_END_YEAR = 2025


US_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC", "PR", "VI", "GU", "AS", "MP",
}

DIRECT_RULES = [
    {
        "main_triggers": ["attack", "attacks", "attacked", "attacking"],
        "relevant_hits": ["cyber", "network", "system", "product", "service", "datacenter", "infrastructure"],
        "irrelevant_hits": ["terror", "war", "contraband", "bomb"],
    },
    {
        "main_triggers": ["threat", "threats"],
        "relevant_hits": ["cyber", "network", "system", "product", "service", "datacenter", "infrastructure"],
        "irrelevant_hits": ["terror", "simulator", "disease", "legal action", "competitive", "competitors", "substitute", "patent", "nuclear", "life", "threaten"],
    },
    {
        "main_triggers": ["computer", "computers", "information system", "information systems"],
        "relevant_hits": ["malware", "virus", "viruses", "intrusion", "intrusions"],
        "irrelevant_hits": [],
    },
    {
        "main_triggers": ["malicious"],
        "relevant_hits": ["software", "program", "third party", "third-party", "attack", "attacks"],
        "irrelevant_hits": ["fires", "product sales", "warranty claim"],
    },
    {
        "main_triggers": ["breach", "breaches"],
        "relevant_hits": [],
        "irrelevant_hits": ["fiduciary duty", "covenant", "credit", "agreement", "warranty", "warranties", "obligations", "regulations", "contract", "resolution"],
    },
    {
        "main_triggers": [
            "hacker", "hackers", "hacking", "social engineering",
            "denial of service", "denial-of-service", "phishing",
            "cyberattack", "cyberattacks", "cyber risk", "cyber risks",
            "cyber security", "cybersecurity", "cyber intrusion", "cyber intrusions",
            "unauthorized access", "breach in security", "security breach", "security breaches",
        ],
        "relevant_hits": [],
        "irrelevant_hits": [],
    },
]

INDIRECT_CATEGORIES = {
    "indirect_company_business": [
        (["company", "regular course", "business", "operation", "operations", "services"], [], []),
        (["technology", "technologies"], ["computer", "information", "communication", "proprietary", "infrastructure", "reliance", "digital", "advances"], []),
        (["information"], ["network", "services", "systems", "confidential", "proprietary", "account"], []),
        (["electronic"], ["network", "services", "systems", "information"], []),
        (["computer", "telecommunication", "third-party", "infrastructure"], [], []),
        (["systems", "networks", "facilities", "network", "system", "facility"], [], []),
        (["collect", "store", "transmit", "retrieve", "sensitive", "critical", "protection"], ["data", "information"], []),
        (["it environment", "it systems", "operational systems", "communication systems", "critical infrastructure"], [], []),
        (["security"], ["network", "product", "service", "system", "device", "data", "infrastructure", "patch", "cloud", "web", "email", "vulnerability", "threat", "breach", "penetrate", "bypass", "compromised", "incidence", "incident", "circumvent", "measures", "portfolio", "solutions", "practices", "standards"], []),
        (["vulnerabilities", "vulnerability"], ["network", "product", "service", "system", "device", "data", "infrastructure", "claims"], []),
    ],
    "indirect_internal_consequences": [
        (["integrity", "reliability", "protect", "protection", "protecting", "prevent", "prevention", "preventing", "monitors", "monitor", "compromise", "secure", "failure"], ["network", "products", "services", "systems", "data", "measures", "information"], []),
        (["gain access", "gained access", "gaining access"], ["network", "systems", "data", "datacenter"], []),
        (["access", "accessed", "modified"], [], ["improper", "improperly"]),
        (["theft", "misuse", "misusing", "modification", "destruction", "lost", "loss", "stolen", "steal", "disclose", "publicly disclosed"], ["assets", "intellectual property", "data", "information"], []),
        (["investigate", "remediate", "remediation", "recover", "repair", "replace"], ["network", "products", "services", "systems", "data", "measures", "efforts"], []),
        (["interruptions", "disruptions", "delays"], ["network", "services", "system"], []),
        (["degrade the user experience", "invasion", "user names", "password", "passwords", "break-ins", "break-in", "terminated agreements"], [], []),
    ],
    "indirect_legal_consequences": [
        (["legal"], ["claims", "actions", "challenges", "liability"], []),
        (["legislative actions", "legislative action"], [], []),
        (["regulatory"], ["actions", "investigations", "agencies"], []),
        (["liability", "liabilities"], ["claims", "claim"], []),
        (["lawsuits", "lawsuit", "litigation", "litigations"], [], []),
    ],
    "indirect_economic_consequences": [
        (["business"], ["adversely", "material", "harm", "disruptive", "negative"], []),
        (["operations", "services", "operation", "service"], ["disrupt", "disrupted", "disrupts", "disrupting"], []),
        (["revenues", "revenue"], ["reduce", "adversely", "loss", "lose", "losing"], []),
        (["cost", "costs"], ["increase", "increasing", "remedy"], []),
        (["operating results", "operating margin"], ["harm", "diminish", "reduce", "harmed", "diminished", "reduced"], []),
        (["earnings"], ["reduce", "adversely", "reduced"], []),
        (["financial"], ["harm", "diminish", "adversely", "material", "damage", "negative", "harmed", "diminished", "damaged"], []),
        (["competitive position"], ["harm", "diminish", "harmed", "diminished"], []),
        (["reputation"], ["harm", "damage", "loss", "adverse", "harmed", "damaged"], []),
        (["brand"], ["harm", "damage", "harmed", "damaged"], []),
    ],
}

CYBER_SECTIONS = [
    "risk factors", "principal risks", "principal risk and uncertainties",
    "cybersecurity", "cyber security", "information security", "data protection",
    "privacy", "technology risks", "operational risks", "digital risks",
]

SENTENCE_FIELDS = [
    "page_no", "sentence_id", "sentence_text", "hit_type", "triggering_keyword",
    "matched_relevant_terms", "matched_irrelevant_terms",
    "Identifier (RIC)", "company_name", "ticker", "CIK", "TRBC Industry Name", "SIC CODE",
    "isin", "country_name", "fiscal_year", "reported_year", "report_date", "form_type", "filing_date",
    "accession_number", "file_name", "file_path",
    "total_sentences_in_report", "total_sentences_that_have_keywords",
    "total_keywords_found_in_report", "total_relevant_keywords_found", "total_irrelevant_keywords_found",
]

SUMMARY_FIELDS = [
    "Identifier (RIC)", "company_name", "ticker", "CIK", "TRBC Industry Name", "SIC CODE",
    "isin", "country_name", "fiscal_year", "reported_year", "report_date",
    "form_type", "filing_date", "accession_number", "file_name", "file_path",
    "language_guess", "pages_total", "total_sentences_in_report",
    "pages_with_hits", "total_sentences_that_have_keywords",
    "direct_hits_count", "indirect_hits_count", "total_hits",
    "total_keywords_found_in_report", "total_relevant_keywords_found", "total_irrelevant_keywords_found",
    "direct_keywords_found", "triggering_keywords", "matched_relevant_terms", "matched_irrelevant_terms",
    "categories_found", "has_cyber_disclosure", "first_hit_page", "processing_status", "error_message",
]

AUDIT_FIELDS = [
    "file_name", "sentence_id", "sentence_text", "tested_rule", "matched_main_term",
    "matched_relevant", "matched_irrelevant", "final_decision",
]


class SecClient:
    def __init__(self, user_agent: str, min_interval: float = 0.2):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json, text/plain, */*",
        })
        self.min_interval = max(0.11, float(min_interval))
        self._last_request_ts = 0.0

    def _wait(self):
        elapsed = time.time() - self._last_request_ts
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def _normalize_url(self, url: str) -> str:
        """
        Fix request URLs before calling requests.get().

        This prevents requests.exceptions.MissingSchema when a URL is:
        - empty
        - a SEC relative path such as /Archives/...
        - missing https://
        """
        if url is None:
            return ""

        url = str(url).strip()

        if not url:
            return ""

        # SEC relative link
        if url.startswith("/"):
            return urljoin(SEC, url)

        # URL without scheme, for example: www.sec.gov/Archives/...
        if not url.startswith(("http://", "https://")):
            if url.startswith("www.sec.gov") or url.startswith("sec.gov"):
                return "https://" + url
            if url.startswith("data.sec.gov"):
                return "https://" + url

        return url

    def get_json(self, url: str) -> dict:
        url = self._normalize_url(url)
        if not url:
            raise ValueError("Empty URL passed to get_json(); skipped to avoid MissingSchema error.")

        self._wait()
        r = self.session.get(url, timeout=60)
        self._last_request_ts = time.time()
        r.raise_for_status()
        return r.json()

    def get_text(self, url: str) -> str:
        url = self._normalize_url(url)
        if not url:
            raise ValueError("Empty URL passed to get_text(); skipped to avoid MissingSchema error.")

        self._wait()
        r = self.session.get(url, timeout=60)
        self._last_request_ts = time.time()
        r.raise_for_status()
        return r.text


def normalize(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", (text or "").upper())


def clean_header_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def load_external_metadata(metadata_csv: Optional[str]) -> Dict[str, dict]:
    """
    Optional merge file for variables not normally available from SEC EDGAR, especially
    Identifier (RIC) and TRBC Industry Name. The SEC submissions endpoint normally
    provides SIC CODE, while RIC/TRBC usually come from LSEG/Refinitiv.
    """
    if not metadata_csv:
        return {}

    path = Path(metadata_csv)
    if not path.exists():
        raise FileNotFoundError(f"Metadata CSV not found: {metadata_csv}")

    aliases = {
        "Identifier (RIC)": {"identifierric", "ric", "identifier"},
        "Company Name": {"companyname", "company", "name", "companytitle", "title"},
        "ticker": {"ticker", "tickers", "symbol"},
        "CIK": {"cik", "cikcode", "cikstr"},
        "TRBC Industry Name": {"trbcindustryname", "trbcindustry", "trbc", "industryname"},
        "SIC CODE": {"siccode", "sic", "standardindustrialclassification"},
    }

    out = {}
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return {}
        colmap = {}
        for col in reader.fieldnames:
            cleaned = clean_header_name(col)
            for standard, allowed in aliases.items():
                if cleaned in allowed:
                    colmap[standard] = col
                    break

        for row in reader:
            def val(name: str) -> str:
                col = colmap.get(name)
                return (row.get(col, "") if col else "").strip()

            rec = {
                "Identifier (RIC)": val("Identifier (RIC)"),
                "Company Name": val("Company Name"),
                "ticker": val("ticker"),
                "CIK": val("CIK").lstrip("0"),
                "TRBC Industry Name": val("TRBC Industry Name"),
                "SIC CODE": val("SIC CODE"),
            }
            keys = {
                normalize(rec["Identifier (RIC)"]),
                normalize(rec["ticker"]),
                normalize(rec["Company Name"]),
                normalize(rec["CIK"]),
            }
            for key in keys:
                if key:
                    out[key] = rec
    return out


def lookup_external_metadata(company: dict, external_metadata: Optional[Dict[str, dict]] = None) -> dict:
    external_metadata = external_metadata or {}
    possible_keys = [
        company.get("ticker", ""),
        company.get("company_name", ""),
        company.get("cik", ""),
        str(company.get("cik", "")).lstrip("0"),
    ]
    for key in possible_keys:
        rec = external_metadata.get(normalize(key))
        if rec:
            return rec
    return {}


def first_regex(text: str, patterns: List[str]) -> str:
    for pat in patterns:
        m = re.search(pat, text or "", flags=re.IGNORECASE)
        if m:
            return (m.group(1) or "").strip()
    return ""


def extract_metadata_from_text(full_text: str) -> dict:
    """Try to extract RIC/TRBC/SIC if those labels are printed inside the filing text."""
    return {
        "Identifier (RIC)": first_regex(full_text, [
            r"\bIdentifier\s*\(?\s*RIC\s*\)?\s*[:=]\s*([A-Z0-9.\-]+)",
            r"\bRIC\s*[:=]\s*([A-Z0-9.\-]+)",
        ]),
        "TRBC Industry Name": first_regex(full_text, [
            r"\bTRBC\s+Industry\s+Name\s*[:=]\s*([^\n\r;|]+)",
            r"\bTRBC\s+Industry\s*[:=]\s*([^\n\r;|]+)",
        ]),
        "SIC CODE": first_regex(full_text, [
            r"\bSIC\s+CODE\s*[:=]\s*(\d{2,4})",
            r"\bSIC\s*[:=]\s*(\d{2,4})",
        ]),
    }


def sec_sic_code(submissions: dict) -> str:
    return str((submissions or {}).get("sic") or "").strip()


def build_company_metadata(company: dict, full_text: str = "", external_metadata: Optional[Dict[str, dict]] = None) -> dict:
    ext = lookup_external_metadata(company, external_metadata)
    text_meta = extract_metadata_from_text(full_text) if full_text else {}
    return {
        "Identifier (RIC)": ext.get("Identifier (RIC)") or text_meta.get("Identifier (RIC)") or "",
        "TRBC Industry Name": ext.get("TRBC Industry Name") or text_meta.get("TRBC Industry Name") or "",
        "SIC CODE": ext.get("SIC CODE") or text_meta.get("SIC CODE") or sec_sic_code(company.get("submissions", {})),
    }


def load_tickers(client: SecClient) -> List[dict]:
    data = client.get_json(TICKERS_URL)
    items = list(data.values()) if isinstance(data, dict) else list(data)
    for item in items:
        item["cik"] = str(item["cik_str"]).zfill(10)
    return items


def resolve_company(client: SecClient, identifier: str, tickers_cache: Optional[List[dict]] = None) -> dict:
    if identifier.isdigit():
        cik = identifier.zfill(10)
        sub = client.get_json(SUBMISSIONS_URL.format(cik=cik))
        return {
            "cik": cik,
            "company_name": sub.get("name", ""),
            "ticker": (sub.get("tickers") or [""])[0],
            "submissions": sub,
        }

    items = tickers_cache or load_tickers(client)
    ident_n = normalize(identifier)
    exact_ticker = None
    exact_name = None
    partial_name = None
    for item in items:
        ticker = str(item.get("ticker", ""))
        title = str(item.get("title", ""))
        if normalize(ticker) == ident_n:
            exact_ticker = item
            break
        if normalize(title) == ident_n:
            exact_name = item
        elif ident_n and ident_n in normalize(title) and partial_name is None:
            partial_name = item

    chosen = exact_ticker or exact_name or partial_name
    if not chosen:
        raise SystemExit(f"Could not resolve identifier: {identifier}")

    cik = chosen["cik"]
    sub = client.get_json(SUBMISSIONS_URL.format(cik=cik))
    return {
        "cik": cik,
        "company_name": sub.get("name") or chosen.get("title", ""),
        "ticker": (sub.get("tickers") or [chosen.get("ticker", "")])[0],
        "submissions": sub,
    }


def iter_submission_rows(submissions: dict) -> Iterable[dict]:
    recent = submissions.get("filings", {}).get("recent", {})
    keys = ["accessionNumber", "form", "filingDate", "reportDate", "primaryDocument"]
    n = len(recent.get("accessionNumber", []))
    for i in range(n):
        yield {k: (recent.get(k, [None] * n)[i]) for k in keys}


def filing_rows(
    client: SecClient,
    cik: str,
    submissions: dict,
    forms: set,
    limit: int,
    start_year: Optional[int] = DEFAULT_START_YEAR,
    end_year: Optional[int] = DEFAULT_END_YEAR,
    all_reported_years: bool = False,
) -> List[dict]:
    rows = list(iter_submission_rows(submissions))
    extra_files = submissions.get("filings", {}).get("files", []) or []
    for extra in extra_files:
        current_matching = len([r for r in rows if (r.get("form") or "").upper() in forms])
        if limit and limit > 0 and current_matching >= limit:
            break
        name = extra.get("name")
        if not name:
            continue
        more = client.get_json(urljoin(f"{DATA}/submissions/", name))
        rows.extend(iter_submission_rows({"filings": {"recent": more}}))

    out = []
    cik_plain = str(int(cik))
    seen = set()
    for r in rows:
        form = (r.get("form") or "").upper()
        if forms and form not in forms:
            continue

        fiscal_year = fiscal_year_from_date(r.get("reportDate", ""))
        if not all_reported_years and fiscal_year:
            fy_int = int(fiscal_year)
            if start_year is not None and fy_int < start_year:
                continue
            if end_year is not None and fy_int > end_year:
                continue

        accn = r.get("accessionNumber")
        if not accn or accn in seen:
            continue
        seen.add(accn)
        doc = r.get("primaryDocument") or ""
        accn_nodash = accn.replace("-", "")
        # If SEC does not provide primaryDocument, fall back to the accession text file.
        # This prevents an empty file_path from being passed to requests.get().
        filing_url = (
            f"{SEC}/Archives/edgar/data/{cik_plain}/{accn_nodash}/{doc}"
            if doc
            else f"{SEC}/Archives/edgar/data/{cik_plain}/{accn_nodash}/{accn}.txt"
        )
        out.append({
            "form_type": form,
            "filing_date": r.get("filingDate", ""),
            "period_end_date": r.get("reportDate", ""),
            "primary_document": doc,
            "accession_number": accn,
            "file_name": doc or f"{accn}.txt",
            "file_path": filing_url,
        })
        if limit and limit > 0 and len(out) >= limit:
            break
    return out


def choose_country_name(submissions: dict) -> str:
    business = submissions.get("addresses", {}).get("business", {}) or {}
    mailing = submissions.get("addresses", {}).get("mailing", {}) or {}
    candidates = [
        submissions.get("stateOfIncorporationDescription"),
        business.get("stateOrCountryDescription"),
        mailing.get("stateOrCountryDescription"),
        business.get("stateOrCountry"),
        mailing.get("stateOrCountry"),
    ]
    for value in candidates:
        if not value:
            continue
        value = str(value).strip()
        if value.upper() in US_CODES:
            return "United States"
        if len(value) == 2 and value.isalpha() and value.upper() in US_CODES:
            return "United States"
        return value.title() if value.isupper() and len(value) > 3 else value
    return "Unknown"


def guess_language(text: str) -> str:
    ascii_ratio = sum(1 for c in text[:5000] if ord(c) < 128) / max(1, len(text[:5000]))
    return "en" if ascii_ratio > 0.9 else "unknown"


def contains_word(text: str, word: str) -> bool:
    return re.search(r"\b" + re.escape(word) + r"\b", text) is not None


def match_direct_rules(sentence_text: str) -> Optional[dict]:
    lower_text = sentence_text.lower()
    for rule in DIRECT_RULES:
        main_match = next((w for w in rule["main_triggers"] if contains_word(lower_text, w)), None)
        if main_match:
            irrel_match = next((w for w in rule["irrelevant_hits"] if contains_word(lower_text, w)), None)
            if irrel_match:
                continue
            if not rule["relevant_hits"]:
                return {"main": main_match, "rel": "", "irrel": irrel_match or ""}
            rel_match = next((w for w in rule["relevant_hits"] if contains_word(lower_text, w)), None)
            if rel_match:
                return {"main": main_match, "rel": rel_match, "irrel": irrel_match or ""}
    return None


def match_indirect_rules(sentence_text: str) -> Optional[dict]:
    lower_text = sentence_text.lower()
    for category, rules in INDIRECT_CATEGORIES.items():
        for primary_terms, secondary_terms, irrelevant_terms in rules:
            pri_match = next((w for w in primary_terms if contains_word(lower_text, w)), None)
            if pri_match:
                irr_match = next((w for w in irrelevant_terms if contains_word(lower_text, w)), None)
                if irr_match:
                    continue
                if not secondary_terms:
                    return {"category": category, "main": pri_match, "rel": ""}
                sec_match = next((w for w in secondary_terms if contains_word(lower_text, w)), None)
                if sec_match:
                    return {"category": category, "main": pri_match, "rel": sec_match}
    return None


def extract_isin(text: str) -> str:
    m = re.search(r"\b([A-Z]{2}[A-Z0-9]{9}[0-9])\b", text)
    return m.group(1) if m else ""


def fiscal_year_from_date(date_str: str) -> str:
    if not date_str:
        return ""
    m = re.match(r"(\d{4})-\d{2}-\d{2}", str(date_str))
    return m.group(1) if m else ""


def extract_fiscal_year_from_text(text: str) -> str:
    match_text = re.search(
        r"fiscal year ended.*?((?:19|20)\d{2})|annual report\s+((?:19|20)\d{2})",
        text[:12000].lower()
    )
    if match_text:
        return match_text.group(1) or match_text.group(2) or ""
    return ""


def is_heading(block_text: str) -> bool:
    cleaned = block_text.strip()
    if not cleaned:
        return False
    if len(cleaned) > 120 or cleaned.endswith("."):
        return False
    words = cleaned.split()
    if not words or len(words) > 14:
        return False
    upper_count = sum(1 for w in words if w.isupper())
    title_count = sum(1 for w in words if w.istitle())
    return upper_count == len(words) or title_count >= len(words) - 2


def html_to_blocks(raw_text: str) -> str:
    text = raw_text.replace("\r", "\n")
    replacements = [
        (r"(?i)<br\s*/?>", "\n"),
        (r"(?i)</p>", "\n"),
        (r"(?i)</div>", "\n"),
        (r"(?i)</tr>", "\n"),
        (r"(?i)</li>", "\n"),
        (r"(?i)</h[1-6]>", "\n"),
        (r"(?i)</table>", "\n"),
        (r"(?i)<hr[^>]*>", "\n---PAGEBREAK---\n"),
    ]
    for pat, repl in replacements:
        text = re.sub(pat, repl, text)
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def extract_document_sentences(raw_text: str) -> List[dict]:
    text = html_to_blocks(raw_text)
    blocks = [b.strip() for b in re.split(r"\n+", text) if b.strip()]
    sentences_data = []
    sentence_id = 1
    page_no = 1

    for block in blocks:
        if block == "---PAGEBREAK---":
            page_no += 1
            continue
        if re.match(r"(?i)^page\s+\d+\s*$", block):
            try:
                page_no = int(re.findall(r"\d+", block)[0])
            except Exception:
                page_no += 1
            continue

        head = is_heading(block)
        if head:
            sentences_data.append({
                "page_no": page_no,
                "sentence_id": sentence_id,
                "sentence_text": block,
                "is_heading": True,
            })
            sentence_id += 1
            continue

        block = block.replace("\n", " ")
        raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", block)
        for sent in raw_sentences:
            cleaned = sent.strip()
            if len(cleaned) > 5:
                sentences_data.append({
                    "page_no": page_no,
                    "sentence_id": sentence_id,
                    "sentence_text": cleaned,
                    "is_heading": False,
                })
                sentence_id += 1
    return sentences_data


def ensure_csv_header(path: Path, fields: List[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()


def append_rows(path: Path, rows: List[dict], fields: List[str]):
    if not rows:
        return
    ensure_csv_header(path, fields)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writerows(rows)



def unique_sorted_terms(values: Iterable[str]) -> List[str]:
    """Return sorted unique non-empty terms while preserving readable lowercase text."""
    terms = []
    seen = set()
    for value in values:
        if value is None:
            continue
        for piece in str(value).split(","):
            term = piece.strip()
            if not term:
                continue
            key = term.lower()
            if key not in seen:
                seen.add(key)
                terms.append(term)
    return sorted(terms, key=lambda x: x.lower())


def rule_term_sets() -> Tuple[set, set, set]:
    """
    Build unique term sets from the rule dictionaries.
    - triggering terms = main trigger terms
    - relevant terms = context terms that confirm cybersecurity relevance
    - irrelevant terms = exclusion terms used to remove false positives
    """
    triggering = set()
    relevant = set()
    irrelevant = set()

    for rule in DIRECT_RULES:
        triggering.update(t.lower() for t in rule.get("main_triggers", []) if t)
        relevant.update(t.lower() for t in rule.get("relevant_hits", []) if t)
        irrelevant.update(t.lower() for t in rule.get("irrelevant_hits", []) if t)

    for rules in INDIRECT_CATEGORIES.values():
        for primary_terms, secondary_terms, irrelevant_terms in rules:
            triggering.update(t.lower() for t in primary_terms if t)
            relevant.update(t.lower() for t in secondary_terms if t)
            irrelevant.update(t.lower() for t in irrelevant_terms if t)

    return triggering, relevant, irrelevant


def count_term_occurrences(text: str, terms: Iterable[str]) -> int:
    """
    Count term occurrences in report text using case-insensitive phrase matching.
    This counts actual appearances in the report, not only extracted hit rows.
    """
    lower_text = (text or "").lower()
    total = 0
    for term in sorted(set(t.lower() for t in terms if t), key=len, reverse=True):
        pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        total += len(re.findall(pattern, lower_text))
    return total


def report_keyword_counts(full_text: str) -> dict:
    """
    Report-level keyword counts requested for CSV output.

    IMPORTANT LOGIC:
    total_keywords_found_in_report = total_relevant_keywords_found + total_irrelevant_keywords_found

    Triggering keywords are still counted internally for checking/auditing, but they are NOT
    added to total_keywords_found_in_report. This guarantees that:

        total_relevant_keywords_found + total_irrelevant_keywords_found
        == total_keywords_found_in_report
    """
    triggering_terms, relevant_terms, irrelevant_terms = rule_term_sets()

    triggering_count = count_term_occurrences(full_text, triggering_terms)
    relevant_count = count_term_occurrences(full_text, relevant_terms)
    irrelevant_count = count_term_occurrences(full_text, irrelevant_terms)

    # User-requested accounting identity:
    # Total = Relevant + Irrelevant
    total_count = relevant_count + irrelevant_count

    return {
        "total_triggering_keywords_found": triggering_count,
        "total_relevant_keywords_found": relevant_count,
        "total_irrelevant_keywords_found": irrelevant_count,
        "total_keywords_found_in_report": total_count,
    }


def hit_keyword_aggregates(extracted_hits: List[dict]) -> dict:
    """
    Aggregate matched terms from the extracted hit sentences.
    These fields make the file-level summary easier to merge with panel data.
    """
    triggering_keywords = unique_sorted_terms(h.get("triggering_keyword", "") for h in extracted_hits)
    matched_relevant_terms = unique_sorted_terms(h.get("matched_relevant_terms", "") for h in extracted_hits)
    matched_irrelevant_terms = unique_sorted_terms(h.get("matched_irrelevant_terms", "") for h in extracted_hits)

    return {
        "triggering_keywords": ", ".join(triggering_keywords),
        "matched_relevant_terms": ", ".join(matched_relevant_terms),
        "matched_irrelevant_terms": ", ".join(matched_irrelevant_terms),
    }


def process_filing(
    client: SecClient,
    company: dict,
    filing_meta: dict,
    max_indirect_window: int = 10,
    external_metadata: Optional[Dict[str, dict]] = None,
) -> Tuple[List[dict], dict, List[dict]]:
    filing_url = filing_meta["file_path"]
    raw_text = client.get_text(filing_url)
    sentences_data = extract_document_sentences(raw_text)

    if not sentences_data:
        company_meta = build_company_metadata(company, "", external_metadata)
        fiscal_year = fiscal_year_from_date(filing_meta["period_end_date"])
        summary = OrderedDict((k, "") for k in SUMMARY_FIELDS)
        summary.update({
            **company_meta,
            "company_name": company["company_name"],
            "ticker": company["ticker"],
            "CIK": company["cik"],
            "country_name": choose_country_name(company["submissions"]),
            "fiscal_year": fiscal_year,
            "reported_year": fiscal_year,
            "report_date": filing_meta.get("period_end_date") or filing_meta.get("filing_date", ""),
            "form_type": filing_meta["form_type"],
            "filing_date": filing_meta["filing_date"],
            "accession_number": filing_meta["accession_number"],
            "file_name": filing_meta["file_name"],
            "file_path": filing_url,
            "pages_total": 0,
            "total_sentences_in_report": 0,
            "pages_with_hits": 0,
            "total_sentences_that_have_keywords": 0,
            "direct_hits_count": 0,
            "indirect_hits_count": 0,
            "total_hits": 0,
            "total_keywords_found_in_report": 0,
            "total_relevant_keywords_found": 0,
            "total_irrelevant_keywords_found": 0,
            "triggering_keywords": "",
            "matched_relevant_terms": "",
            "matched_irrelevant_terms": "",
            "has_cyber_disclosure": False,
            "processing_status": "NoTextExtracted",
            "error_message": "No text extracted from filing document.",
        })
        return [], summary, []

    full_text = " ".join(x["sentence_text"] for x in sentences_data)
    company_meta = build_company_metadata(company, full_text, external_metadata)

    company_name = company["company_name"]
    ticker = company["ticker"]
    cik = company["cik"]
    country_name = choose_country_name(company["submissions"])
    isin = extract_isin(full_text)
    fiscal_year = fiscal_year_from_date(filing_meta["period_end_date"]) or extract_fiscal_year_from_text(full_text)
    language_guess = guess_language(full_text)

    current_section = "Unknown"
    for s in sentences_data:
        if s["is_heading"]:
            current_section = s["sentence_text"]
        s["section_title_guess"] = current_section
        s["in_priority_section"] = any(cs.lower() in current_section.lower() for cs in CYBER_SECTIONS)

    extracted_hits = []
    audits = []
    i = 0
    sent_len = len(sentences_data)

    while i < sent_len:
        s = sentences_data[i]
        dir_match = match_direct_rules(s["sentence_text"])

        if dir_match:
            audits.append({
                "file_name": filing_meta["file_name"],
                "sentence_id": s["sentence_id"],
                "sentence_text": s["sentence_text"],
                "tested_rule": "direct",
                "matched_main_term": dir_match["main"],
                "matched_relevant": dir_match["rel"],
                "matched_irrelevant": dir_match["irrel"],
                "final_decision": "direct_hit",
            })

            hit = s.copy()
            hit.update({
                "hit_type": "direct",
                "hit_category": "direct_description",
                "triggering_keyword": dir_match["main"],
                "matched_relevant_terms": dir_match["rel"],
                "matched_irrelevant_terms": dir_match["irrel"],
            })
            extracted_hits.append(hit)

            for w in range(1, max_indirect_window + 1):
                idx = i + w
                if idx >= sent_len:
                    break
                ind_s = sentences_data[idx]
                if ind_s["is_heading"]:
                    break
                ind_match = match_indirect_rules(ind_s["sentence_text"])
                if ind_match:
                    ind_hit = ind_s.copy()
                    ind_hit.update({
                        "hit_type": "indirect",
                        "hit_category": ind_match["category"],
                        "triggering_keyword": ind_match["main"],
                        "matched_relevant_terms": ind_match["rel"],
                        "matched_irrelevant_terms": "",
                    })
                    extracted_hits.append(ind_hit)
                    audits.append({
                        "file_name": filing_meta["file_name"],
                        "sentence_id": ind_s["sentence_id"],
                        "sentence_text": ind_s["sentence_text"],
                        "tested_rule": "indirect",
                        "matched_main_term": ind_match["main"],
                        "matched_relevant": ind_match["rel"],
                        "matched_irrelevant": "",
                        "final_decision": "indirect_hit",
                    })
        i += 1

    dedup_hits = OrderedDict((h["sentence_id"], h) for h in extracted_hits)
    extracted_hits = list(dedup_hits.values())
    extracted_hits.sort(key=lambda x: x["sentence_id"])

    priority_hits = [h for h in extracted_hits if h["in_priority_section"]]
    if priority_hits:
        extracted_hits = priority_hits

    total_pages = max((s["page_no"] for s in sentences_data), default=1)
    total_sentences_in_report = sum(1 for s in sentences_data if not s.get("is_heading"))
    total_sentences_that_have_keywords = len({h["sentence_id"] for h in extracted_hits})
    direct_hits_count = sum(1 for h in extracted_hits if h["hit_type"] == "direct")
    indirect_hits_count = sum(1 for h in extracted_hits if h["hit_type"] == "indirect")
    pages_with_hits = sorted({h["page_no"] for h in extracted_hits})
    categories_found = sorted({h.get("hit_category", "") for h in extracted_hits if h.get("hit_category")})
    keywords_found = sorted({
        h.get("triggering_keyword", "")
        for h in extracted_hits
        if h.get("hit_type") == "direct" and h.get("triggering_keyword")
    })

    keyword_counts = report_keyword_counts(full_text)
    keyword_aggs = hit_keyword_aggregates(extracted_hits)

    report_date = filing_meta.get("period_end_date") or filing_meta.get("filing_date") or datetime.today().strftime("%Y-%m-%d")

    for hit in extracted_hits:
        for helper in ["is_heading", "section_title_guess", "in_priority_section", "hit_category"]:
            hit.pop(helper, None)
        hit.update({
            **company_meta,
            "company_name": company_name,
            "ticker": ticker,
            "CIK": cik,
            "isin": isin,
            "country_name": country_name,
            "fiscal_year": fiscal_year,
            "reported_year": fiscal_year,
            "report_date": report_date,
            "form_type": filing_meta["form_type"],
            "filing_date": filing_meta["filing_date"],
            "accession_number": filing_meta["accession_number"],
            "file_name": filing_meta["file_name"],
            "file_path": filing_url,
            "total_sentences_in_report": total_sentences_in_report,
            "total_sentences_that_have_keywords": total_sentences_that_have_keywords,
            "total_keywords_found_in_report": keyword_counts["total_keywords_found_in_report"],
            "total_relevant_keywords_found": keyword_counts["total_relevant_keywords_found"],
            "total_irrelevant_keywords_found": keyword_counts["total_irrelevant_keywords_found"],
        })

    summary = OrderedDict((k, "") for k in SUMMARY_FIELDS)
    summary.update({
        **company_meta,
        "company_name": company_name,
        "ticker": ticker,
        "CIK": cik,
        "isin": isin,
        "country_name": country_name,
        "fiscal_year": fiscal_year,
        "reported_year": fiscal_year,
        "report_date": report_date,
        "form_type": filing_meta["form_type"],
        "filing_date": filing_meta["filing_date"],
        "accession_number": filing_meta["accession_number"],
        "file_name": filing_meta["file_name"],
        "file_path": filing_url,
        "language_guess": language_guess,
        "pages_total": total_pages,
        "total_sentences_in_report": total_sentences_in_report,
        "pages_with_hits": len(pages_with_hits),
        "total_sentences_that_have_keywords": total_sentences_that_have_keywords,
        "direct_hits_count": direct_hits_count,
        "indirect_hits_count": indirect_hits_count,
        "total_hits": len(extracted_hits),
        "total_keywords_found_in_report": keyword_counts["total_keywords_found_in_report"],
        "total_relevant_keywords_found": keyword_counts["total_relevant_keywords_found"],
        "total_irrelevant_keywords_found": keyword_counts["total_irrelevant_keywords_found"],
        "direct_keywords_found": ", ".join(keywords_found),
        **keyword_aggs,
        "categories_found": ", ".join(categories_found),
        "has_cyber_disclosure": len(extracted_hits) > 0,
        "first_hit_page": pages_with_hits[0] if pages_with_hits else "",
        "processing_status": "Success",
        "error_message": "",
    })

    return extracted_hits, summary, audits


def append_error_summary(
    path: Path,
    company: dict,
    filing_meta: dict,
    message: str,
    external_metadata: Optional[Dict[str, dict]] = None,
):
    company_meta = build_company_metadata(company, "", external_metadata)
    fiscal_year = fiscal_year_from_date(filing_meta.get("period_end_date", ""))

    summary = OrderedDict((k, "") for k in SUMMARY_FIELDS)
    summary.update({
        **company_meta,
        "company_name": company.get("company_name", ""),
        "ticker": company.get("ticker", ""),
        "CIK": company.get("cik", ""),
        "country_name": choose_country_name(company.get("submissions", {})) if company.get("submissions") else "Unknown",
        "fiscal_year": fiscal_year,
        "reported_year": fiscal_year,
        "report_date": filing_meta.get("period_end_date") or filing_meta.get("filing_date", ""),
        "form_type": filing_meta.get("form_type", ""),
        "filing_date": filing_meta.get("filing_date", ""),
        "accession_number": filing_meta.get("accession_number", ""),
        "file_name": filing_meta.get("file_name", ""),
        "file_path": filing_meta.get("file_path", ""),
        "pages_total": 0,
        "total_sentences_in_report": 0,
        "pages_with_hits": 0,
        "total_sentences_that_have_keywords": 0,
        "direct_hits_count": 0,
        "indirect_hits_count": 0,
        "total_hits": 0,
        "total_keywords_found_in_report": 0,
        "total_relevant_keywords_found": 0,
        "total_irrelevant_keywords_found": 0,
        "triggering_keywords": "",
        "matched_relevant_terms": "",
        "matched_irrelevant_terms": "",
        "has_cyber_disclosure": False,
        "processing_status": "Error",
        "error_message": message,
    })

    append_rows(path, [summary], SUMMARY_FIELDS)


def make_zero_year_summary(company: dict, year: int, external_metadata: Optional[Dict[str, dict]] = None) -> OrderedDict:
    company_meta = build_company_metadata(company, "", external_metadata)

    summary = OrderedDict((k, "") for k in SUMMARY_FIELDS)
    summary.update({
        **company_meta,
        "company_name": company.get("company_name", ""),
        "ticker": company.get("ticker", ""),
        "CIK": company.get("cik", ""),
        "country_name": choose_country_name(company.get("submissions", {})) if company.get("submissions") else "Unknown",
        "fiscal_year": str(year),
        "reported_year": str(year),
        "report_date": "",
        "pages_total": 0,
        "total_sentences_in_report": 0,
        "pages_with_hits": 0,
        "total_sentences_that_have_keywords": 0,
        "direct_hits_count": 0,
        "indirect_hits_count": 0,
        "total_hits": 0,
        "total_keywords_found_in_report": 0,
        "total_relevant_keywords_found": 0,
        "total_irrelevant_keywords_found": 0,
        "triggering_keywords": "",
        "matched_relevant_terms": "",
        "matched_irrelevant_terms": "",
        "has_cyber_disclosure": False,
        "processing_status": "NoFilingData",
        "error_message": "No matching filing/data found for this company-year.",
    })

    return summary


def process_company_filings(
    client: SecClient,
    company: dict,
    forms: set,
    filings_limit: int,
    output_folder: Path,
    max_indirect_window: int,
    start_year: Optional[int] = DEFAULT_START_YEAR,
    end_year: Optional[int] = DEFAULT_END_YEAR,
    all_reported_years: bool = False,
    no_zero_years: bool = False,
    external_metadata: Optional[Dict[str, dict]] = None,
):
    filings = filing_rows(
        client,
        company["cik"],
        company["submissions"],
        forms,
        filings_limit,
        start_year,
        end_year,
        all_reported_years=all_reported_years
    )

    sent_out = output_folder / SENTENCE_OUTPUT
    sum_out = output_folder / SUMMARY_OUTPUT
    audit_out = output_folder / AUDIT_OUTPUT
    years_with_rows = set()

    for filing_meta in filings:
        fy = fiscal_year_from_date(filing_meta.get("period_end_date", ""))

        try:
            sentences, summary, audits = process_filing(
                client,
                company,
                filing_meta,
                max_indirect_window=max_indirect_window,
                external_metadata=external_metadata,
            )

            if summary.get("fiscal_year"):
                years_with_rows.add(str(summary.get("fiscal_year")))
            elif fy:
                years_with_rows.add(str(fy))

            append_rows(sent_out, sentences, SENTENCE_FIELDS)
            append_rows(sum_out, [summary], SUMMARY_FIELDS)
            append_rows(audit_out, audits, AUDIT_FIELDS)

            logging.info(
                "Processed %s | %s | hits=%s",
                company["company_name"],
                filing_meta["accession_number"],
                summary["total_hits"]
            )

        except Exception as exc:
            logging.exception(
                "Failed processing %s %s",
                company["company_name"],
                filing_meta["accession_number"]
            )
            append_error_summary(
                sum_out,
                company,
                filing_meta,
                str(exc),
                external_metadata=external_metadata
            )
            if fy:
                years_with_rows.add(str(fy))

    # Optional balanced-panel zero rows.
    # When --all-reported-years or --no-zero-years is used, only actual EDGAR filings are exported.
    zero_rows = []
    if not all_reported_years and not no_zero_years and start_year is not None and end_year is not None:
        zero_rows = [
            make_zero_year_summary(company, year, external_metadata=external_metadata)
            for year in range(start_year, end_year + 1)
            if str(year) not in years_with_rows
        ]

    append_rows(sum_out, zero_rows, SUMMARY_FIELDS)


def iter_all_companies(client: SecClient, start_index: int = 0, max_companies: Optional[int] = None):
    items = load_tickers(client)
    count = 0

    for idx, item in enumerate(items):
        if idx < start_index:
            continue

        yield idx, {
            "cik": item["cik"],
            "company_name": item.get("title", ""),
            "ticker": item.get("ticker", ""),
        }

        count += 1
        if max_companies is not None and count >= max_companies:
            break


def setup_logging(output_folder: Path):
    output_folder.mkdir(parents=True, exist_ok=True)
    log_path = output_folder / LOG_FILE

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    fh.setFormatter(formatter)

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)

    root.addHandler(fh)
    root.addHandler(sh)


def main():
    p = argparse.ArgumentParser(
        description="Extract cybersecurity disclosure outputs from SEC EDGAR filings."
    )

    p.add_argument("identifier", nargs="?", help="Ticker, company name, or numeric CIK")
    p.add_argument("--all-companies", action="store_true", help="Iterate through SEC company_tickers.json")
    p.add_argument("--forms", nargs="+", default=["10-K", "20-F"], help="Form types to include, e.g. 10-K 20-F")
    p.add_argument("--filings-limit", type=int, default=100, help="Max matching filings per company. Use 100 or more for 1990-2025 coverage.")
    p.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR, help="First fiscal/reported year to include in the balanced panel")
    p.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR, help="Last fiscal/reported year to include in the balanced panel")
    p.add_argument("--all-reported-years", action="store_true", help="Keep all fiscal/report years as reported in SEC EDGAR; ignore --start-year and --end-year filters")
    p.add_argument("--no-zero-years", action="store_true", help="Do not create artificial zero rows for missing company-years")
    p.add_argument("--metadata-csv", default="", help="Optional CSV with Identifier (RIC), Company Name, TRBC Industry Name, SIC CODE, ticker, or CIK")
    p.add_argument("--output-folder", default="./edgar_cyber_output", help="Folder for output CSV files")
    p.add_argument("--request-interval", type=float, default=0.2, help="Minimum seconds between SEC requests")
    p.add_argument("--start-index", type=int, default=0, help="For --all-companies mode")
    p.add_argument("--max-companies", type=int, default=None, help="For --all-companies mode")
    p.add_argument("--max-indirect-window", type=int, default=10, help="How many following sentences to scan for indirect hits")
    p.add_argument("--user-agent", required=True, help='Descriptive SEC-compliant user agent, e.g. "Jane Doe jane@example.com"')

    args = p.parse_args()

    if not args.identifier and not args.all_companies:
        p.error("Provide an identifier or use --all-companies")

    if args.identifier and args.all_companies:
        p.error("Use either a single identifier or --all-companies, not both")

    if not args.all_reported_years and args.start_year > args.end_year:
        p.error("--start-year cannot be greater than --end-year")

    if args.all_reported_years:
        args.start_year = None
        args.end_year = None
        args.no_zero_years = True

    output_folder = Path(args.output_folder)
    setup_logging(output_folder)

    client = SecClient(args.user_agent, min_interval=args.request_interval)
    forms = {x.upper() for x in args.forms}
    external_metadata = load_external_metadata(args.metadata_csv)

    ensure_csv_header(output_folder / SENTENCE_OUTPUT, SENTENCE_FIELDS)
    ensure_csv_header(output_folder / SUMMARY_OUTPUT, SUMMARY_FIELDS)
    ensure_csv_header(output_folder / AUDIT_OUTPUT, AUDIT_FIELDS)

    if args.all_companies:
        processed = 0

        for idx, stub in iter_all_companies(
            client,
            start_index=args.start_index,
            max_companies=args.max_companies
        ):
            try:
                sub = client.get_json(SUBMISSIONS_URL.format(cik=stub["cik"]))

                company = {
                    "cik": stub["cik"],
                    "company_name": sub.get("name") or stub.get("company_name", ""),
                    "ticker": (sub.get("tickers") or [stub.get("ticker", "")])[0],
                    "submissions": sub,
                }

                process_company_filings(
                    client,
                    company,
                    forms,
                    args.filings_limit,
                    output_folder,
                    args.max_indirect_window,
                    start_year=args.start_year,
                    end_year=args.end_year,
                    all_reported_years=args.all_reported_years,
                    no_zero_years=args.no_zero_years,
                    external_metadata=external_metadata,
                )

                processed += 1

                print(json.dumps({
                    "index": idx,
                    "company": company["company_name"],
                    "ticker": company["ticker"],
                    "CIK": company["cik"]
                }))

            except Exception as exc:
                logging.exception("Failed company at index %s", idx)

                err_summary = OrderedDict((k, "") for k in SUMMARY_FIELDS)
                err_meta = build_company_metadata(
                    {**stub, "submissions": {}},
                    "",
                    external_metadata
                )

                err_summary.update({
                    **err_meta,
                    "company_name": stub.get("company_name", ""),
                    "ticker": stub.get("ticker", ""),
                    "CIK": stub.get("cik", ""),
                    "report_date": "",
                    "pages_total": 0,
                    "total_sentences_in_report": 0,
                    "pages_with_hits": 0,
                    "total_sentences_that_have_keywords": 0,
                    "direct_hits_count": 0,
                    "indirect_hits_count": 0,
                    "total_hits": 0,
                    "total_keywords_found_in_report": 0,
                    "total_relevant_keywords_found": 0,
                    "total_irrelevant_keywords_found": 0,
                    "triggering_keywords": "",
                    "matched_relevant_terms": "",
                    "matched_irrelevant_terms": "",
                    "has_cyber_disclosure": False,
                    "processing_status": "Error",
                    "error_message": str(exc),
                })

                append_rows(output_folder / SUMMARY_OUTPUT, [err_summary], SUMMARY_FIELDS)

        print(json.dumps({
            "mode": "all-companies",
            "companies_processed": processed,
            "output_folder": str(output_folder.resolve()),
        }, indent=2))

        return

    company = resolve_company(client, args.identifier)

    process_company_filings(
        client,
        company,
        forms,
        args.filings_limit,
        output_folder,
        args.max_indirect_window,
        start_year=args.start_year,
        end_year=args.end_year,
        all_reported_years=args.all_reported_years,
        no_zero_years=args.no_zero_years,
        external_metadata=external_metadata,
    )

    print(json.dumps({
        "mode": "single-company",
        "company_name": company["company_name"],
        "ticker": company["ticker"],
        "CIK": company["cik"],
        "output_folder": str(output_folder.resolve()),
    }, indent=2))


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        msg = f"HTTP error: {e.response.status_code} for {e.response.url}"
        raise SystemExit(msg) from e