#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
ai_data_extraction_code.py

Purpose
-------
Extract AI Focus from SEC EDGAR annual reports using the paid sec-api.io API.

This script is AI only.

"Artificial intelligence focus and firm performance",


Main AI measure
---------------
AI Focus = (Number of AI-related words in the full 10-K annual report /
            Total number of words in the full 10-K annual report) * 100

Additional recommended variables
--------------------------------
ai_focus_reg = ai_focus * 1000
ai_unique_terms_found = number of distinct AI keywords found in the filing
ff12_industry = Fama-French 12 industry classification based on SIC code

Sentence classification
-----------------------
AI-keyword sentences are classified as:
- positive_ai_reference: sentence contains an AI keyword and clearly indicates AI use/adoption/deployment.
- negative_ai_reference: sentence contains an AI keyword but states that AI use is not allowed,
  not used, prohibited, restricted, banned, or similar.
- neutral_ai_reference: sentence contains an AI keyword but does not clearly confirm use or non-use.

Main outputs
------------
1. ai_file_level_summary.csv
2. ai_sentence_level_disclosures.csv
3. ai_keyword_level_counts.csv
4. optional_ai_keyword_audit.csv
5. failed_filings.csv
6. ai_extraction_log.txt

Important
---------

Do NOT hard-code your SEC API key.

Here is how to Set API key in Windows Command Prompt:

    setx SEC_API_KEY "YOUR_API_KEY_HERE"

Check API key:

    echo %SEC_API_KEY%

Then close and reopen VS Code / Command Prompt(optional).

Install packages:

    pip install pandas openpyxl sec-api requests

Data retrival algorithm:

python ai_data_extraction_code.py --all-companies --forms 10-K --start-year 2023 --end-year 2023 --max-filings 50000 --output-folder "G:\Edgar Datatabses\ai_relevance_all_2023" --user-agent "Your Name your.name@example.org" --enrich-online --fill-trbc-with-sec-sic-description
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Iterable, Set

import pandas as pd
import requests
from sec_api import QueryApi


# ============================================================
# 1. AI KEYWORDS FROM MISHRA ET AL. (2022) INTERNET APPENDIX III
# ============================================================

AI_KEYWORDS = [
    "Pattern recognition",
    "Speech recognition",
    "OCR",
    "Handwriting recognition",
    "Facial recognition",
    "Natural Language Processing",
    "Natural Language Understanding",
    "Intent classification",
    "Slot filling",
    "Entity recognition",
    "Semantic translation",
    "Machine translation",
    "Chatbot",
    "Autonomous agent",
    "Language identification",
    "Named entity extraction",
    "Named entity recognition",
    "Relationship extraction",
    "Terminology extraction",
    "Semantic web",
    "Computer vision",
    "Object recognition",
    "Intelligent word recognition",
    "Intelligent image analysis",
    "Image processing",
    "Robotic process automation",
    "Robotic",
    "Robot",
    "Artificial Intelligence",
    "Deep learning",
    "Neural network",
    "Artificial neural network",
    "Convolutional neural network",
    "Recurrent neural network",
    "Generative adversarial network",
    "Feedforward network",
    "Machine learning",
    "Supervised machine learning",
    "Unsupervised machine learning",
    "Supervised learning",
    "Unsupervised learning",
    "Reinforcement learning",
    "Model registry",
    "Model manifestation",
    "Model servicing",
    "Model monitoring",
    "Model validation",
    "Transfer learning",
    "Oneshot learning",
    "Pooling",
    "Predictive analytics",
    "Cognitive framework",
    "Cognitive services",
    "Machine learning model",
    "Machine learning framework",
    "Model training",
    "Customer segmentation",
    "Personalization engines",
    "Inferencing",
    "Embedding",
    "Algorithm",
    "Automation",
    "Data science",
    "Data acquisition",
    "Data processing",
    "Modelling",
    "AI Operations",
    "AIOps",
    "Machine Learning Ops",
    "MLOps",
    "Machine Learning ontologies",
    "AI ethics",
    "Machine Learning bias",
    "Machine bias",
    "Training data",
    "Data pipelines",
    "Python",
    "TensorFlow",
    "Tensor",
    "Tensor Processing Unit",
    "TPU",
    "Cuda",
    "Dialogflow",
    "Word2Vec",
    "Doc2Vec",
    "GloVe",
    "Universal Sentence Encoding",
    "Embeddings from language models",
    "Neural network language model",
    "Latent semantic analysis",
    "Vector space models",
    "Deep averaging network",
    "Prediction",
    "Clustering engine",
    "Topic modelling",
    "MathWorks",
    "Databricks",
    "H20.ai",
    "Datarobot",
    "Amazon Machine Learning",
    "Google Cloud Platform",
    "Google Cloud Machine Learning",
    "IBM Watson",
    "Microsoft Azure Machine Learning",
    "Azure cognitive toolkit",
    "Apache SystemML",
    "Apache Spark MLlib",
    "Apache Mahout",
    "Caffe",
    "OpenNN",
    "Torch",
    "Deeplearning4j",
    "Veles",
    "Theano",
    "Scikit learning",
    "PyTorch",
    "Keras",
    "RapidMiner",
    "Pandas",
    "KNIME",
    "Alteryx",
    "SAS",
]

# Additional modern AI terms frequently appearing in recent SEC filings.
# These are added to improve coverage for newer AI disclosures.
# Duplicates are removed below, preserving the first occurrence.
AI_ADDITIONAL_KEYWORDS = [
    "AI",
    "Generative AI",
    "GenAI",
    "Large language model",
    "Large language models",
    "LLM",
    "LLMs",
    "Foundation model",
    "Foundation models",
    "Transformer model",
    "Transformer models",
    "GPT",
    "ChatGPT",
    "OpenAI",
    "Copilot",
    "AI assistant",
    "Virtual assistant",
    "Conversational AI",
    "AI model",
    "AI models",
    "AI platform",
    "AI platforms",
    "AI system",
    "AI systems",
    "AI tool",
    "AI tools",
    "AI solution",
    "AI solutions",
    "AI-powered",
    "AI-enabled",
    "AI-driven",
    "Agentic AI",
    "Autonomous AI",
    "Responsible AI",
    "AI governance",
    "AI safety",
    "AI risk management",
    "Prompt engineering",
    "Retrieval augmented generation",
    "RAG",
    "Fine-tuning",
    "Fine tuning",
    "Synthetic data",
    "Computer-generated content",
    "Automated decision-making",
    "Automated decision making",
    "Decision automation",
    "Recommendation engine",
    "Recommendation engines",
    "Recommendation system",
    "Recommendation systems",
    "Anomaly detection",
    "Fraud detection model",
    "Natural language generation",
    "Text analytics",
    "Text mining",
    "Voice recognition",
    "Image recognition",
    "Visual recognition",
    "Autonomous vehicle",
    "Autonomous vehicles",
    "Robotic automation",
    "Intelligent automation",
    "Intelligent virtual agent",
    "Intelligent virtual agents",
]

AI_KEYWORDS = list(dict.fromkeys([kw.strip() for kw in (AI_KEYWORDS + AI_ADDITIONAL_KEYWORDS) if kw.strip()]))

# Extra sentence-classification alias.
# This catches sentences such as "Using AI is not allowed".
# It is used only for sentence/context classification.
# The Mishra-style AI Focus denominator/numerator still uses AI_KEYWORDS above.
AI_CLASSIFICATION_TERMS = list(dict.fromkeys(AI_KEYWORDS))



# ============================================================
# 2. OUTPUT COLUMNS
# ============================================================

FILE_LEVEL_COLUMNS = [
    "Identifier (RIC)",
    "company_name",
    "ticker",
    "CIK",
    "TRBC Industry Name",
    "SIC CODE",
    "SEC SIC Description",
    "SEC entityType",
    "SEC tickers",
    "SEC exchanges",
    "metadata_source",
    "ff12_industry",
    "isin",
    "country_name",
    "fiscal_year",
    "reported_year",
    "report_date",
    "form_type",
    "filing_date",
    "accession_number",
    "filing_url",
    "file_name",
    "file_path",
    "language_guess",
    "total_words_in_report",
    "ai_focus",
    "ai_focus_reg",
    "ai_unique_terms_found",
    "total_sentences_in_report",
    "total_sentences_that_have_keywords",
    "direct_hits_count",
    "indirect_hits_count",
    "total_hits",
    "positive_ai_sentence_count",
    "negative_ai_sentence_count",
    "neutral_ai_sentence_count",
    "relevant_ai_sentence_count",
    "irrelevant_ai_sentence_count",
    "total_direct_keywords_found",
    "total_indirect_keywords_found",
    "total_keywords_found_in_report",
    "positive_ai_keyword_count",
    "negative_ai_keyword_count",
    "neutral_ai_keyword_count",
    "relevant_ai_keyword_count",
    "irrelevant_ai_keyword_count",
    "total_relevant_keywords_found",
    "total_irrelevant_keywords_found",
    "total_ai_keywords_found",
    "direct_keywords_found",
    "triggering_keywords",
    "matched_relevant_terms",
    "matched_irrelevant_terms",
    "positive_ai_keywords_found",
    "negative_ai_keywords_found",
    "relevant_ai_keywords_found",
    "irrelevant_ai_keywords_found",
    "ai_keywords_found",
    "has_ai_disclosure",
    "has_positive_ai_disclosure",
    "has_negative_ai_disclosure",
    "has_relevant_ai_disclosure",
    "has_irrelevant_ai_disclosure",
    "processing_status",
]

SENTENCE_LEVEL_COLUMNS = [
    "page_no",
    "sentence_id",
    "sentence_text",
    "ai_use_classification",
    "ai_use_polarity",
    "ai_relevance_classification",
    "ai_relevance_binary",
    "ai_relevance_reason",
    "ai_negative_signal",
    "sentence_sentiment",
    "keywords_found_json",
    "keyword_context_json",
    "classification_explanation",
    "hit_type",
    "triggering_keyword",
    "matched_relevant_terms",
    "matched_irrelevant_terms",
    "direct_keyword_count_in_sentence",
    "indirect_keyword_count_in_sentence",
    "Identifier (RIC)",
    "company_name",
    "ticker",
    "CIK",
    "TRBC Industry Name",
    "SIC CODE",
    "SEC SIC Description",
    "SEC entityType",
    "SEC tickers",
    "SEC exchanges",
    "metadata_source",
    "ff12_industry",
    "isin",
    "country_name",
    "fiscal_year",
    "reported_year",
    "report_date",
    "form_type",
    "filing_date",
    "accession_number",
    "filing_url",
    "file_name",
    "file_path",
    "total_words_in_report",
    "ai_focus",
    "ai_focus_reg",
    "ai_unique_terms_found",
    "total_sentences_in_report",
    "total_sentences_that_have_keywords",
    "total_direct_keywords_found",
    "total_indirect_keywords_found",
    "total_keywords_found_in_report",
    "positive_ai_keyword_count",
    "negative_ai_keyword_count",
    "neutral_ai_keyword_count",
    "relevant_ai_keyword_count",
    "irrelevant_ai_keyword_count",
    "total_relevant_keywords_found",
    "total_irrelevant_keywords_found",
    "total_ai_keywords_found",
]

KEYWORD_LEVEL_COLUMNS = [
    "Identifier (RIC)",
    "company_name",
    "ticker",
    "CIK",
    "TRBC Industry Name",
    "SIC CODE",
    "SEC SIC Description",
    "SEC entityType",
    "SEC tickers",
    "SEC exchanges",
    "metadata_source",
    "ff12_industry",
    "isin",
    "country_name",
    "fiscal_year",
    "reported_year",
    "report_date",
    "form_type",
    "filing_date",
    "accession_number",
    "filing_url",
    "file_name",
    "file_path",
    "keyword",
    "keyword_count",
    "total_words_in_report",
    "total_ai_keywords_found",
    "ai_unique_terms_found",
    "ai_focus",
    "ai_focus_reg",
]

AUDIT_COLUMNS = [
    "company_name",
    "ticker",
    "CIK",
    "fiscal_year",
    "form_type",
    "filing_date",
    "accession_number",
    "sentence_id",
    "sentence_text",
    "tested_rule",
    "matched_main_term",
    "matched_relevant",
    "matched_irrelevant",
    "ai_use_classification",
    "ai_use_polarity",
    "ai_relevance_classification",
    "ai_relevance_binary",
    "ai_relevance_reason",
    "ai_negative_signal",
    "sentence_sentiment",
    "keywords_found_json",
    "keyword_context_json",
    "classification_explanation",
    "final_decision",
]



FAILED_COLUMNS = [
    "company_name",
    "ticker",
    "CIK",
    "form_type",
    "filing_date",
    "accession_number",
    "filing_url",
]


# ============================================================
# 3. HELPER FUNCTIONS
# ============================================================

def setup_logging(output_folder: Path) -> None:
    output_folder.mkdir(parents=True, exist_ok=True)
    log_file = output_folder / "ai_extraction_log.txt"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = str(text)
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\xa0", " ")
    text = text.replace("•", ". ")
    text = text.replace("●", ". ")
    text = text.replace("▪", ". ")
    text = text.replace("–", "-")
    text = text.replace("—", "-")

    return text.strip()


def split_sentences(text: str) -> List[str]:
    text = clean_text(text)

    if not text:
        return []

    abbreviations = {
        "inc.", "corp.", "co.", "ltd.", "llc.", "u.s.", "u.k.",
        "e.g.", "i.e.", "mr.", "mrs.", "ms.", "dr.", "no.",
        "fig.", "vs.", "etc.", "jan.", "feb.", "mar.", "apr.",
        "jun.", "jul.", "aug.", "sep.", "sept.", "oct.", "nov.", "dec."
    }

    raw_parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text)

    sentences = []
    buffer = ""

    for part in raw_parts:
        part = part.strip()
        if not part:
            continue

        candidate = buffer + " " + part if buffer else part
        tokens = candidate.split()
        last_token = tokens[-1].lower() if tokens else ""

        if last_token in abbreviations:
            buffer = candidate
            continue

        if len(tokens) < 3:
            buffer = candidate
            continue

        sentences.append(candidate.strip())
        buffer = ""

    if buffer:
        sentences.append(buffer.strip())

    return sentences


def count_total_words(text: str) -> int:
    if not text:
        return 0

    cleaned = clean_text(text)
    words = re.findall(r"\b[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*\b", cleaned)

    return len(words)


def html_to_text(html: str) -> str:
    if not html:
        return ""

    html = str(html)

    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    html = re.sub(r"(?is)<head.*?>.*?</head>", " ", html)

    html = re.sub(r"(?i)<br\s*/?>", " ", html)
    html = re.sub(
        r"(?i)</(p|div|tr|td|th|li|table|section|article|h[1-6])>",
        " ",
        html,
    )

    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = unescape(text)

    return clean_text(text)


def safe_ratio(numerator: int, denominator: int, multiplier: float = 1.0) -> float:
    if not denominator:
        return 0.0
    return round((float(numerator) / float(denominator)) * multiplier, 10)


def lower(text: str) -> str:
    return text.lower() if isinstance(text, str) else ""


def normalize_for_matching(text: str) -> str:
    text = lower(clean_text(text))
    text = text.replace("‐", "-").replace("‒", "-")
    text = re.sub(r"\s+", " ", text)
    return text


def contains_term(text_low: str, term: str) -> bool:
    term_low = term.lower().strip()
    term_low = re.sub(r"\s+", " ", term_low)

    if not term_low:
        return False

    if re.fullmatch(r"[a-z0-9]+", term_low):
        return re.search(rf"\b{re.escape(term_low)}\b", text_low) is not None

    return re.search(re.escape(term_low), text_low) is not None


def count_one_keyword_occurrences(text: str, keyword: str) -> int:
    if not text or not keyword:
        return 0

    text_low = normalize_for_matching(text)
    keyword_low = keyword.lower().strip()
    keyword_low = re.sub(r"\s+", " ", keyword_low)

    if re.fullmatch(r"[a-z0-9]+", keyword_low):
        return len(re.findall(rf"\b{re.escape(keyword_low)}\b", text_low))

    return len(re.findall(re.escape(keyword_low), text_low))


def find_terms(text: str, terms: Iterable[str]) -> List[str]:
    text_low = normalize_for_matching(text)
    found = []

    for term in terms:
        if contains_term(text_low, term):
            found.append(term)

    return sorted(set(found))


def count_keyword_occurrences(text: str, terms: Iterable[str]) -> int:
    total = 0

    for term in set(terms):
        total += count_one_keyword_occurrences(text, term)

    return total


def count_ai_keywords(text: str, keywords: Iterable[str]) -> Dict[str, int]:
    counts = {}

    for keyword in keywords:
        c = count_one_keyword_occurrences(text, keyword)
        if c > 0:
            counts[keyword] = c

    return counts


def unique_join(items: Iterable[str]) -> str:
    return "; ".join(sorted(set([str(x).strip() for x in items if str(x).strip()])))


def safe_get(d: Dict, keys: List[str], default: str = "") -> str:
    for key in keys:
        val = d.get(key)
        if val not in [None, "", "None"]:
            return str(val)
    return default


def normalize_cik(cik: str) -> str:
    if cik in [None, ""]:
        return ""

    digits = re.sub(r"\D", "", str(cik))

    return digits.zfill(10) if digits else ""


def guess_fiscal_year(filing: Dict) -> str:
    period = safe_get(filing, ["periodOfReport", "period_of_report", "reportDate"], "")

    if period and re.match(r"\d{4}", period):
        return period[:4]

    filed = safe_get(filing, ["filedAt", "filed_at"], "")

    if filed and re.match(r"\d{4}", filed):
        return filed[:4]

    return ""

SEC_SUBMISSIONS_CACHE: Dict[str, Dict[str, str]] = {}


def fetch_sec_submission_metadata(
    cik: str,
    user_agent: str = "",
    max_retries: int = 3,
    sleep_seconds: float = 0.15,
) -> Dict[str, str]:
    """
    Fetch public company metadata from the official SEC submissions endpoint.

    This can help fill SIC CODE and SEC SIC Description when sec-api.io
    metadata is empty. It does not provide true TRBC or ISIN.

    Endpoint used:
        https://data.sec.gov/submissions/CIK##########.json
    """
    cik_norm = normalize_cik(cik)

    if not cik_norm:
        return {}

    if cik_norm in SEC_SUBMISSIONS_CACHE:
        return SEC_SUBMISSIONS_CACHE[cik_norm]

    url = f"https://data.sec.gov/submissions/CIK{cik_norm}.json"

    headers = {
        "User-Agent": user_agent or "academic-research-contact@example.com",
        "Accept-Encoding": "gzip, deflate",
    }

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            tickers = data.get("tickers", [])
            exchanges = data.get("exchanges", [])

            if isinstance(tickers, list):
                tickers_text = "; ".join([str(x) for x in tickers if str(x).strip()])
            else:
                tickers_text = str(tickers or "")

            if isinstance(exchanges, list):
                exchanges_text = "; ".join([str(x) for x in exchanges if str(x).strip()])
            else:
                exchanges_text = str(exchanges or "")

            out = {
                "SIC CODE": str(data.get("sic", "") or ""),
                "SEC SIC Description": str(data.get("sicDescription", "") or ""),
                "SEC entityType": str(data.get("entityType", "") or ""),
                "SEC tickers": tickers_text,
                "SEC exchanges": exchanges_text,
                "metadata_source": "SEC submissions API",
            }

            SEC_SUBMISSIONS_CACHE[cik_norm] = out
            time.sleep(sleep_seconds)
            return out

        except Exception as e:
            last_error = e
            wait = min(10, attempt * 2)
            logging.warning(
                f"SEC metadata lookup failed for CIK {cik_norm} "
                f"attempt {attempt}/{max_retries}: {e}. Waiting {wait}s..."
            )
            time.sleep(wait)

    logging.warning(f"SEC metadata lookup failed permanently for CIK {cik_norm}: {last_error}")
    SEC_SUBMISSIONS_CACHE[cik_norm] = {}
    return {}


def merge_online_metadata(
    base_meta: Dict[str, str],
    online_meta: Dict[str, str],
    fill_trbc_with_sec_sic_description: bool = False,
) -> Dict[str, str]:
    """
    Merge online SEC metadata into the filing metadata without overwriting
    good existing values unless the existing value is empty.

    Note:
    - SEC can provide SIC and SIC Description.
    - SEC does not provide true TRBC Industry Name or ISIN.
    - If fill_trbc_with_sec_sic_description=True, the script copies
      SEC SIC Description into TRBC Industry Name when TRBC is empty.
      This is a convenience label, not true Refinitiv TRBC.
    """
    if not online_meta:
        return base_meta

    if not str(base_meta.get("SIC CODE", "")).strip() and online_meta.get("SIC CODE"):
        base_meta["SIC CODE"] = online_meta["SIC CODE"]

    for col in ["SEC SIC Description", "SEC entityType", "SEC tickers", "SEC exchanges", "metadata_source"]:
        if not str(base_meta.get(col, "")).strip() and online_meta.get(col):
            base_meta[col] = online_meta[col]

    if fill_trbc_with_sec_sic_description:
        if not str(base_meta.get("TRBC Industry Name", "")).strip() and online_meta.get("SEC SIC Description"):
            base_meta["TRBC Industry Name"] = online_meta["SEC SIC Description"]

    base_meta["ff12_industry"] = map_sic_to_ff12(base_meta.get("SIC CODE", ""))

    return base_meta



def sic_to_int(sic_value: str) -> Optional[int]:
    if sic_value in [None, ""]:
        return None

    digits = re.sub(r"\D", "", str(sic_value))

    if not digits:
        return None

    try:
        return int(digits)
    except Exception:
        return None


def map_sic_to_ff12(sic_value: str) -> str:
    """
    SIC Code
    """
    sic = sic_to_int(sic_value)

    if sic is None:
        return ""

    if (
        100 <= sic <= 999 or
        2000 <= sic <= 2399 or
        2700 <= sic <= 2749 or
        2770 <= sic <= 2799 or
        3100 <= sic <= 3199 or
        3940 <= sic <= 3989
    ):
        return "Consumer NonDurables"

    if (
        2500 <= sic <= 2519 or
        2590 <= sic <= 2599 or
        3630 <= sic <= 3659 or
        3710 <= sic <= 3711 or
        sic == 3714 or
        sic == 3716 or
        3750 <= sic <= 3751 or
        sic == 3792 or
        3900 <= sic <= 3939 or
        3990 <= sic <= 3999
    ):
        return "Consumer Durables"

    if (
        2520 <= sic <= 2589 or
        2600 <= sic <= 2699 or
        2750 <= sic <= 2769 or
        3000 <= sic <= 3099 or
        3200 <= sic <= 3569 or
        3580 <= sic <= 3629 or
        3700 <= sic <= 3709 or
        3712 <= sic <= 3713 or
        sic == 3715 or
        3717 <= sic <= 3749 or
        3752 <= sic <= 3791 or
        3793 <= sic <= 3799 or
        3830 <= sic <= 3839 or
        3860 <= sic <= 3899
    ):
        return "Manufacturing"

    if (
        1200 <= sic <= 1399 or
        2900 <= sic <= 2999
    ):
        return "Energy"

    if (
        2800 <= sic <= 2829 or
        2840 <= sic <= 2899
    ):
        return "Chemicals"

    if (
        3570 <= sic <= 3579 or
        3660 <= sic <= 3692 or
        3694 <= sic <= 3699 or
        3810 <= sic <= 3829 or
        7370 <= sic <= 7379
    ):
        return "Business Equipment"

    if 4800 <= sic <= 4899:
        return "Telecom"

    if 4900 <= sic <= 4949:
        return "Utilities"

    if (
        5000 <= sic <= 5999 or
        7200 <= sic <= 7299 or
        7600 <= sic <= 7699
    ):
        return "Shops"

    if (
        2830 <= sic <= 2839 or
        sic == 3693 or
        3840 <= sic <= 3859 or
        8000 <= sic <= 8099
    ):
        return "Healthcare"

    if 6000 <= sic <= 6999:
        return "Finance"

    return "Other"


def create_csv_if_missing(path: Path, columns: List[str]) -> None:
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()


def ensure_csv_columns(path: Path, columns: List[str]) -> None:
    create_csv_if_missing(path, columns)

    try:
        existing_df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
        return
    except Exception as e:
        logging.warning(f"Could not verify CSV columns for {path}: {e}")
        return

    changed = False

    for col in columns:
        if col not in existing_df.columns:
            existing_df[col] = ""
            changed = True

    ordered_cols = columns + [col for col in existing_df.columns if col not in columns]

    if changed:
        existing_df = existing_df[ordered_cols]
        existing_df.to_csv(path, index=False, encoding="utf-8-sig")


def append_rows(path: Path, columns: List[str], rows: List[Dict]) -> None:
    if not rows:
        return

    ensure_csv_columns(path, columns)

    with path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        for row in rows:
            writer.writerow(row)


def load_processed_accessions(summary_path: Path) -> Set[str]:
    if not summary_path.exists():
        return set()

    try:
        df = pd.read_csv(summary_path, usecols=["accession_number"], dtype=str)
        return set(df["accession_number"].dropna().astype(str))
    except Exception:
        return set()


def read_universe_file(input_file: Optional[str]) -> Tuple[List[str], List[str]]:
    if not input_file:
        return [], []

    path = Path(input_file)

    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    if path.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str)

    ticker_cols = ["ticker", "Ticker", "(tic) Ticker Symbol", "tic", "TICKER"]
    cik_cols = ["CIK", "cik", "Central Index Key", "central_index_key"]

    tickers = []
    ciks = []

    for col in ticker_cols:
        if col in df.columns:
            tickers.extend(df[col].dropna().astype(str).str.strip().tolist())

    for col in cik_cols:
        if col in df.columns:
            ciks.extend(df[col].dropna().astype(str).str.strip().tolist())

    tickers = sorted(set([x.upper() for x in tickers if x and x.lower() != "nan"]))
    ciks = sorted(set([normalize_cik(x) for x in ciks if x and x.lower() != "nan"]))

    return tickers, ciks


# ============================================================
# 4. AI MATCHING, SENTIMENT, CONTEXT CLASSIFICATION, AND AUDIT
# ============================================================

def match_ai_sentence(sentence: str) -> Tuple[bool, List[str]]:
    matched_keywords = find_terms(sentence, AI_CLASSIFICATION_TERMS)
    return len(matched_keywords) > 0, matched_keywords


# Negative AI-use patterns:
# These patterns do NOT remove the sentence from the Mishra-style AI keyword count.
# They only classify the sentence context as negative, for example:
# "Using AI is not allowed in our company" -> Negative.
NEGATIVE_AI_USE_PATTERNS = [
    ("not_allowed_or_prohibited", r"\b(ai|artificial intelligence|machine learning|deep learning|automation|chatbot|algorithm|algorithms)\b.{0,90}\b(not allowed|not permitted|not authorized|prohibited|forbidden|banned|restricted|disallowed)\b"),
    ("not_allowed_or_prohibited", r"\b(not allowed|not permitted|not authorized|prohibited|forbidden|banned|restricted|disallowed)\b.{0,90}\b(ai|artificial intelligence|machine learning|deep learning|automation|chatbot|algorithm|algorithms)\b"),
    ("do_not_use", r"\b(do not|does not|did not|will not|would not|shall not|should not|cannot|can't|may not|must not)\b.{0,70}\b(use|using|utilize|utilizing|employ|employing|deploy|deploying|implement|implementing|adopt|adopting|apply|applying|rely on|relying on)\b.{0,100}\b(ai|artificial intelligence|machine learning|deep learning|automation|chatbot|algorithm|algorithms)\b"),
    ("do_not_use", r"\b(ai|artificial intelligence|machine learning|deep learning|automation|chatbot|algorithm|algorithms)\b.{0,100}\b(do not use|does not use|did not use|will not use|would not use|cannot use|can't use|not used|not utilize|not deploy|not implement|not adopt|not rely on)\b"),
    ("no_use_of_ai", r"\b(no use of|without using|without the use of|free from|absence of)\b.{0,80}\b(ai|artificial intelligence|machine learning|deep learning|automation|chatbot|algorithm|algorithms)\b"),
    ("ban_policy", r"\b(policy|policies|rule|rules|guideline|guidelines|company|employees|staff|users|contractors)\b.{0,140}\b(disallow|disallows|prohibit|prohibits|ban|bans|restrict|restricts|forbid|forbids)\b.{0,100}\b(ai|artificial intelligence|machine learning|deep learning|automation|chatbot|algorithm|algorithms)\b"),
    ("not_currently_using", r"\b(not currently|currently not|no longer|ceased|stopped|suspended)\b.{0,80}\b(use|using|utilizing|employing|deploying|implementing|adopting|applying)\b.{0,100}\b(ai|artificial intelligence|machine learning|deep learning|automation|chatbot|algorithm|algorithms)\b"),
]


# Positive AI-use patterns:
# These identify sentences that indicate active use, adoption, deployment, or investment in AI.
POSITIVE_AI_USE_PATTERNS = [
    ("active_use", r"\b(use|using|uses|utilize|utilizes|utilizing|employ|employs|employing|leverage|leverages|leveraging|rely on|relies on|relying on)\b.{0,90}\b(ai|artificial intelligence|machine learning|deep learning|automation|chatbot|algorithm|algorithms)\b"),
    ("active_use", r"\b(ai|artificial intelligence|machine learning|deep learning|automation|chatbot|algorithm|algorithms)\b.{0,90}\b(is used|are used|used to|used for|supports|support|powers|powered by|enabled by|drives|drive)\b"),
    ("adoption_or_deployment", r"\b(adopt|adopts|adopted|adopting|deploy|deploys|deployed|deploying|implement|implements|implemented|implementing|integrate|integrates|integrated|integrating)\b.{0,100}\b(ai|artificial intelligence|machine learning|deep learning|automation|chatbot|algorithm|algorithms)\b"),
    ("investment_or_development", r"\b(invest|invests|invested|investing|develop|develops|developed|developing|build|builds|built|building)\b.{0,100}\b(ai|artificial intelligence|machine learning|deep learning|automation|chatbot|algorithm|algorithms)\b"),
    ("capability_or_platform", r"\b(our|the company|we)\b.{0,120}\b(ai|artificial intelligence|machine learning|deep learning|automation|chatbot|algorithm|algorithms)\b.{0,120}\b(capability|capabilities|platform|system|systems|solution|solutions|tool|tools|model|models|technology|technologies)\b"),
    ("genai_use", r"\b(use|using|uses|utilize|utilizes|utilizing|leverage|leverages|leveraging|deploy|deploys|deployed|implement|implements|implemented|adopt|adopts|adopted|integrate|integrates|integrated)\b.{0,120}\b(generative ai|genai|large language model|large language models|llm|llms|foundation model|foundation models|chatgpt|gpt|copilot|ai assistant|ai-powered|ai-enabled|ai-driven)\b"),
    ("genai_use", r"\b(generative ai|genai|large language model|large language models|llm|llms|foundation model|foundation models|chatgpt|gpt|copilot|ai assistant|ai-powered|ai-enabled|ai-driven)\b.{0,120}\b(is used|are used|used to|used for|supports|support|powers|powered by|enabled by|drives|drive|improves|improve|automates|automate)\b"),
    ("production_or_operations", r"\b(production|operations|operational|commercial|customer service|fraud detection|risk management|marketing|sales|supply chain|software|platform|product|products|service|services)\b.{0,140}\b(ai|artificial intelligence|machine learning|deep learning|generative ai|genai|llm|llms|automation|chatbot|algorithm|algorithms)\b"),
]


def _find_signal_names(sentence: str, patterns: Iterable[Tuple[str, str]]) -> List[str]:
    sentence_low = normalize_for_matching(sentence)
    signal_names = []
    for signal_name, pattern in patterns:
        if re.search(pattern, sentence_low):
            signal_names.append(signal_name)
    return sorted(set(signal_names))


def classify_ai_sentence_structured(sentence: str, matched_keywords: Iterable[str]) -> Dict:
    """
    Rule-based version of the classification prompt supplied by the user.

    Output shape:
    {
      "sentiment": "Positive/Negative/Neutral",
      "keywords_found": ["keyword1", "keyword2"],
      "keyword_context": {"keyword1": "Positive", "keyword2": "Negative"},
      "explanation": "Brief explanation of the classification."
    }

    Important:
    - This is deterministic and does not call an external LLM/API.
    - It only helps separate AI-keyword sentences into positive, negative, and neutral contexts. It also recognizes standalone "AI" for sentence classification, without changing the Mishra-style AI Focus numerator.
    """
    keywords_found = sorted(set([str(k).strip() for k in matched_keywords if str(k).strip()]))

    if not keywords_found:
        return {
            "sentiment": "Neutral",
            "keywords_found": [],
            "keyword_context": {},
            "explanation": "No AI keyword from the dictionary was found in the sentence."
        }

    negative_signals = _find_signal_names(sentence, NEGATIVE_AI_USE_PATTERNS)
    positive_signals = _find_signal_names(sentence, POSITIVE_AI_USE_PATTERNS)

    if negative_signals:
        sentiment = "Negative"
        explanation = (
            "The sentence contains AI keyword(s), but the surrounding language indicates non-use, prohibition, "
            "restriction, or lack of authorization. Signals: " + unique_join(negative_signals) + "."
        )
    elif positive_signals:
        sentiment = "Positive"
        explanation = (
            "The sentence contains AI keyword(s) and the surrounding language indicates active use, adoption, "
            "deployment, investment, or development. Signals: " + unique_join(positive_signals) + "."
        )
    else:
        sentiment = "Neutral"
        explanation = (
            "The sentence contains AI keyword(s), but the surrounding language does not clearly confirm active use "
            "or non-use/prohibition."
        )

    keyword_context = {keyword: sentiment for keyword in keywords_found}

    return {
        "sentiment": sentiment,
        "keywords_found": keywords_found,
        "keyword_context": keyword_context,
        "explanation": explanation
    }


def classify_ai_sentence(sentence: str, matched_keywords: Iterable[str]) -> Tuple[str, str, str, str, str, str, str]:
    """
    Backward-compatible classification output used in CSV columns.

    Returns:
    ai_use_classification, ai_use_polarity, ai_negative_signal,
    sentence_sentiment, keywords_found_json, keyword_context_json, classification_explanation
    """
    result = classify_ai_sentence_structured(sentence, matched_keywords)
    sentiment = result["sentiment"]

    negative_signal = unique_join(_find_signal_names(sentence, NEGATIVE_AI_USE_PATTERNS))

    if sentiment == "Negative":
        ai_use_classification = "negative_ai_reference"
        ai_use_polarity = "negative"
    elif sentiment == "Positive":
        ai_use_classification = "positive_ai_reference"
        ai_use_polarity = "positive"
    else:
        ai_use_classification = "neutral_ai_reference"
        ai_use_polarity = "neutral"

    return (
        ai_use_classification,
        ai_use_polarity,
        negative_signal,
        sentiment,
        json.dumps(result["keywords_found"], ensure_ascii=False),
        json.dumps(result["keyword_context"], ensure_ascii=False),
        result["explanation"],
    )



def classify_ai_relevance(sentence: str, matched_keywords: Iterable[str]) -> Tuple[str, int, str]:
    """
    Classify an AI-keyword sentence as relevant or irrelevant to the firm's AI experience/use.

    Relevant means the sentence confirms that the reporting company has experienced,
    used, deployed, adopted, developed, integrated, invested in, or operationalized AI.

    Irrelevant means the sentence only mentions AI without confirming firm use, or says
    the company does not use/allow/experience AI, or discusses AI as a general external
    risk, competitor trend, future possibility, regulation, or third-party issue.

    Returns:
    ai_relevance_classification, ai_relevance_binary, ai_relevance_reason
    """
    result = classify_ai_sentence_structured(sentence, matched_keywords)
    sentiment = result.get("sentiment", "Neutral")

    positive_signals = _find_signal_names(sentence, POSITIVE_AI_USE_PATTERNS)
    negative_signals = _find_signal_names(sentence, NEGATIVE_AI_USE_PATTERNS)

    if negative_signals:
        return (
            "irrelevant_ai_reference",
            0,
            "The sentence mentions AI keyword(s), but it states non-use, prohibition, restriction, or lack of authorization. Signals: "
            + unique_join(negative_signals)
            + "."
        )

    if sentiment == "Positive" and positive_signals:
        return (
            "relevant_ai_use",
            1,
            "The sentence reports company AI experience/use, such as use, adoption, deployment, development, integration, investment, or operational application. Signals: "
            + unique_join(positive_signals)
            + "."
        )

    return (
        "irrelevant_ai_reference",
        0,
        "The sentence contains AI keyword(s), but it does not clearly confirm that the reporting company uses, experiences, deploys, adopts, develops, or operationalizes AI."
    )

def build_ai_keyword_audit(sentence: str, sentence_id: int, filing_meta: Dict) -> List[Dict]:
    rows = []
    matched_keywords = find_terms(sentence, AI_CLASSIFICATION_TERMS)

    if not matched_keywords:
        return rows

    (
        ai_use_classification,
        ai_use_polarity,
        ai_negative_signal,
        sentence_sentiment,
        keywords_found_json,
        keyword_context_json,
        classification_explanation,
    ) = classify_ai_sentence(sentence, matched_keywords)

    (
        ai_relevance_classification,
        ai_relevance_binary,
        ai_relevance_reason,
    ) = classify_ai_relevance(sentence, matched_keywords)

    for keyword in matched_keywords:
        rows.append({
            **filing_meta,
            "sentence_id": sentence_id,
            "sentence_text": sentence,
            "tested_rule": "AI keyword dictionary",
            "matched_main_term": keyword,
            "matched_relevant": keyword,
            "matched_irrelevant": "",
            "ai_use_classification": ai_use_classification,
            "ai_use_polarity": ai_use_polarity,
            "ai_relevance_classification": ai_relevance_classification,
            "ai_relevance_binary": ai_relevance_binary,
            "ai_relevance_reason": ai_relevance_reason,
            "ai_negative_signal": ai_negative_signal,
            "sentence_sentiment": sentence_sentiment,
            "keywords_found_json": keywords_found_json,
            "keyword_context_json": keyword_context_json,
            "classification_explanation": classification_explanation,
            "final_decision": "ai_keyword_hit",
        })

    return rows


# ============================================================
# 5. SEC API CLIENT
# ============================================================

@dataclass
class SecApiClient:
    api_key: str
    sleep_seconds: float = 0.15
    max_retries: int = 3
    user_agent: str = ""

    def __post_init__(self):
        self.query_api = QueryApi(api_key=self.api_key)

    def _retry(self, func, *args, **kwargs):
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                time.sleep(self.sleep_seconds)
                return result
            except Exception as e:
                last_error = e
                wait = min(30, attempt * 3)
                logging.warning(
                    f"API attempt {attempt}/{self.max_retries} failed: {e}. Waiting {wait}s..."
                )
                time.sleep(wait)

        raise last_error

    @staticmethod
    def build_forms_query(forms: List[str]) -> str:
        form_parts = [f'formType:"{form}"' for form in forms]
        return "(" + " OR ".join(form_parts) + ")"

    def search_filings(
        self,
        forms: List[str],
        start_year: int,
        end_year: int,
        max_filings: int,
        batch_size: int,
        tickers: Optional[List[str]] = None,
        ciks: Optional[List[str]] = None,
        all_companies: bool = False,
    ) -> List[Dict]:

        if not all_companies and not tickers and not ciks:
            raise ValueError(
                "You must provide --all-companies, --tickers, --ciks, or --input-file."
            )

        forms_query = self.build_forms_query(forms)
        batch_size = min(batch_size, 50)

        all_results: List[Dict] = []
        search_units = []

        if all_companies:
            search_units.append(("ALL", ""))
        else:
            for ticker in tickers or []:
                search_units.append(("TICKER", f'ticker:{ticker}'))

            for cik in ciks or []:
                cik_digits = normalize_cik(cik)
                if cik_digits:
                    search_units.append(("CIK", f'cik:{int(cik_digits)}'))

        for unit_type, unit_query in search_units:
            for year in range(end_year, start_year - 1, -1):
                if len(all_results) >= max_filings:
                    break

                offset = 0

                while len(all_results) < max_filings:
                    remaining = max_filings - len(all_results)
                    size = min(batch_size, remaining)

                    date_query = f'filedAt:[{year}-01-01 TO {year}-12-31]'

                    amended_filter = (
                        'NOT formType:"10-K/A" '
                        'AND NOT formType:"10-K405/A" '
                        'AND NOT formType:"10-KSB40/A" '
                        'AND NOT formType:"10-KSB/A"'
                    )

                    query_parts = [forms_query, date_query, amended_filter]

                    if unit_query:
                        query_parts.insert(0, unit_query)

                    lucene_query = " AND ".join(query_parts)

                    query = {
                        "query": lucene_query,
                        "from": str(offset),
                        "size": str(size),
                        "sort": [{"filedAt": {"order": "desc"}}],
                    }

                    logging.info(
                        f"Searching API: unit={unit_type} | year={year} | offset={offset} | size={size}"
                    )

                    response = self._retry(self.query_api.get_filings, query)
                    filings = response.get("filings", []) if isinstance(response, dict) else []

                    if not filings:
                        break

                    all_results.extend(filings)

                    if len(filings) < size:
                        break

                    offset += size

                    if offset >= 10000:
                        logging.warning(
                            f"Reached offset 10,000 for year {year}. Moving to previous year."
                        )
                        break

        seen = set()
        unique_results = []

        for filing in all_results:
            acc = safe_get(
                filing,
                ["accessionNo", "accession_number", "accessionNumber"],
                "",
            )

            if not acc:
                acc = safe_get(filing, ["id"], "")

            if acc in seen:
                continue

            seen.add(acc)
            unique_results.append(filing)

        return unique_results[:max_filings]

    def extract_full_filing_text(self, filing_url: str) -> str:
        if not filing_url:
            return ""

        headers = {
            "User-Agent": self.user_agent or "academic-research-contact@example.com",
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov" if "sec.gov" in filing_url.lower() else "",
        }

        headers = {k: v for k, v in headers.items() if v}

        def _download():
            response = requests.get(filing_url, headers=headers, timeout=60)
            response.raise_for_status()
            return response.text

        raw_text = self._retry(_download)

        return html_to_text(raw_text)


# ============================================================
# 6. FILING PROCESSOR
# ============================================================

def get_filing_metadata(
    filing: Dict,
    user_agent: str = "",
    enrich_online: bool = False,
    fill_trbc_with_sec_sic_description: bool = False,
) -> Dict:
    company_name = safe_get(filing, ["companyName", "company_name", "name"], "")
    ticker = safe_get(filing, ["ticker", "tickerSymbol"], "")
    cik = normalize_cik(safe_get(filing, ["cik", "CIK"], ""))
    sic_code = safe_get(filing, ["sic", "SIC"], "")
    ff12_industry = map_sic_to_ff12(sic_code)

    form_type = safe_get(filing, ["formType", "form_type"], "")
    filing_date = safe_get(filing, ["filedAt", "filed_at"], "")
    accession_number = safe_get(
        filing,
        ["accessionNo", "accession_number", "accessionNumber"],
        "",
    )
    filing_url = safe_get(
        filing,
        ["linkToFilingDetails", "linkToHtml", "filingUrl", "url"],
        "",
    )
    report_date = safe_get(filing, ["periodOfReport", "reportDate"], "")
    fiscal_year = guess_fiscal_year(filing)

    file_name = f"{ticker or cik}_{fiscal_year}_{form_type}_{accession_number}"
    file_name = file_name.replace("/", "-").replace("\\", "-").replace(" ", "_")

    meta = {
        "Identifier (RIC)": "",
        "company_name": company_name,
        "ticker": ticker,
        "CIK": cik,
        "TRBC Industry Name": "",
        "SIC CODE": sic_code,
        "SEC SIC Description": "",
        "SEC entityType": "",
        "SEC tickers": "",
        "SEC exchanges": "",
        "metadata_source": "sec-api.io filing metadata" if sic_code else "",
        "ff12_industry": ff12_industry,
        "isin": "",
        "country_name": "United States",
        "fiscal_year": fiscal_year,
        "reported_year": fiscal_year,
        "report_date": report_date,
        "form_type": form_type,
        "filing_date": filing_date,
        "accession_number": accession_number,
        "filing_url": filing_url,
        "file_name": file_name,
        "file_path": "",
        "language_guess": "en",
    }

    if enrich_online:
        online_meta = fetch_sec_submission_metadata(cik, user_agent=user_agent)
        meta = merge_online_metadata(
            meta,
            online_meta,
            fill_trbc_with_sec_sic_description=fill_trbc_with_sec_sic_description,
        )

    return meta


def empty_summary(meta: Dict, status: str) -> Dict:
    return {
        **meta,
        "total_words_in_report": 0,
        "ai_focus": 0.0,
        "ai_focus_reg": 0.0,
        "ai_unique_terms_found": 0,
        "total_sentences_in_report": 0,
        "total_sentences_that_have_keywords": 0,
        "direct_hits_count": 0,
        "indirect_hits_count": 0,
        "total_hits": 0,
        "positive_ai_sentence_count": 0,
        "negative_ai_sentence_count": 0,
        "neutral_ai_sentence_count": 0,
        "relevant_ai_sentence_count": 0,
        "irrelevant_ai_sentence_count": 0,
        "total_direct_keywords_found": 0,
        "total_indirect_keywords_found": 0,
        "total_keywords_found_in_report": 0,
        "positive_ai_keyword_count": 0,
        "negative_ai_keyword_count": 0,
        "neutral_ai_keyword_count": 0,
        "relevant_ai_keyword_count": 0,
        "irrelevant_ai_keyword_count": 0,
        "total_relevant_keywords_found": 0,
        "total_irrelevant_keywords_found": 0,
        "total_ai_keywords_found": 0,
        "direct_keywords_found": "",
        "triggering_keywords": "",
        "matched_relevant_terms": "",
        "matched_irrelevant_terms": "",
        "positive_ai_keywords_found": "",
        "negative_ai_keywords_found": "",
        "relevant_ai_keywords_found": "",
        "irrelevant_ai_keywords_found": "",
        "ai_keywords_found": "",
        "has_ai_disclosure": 0,
        "has_positive_ai_disclosure": 0,
        "has_negative_ai_disclosure": 0,
        "has_relevant_ai_disclosure": 0,
        "has_irrelevant_ai_disclosure": 0,
        "processing_status": status,
    }


def process_filing(
    client: SecApiClient,
    filing: Dict,
    output_folder: Path,
    save_text: bool = False,
    enrich_online: bool = False,
    fill_trbc_with_sec_sic_description: bool = False,
) -> Tuple[Dict, List[Dict], List[Dict], List[Dict], Optional[Dict]]:

    meta = get_filing_metadata(
        filing,
        user_agent=client.user_agent,
        enrich_online=enrich_online,
        fill_trbc_with_sec_sic_description=fill_trbc_with_sec_sic_description,
    )
    filing_url = meta["filing_url"]
    accession = meta["accession_number"]

    try:
        full_text = client.extract_full_filing_text(filing_url)

        if save_text:
            text_dir = output_folder / "full_10k_texts"
            text_dir.mkdir(parents=True, exist_ok=True)
            text_path = text_dir / f"{meta['file_name']}.txt"
            text_path.write_text(full_text, encoding="utf-8")
            meta["file_path"] = str(text_path)

        total_words = count_total_words(full_text)

        if total_words == 0:
            return empty_summary(meta, "NO_TEXT"), [], [], [], None

        keyword_counts = count_ai_keywords(full_text, AI_KEYWORDS)
        total_ai_keywords_found = sum(keyword_counts.values())
        ai_unique_terms_found = len(keyword_counts)

        ai_focus = safe_ratio(total_ai_keywords_found, total_words, multiplier=100)
        ai_focus_reg = round(ai_focus * 1000, 10)

        sentences = split_sentences(full_text)
        total_sentences = len(sentences)

        sentence_rows: List[Dict] = []
        audit_rows: List[Dict] = []
        all_ai_keywords = []
        positive_ai_keywords = []
        negative_ai_keywords = []
        neutral_ai_keywords = []
        relevant_ai_keywords = []
        irrelevant_ai_keywords = []

        audit_meta = {
            "company_name": meta["company_name"],
            "ticker": meta["ticker"],
            "CIK": meta["CIK"],
            "fiscal_year": meta["fiscal_year"],
            "form_type": meta["form_type"],
            "filing_date": meta["filing_date"],
            "accession_number": meta["accession_number"],
        }

        for i, sentence in enumerate(sentences, start=1):
            audit_rows.extend(build_ai_keyword_audit(sentence, i, audit_meta))

            is_ai_hit, matched_keywords = match_ai_sentence(sentence)

            if not is_ai_hit:
                continue

            sentence_keyword_count = count_keyword_occurrences(sentence, matched_keywords)

            (
                ai_use_classification,
                ai_use_polarity,
                ai_negative_signal,
                sentence_sentiment,
                keywords_found_json,
                keyword_context_json,
                classification_explanation,
            ) = classify_ai_sentence(
                sentence,
                matched_keywords,
            )

            (
                ai_relevance_classification,
                ai_relevance_binary,
                ai_relevance_reason,
            ) = classify_ai_relevance(
                sentence,
                matched_keywords,
            )

            all_ai_keywords.extend(matched_keywords)

            if ai_use_polarity == "positive":
                positive_ai_keywords.extend(matched_keywords)
            elif ai_use_polarity == "negative":
                negative_ai_keywords.extend(matched_keywords)
            else:
                neutral_ai_keywords.extend(matched_keywords)

            if ai_relevance_binary == 1:
                relevant_ai_keywords.extend(matched_keywords)
            else:
                irrelevant_ai_keywords.extend(matched_keywords)

            row = {
                **meta,
                "page_no": "",
                "sentence_id": i,
                "sentence_text": sentence,
                "ai_use_classification": ai_use_classification,
                "ai_use_polarity": ai_use_polarity,
                "ai_relevance_classification": ai_relevance_classification,
                "ai_relevance_binary": ai_relevance_binary,
                "ai_relevance_reason": ai_relevance_reason,
                "ai_negative_signal": ai_negative_signal,
                "sentence_sentiment": sentence_sentiment,
                "keywords_found_json": keywords_found_json,
                "keyword_context_json": keyword_context_json,
                "classification_explanation": classification_explanation,
                "hit_type": "direct",
                "triggering_keyword": unique_join(matched_keywords),
                "matched_relevant_terms": unique_join(matched_keywords),
                "matched_irrelevant_terms": "",
                "direct_keyword_count_in_sentence": sentence_keyword_count,
                "indirect_keyword_count_in_sentence": 0,
            }

            sentence_rows.append(row)

        direct_hits_count = len(sentence_rows)
        indirect_hits_count = 0
        total_hits = direct_hits_count

        positive_ai_sentence_count = sum(
            1 for row in sentence_rows
            if row.get("ai_use_polarity") == "positive"
        )
        negative_ai_sentence_count = sum(
            1 for row in sentence_rows
            if row.get("ai_use_polarity") == "negative"
        )
        neutral_ai_sentence_count = sum(
            1 for row in sentence_rows
            if row.get("ai_use_polarity") == "neutral"
        )

        relevant_ai_sentence_count = sum(
            1 for row in sentence_rows
            if int(row.get("ai_relevance_binary", 0) or 0) == 1
        )
        irrelevant_ai_sentence_count = sum(
            1 for row in sentence_rows
            if int(row.get("ai_relevance_binary", 0) or 0) == 0
        )

        total_direct_keywords_found = sum(
            int(row.get("direct_keyword_count_in_sentence", 0) or 0)
            for row in sentence_rows
        )

        positive_ai_keyword_count = sum(
            int(row.get("direct_keyword_count_in_sentence", 0) or 0)
            for row in sentence_rows
            if row.get("ai_use_polarity") == "positive"
        )
        negative_ai_keyword_count = sum(
            int(row.get("direct_keyword_count_in_sentence", 0) or 0)
            for row in sentence_rows
            if row.get("ai_use_polarity") == "negative"
        )
        neutral_ai_keyword_count = sum(
            int(row.get("direct_keyword_count_in_sentence", 0) or 0)
            for row in sentence_rows
            if row.get("ai_use_polarity") == "neutral"
        )

        relevant_ai_keyword_count = sum(
            int(row.get("direct_keyword_count_in_sentence", 0) or 0)
            for row in sentence_rows
            if int(row.get("ai_relevance_binary", 0) or 0) == 1
        )
        irrelevant_ai_keyword_count = sum(
            int(row.get("direct_keyword_count_in_sentence", 0) or 0)
            for row in sentence_rows
            if int(row.get("ai_relevance_binary", 0) or 0) == 0
        )

        total_indirect_keywords_found = 0

        total_keywords_found_in_report = total_ai_keywords_found
        total_relevant_keywords_found = total_ai_keywords_found
        total_irrelevant_keywords_found = 0
        for row in sentence_rows:
            row["total_words_in_report"] = total_words
            row["ai_focus"] = ai_focus
            row["ai_focus_reg"] = ai_focus_reg
            row["ai_unique_terms_found"] = ai_unique_terms_found
            row["total_sentences_in_report"] = total_sentences
            row["total_sentences_that_have_keywords"] = total_hits
            row["total_direct_keywords_found"] = total_direct_keywords_found
            row["total_indirect_keywords_found"] = total_indirect_keywords_found
            row["total_keywords_found_in_report"] = total_keywords_found_in_report
            row["positive_ai_keyword_count"] = positive_ai_keyword_count
            row["negative_ai_keyword_count"] = negative_ai_keyword_count
            row["neutral_ai_keyword_count"] = neutral_ai_keyword_count
            row["relevant_ai_keyword_count"] = relevant_ai_keyword_count
            row["irrelevant_ai_keyword_count"] = irrelevant_ai_keyword_count
            row["total_relevant_keywords_found"] = total_relevant_keywords_found
            row["total_irrelevant_keywords_found"] = total_irrelevant_keywords_found
            row["total_ai_keywords_found"] = total_ai_keywords_found

        summary = {
            **meta,
            "total_words_in_report": total_words,
            "ai_focus": ai_focus,
            "ai_focus_reg": ai_focus_reg,
            "ai_unique_terms_found": ai_unique_terms_found,
            "total_sentences_in_report": total_sentences,
            "total_sentences_that_have_keywords": total_hits,
            "direct_hits_count": direct_hits_count,
            "indirect_hits_count": indirect_hits_count,
            "total_hits": total_hits,
            "positive_ai_sentence_count": positive_ai_sentence_count,
            "negative_ai_sentence_count": negative_ai_sentence_count,
            "neutral_ai_sentence_count": neutral_ai_sentence_count,
            "relevant_ai_sentence_count": relevant_ai_sentence_count,
            "irrelevant_ai_sentence_count": irrelevant_ai_sentence_count,
            "total_direct_keywords_found": total_direct_keywords_found,
            "total_indirect_keywords_found": total_indirect_keywords_found,
            "total_keywords_found_in_report": total_keywords_found_in_report,
            "positive_ai_keyword_count": positive_ai_keyword_count,
            "negative_ai_keyword_count": negative_ai_keyword_count,
            "neutral_ai_keyword_count": neutral_ai_keyword_count,
            "relevant_ai_keyword_count": relevant_ai_keyword_count,
            "irrelevant_ai_keyword_count": irrelevant_ai_keyword_count,
            "total_relevant_keywords_found": total_relevant_keywords_found,
            "total_irrelevant_keywords_found": total_irrelevant_keywords_found,
            "total_ai_keywords_found": total_ai_keywords_found,
            "direct_keywords_found": unique_join(all_ai_keywords),
            "triggering_keywords": unique_join(all_ai_keywords),
            "matched_relevant_terms": unique_join(all_ai_keywords),
            "matched_irrelevant_terms": "",
            "positive_ai_keywords_found": unique_join(positive_ai_keywords),
            "negative_ai_keywords_found": unique_join(negative_ai_keywords),
            "relevant_ai_keywords_found": unique_join(relevant_ai_keywords),
            "irrelevant_ai_keywords_found": unique_join(irrelevant_ai_keywords),
            "ai_keywords_found": unique_join(keyword_counts.keys()),
            "has_ai_disclosure": 1 if total_ai_keywords_found > 0 else 0,
            "has_positive_ai_disclosure": 1 if positive_ai_sentence_count > 0 else 0,
            "has_negative_ai_disclosure": 1 if negative_ai_sentence_count > 0 else 0,
            "has_relevant_ai_disclosure": 1 if relevant_ai_sentence_count > 0 else 0,
            "has_irrelevant_ai_disclosure": 1 if irrelevant_ai_sentence_count > 0 else 0,
            "processing_status": "OK",
        }

        keyword_rows: List[Dict] = []

        for keyword, count in sorted(keyword_counts.items()):
            keyword_rows.append({
                "Identifier (RIC)": meta["Identifier (RIC)"],
                "company_name": meta["company_name"],
                "ticker": meta["ticker"],
                "CIK": meta["CIK"],
                "TRBC Industry Name": meta["TRBC Industry Name"],
                "SIC CODE": meta["SIC CODE"],
                "SEC SIC Description": meta["SEC SIC Description"],
                "SEC entityType": meta["SEC entityType"],
                "SEC tickers": meta["SEC tickers"],
                "SEC exchanges": meta["SEC exchanges"],
                "metadata_source": meta["metadata_source"],
                "ff12_industry": meta["ff12_industry"],
                "isin": meta["isin"],
                "country_name": meta["country_name"],
                "fiscal_year": meta["fiscal_year"],
                "reported_year": meta["reported_year"],
                "report_date": meta["report_date"],
                "form_type": meta["form_type"],
                "filing_date": meta["filing_date"],
                "accession_number": meta["accession_number"],
                "filing_url": meta["filing_url"],
                "file_name": meta["file_name"],
                "file_path": meta["file_path"],
                "keyword": keyword,
                "keyword_count": count,
                "total_words_in_report": total_words,
                "total_ai_keywords_found": total_ai_keywords_found,
                "ai_unique_terms_found": ai_unique_terms_found,
                "ai_focus": ai_focus,
                "ai_focus_reg": ai_focus_reg,
            })

        logging.info(
            f"Processed {meta['company_name']} | {accession} | "
            f"AI keywords={total_ai_keywords_found} | unique AI terms={ai_unique_terms_found} | "
            f"AI sentences={total_hits} | words={total_words} | AI Focus={ai_focus}"
        )

        return summary, sentence_rows, keyword_rows, audit_rows, None

    except Exception as e:
        logging.exception(f"Failed processing {meta.get('company_name', '')} {accession}")

        failed = {
            "company_name": meta.get("company_name", ""),
            "ticker": meta.get("ticker", ""),
            "CIK": meta.get("CIK", ""),
            "form_type": meta.get("form_type", ""),
            "filing_date": meta.get("filing_date", ""),
            "accession_number": meta.get("accession_number", ""),
            "filing_url": meta.get("filing_url", ""),
        }

        return empty_summary(meta, "FAILED"), [], [], [], failed


# ============================================================
# 7. MAIN
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract AI Focus and AI keyword sentences from EDGAR filings using sec-api.io."
    )

    parser.add_argument(
        "--all-companies",
        action="store_true",
        help="Search all companies in SEC API for selected forms and date range.",
    )

    parser.add_argument(
        "--tickers",
        nargs="*",
        default=[],
        help="Optional list of tickers, e.g. --tickers AAPL MSFT NVDA",
    )

    parser.add_argument(
        "--ciks",
        nargs="*",
        default=[],
        help="Optional list of CIKs, e.g. --ciks 0000320193 0000789019",
    )

    parser.add_argument(
        "--input-file",
        default=None,
        help="Optional CSV/XLSX containing ticker or CIK columns.",
    )

    parser.add_argument(
        "--forms",
        nargs="+",
        default=["10-K", "10-K405", "10-KSB40"],
        help="Forms to extract. Default: 10-K 10-K405 10-KSB40.",
    )

    parser.add_argument(
        "--start-year",
        type=int,
        default=2005,
        help="Start filing year. Default: 2005.",
    )

    parser.add_argument(
        "--end-year",
        type=int,
        default=2019,
        help="End filing year. Default: 2019.",
    )

    parser.add_argument(
        "--max-filings",
        "--filings-limit",
        dest="max_filings",
        type=int,
        default=100,
        help="Maximum number of filings to process.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="SEC API query batch size. Max recommended: 50.",
    )

    parser.add_argument(
        "--output-folder",
        required=True,
        help="Folder where output CSVs and logs will be saved.",
    )

    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.15,
        help="Sleep seconds between API calls.",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum API retries.",
    )

    parser.add_argument(
        "--save-text",
        action="store_true",
        help="Save cleaned full 10-K text files.",
    )

    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not skip filings already found in ai_file_level_summary.csv.",
    )

    parser.add_argument(
        "--user-agent",
        default="",
        help="SEC user-agent/email, e.g. your email address.",
    )

    parser.add_argument(
        "--enrich-online",
        action="store_true",
        help="Fetch missing SIC metadata from the official SEC submissions API using CIK.",
    )

    parser.add_argument(
        "--fill-trbc-with-sec-sic-description",
        action="store_true",
        help=(
            "If TRBC Industry Name is empty, fill it with SEC SIC Description. "
            "This is not true Refinitiv TRBC, but it avoids a blank industry label."
        ),
    )

    return parser.parse_args()


def main():
    args = parse_args()

    output_folder = Path(args.output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    setup_logging(output_folder)

    api_key = os.getenv("SEC_API_KEY")

    if not api_key:
        raise RuntimeError(
            "SEC_API_KEY is missing. Set it first:\n"
            '  setx SEC_API_KEY "YOUR_API_KEY_HERE"\n'
            "Then close and reopen VS Code / Command Prompt."
        )

    summary_path = output_folder / "ai_file_level_summary.csv"
    sentence_path = output_folder / "ai_sentence_level_disclosures.csv"
    keyword_path = output_folder / "ai_keyword_level_counts.csv"
    audit_path = output_folder / "optional_ai_keyword_audit.csv"
    failed_path = output_folder / "failed_filings.csv"

    ensure_csv_columns(summary_path, FILE_LEVEL_COLUMNS)
    ensure_csv_columns(sentence_path, SENTENCE_LEVEL_COLUMNS)
    ensure_csv_columns(keyword_path, KEYWORD_LEVEL_COLUMNS)
    ensure_csv_columns(audit_path, AUDIT_COLUMNS)
    ensure_csv_columns(failed_path, FAILED_COLUMNS)

    input_tickers, input_ciks = read_universe_file(args.input_file)

    tickers = sorted(set([x.upper() for x in args.tickers] + input_tickers))
    ciks = sorted(set([normalize_cik(x) for x in args.ciks] + input_ciks))

    logging.info("============================================================")
    logging.info("AI Focus EDGAR API extractor started")
    logging.info("AI ONLY: no cybersecurity rules are used")
    logging.info(f"Number of AI keywords: {len(AI_KEYWORDS)}")
    logging.info(f"Forms: {args.forms}")
    logging.info(f"Years: {args.start_year} - {args.end_year}")
    logging.info(f"All companies: {args.all_companies}")
    logging.info(f"Tickers: {tickers[:20]}{'...' if len(tickers) > 20 else ''}")
    logging.info(f"CIKs: {ciks[:20]}{'...' if len(ciks) > 20 else ''}")
    logging.info(f"Max filings: {args.max_filings}")
    logging.info(f"Batch size: {args.batch_size}")
    logging.info(f"Output folder: {output_folder}")
    if args.user_agent:
        logging.info(f"User agent/email provided: {args.user_agent}")
    logging.info(f"Online SEC metadata enrichment: {args.enrich_online}")
    logging.info(f"Fill TRBC with SEC SIC Description: {args.fill_trbc_with_sec_sic_description}")
    logging.info("============================================================")

    client = SecApiClient(
        api_key=api_key,
        sleep_seconds=args.sleep_seconds,
        max_retries=args.max_retries,
        user_agent=args.user_agent,
    )

    filings = client.search_filings(
        forms=args.forms,
        start_year=args.start_year,
        end_year=args.end_year,
        max_filings=args.max_filings,
        batch_size=args.batch_size,
        tickers=tickers,
        ciks=ciks,
        all_companies=args.all_companies,
    )

    logging.info(f"Total unique filings found: {len(filings)}")

    processed_accessions = set()

    if not args.no_resume:
        processed_accessions = load_processed_accessions(summary_path)
        logging.info(
            f"Resume mode: {len(processed_accessions)} already processed filings found."
        )

    total_processed = 0
    total_skipped = 0
    total_failed = 0

    for filing in filings:
        accession = safe_get(
            filing,
            ["accessionNo", "accession_number", "accessionNumber"],
            "",
        )

        if accession and accession in processed_accessions:
            total_skipped += 1
            logging.info(f"Skipping already processed filing: {accession}")
            continue

        summary, sentence_rows, keyword_rows, audit_rows, failed = process_filing(
            client=client,
            filing=filing,
            output_folder=output_folder,
            save_text=args.save_text,
            enrich_online=args.enrich_online,
            fill_trbc_with_sec_sic_description=args.fill_trbc_with_sec_sic_description,
        )

        append_rows(summary_path, FILE_LEVEL_COLUMNS, [summary])
        append_rows(sentence_path, SENTENCE_LEVEL_COLUMNS, sentence_rows)
        append_rows(keyword_path, KEYWORD_LEVEL_COLUMNS, keyword_rows)
        append_rows(audit_path, AUDIT_COLUMNS, audit_rows)

        if failed:
            append_rows(failed_path, FAILED_COLUMNS, [failed])
            total_failed += 1

        total_processed += 1

        if total_processed % 25 == 0:
            logging.info(
                f"Progress: processed={total_processed}, "
                f"skipped={total_skipped}, failed={total_failed}"
            )

    logging.info("============================================================")
    logging.info("FINISHED")
    logging.info(f"Processed: {total_processed}")
    logging.info(f"Skipped: {total_skipped}")
    logging.info(f"Failed: {total_failed}")
    logging.info(f"Output file: {summary_path}")
    logging.info(f"Output file: {sentence_path}")
    logging.info(f"Output file: {keyword_path}")
    logging.info(f"Output file: {audit_path}")
    logging.info(f"Output file: {failed_path}")
    logging.info("============================================================")


if __name__ == "__main__":
    main()