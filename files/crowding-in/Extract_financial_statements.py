#!/usr/bin/env python3
"""Extract African company financial statement line items from PDFs to Excel.

Install: python -m pip install pymupdf openpyxl
Run:     python extract_africa_financials.py
Test:    python extract_africa_financials.py --limit 10

No network, search API, or CSV files. Does not automatically OCR scanned PDFs.
Every figure is a candidate requiring validation against its PDF source.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
import re
import sys
import unicodedata

import fitz  # PyMuPDF
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

DEFAULT_ROOT = Path(r"C:\Users\s180020\Desktop\Mine\Crowding_in\Africa_FS")
DEFAULT_OUTPUT = "Financial_Extraction_2000_2025.xlsx"
# Dictionary entries: variable, category, alternative names found in audited statements.
# Specific/long names have priority; short ambiguous labels deliberately omitted.
VARIABLES = {
"total_assets": ("Balance sheet", "total assets|assets total|total asset|asset total|assets, total|aggregate assets|total book assets|total asset value|assets (total)|total assets employed"),
"current_assets": ("Balance sheet", "total current assets|current assets total|current asset total|total short term assets|total short-term assets|current assets"),
"noncurrent_assets": ("Balance sheet", "total non current assets|total non-current assets|non current assets total|non-current assets|non current assets|total fixed assets"),
"cash_equivalents": ("Balance sheet", "cash and cash equivalents|cash & cash equivalents|cash and bank balances|bank and cash balances|cash at bank and in hand|cash in hand and at bank|cash and bank|cash and balances with banks|cash balances|cash equivalents"),
"short_term_investments": ("Balance sheet", "short term investments|short-term investments|current financial investments|marketable securities|short term deposits"),
"trade_receivables": ("Balance sheet", "trade and other receivables|trade receivables|accounts receivable|trade debtors|trade and sundry debtors|receivables from customers|trade debtors and other receivables"),
"inventories": ("Balance sheet", "inventories|inventory|stocks and work in progress|stock and work in progress|stock in trade|stock of goods|stocks"),
"ppe_net": ("Balance sheet", "property plant and equipment|property, plant and equipment|property plant & equipment|property, plant & equipment|net property plant and equipment|property and equipment net|tangible fixed assets|net tangible assets|fixed assets tangible|net ppe|ppe"),
"intangible_assets": ("Balance sheet", "intangible assets|intangible asset|other intangible assets|intangible fixed assets|intangible property"),
"goodwill": ("Balance sheet", "goodwill|goodwill on consolidation|purchased goodwill"),
"long_term_investments": ("Balance sheet", "long term investments|long-term investments|non current financial assets|non-current investments|investments in associates|investments in subsidiaries|other investments"),
"deferred_tax_assets": ("Balance sheet", "deferred tax assets|deferred tax asset|deferred taxation assets"),
"other_current_assets": ("Balance sheet", "other current assets|other short term assets|other short-term assets"),
"other_noncurrent_assets": ("Balance sheet", "other non current assets|other non-current assets|other long term assets"),
"total_liabilities": ("Balance sheet", "total liabilities|liabilities total|total liability|liabilities, total|aggregate liabilities"),
"current_liabilities": ("Balance sheet", "total current liabilities|current liabilities total|total short term liabilities|current liabilities|short term liabilities"),
"noncurrent_liabilities": ("Balance sheet", "total non current liabilities|total non-current liabilities|non current liabilities total|non current liabilities|non-current liabilities|long term liabilities"),
"short_term_debt": ("Debt", "short term borrowings|short-term borrowings|short term debt|short-term debt|current interest bearing borrowings|current bank loans|bank overdrafts|bank overdraft|short term loans|short-term loans|current loans and borrowings|loans and borrowings current"),
"long_term_debt": ("Debt", "long term borrowings|long-term borrowings|long term debt|long-term debt|non current loans and borrowings|non-current loans and borrowings|loans and borrowings non current|non-current bank loans|long term loans|long-term loans"),
"current_portion_ltd": ("Debt", "current portion of long term debt|current portion of long-term debt|current maturities of long term debt|current maturity of long-term borrowings|current portion of non-current borrowings"),
"bank_loans": ("Debt", "bank loans and advances|borrowings from banks|bank loans|bank borrowings|loans from banks|bank credit facilities|bank overdrafts and loans"),
"bonds_payable": ("Debt", "bonds payable|corporate bonds|notes payable|debentures|issued debt securities|listed bonds|senior notes|bonds and notes"),
"lease_liabilities_current": ("Debt", "current lease liabilities|lease liabilities current|current portion of lease liabilities|short term lease liabilities"),
"lease_liabilities_noncurrent": ("Debt", "non current lease liabilities|non-current lease liabilities|lease liabilities non current|long term lease liabilities"),
"trade_payables": ("Balance sheet", "trade and other payables|trade payables|accounts payable|trade creditors|trade and sundry creditors|amounts payable to suppliers"),
"related_party_borrowings": ("Debt", "loans from related parties|loans from group companies|borrowings from related parties|related party loans|loans from parent company|intercompany loans"),
"deferred_tax_liabilities": ("Balance sheet", "deferred tax liabilities|deferred tax liability|deferred taxation liability"),
"total_equity": ("Balance sheet", "total shareholders equity|total shareholder equity|total stockholders equity|total equity attributable to owners|shareholders funds|total equity|equity total|total capital and reserves"),
"common_equity": ("Balance sheet", "equity attributable to owners of the company|equity attributable to equity holders|equity attributable to owners|common shareholders equity|ordinary shareholders equity|equity attributable to shareholders"),
"share_capital": ("Balance sheet", "issued share capital|ordinary share capital|paid up capital|paid-up share capital|share capital|stated capital"),
"share_premium": ("Balance sheet", "share premium account|share premium|additional paid in capital|additional paid-in capital"),
"retained_earnings": ("Balance sheet", "retained earnings|retained profit|retained profits|accumulated profits|accumulated losses|revenue reserves"),
"reserves": ("Balance sheet", "other reserves|capital reserves|revaluation reserves|general reserves|statutory reserves"),
"noncontrolling_interest": ("Balance sheet", "non controlling interests|non-controlling interests|minority interest|minority interests"),
"revenue": ("Income statement", "revenue from contracts with customers|revenue from operations|net sales revenue|turnover from operations|net turnover|sales revenue|net revenue|net sales|total revenue|revenue|turnover"),
"gross_revenue": ("Income statement", "gross revenue|gross sales|gross turnover"),
"cost_of_sales": ("Income statement", "cost of goods sold|cost of sales|cost of revenue|cost of turnover|cost of services rendered|direct cost of sales|direct costs"),
"gross_profit": ("Income statement", "gross profit|gross income|gross operating profit|gross margin amount"),
"other_operating_income": ("Income statement", "other operating income|other income|other operating revenue"),
"selling_expenses": ("Income statement", "selling and distribution expenses|selling and marketing expenses|distribution and selling expenses|selling expenses|distribution expenses|marketing and distribution costs"),
"administrative_expenses": ("Income statement", "general and administrative expenses|administrative expenses|administration expenses|administrative costs|general administrative costs"),
"operating_expenses": ("Income statement", "other operating expenses|other operating costs|operating expenses|operational expenses"),
"operating_income": ("Income statement", "results from operating activities|profit from operating activities|profit from operations|operating profit before tax|operating profit|operating income|operating result|profit from ordinary activities before interest|earnings before interest and tax|earnings before interest and taxes|ebit"),
"depreciation": ("Income statement", "depreciation of property plant and equipment|depreciation expense|depreciation charge|depreciation of fixed assets|depreciation"),
"amortization": ("Income statement", "amortisation expense|amortization expense|amortisation of intangible assets|amortization of intangible assets|amortisation|amortization"),
"ebitda": ("Income statement", "earnings before interest taxes depreciation and amortization|earnings before interest tax depreciation and amortisation|adjusted ebitda|ebitda"),
"finance_income": ("Income statement", "finance income|financial income|interest income|investment income"),
"finance_costs": ("Income statement", "net finance costs|net finance cost|finance costs|financial expenses|borrowing costs|finance expenses|financing costs"),
"interest_expense": ("Income statement", "interest expenses|interest expense|interest on borrowings|interest paid on borrowings|finance charges on loans"),
"profit_before_tax": ("Income statement", "profit before income tax|profit before taxation|profit before tax|earnings before tax|profit before taxes|income before income tax|income before tax|pbt"),
"income_tax_expense": ("Income statement", "income tax expense|income tax expenses|taxation charge|tax expense|income tax charge|corporate income tax expense"),
"net_income": ("Income statement", "profit and total comprehensive income for the year|profit after income tax|profit after taxation|profit after tax|profit for the year|profit for the period|net profit after tax|net profit|net earnings|net income|earnings after tax"),
"total_comprehensive_income": ("Income statement", "total comprehensive income for the year|total comprehensive income|total comprehensive profit|total comprehensive loss"),
"earnings_per_share": ("Per share", "basic earnings per share|earnings per share basic|basic eps|earnings per share|eps basic"),
"diluted_eps": ("Per share", "diluted earnings per share|earnings per share diluted|diluted eps"),
"operating_cash_flow": ("Cash flow", "net cash generated from operating activities|net cash from operating activities|net cash provided by operating activities|net cash used in operating activities|cash flows from operating activities|cash flow from operations|cash flow from operating activities|operating cash flow"),
"investing_cash_flow": ("Cash flow", "net cash from investing activities|net cash used in investing activities|net cash generated from investing activities|cash flows from investing activities|investing cash flow"),
"financing_cash_flow": ("Cash flow", "net cash from financing activities|net cash used in financing activities|net cash generated from financing activities|cash flows from financing activities|financing cash flow"),
"capital_expenditure": ("Cash flow", "purchase of property plant and equipment|purchases of property plant and equipment|acquisition of property plant and equipment|additions to property plant and equipment|capital expenditures|capital expenditure|capital spending|purchase of fixed assets|purchases of fixed assets|capex"),
"acquisitions": ("Cash flow", "acquisition of subsidiaries|purchase of subsidiaries|business combinations acquisitions|acquisition of businesses|business acquisitions"),
"debt_issued": ("Cash flow", "proceeds from borrowings|proceeds from loans|new borrowings|loans received|proceeds from issue of debt|proceeds from bank loans|drawdown of borrowings"),
"debt_repaid": ("Cash flow", "repayment of borrowings|repayments of borrowings|repayment of loans|repayments of loans|loans repaid|repayment of bank loans|debt repayments"),
"interest_paid": ("Cash flow", "interest paid|finance costs paid|interest payments"),
"dividends_paid": ("Cash flow", "dividends paid|dividend paid|cash dividends paid|payment of dividends"),
"income_taxes_paid": ("Cash flow", "income tax paid|income taxes paid|taxes paid|corporation tax paid"),
"cash_beginning": ("Cash flow", "cash and cash equivalents at beginning of year|cash at beginning of the year|cash and cash equivalents at start of year|opening cash balance"),
"cash_ending": ("Cash flow", "cash and cash equivalents at end of year|cash and cash equivalents at end of period|closing cash balance|cash at end of the year"),
"net_change_cash": ("Cash flow", "net increase in cash and cash equivalents|net decrease in cash and cash equivalents|net change in cash and cash equivalents|increase in cash and cash equivalents"),
"shares_outstanding": ("Shares", "number of ordinary shares outstanding|ordinary shares in issue|shares outstanding|number of shares in issue|issued ordinary shares|issued shares"),
"weighted_avg_shares": ("Shares", "weighted average number of ordinary shares|weighted average shares outstanding|weighted average number of shares|weighted average ordinary shares"),
"dividend_per_share": ("Per share", "dividends per share|dividend per share|dividend per ordinary share|dps"),
"dividend_total": ("Shares", "total dividend declared|total dividends declared|dividend declared|dividends declared"),
"net_debt_reported": ("Debt", "net debt position|net debt|net indebtedness|net borrowings"),
"foreign_currency_debt": ("Debt", "foreign currency denominated borrowings|foreign currency borrowings|foreign currency debt|foreign currency loans"),
"domestic_bank_debt": ("Debt", "domestic bank loans|local bank borrowings|domestic bank borrowings|local currency bank loans"),
"usd_debt": ("Debt", "usd denominated loan|us dollar denominated debt|us dollar borrowings|usd loans"),
"secured_debt": ("Debt", "secured borrowings|secured bank loans|secured loans|secured debt"),
"unsecured_debt": ("Debt", "unsecured borrowings|unsecured bank loans|unsecured loans|unsecured debt"),
}
ALIAS_MAP = []
for variable, (category, names) in VARIABLES.items():
    for alias in names.split("|"):
        ALIAS_MAP.append((variable, category, alias))
ALIAS_MAP.sort(key=lambda a: len(a[2]), reverse=True)

NUMBER = re.compile(r"(?<![A-Za-z])(?:\(?-?\d{1,3}(?:[, .]\d{3})+(?:\.\d+)?\)?|\(?-?\d+(?:\.\d+)?\)?)(?![A-Za-z])")
YEAR = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
PER_SHARE = {"earnings_per_share", "diluted_eps", "dividend_per_share"}
NONMONETARY = {"shares_outstanding", "weighted_avg_shares"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).lower()
    s = s.replace("&", " and ").replace("’", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def parse_number(token):
    t = token.strip()
    negative = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(" ", "").replace(",", "")
    try:
        v = float(t)
        if abs(v) > 1e15:
            return None
        return -abs(v) if negative else v
    except ValueError:
        return None


def matched_label(line):
    """Require alias at start; do not match arbitrary prose in reports."""
    normalized = norm(line)
    for var, category, alias in ALIAS_MAP:
        a = norm(alias)
        if normalized == a or normalized.startswith(a + " "):
            return var, category, alias
    return None


def report_kind(text, filename):
    body = norm(text[:1100] + " " + filename)
    if re.search(r"\b(interim|half year|half yearly|first half|six months|6 months|quarterly|q1|q2|q3|nine months|unaudited interim)\b", norm(text[:250] + " " + filename)):
        return "INTERIM"
    if "press release" in body or "full year results" in body or "annual results" in body:
        return "ANNUAL_RELEASE"
    if "annual report" in body or "audited financial statements" in body:
        return "ANNUAL_REPORT"
    return "UNKNOWN_PERIOD"


def unit_info(text):
    s = norm(text[:7000])
    currency = "RWF" if re.search(r"\b(rwf|frw|rwandan francs|rwanda francs)\b", s) else "UNKNOWN"
    # Specific thousand notation from statement headings, not from arbitrary date or text.
    if re.search(r"\b(?:rwf|frw)\s*000\b|\bin thousands of (?:rwf|frw|rwandan francs)\b|\b(?:rwf|frw) thousands\b", s):
        return currency, 1000, "thousands"
    if re.search(r"\b(?:rwf|frw)\s*million(?:s)?\b|\b(?:rwf|frw)\s*mn\b|\bin millions of (?:rwf|frw)\b", s):
        return currency, 1000000, "millions"
    return currency, None, "UNKNOWN_SCALE"


def find_year_columns(lines, default_year):
    """Capture comparative year headers; do not infer from PDF publication date."""
    for line in lines[:45]:
        ys = [int(x) for x in YEAR.findall(line)]
        ys = list(dict.fromkeys(y for y in ys if 2000 <= y <= 2025))
        if len(ys) >= 2 and len(line) < 170 :
            return ys[:2]
    return [default_year] if default_year else []


def document_year(first_pages):
    header = " ".join(first_pages[:2])[:8500]
    patterns = [
        r"(?:year|period) ended\s+(?:on\s+)?(?:\d{1,2}\s+)?(?:december|march|june|september|january|february|april|may|july|august|october|november)\s+(20\d{2})",
        r"(?:for the year ended|for the period ended)\s+\d{1,2}\s+\w+\s+(20\d{2})",
        r"\breports?\s+(20\d{2})\s+(?:full year|annual|financial year)\b",
        r"\b(20\d{2})\s+full year results\b",
        r"annual results for the period to\s+\d{1,2}(?:st|nd|rd|th)?\s+december[,]?\s*(20\d{2})",
    ]
    for p in patterns:
        found = re.search(p, header, re.I)
        if found:
            return int(found.group(1))
    return None


def company_from_filename(pdf):
    title = re.sub(r"\([^)]*\)", " ", pdf.stem)
    title = re.sub(r"(?:annual report|financial statements?|audited accounts?|full year results?|\b20\d\d\b)", " ", title, flags=re.I)
    return re.sub(r"\s+", " ", title.replace("_", " ")).strip(" -_.") or pdf.stem


def match_company(filename, known):
    raw = company_from_filename(filename)
    if not known:
        return raw, "FILENAME_ONLY"
    n = norm(raw)
    candidates = [(SequenceMatcher(None, n, norm(k)).ratio(), k) for k in known]
    score, winner = max(candidates, default=(0, raw))
    return (winner, "MASTER_MATCH") if score >= .78 else (raw, "FILENAME_ONLY_REVIEW")


def load_company_master(base):
    known = {}
    for file in (base / "Private_Companies.xlsx", base / "Public_Companies.xlsx"):
        if not file.exists():
            continue
        from openpyxl import load_workbook
        wb = load_workbook(file, read_only=True, data_only=True)
        it = wb.active.iter_rows(values_only=True)
        header = [str(x).strip() if x else "" for x in next(it, [])]
        if "Company" in header:
            idx = header.index("Company")
            for row in it:
                if idx < len(row) and row[idx]:
                    known[str(row[idx]).strip()] = True
        wb.close()
    return list(known)


def extract_rows(page):
    """Use selectable PDF text. Extract line items, not narrative paragraph numbers."""
    text = page.get_text("text", sort=True) or ""
    return [line.strip() for line in text.splitlines() if line.strip()], text


def find_candidates(lines, years, pdf, page_no, company, company_flag, kind, currency, factor, scale_name):
    """Require two year-headed financial columns. Avoid prose, percentages and note numbers."""
    out=[]
    # A year header with two year columns is the safety gate for automatic numeric parsing.
    if len(years) < 2:
        return out
    for i, line in enumerate(lines):
        hit = matched_label(line)
        if not hit:
            continue
        var, group, alias = hit
        # Don't accept narrative lines. Balance-sheet labels are followed by aligned figures.
        # A change-percent column, where present, is *not* a fiscal year.
        trimmed = re.sub(r"\s+\(?-?\d+(?:\.\d+)?\)?\s*%\s*$", "", line)
        m = re.search(r"\s{2,}(?=\(?-?\d)", trimmed)
        if m is None:
            continue
        label, figures = trimmed[:m.start()].strip(), trimmed[m.end():]
        # Ensure a specific accounting label rather than a sentence or subtotal prose.
        if len(label) > 95 or re.search(r"[.;:]", label):
            continue
        if not (norm(label)==norm(alias) or norm(label).startswith(norm(alias)+" ")):
            continue
        tokens = [parse_number(x.group()) for x in NUMBER.finditer(figures)]
        values = [x for x in tokens if x is not None]
        if len(values)<len(years):
            continue
        # A note reference may precede values, but the leftmost of the last N are the year columns.
        values = values[-len(years):]
        for year, value in zip(years, values):
            if not 2000<=year<=2025:
                continue
            quality = 82
            if kind == "ANNUAL_REPORT": quality += 8
            if kind == "INTERIM": quality -= 25
            if factor is None and var not in PER_SHARE | NONMONETARY: quality -= 18
            standardized = (value * factor) if factor and var not in PER_SHARE | NONMONETARY else None
            out.append(dict(company=company, company_match=company_flag, year=year, variable=var,
                category=group, raw_value=value, currency=currency, unit=scale_name,
                scale_factor=factor, amount_local_units=standardized, original_label=alias,
                matched_line=line[:350], pdf=str(pdf), page=page_no, period=kind,
                score=max(0, min(100, quality)), status="REVIEW_REQUIRED"))
    return out

def choose_candidates(candidates):
    groups = defaultdict(list)
    for c in candidates:
        # Interim observations never overwrite full-year observations.
        groups[(c['company'], c['year'], c['variable'], c['period']=='INTERIM')].append(c)
    selected = []
    for group in groups.values():
        group.sort(key=lambda r:(r['score'], r['period']=="ANNUAL_REPORT", r['scale_factor'] is not None), reverse=True)
        winner = dict(group[0])
        equiv = {x['amount_local_units'] for x in group if x['amount_local_units'] is not None}
        winner['status'] = ("CONFLICT_REVIEW" if len(equiv)>1 else
                            "UNIT_REVIEW" if winner['scale_factor'] is None and winner['variable'] not in PER_SHARE|NONMONETARY else
                            "REVIEW_REQUIRED")
        winner['competing_candidates'] = len(group)
        selected.append(winner)
    return selected


def derive(selected):
    groups = defaultdict(dict)
    for r in selected:
        if r['period']=='INTERIM' or r['status']=='CONFLICT_REVIEW':
            continue
        key = (r['company'], r['year'])
        if r['amount_local_units'] is not None:
            groups[key][r['variable']] = r['amount_local_units']
        elif r['variable'] in PER_SHARE | NONMONETARY:
            groups[key][r['variable']] = r['raw_value']
    results = []
    def ratio(num, den):
        return (num/den if num is not None and den not in (None,0) else None)
    for (company, year), d in sorted(groups.items()):
        short = d.get('short_term_debt')
        long = d.get('long_term_debt')
        # Current portions are not added again: they may already be included in current loans.
        debt = short+long if short is not None and long is not None else None
        assets = d.get('total_assets')
        op = d.get('operating_income')
        depr = d.get('depreciation')
        amort = d.get('amortization')
        ebitda = d.get('ebitda')
        roa_numerator = ebitda if ebitda is not None else (
            op+depr+amort if all(v is not None for v in (op,depr,amort)) else None)
        results.append(dict(company=company, year=year, total_debt=debt,
            leverage=ratio(debt,assets), long_term_leverage=ratio(long,assets),
            short_term_leverage=ratio(short,assets), tangibility=ratio(d.get('ppe_net'),assets),
            roa_jibs=ratio(roa_numerator,assets), ln_assets=(__import__('math').log(assets) if assets is not None and assets>0 else None),
            current_ratio=ratio(d.get('current_assets'),d.get('current_liabilities')),
            net_debt=(debt-d['cash_equivalents'] if debt is not None and d.get('cash_equivalents') is not None else None),
            debt_to_equity=ratio(debt,d.get('total_equity')),
            gross_margin=ratio(d.get('gross_profit'),d.get('revenue')),
            net_margin=ratio(d.get('net_income'),d.get('revenue')),
            capex_to_assets=ratio(d.get('capital_expenditure'),assets),
            note="PROVISIONAL: verify raw amounts, unit scaling, and debt definitions"))
    return results


def style_sheet(ws):
    ws.freeze_panes = 'C2'
    ws.auto_filter.ref = ws.dimensions
    ws.row_dimensions[1].height = 27
    for cell in ws[1]:
        cell.font = Font(name='Calibri', bold=True, color='000000', size=10)
        cell.alignment = Alignment(vertical='center', wrap_text=True)
        cell.fill = PatternFill('solid', fgColor='E6E6E6')
    for col in ws.columns:
        header = str(col[0].value)
        width = min(55, max(13, len(header)+3))
        if header in ('pdf','matched_line','note','aliases'): width=55
        if header in ('company','original_label'): width=32
        ws.column_dimensions[get_column_letter(col[0].column)].width = width
    ws.sheet_view.showGridLines = False


def add_sheet(wb, name, records, headers):
    ws = wb.create_sheet(name)
    ws.append(headers)
    for r in records:
        ws.append([r.get(h) for h in headers])
    style_sheet(ws)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, float):
                cell.number_format = '#,##0.000000;[Red](#,##0.000000)'
    return ws


def export_excel(path, selected, all_candidates, derived, pdf_log):
    wb = Workbook()
    wb.remove(wb.active)
    base = ['company','year','variable','category','raw_value','currency','unit','scale_factor',
            'amount_local_units','period','score','status','original_label','matched_line','pdf','page','company_match']
    add_sheet(wb,'Selected_Values',selected,base+['competing_candidates'])
    add_sheet(wb,'All_Candidates',all_candidates,base)
    add_sheet(wb,'Derived_JIBS',derived,['company','year','total_debt','leverage','long_term_leverage',
         'short_term_leverage','tangibility','roa_jibs','ln_assets','current_ratio','net_debt',
         'debt_to_equity','gross_margin','net_margin','capex_to_assets','note'])
    add_sheet(wb,'PDF_Audit',pdf_log,['pdf','company','company_match','period','report_year','pages',
        'text_pages','scanned_pages','candidate_values','status'])
    dictionary=[{'variable':key,'category':value[0], 'aliases':value[1].replace('|','; ')} for key,value in VARIABLES.items()]
    add_sheet(wb,'Keyword_Dictionary',dictionary,['variable','category','aliases'])
    wb.save(path)


def main():
    p=argparse.ArgumentParser(description='PDF financial statement extraction into Excel only')
    p.add_argument('--input',type=Path,default=DEFAULT_ROOT)
    p.add_argument('--output',type=Path,default=None)
    p.add_argument('--limit',type=int,default=0,help='Maximum number of PDFs; 0=all')
    args=p.parse_args()
    root=args.input
    if not root.is_dir():
        sys.exit(f'Cannot find report folder: {root}\nVerify --input path exists on this computer.')
    pdfs=sorted(root.rglob('*.pdf'))
    if args.limit: pdfs=pdfs[:args.limit]
    if not pdfs: sys.exit(f'No PDF reports found under {root}')
    output=args.output or (root / DEFAULT_OUTPUT)
    companies=load_company_master(root.parent.parent)
    all_candidates=[]; pdf_log=[]
    for idx, pdf in enumerate(pdfs,1):
        print(f'[{idx}/{len(pdfs)}] {pdf.name}',flush=True)
        company, company_flag=match_company(pdf,companies)
        try:
            with fitz.open(pdf) as doc:
                pages=[]; text_pages=0
                for page in doc:
                    lines,txt=extract_rows(page)
                    pages.append((lines,txt))
                    if len(txt.strip())>=40: text_pages+=1
                first=[txt for lines,txt in pages[:2]]
                kind=report_kind(' '.join(first),pdf.name)
                year=document_year(first)
                count=0
                for page_no,(lines,txt) in enumerate(pages,1):
                    if len(txt.strip()) < 40: continue
                    years=find_year_columns(lines,year)
                    # Never assign a year based solely on date in the PDF filename.
                    currency,factor,scale=unit_info(txt[:5000]+' '+' '.join(first)[:1800])
                    if kind=='INTERIM' and not years: continue
                    found=find_candidates(lines,years,pdf,page_no,company,company_flag,
                        kind,currency,factor,scale)
                    all_candidates.extend(found); count+=len(found)
                pdf_log.append(dict(pdf=str(pdf),company=company,company_match=company_flag,
                    period=kind,report_year=year,pages=len(doc),text_pages=text_pages,
                    scanned_pages=len(doc)-text_pages,candidate_values=count,
                    status='SCANNED_PDF_NEEDS_OCR' if text_pages==0 else 'REVIEW_REQUIRED'))
        except Exception as ex:
            pdf_log.append(dict(pdf=str(pdf),company=company,company_match=company_flag,
                period='',report_year='',pages='',text_pages='',scanned_pages='',
                candidate_values=0,status=f'ERROR: {str(ex)[:180]}'))
    selected=choose_candidates(all_candidates)
    derived=derive(selected)
    output.parent.mkdir(parents=True,exist_ok=True)
    export_excel(output,selected,all_candidates,derived,pdf_log)
    print(f'\nEXCEL SAVED: {output}')
    print(f'PDFs: {len(pdfs)}; candidates: {len(all_candidates)}; selected: {len(selected)}; firm-years: {len(derived)}')
    print('All extracted results are provisional. Check Selected_Values and PDF_Audit before analysis.')

if __name__=='__main__': main()
