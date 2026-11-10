import gzip
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts import import_openfoodfacts as catalog

class CatalogImportTests(unittest.TestCase):
    def test_streamed_catalog_builds_atomic_lookup_database(self):
        source = ('code\tproduct_name\tabbreviated_product_name\tgeneric_name\tquantity\tlast_modified_t\n'
                  '012345678905\tPasta\t\t\t16 oz\t123\n'
                  'bad\tIgnored\t\t\t1 kg\t124\n').encode()
        with tempfile.TemporaryDirectory() as directory:
            old = catalog.TARGET
            catalog.TARGET = Path(directory) / 'catalog.sqlite'
            try:
                with patch.object(catalog, 'urlopen', return_value=io.BytesIO(gzip.compress(source))):
                    catalog.import_catalog('etag-1', 'today')
                with sqlite3.connect(catalog.TARGET) as db:
                    product = db.execute('SELECT * FROM products').fetchone()
                    metadata = dict(db.execute('SELECT key,value FROM metadata'))
                self.assertEqual(product[:2], ('00012345678905', 'Pasta'))
                self.assertAlmostEqual(product[2], 453.59237)
                self.assertEqual(product[3:5], ('g', 1))
                self.assertEqual(metadata['products'], '1')
                self.assertEqual(metadata['etag'], 'etag-1')
                self.assertFalse(catalog.TARGET.with_suffix('.sqlite.new').exists())
            finally:
                catalog.TARGET = old

if __name__ == '__main__':
    unittest.main()
