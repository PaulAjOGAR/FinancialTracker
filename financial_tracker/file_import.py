import csv
import json
import io
import re
from datetime import datetime

try:
    import openpyxl
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


# ── MERCHANT → CATEGORY MAPPING ──────────────────────────────────────────────
# Add keywords here to improve auto-categorisation.
MERCHANT_CATEGORIES = {
    'food': [
        'aldi', 'lidl', 'asda', 'tesco', 'sainsbury', 'morrisons', 'waitrose',
        'coop', 'co-op', 'marks&spencer', 'mns', 'iceland', 'farmfoods',
        'kfc', 'mcdonalds', 'subway', 'pizza', 'hungry', 'greggs', 'costa',
        'starbucks', 'pret', 'nando', 'popeye', 'chickando', 'jollibee',
        'slim chicken', 'phat bun', 'afro', 'fresh food', 'market',
        'minimarket', 'catering', 'restaurant', 'cafe', 'kebab', 'burger',
        'tgtg', 'deliveroo', 'just eat', 'uber eats', 'continental',
        'sunningham', 'sunninghill', 'newsagent', 'news', 'campus news',
        'ntsu', 'ntu cater',
    ],
    'transport': [
        'uber *trip', 'uber* trip', 'paypal *ubertrip', 'bolt',
        'lime*pass', 'lime*ride', 'lim*ride', 'lime*subscription',
        'national express', 'stagecoach', 'transdev', 'trainline',
        'tramlink', 'tramline', 'tram link', 'contactless.travel',
        'nct ', 'nct bus', 'ncl', 'bus', 'coach', 'rail', 'train',
        'blazefield', 'nottingham contact', 'nottingham city tr',
        'first glasgow',
    ],
    'house': [
        'amazon', 'argos', 'ikea', 'onebelow', 'one below',
        'savers', 'poundland', 'ryman', 'wilko', 'b&m', 'home',
        'moneybox', 'three store', 'three\n', 'three mobile',
        'microsoft', 'apple.com', 'google play', 'google *play',
        'netflix', 'spotify', 'amazon prime', 'disney',
        'adobe', 'cursor', 'credit engine', 'scoresmatter',
        'lumin', 'remini', 'headway', 'app.remini',
    ],
    'clothes': [
        'primark', 'next retail', 'sportsdirect', 'sports direct',
        'asos', 'shein', 'h&m', 'zara', 'topshop', 'new look',
        'marks&spencer',
    ],
    'savings': [
        'moneybox', 'transfer/self', 'account 2', 'savings', 'isa ',
        'paul ogar\nmonzo', 'monzo-', 'revolut',
    ],
}

VALID_CATEGORIES = {'food', 'house', 'transport', 'clothes', 'savings', 'misc'}


def auto_category(description):
    desc_lower = description.lower()
    for cat, keywords in MERCHANT_CATEGORIES.items():
        if any(k in desc_lower for k in keywords):
            return cat
    return 'misc'


def clean_cell(val):
    if val is None:
        return ''
    return ' '.join(str(val).replace('\n', ' ').split()).strip()


def parse_amount(val):
    if not val:
        return None
    clean = re.sub(r'[£,\-\s]', '', str(val)).strip()
    try:
        return abs(float(clean))
    except (ValueError, TypeError):
        return None


def parse_date(raw):
    raw = str(raw).replace(' /', '/').replace('/ ', '/').strip()
    formats = [
        '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y',
        '%d/%m/%y', '%Y/%m/%d', '%d.%m.%Y',
        '%d %b %Y', '%d %B %Y',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    # Try partial match e.g. '11/02/2026' buried in a longer string
    m = re.search(r'(\d{2})/(\d{2})/(\d{4})', raw)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)}/{m.group(2)}/{m.group(3)}", '%d/%m/%Y').strftime('%Y-%m-%d')
        except ValueError:
            pass
    return None


def normalise_type(raw):
    val = str(raw).strip().lower()
    if val in ('i', 'income', 'in', 'credit', 'money in'):
        return 'I'
    if val in ('e', 'expense', 'out', 'debit', 'expenditure', 'money out'):
        return 'E'
    return None


def normalise_category(raw):
    val = str(raw).strip().lower()
    return val if val in VALID_CATEGORIES else 'misc'


# ── COLUMN ALIAS DETECTION ───────────────────────────────────────────────────
COLUMN_ALIASES = {
    'amount':      ['amount', 'value', 'sum', 'price', 'cost', 'total'],
    'money_in':    ['money in', 'credit', 'paid in', 'in', 'deposit', 'income'],
    'money_out':   ['money out', 'debit', 'paid out', 'out', 'withdrawal', 'expense'],
    't_type':      ['type', 't_type', 'transaction_type', 'kind', 'direction'],
    'category':    ['category', 'cat', 'group', 'tag', 'label'],
    'date':        ['date', 'datetime', 'transaction_date', 'when'],
    'description': ['description', 'desc', 'note', 'notes', 'memo', 'details', 'reference', 'narrative'],
}


def detect_columns(headers):
    mapping = {}
    for i, header in enumerate(headers):
        clean = str(header).strip().lower()
        for field, aliases in COLUMN_ALIASES.items():
            if clean in aliases and field not in mapping:
                mapping[field] = i
    return mapping


def row_to_transaction(row, mapping):
    result = {
        'amount':      None,
        't_type':      None,
        'category':    'misc',
        'date':        datetime.today().strftime('%Y-%m-%d'),
        'description': '',
        'error':       None,
    }
    errors = []

    # Handle split money_in / money_out columns (bank statement format)
    if 'money_in' in mapping or 'money_out' in mapping:
        in_val  = row[mapping['money_in']]  if 'money_in'  in mapping else ''
        out_val = row[mapping['money_out']] if 'money_out' in mapping else ''
        amount_in  = parse_amount(in_val)
        amount_out = parse_amount(out_val)
        if amount_in and not amount_out:
            result['amount'] = amount_in
            result['t_type'] = 'I'
        elif amount_out and not amount_in:
            result['amount'] = amount_out
            result['t_type'] = 'E'
        elif amount_in and amount_out:
            result['amount'] = amount_out
            result['t_type'] = 'E'
        else:
            errors.append('No valid amount found')
    elif 'amount' in mapping:
        try:
            result['amount'] = abs(float(str(row[mapping['amount']]).replace('£','').replace(',','').strip()))
        except (ValueError, IndexError):
            errors.append('Invalid amount')
    else:
        errors.append('No amount column found')

    if 't_type' in mapping and not result['t_type']:
        t = normalise_type(row[mapping['t_type']])
        result['t_type'] = t if t else 'E'

    if not result['t_type']:
        result['t_type'] = 'E'

    if 'category' in mapping:
        result['category'] = normalise_category(row[mapping['category']])

    if 'date' in mapping:
        d = parse_date(row[mapping['date']])
        if d:
            result['date'] = d
        else:
            errors.append(f"Unrecognised date: {row[mapping['date']]}")

    if 'description' in mapping:
        desc = str(row[mapping['description']]).strip()[:100]
        result['description'] = desc
        if result['category'] == 'misc':
            result['category'] = auto_category(desc)

    result['error'] = '; '.join(errors) if errors else None
    return result


# ── FILE PARSERS ─────────────────────────────────────────────────────────────

def parse_csv(file_bytes):
    text = file_bytes.decode('utf-8-sig', errors='replace')
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        raise ValueError("CSV file is empty.")
    return rows[0], rows[1:]


def parse_xlsx(file_bytes):
    if not XLSX_AVAILABLE:
        raise ValueError("openpyxl not installed. Run: pip install openpyxl")
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    all_rows = [[str(cell.value) if cell.value is not None else '' for cell in row] for row in ws.iter_rows()]
    wb.close()
    all_rows = [r for r in all_rows if any(c.strip() for c in r)]
    if not all_rows:
        raise ValueError("Excel file is empty.")
    return all_rows[0], all_rows[1:]


def parse_json(file_bytes):
    data = json.loads(file_bytes.decode('utf-8'))
    if isinstance(data, dict):
        for key in ('transactions', 'data', 'records', 'items'):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            raise ValueError("JSON object found but no 'transactions', 'data', or 'records' key.")
    if not isinstance(data, list) or not data:
        raise ValueError("JSON must be a list of transaction objects.")
    headers = []
    for item in data:
        for k in item.keys():
            if k not in headers:
                headers.append(k)
    rows = [[str(item.get(h, '')) for h in headers] for item in data]
    return headers, rows


def parse_txt(file_bytes):
    text = file_bytes.decode('utf-8-sig', errors='replace')
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        raise ValueError("Text file is empty.")
    for delimiter in ['\t', '|', ',', ';']:
        if delimiter in lines[0]:
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            rows = [r for r in reader if any(c.strip() for c in r)]
            if rows:
                return rows[0], rows[1:]
    raise ValueError("Could not detect delimiter. Use tab, pipe, comma, or semicolon.")


def parse_pdf(file_bytes):
    """
    Parses bank statement PDFs with Date / Description / Money in / Money out / Balance columns.
    Falls back to generic table parsing for other PDF formats.
    """
    if not PDF_AVAILABLE:
        raise ValueError("pdfplumber not installed. Run: pip install pdfplumber")

    SKIP_LABELS = {
        'available balance', "last night's balance", 'overdraft limit',
        'date', 'description', 'money in', 'money out', 'balance', '',
    }

    transactions = []
    current_date = None

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row:
                        continue

                    cells = [clean_cell(c) for c in row]

                    # Skip header / summary rows
                    first = cells[0].lower() if cells else ''
                    if first in SKIP_LABELS:
                        continue

                    # Must have at least 4 columns for a valid transaction row
                    if len(cells) < 4:
                        continue

                    date_raw  = cells[0]
                    desc      = cells[1] if len(cells) > 1 else ''
                    money_in  = cells[2] if len(cells) > 2 else ''
                    money_out = cells[3] if len(cells) > 3 else ''

                    # Update current date if this row has one
                    parsed = parse_date(date_raw)
                    if parsed:
                        current_date = parsed

                    # Skip rows with no amounts (continuation rows, blank rows)
                    amt_in  = parse_amount(money_in)
                    amt_out = parse_amount(money_out)
                    if not amt_in and not amt_out:
                        continue

                    if not desc or not desc.strip():
                        continue

                    if amt_in and not amt_out:
                        t_type = 'I'
                        amount = amt_in
                    elif amt_out and not amt_in:
                        t_type = 'E'
                        amount = amt_out
                    else:
                        # Both present — treat as expense
                        t_type = 'E'
                        amount = amt_out

                    category = auto_category(desc)

                    transactions.append({
                        'amount':      amount,
                        't_type':      t_type,
                        'category':    category,
                        'date':        current_date or datetime.today().strftime('%Y-%m-%d'),
                        'description': desc[:100],
                        'error':       None if current_date else 'Date not detected',
                    })

    if transactions:
        valid   = sum(1 for t in transactions if not t['error'])
        invalid = len(transactions) - valid
        return {
            'transactions': transactions,
            'total':   len(transactions),
            'valid':   valid,
            'invalid': invalid,
        }

    # Fallback: generic table extraction for non-bank-statement PDFs
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        all_rows = []
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                all_rows.extend([[clean_cell(c) for c in row] for row in table])

    all_rows = [r for r in all_rows if any(c for c in r)]
    if len(all_rows) < 2:
        raise ValueError("Could not find any tabular transaction data in this PDF.")

    headers = all_rows[0]
    mapping = detect_columns(headers)
    parsed  = [row_to_transaction(row, mapping) for row in all_rows[1:] if any(r for r in row)]
    valid   = sum(1 for t in parsed if not t['error'])
    return {
        'transactions': parsed,
        'total':   len(parsed),
        'valid':   valid,
        'invalid': len(parsed) - valid,
    }


# ── MAIN ENTRY POINT ─────────────────────────────────────────────────────────

def parse_file(filename, file_bytes):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    if ext == 'pdf':
        return parse_pdf(file_bytes)

    if ext == 'csv':
        headers, rows = parse_csv(file_bytes)
    elif ext in ('xlsx', 'xls'):
        headers, rows = parse_xlsx(file_bytes)
    elif ext == 'json':
        headers, rows = parse_json(file_bytes)
    elif ext == 'txt':
        headers, rows = parse_txt(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: .{ext}. Supported: csv, xlsx, json, txt, pdf")

    mapping      = detect_columns(headers)
    transactions = [row_to_transaction(row, mapping) for row in rows if any(str(c).strip() for c in row)]
    valid        = sum(1 for t in transactions if not t['error'])

    return {
        'transactions': transactions,
        'total':   len(transactions),
        'valid':   valid,
        'invalid': len(transactions) - valid,
    }