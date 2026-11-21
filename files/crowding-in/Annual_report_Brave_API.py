"""Annual-report collector (2000–2025).

Inputs (located in --base): Private_Companies.xlsx and Public_Companies.xlsx
Also accepts names ending in (1).xlsx.
Search providers: ddgs (no key), Brave Search API (optional).
IMPORTANT: search matches and downloaded PDFs require manual review.
"""
from __future__ import annotations
import argparse
import hashlib
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import requests
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment

DEFAULT_BASE = Path(r'C:\Users\s180020\Desktop\Mine\For website')
AGENT = 'AcademicReportResearchBot/1.1 (public research; contact researcher before deployment)'
OUTPUT_COLS = ['company_type','company','country_code','country','industry','report_year','search_type',
               'provider','title','url','snippet','company_match','year_match','document_match',
               'review_status','download_status','local_pdf','searched_at']
STOPWORDS = {'limited','ltd','plc','company','co','group','holdings','holding','corporation','corp','inc','sa','spa','pty','the','and','of','international','africa'}
REPORT_WORDS = ('annual report', 'annual financial', 'financial statements', 'audited accounts',
                'financial report', 'integrated report', 'rapport annuel', 'etats financiers')


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', str(s).lower()).strip()


def sha(s):
    return hashlib.sha256(str(s).encode('utf-8')).hexdigest()


def slug(s):
    head = re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_')[:55]
    return f'{head}_{sha(s)[:8]}'


def read_companies(base, types, limit):
    rows, seen = [], set()
    for kind in types:
        options = [base / f'{kind}_Companies.xlsx', base / f'{kind}_Companies(1).xlsx',
                   base / f'{kind}_Companies (1).xlsx']
        file = next((x for x in options if x.is_file()), None)
        if file is None:
            raise FileNotFoundError(f'Cannot locate {kind} Excel file. Looked for: {options}')
        print(f'Reading {file}')
        book = load_workbook(file, read_only=True, data_only=True)
        sheet = book.active
        data = sheet.iter_rows(values_only=True)
        header = [str(x).strip() if x is not None else '' for x in next(data)]
        required = ('Company', 'Country code', 'Country', 'Industry')
        missing = [c for c in required if c not in header]
        if missing:
            book.close()
            raise ValueError(f'{file}: missing columns {missing}; found {header}')
        positions = {c: header.index(c) for c in required}
        found = 0
        for cells in data:
            item = {c: str(cells[ix]).strip() if ix < len(cells) and cells[ix] is not None else ''
                    for c, ix in positions.items()}
            if not item['Company']:
                continue
            key = (kind, norm(item['Company']), norm(item['Country']))
            if key in seen:
                continue
            seen.add(key)
            rows.append((kind, item['Company'], item['Country code'], item['Country'], item['Industry']))
            found += 1
            if limit and found >= limit:
                break
        book.close()
        print(f'Loaded {found} {kind.lower()} companies')
    return rows


def database(path):
    db = sqlite3.connect(path)
    db.execute('''CREATE TABLE IF NOT EXISTS searches (
        search_id TEXT PRIMARY KEY, company_type TEXT, company TEXT, report_year INTEGER,
        search_type TEXT, provider TEXT, query TEXT, searched_at TEXT, result_count INTEGER)''')
    db.execute('''CREATE TABLE IF NOT EXISTS candidates (
        result_id TEXT PRIMARY KEY, company_type TEXT, company TEXT, country_code TEXT,
        country TEXT, industry TEXT, report_year INTEGER, search_type TEXT, provider TEXT,
        title TEXT, url TEXT, snippet TEXT, company_match TEXT, year_match TEXT,
        document_match TEXT, review_status TEXT, download_status TEXT, local_pdf TEXT,
        searched_at TEXT)''')
    db.commit()
    return db


def search_web(query, mode, session, api_key):
    if mode == 'brave':
        if not api_key:
            raise RuntimeError('Brave mode needs BRAVE_API_KEY in the environment')
        r = session.get('https://api.search.brave.com/res/v1/web/search', params={'q': query, 'count': 8},
                        headers={'X-Subscription-Token': api_key, 'Accept': 'application/json'}, timeout=35)
        if r.status_code in (401, 403, 429):
            raise RuntimeError(f'Brave HTTP {r.status_code}: authentication, quota or rate-limit error')
        r.raise_for_status()
        return [(x.get('title', ''), x.get('url', ''), x.get('description', ''))
                for x in r.json().get('web', {}).get('results', [])]
    try:
        from ddgs import DDGS
    except ImportError as ex:
        raise RuntimeError('Install ddgs in this Python environment: %pip install ddgs') from ex
    with DDGS() as engine:
        items = engine.text(query, max_results=8) or []
        return [(x.get('title', ''), x.get('href') or x.get('url', ''), x.get('body') or x.get('description', ''))
                for x in items]


def assess(company, year, job, title, url, snippet):
    combined = norm(' '.join([title, url, snippet]))
    tokens = [w for w in norm(company).split() if len(w) >= 3 and w not in STOPWORDS]
    overlap = sum(w in combined.split() for w in set(tokens))
    company_match = bool(tokens) and overlap >= min(2, len(set(tokens))) and (len(tokens) > 1 or len(tokens[0]) >= 7)
    year_match = year is not None and bool(re.search(rf'(?<!\d){year}(?!\d)', combined))
    report_match = any(term in combined for term in REPORT_WORDS)
    if job == 'website':
        verdict = 'POSSIBLE_OFFICIAL_WEBSITE_REVIEW' if company_match else 'UNVERIFIED'
    else:
        verdict = 'PROMISING_REVIEW_REQUIRED' if company_match and year_match and report_match else 'UNVERIFIED'
    return ('YES' if company_match else 'NO', 'YES' if year_match else 'NO',
            'YES' if report_match else 'NO', verdict)


class Robots:
    def __init__(self, session):
        self.session, self.rules, self.last = session, {}, {}

    def allowed(self, url):
        u = urlparse(url)
        if u.scheme not in ('http', 'https') or not u.hostname:
            return False, 'INVALID_URL'
        origin = f'{u.scheme}://{u.netloc}'
        if origin not in self.rules:
            try:
                r = self.session.get(origin + '/robots.txt', timeout=12)
                if r.status_code == 404:
                    self.rules[origin] = 'allow'
                elif r.status_code == 200:
                    p = RobotFileParser()
                    p.parse(r.text.splitlines())
                    self.rules[origin] = p
                else:
                    self.rules[origin] = None
            except requests.RequestException:
                self.rules[origin] = None
        rule = self.rules[origin]
        if rule == 'allow':
            return True, ''
        if rule is None:
            return False, 'ROBOTS_UNAVAILABLE'
        return (bool(rule.can_fetch(AGENT, url)), 'ROBOTS_DISALLOWED')

    def delay(self, url):
        domain = urlparse(url).netloc
        remaining = 3 - (time.monotonic() - self.last.get(domain, 0))
        if remaining > 0:
            time.sleep(remaining)
        self.last[domain] = time.monotonic()


def download_pdf(session, robots, url, target):
    temp = target.with_suffix('.part')
    try:
        current = url
        for _ in range(6):
            yes, why = robots.allowed(current)
            if not yes:
                return why, ''
            robots.delay(current)
            response = session.get(current, stream=True, allow_redirects=False, timeout=(12, 55))
            if response.status_code in (301,302,303,307,308):
                nxt = urljoin(current, response.headers.get('Location', ''))
                response.close()
                current = nxt
                continue
            break
        else:
            return 'TOO_MANY_REDIRECTS', ''
        with response:
            if response.status_code in (401,403,429):
                return f'ACCESS_RESTRICTED_{response.status_code}', ''
            response.raise_for_status()
            if 'html' in response.headers.get('Content-Type','').lower():
                return 'HTML_NOT_PDF', ''
            target.parent.mkdir(parents=True, exist_ok=True)
            total = 0
            with temp.open('wb') as f:
                for chunk in response.iter_content(65536):
                    if chunk:
                        total += len(chunk)
                        if total > 60 * 1024 * 1024:
                            raise ValueError('PDF larger than 60 MB')
                        f.write(chunk)
        with temp.open('rb') as f:
            if b'%PDF-' not in f.read(1024):
                return 'NOT_PDF', ''
        temp.replace(target)
        return 'DOWNLOADED_UNVERIFIED', str(target)
    except (requests.RequestException, OSError, ValueError) as e:
        return 'DOWNLOAD_ERROR: ' + str(e)[:120], ''
    finally:
        temp.unlink(missing_ok=True)


def export(db, output):
    book = Workbook()
    book.remove(book.active)
    fetched = db.execute('SELECT ' + ','.join(OUTPUT_COLS) + ' FROM candidates ORDER BY company_type,company,report_year').fetchall()
    for kind in ('Private','Public'):
        sheet = book.create_sheet(kind)
        sheet.append(OUTPUT_COLS)
        for r in fetched:
            if r[0] == kind:
                sheet.append(r)
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for col in 'ABCDEFGHIJKLMNOPQR':
            sheet.column_dimensions[col].width = 20
        sheet.column_dimensions['B'].width = 38
        sheet.column_dimensions['J'].width = 55
        sheet.column_dimensions['K'].width = 75
        sheet.column_dimensions['L'].width = 55
        sheet.column_dimensions['Q'].width = 70
        for c in sheet[1]:
            c.font = Font(bold=True, color='FFFFFF')
            c.fill = PatternFill('solid', fgColor='25364A')
            c.alignment = Alignment(wrap_text=True)
    log = book.create_sheet('Search_Log')
    log.append(['search_id','company_type','company','report_year','search_type','provider','query','searched_at','result_count'])
    for record in db.execute('SELECT * FROM searches ORDER BY company_type,company,report_year'):
        log.append(record)
    log.freeze_panes = 'A2'
    log.auto_filter.ref = log.dimensions
    log.column_dimensions['G'].width = 80
    for c in log[1]:
        c.font = Font(bold=True,color='FFFFFF')
        c.fill = PatternFill('solid',fgColor='25364A')
    out = output / 'Company_Report_Inventory.xlsx'
    book.save(out)
    print(f'Exported {len(fetched)} candidate links to {out}')


def main():
    p = argparse.ArgumentParser(description='Find African company annual reports using free search or optional Brave API')
    p.add_argument('--base', type=Path, default=DEFAULT_BASE)
    p.add_argument('--type', choices=['private','public','both'], default='both')
    p.add_argument('--limit', type=int, default=10, help='Max companies PER type (0 = all)')
    p.add_argument('--start', type=int, default=2000)
    p.add_argument('--end', type=int, default=2025)
    p.add_argument('--provider', choices=['free','brave','hybrid'], default='free')
    p.add_argument('--max-searches', type=int, default=30, help='Maximum new searches per run (0 = unlimited)')
    p.add_argument('--download', action='store_true')
    p.add_argument('--no-search', action='store_true', help='Verify input and export empty inventory without network')
    args = p.parse_args()
    if args.start > args.end or args.start < 1900 or args.end > 2100 or args.limit < 0 or args.max_searches < 0:
        p.error('Invalid year range or limit')
    api_key = os.environ.get('BRAVE_API_KEY','').strip()
    if args.provider == 'brave' and not api_key and not args.no_search:
        p.error('Brave search requires BRAVE_API_KEY')
    kinds = ['Private','Public'] if args.type == 'both' else [args.type.title()]
    companies = read_companies(args.base, kinds, args.limit)
    out = args.base / 'Collected_Company_Reports'
    out.mkdir(exist_ok=True, parents=True)
    db = database(out / 'collection_progress.sqlite')
    session = requests.Session()
    session.headers['User-Agent'] = AGENT
    robots = Robots(session)
    used = 0
    stopped = False
    try:
        if args.no_search:
            print('Input verification complete; no web searches requested.')
        else:
            for idx, (kind, company, code, country, industry) in enumerate(companies, 1):
                print(f'[{idx}/{len(companies)}] {kind}: {company} ({country})', flush=True)
                jobs = [(None,'website',f'"{company}" "{country}" official company website investor relations')]
                jobs += [(y,'annual_report',f'"{company}" "{country}" annual report financial statements {y} pdf')
                         for y in range(args.start, args.end + 1)]
                for year, job, query in jobs:
                    # In hybrid mode, try free first, then Brave only if no promising matches.
                    options = ['free','brave'] if args.provider == 'hybrid' and api_key else [args.provider if args.provider != 'hybrid' else 'free']
                    promising = False
                    for provider in options:
                        sid = sha((kind,company,country,year,job,provider))
                        done = db.execute('SELECT 1 FROM searches WHERE search_id=?',(sid,)).fetchone()
                        if done:
                            count = db.execute("SELECT COUNT(*) FROM candidates WHERE company_type=? AND company=? AND report_year IS ? AND search_type=? AND review_status != 'UNVERIFIED'",(kind,company,year,job)).fetchone()[0]
                            if count: promising = True
                            if promising: break
                            continue
                        if args.max_searches and used >= args.max_searches:
                            stopped = True
                            break
                        try:
                            results = search_web(query, provider, session, api_key)
                        except Exception as ex:
                            print(f'Search error ({provider}, {company}, {year}): {ex}')
                            # Failures are NOT recorded as completed. In hybrid mode, try paid fallback.
                            continue
                        used += 1
                        for title,url,snippet in results:
                            if not url.startswith(('https://','http://')):
                                continue
                            mc,ym,rm,verdict = assess(company,year,job,str(title),str(url),str(snippet))
                            if verdict != 'UNVERIFIED': promising = True
                            rid = sha((sid,url))
                            status,path = 'NOT_DOWNLOADED',''
                            if args.download and job != 'website' and verdict == 'PROMISING_REVIEW_REQUIRED' and '.pdf' in urlparse(url).path.lower():
                                target = out / 'PDFs' / kind / slug(company) / str(year) / (rid[:16]+'.pdf')
                                if target.exists():
                                    status,path = 'ALREADY_DOWNLOADED_UNVERIFIED',str(target)
                                else:
                                    status,path = download_pdf(session,robots,url,target)
                            db.execute('INSERT OR REPLACE INTO candidates VALUES ('+','.join(['?']*19)+')',
                                       (rid,kind,company,code,country,industry,year,job,provider,title,url,snippet,
                                        mc,ym,rm,verdict,status,path,stamp()))
                        db.execute('INSERT INTO searches VALUES (?,?,?,?,?,?,?,?,?)',
                                   (sid,kind,company,year,job,provider,query,stamp(),len(results)))
                        db.commit()
                        time.sleep(2)
                        if promising: break
                    if stopped: break
                if stopped: break
    except KeyboardInterrupt:
        print('Stopped by user; saved progress will be exported.')
    finally:
        export(db,out)
        db.close()
        session.close()
    print(f'New search requests: {used}. Provider: {args.provider}. Rerun same command to resume.')
    if stopped:
        print('Search cap reached; rerun to continue.')

if __name__ == '__main__':
    main()
