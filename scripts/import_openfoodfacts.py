"""Stream the Open Food Facts CSV export into an atomic local barcode index."""
import csv
import gzip
import io
import os
from pathlib import Path
import sqlite3
import sys
import time
from urllib.request import Request, urlopen

from app import code, parse_package, text

URL = os.getenv('OFF_CSV_URL', 'https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz')
TARGET = Path(os.getenv('OFF_DB', '/data/openfoodfacts.sqlite'))
USER_AGENT = os.getenv('OFF_USER_AGENT', 'HouseholdPantry/0.1 (local household app)')
INTERVAL = max(1.0, float(os.getenv('OFF_INDEX_INTERVAL_HOURS', '720'))) * 3600
BATCH = 10000

def current_etag():
    try:
        with sqlite3.connect(f'file:{TARGET}?mode=ro', uri=True) as db:
            row = db.execute("SELECT value FROM metadata WHERE key='etag'").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None

def source_metadata():
    request = Request(URL, method='HEAD', headers={'User-Agent':USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return response.headers.get('ETag',''), response.headers.get('Last-Modified','')

def product(row):
    try:
        barcode = code(row.get('code','').strip())
        name = text(row.get('product_name') or row.get('abbreviated_product_name') or
                    row.get('generic_name'), 500)[:160]
    except (TypeError, ValueError):
        return None
    parsed = parse_package(row.get('quantity',''))
    pack, unit, size_known = (*parsed, 1) if parsed else (1, 'item', 0)
    try:
        modified = int(row.get('last_modified_t') or 0)
    except ValueError:
        modified = 0
    return barcode, name, pack, unit, size_known, modified

def import_catalog(etag, last_modified):
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    temporary = TARGET.with_suffix('.sqlite.new')
    temporary.unlink(missing_ok=True)
    db = sqlite3.connect(temporary)
    try:
        db.executescript('''
          PRAGMA journal_mode=OFF;
          PRAGMA synchronous=OFF;
          PRAGMA temp_store=MEMORY;
          CREATE TABLE products (
            barcode TEXT PRIMARY KEY, name TEXT NOT NULL, pack REAL NOT NULL,
            unit TEXT NOT NULL, size_known INTEGER NOT NULL, modified INTEGER NOT NULL
          ) WITHOUT ROWID;
          CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID;
        ''')
        request = Request(URL, headers={'User-Agent':USER_AGENT})
        csv.field_size_limit(10_000_000)
        with urlopen(request, timeout=120) as response, gzip.GzipFile(fileobj=response) as compressed:
            stream = io.TextIOWrapper(compressed, encoding='utf-8', errors='replace', newline='')
            reader = csv.DictReader(stream, delimiter='\t')
            rows, imported = [], 0
            for source in reader:
                parsed = product(source)
                if not parsed:
                    continue
                rows.append(parsed)
                if len(rows) >= BATCH:
                    db.executemany('INSERT OR REPLACE INTO products VALUES(?,?,?,?,?,?)', rows)
                    imported += len(rows)
                    rows.clear()
                    if imported % 100000 == 0:
                        print(f'Indexed {imported:,} products', flush=True)
            if rows:
                db.executemany('INSERT OR REPLACE INTO products VALUES(?,?,?,?,?,?)', rows)
                imported += len(rows)
        imported = db.execute('SELECT COUNT(*) FROM products').fetchone()[0]
        updated = time.time()
        db.executemany('INSERT INTO metadata VALUES(?,?)', [
            ('etag',etag), ('source_last_modified',last_modified),
            ('updated_at',str(updated)), ('products',str(imported)), ('source_url',URL)])
        db.commit()
        db.execute('PRAGMA optimize')
        db.close()
        os.replace(temporary, TARGET)
        print(f'Open Food Facts index ready: {imported:,} products', flush=True)
    except BaseException:
        db.close()
        temporary.unlink(missing_ok=True)
        raise

def update():
    etag, last_modified = source_metadata()
    if etag and etag == current_etag():
        print('Open Food Facts index is current', flush=True)
        return
    print('Downloading and indexing the Open Food Facts CSV export', flush=True)
    import_catalog(etag, last_modified)

def main():
    while True:
        try:
            update()
        except Exception as error:
            print(f'Open Food Facts index update failed: {error}', file=sys.stderr, flush=True)
        time.sleep(INTERVAL)

if __name__ == '__main__':
    main()
