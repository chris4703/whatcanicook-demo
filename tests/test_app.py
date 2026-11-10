import io, json, tempfile, time, unittest, uuid
from unittest.mock import patch
from pathlib import Path
import app

class PantryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        app.DB=str(Path(self.tmp.name)/'test.sqlite')
        app.init()
    def tearDown(self):
        self.tmp.cleanup()
    def item(self,qty=100,unit='g'):
        return app.edit(dict(name='Pasta',qty=qty,unit=unit,pack=500,low=25))['id']
    def consume(self,lines,eid=None):
        return app.consume(dict(event_id=eid or str(uuid.uuid4()),deductions=lines))
    def test_repeat_scans_and_retry_idempotency(self):
        scan=dict(barcode='012345678905',event_id=str(uuid.uuid4()))
        app.scan(scan);app.scan(scan)
        self.assertEqual(app.snapshot()['items'][0]['qty'],1)
        app.scan(dict(barcode='0012345678905',event_id=str(uuid.uuid4())))
        self.assertEqual(len(app.snapshot()['items']),1)
        self.assertEqual(app.snapshot()['items'][0]['qty'],2)
    def test_atomic_deduction_and_undo_preserves_restocks(self):
        iid=self.item();eid=str(uuid.uuid4())
        lines=[dict(item_id=iid,amount=30,unit='g')]
        self.consume(lines,eid);self.consume(lines,eid)
        self.assertEqual(app.snapshot()['items'][0]['qty'],70)
        with app.connect() as db: db.execute('UPDATE items SET qty=qty+50 WHERE id=?',(iid,))
        app.undo(dict(event_id=eid));app.undo(dict(event_id=eid))
        self.assertEqual(app.snapshot()['items'][0]['qty'],150)
    def test_insufficient_stock_rolls_back_all(self):
        a,b=self.item(),self.item()
        with self.assertRaises(ValueError):
            self.consume([dict(item_id=a,amount=10,unit='g'),dict(item_id=b,amount=101,unit='g')])
        self.assertEqual([i['qty'] for i in app.snapshot()['items']],[100,100])
    def test_invalid_amounts_and_units(self):
        iid=self.item()
        for amount in [-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError): self.consume([dict(item_id=iid,amount=amount,unit='g')])
        with self.assertRaises(ValueError): self.consume([dict(item_id=iid,amount=1,unit='ml')])
        with self.assertRaises(ValueError): self.consume([dict(item_id=iid,amount=1,unit='g')]*2)
    def test_stale_shopping_does_not_delete_inventory(self):
        iid=self.item(qty=10)
        self.assertEqual(len(app.snapshot()['automatic']),1)
        with app.connect() as db: db.execute('UPDATE items SET stocked=? WHERE id=?',(time.time()-61*86400,iid))
        self.assertEqual(app.snapshot()['automatic'],[])
        self.assertEqual(app.snapshot()['items'][0]['qty'],10)
    def test_stale_edit_rejected(self):
        iid=self.item();old=app.snapshot()['items'][0]
        self.consume([dict(item_id=iid,amount=1,unit='g')])
        with self.assertRaises(ValueError): app.edit(dict(old,previous_qty=old['qty']))
    def test_delete_item_is_permanent_and_stale_safe(self):
        iid=self.item();item=app.snapshot()['items'][0]
        with self.assertRaises(ValueError): app.delete_item(dict(id=iid,revision=item['revision']+1))
        self.assertEqual(len(app.snapshot()['items']),1)
        self.assertTrue(app.delete_item(dict(id=iid,revision=item['revision']))['ok'])
        self.assertEqual(app.snapshot()['items'],[])
        with self.assertRaises(ValueError): app.delete_item(dict(id=iid,revision=item['revision']))
    def test_undo_rejects_unit_changes(self):
        iid=self.item();event=self.consume([dict(item_id=iid,amount=1,unit='g')])
        with app.connect() as db: db.execute("UPDATE items SET unit='ml' WHERE id=?",(iid,))
        with self.assertRaises(ValueError): app.undo(event)
    def test_package_parser(self):
        self.assertEqual(app.parse_package('500 g'),(500,'g'))
        self.assertEqual(app.parse_package('1.5 l'),(1500,'ml'))
        self.assertAlmostEqual(app.parse_package('16 oz')[0],453.59237)
        for label in ['6 x 200 g','12 count','2 pack','16 oz (454g)','unknown']:
            self.assertIsNone(app.parse_package(label))
    def test_local_catalog_lookup_and_stats(self):
        old=app.OFF_DB;app.OFF_DB=str(Path(self.tmp.name)/'catalog.sqlite')
        try:
            with app.sqlite3.connect(app.OFF_DB) as db:
                db.executescript('CREATE TABLE products(barcode TEXT PRIMARY KEY,name TEXT,pack REAL,unit TEXT,size_known INTEGER,modified INTEGER);CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);')
                db.execute('INSERT INTO products VALUES(?,?,?,?,?,?)',('00012345678905','Pasta',454,'g',1,1))
                db.executemany('INSERT INTO metadata VALUES(?,?)',[('products','1'),('updated_at','123')])
            self.assertEqual(app.local_product('00012345678905')['name'],'Pasta')
            self.assertIsNone(app.local_product('00000000000000'))
            self.assertEqual(app.catalog_stats(),{'catalog_ready':True,'catalog_products':1,'catalog_updated':123.0})
        finally:
            app.OFF_DB=old
    def test_only_cited_recipe_links_and_known_units(self):
        iid=self.item();pantry=app.snapshot()['items']
        recipe=dict(title='Pasta',url='https://example.com/pasta',summary='A meal.',minutes=20,missing=[],staples=['salt'],deductions=[dict(item_id=iid,amount=30,unit='g',ingredient='Pasta')])
        self.assertEqual(app.validate_recipes([recipe],pantry,set(),6),[])
        valid=app.validate_recipes([recipe],pantry,{recipe['url']},6)
        self.assertEqual(len(valid),1)
        recipe['missing']=['a','b','c']
        self.assertEqual(app.validate_recipes([recipe],pantry,{recipe['url']},6),[])

    def test_recipe_search_with_mocked_provider(self):
        iid=self.item();url='https://example.com/recipe'
        recipe=dict(title='Rice bowl',url=url,summary='For six.',minutes=20,missing=[],staples=['salt'],deductions=[dict(item_id=iid,amount=60,unit='g',ingredient='Pasta')])
        result={'output':[{'type':'web_search_call','action':{'sources':[{'url':url}]}},{'content':[{'type':'output_text','text':json.dumps({'recipes':[recipe]}),'annotations':[]}]}]}
        with patch.dict(app.os.environ,{'OPENAI_API_KEY':'test-key'}), patch('app.urlopen',return_value=io.BytesIO(json.dumps(result).encode())) as remote:
            found=app.ai_recipes(dict(servings=6))['recipes']
            self.assertEqual(len(found),1)
            sent=json.loads(remote.call_args.args[0].data)
            self.assertFalse(sent['store'])
            self.assertEqual(sent['tool_choice'],'required')
            self.assertNotIn('text',sent)
            self.assertEqual(app.RECIPE_SCHEMA['properties']['recipes']['items']['properties']['missing']['maxItems'],2)
            self.assertIn('common dried spices',sent['instructions'])
            self.assertIn('fresh herbs, garlic, onions, citrus, rice, chicken, ground beef, milk, pasta, eggs, cheddar cheese, oatmeal or oats, sugar, flour, butter, and honey are staples',sent['instructions'])
            self.assertIn('never need a pantry deduction',sent['instructions'])
            self.assertEqual(app.snapshot()['items'][0]['qty'],100)
    def test_recipe_reformat_keeps_source_validation(self):
        iid=self.item();url='https://example.com/recipe'
        recipe=dict(title='Rice',url=url,summary='For six.',minutes=20,missing=[],staples=[],deductions=[dict(item_id=iid,amount=60,unit='g',ingredient='Pasta')])
        raw={'output':[{'content':[{'type':'output_text','text':'Recipe with citation markers','annotations':[{'type':'url_citation','url':url}]}]}]}
        repaired={'output':[{'content':[{'type':'output_text','text':json.dumps({'recipes':[recipe]})}]}]}
        with patch.dict(app.os.environ,{'OPENAI_API_KEY':'test-key'}), patch('app.urlopen',side_effect=[io.BytesIO(json.dumps(raw).encode()),io.BytesIO(json.dumps(repaired).encode())]) as remote:
            self.assertEqual(len(app.ai_recipes(dict(servings=8))['recipes']),1)
            self.assertEqual(remote.call_count,2)
            repair_request=json.loads(remote.call_args_list[1].args[0].data)
            self.assertEqual(repair_request['text']['format']['type'],'json_schema')
    def test_missing_key_changes_no_inventory(self):
        self.item()
        with patch.dict(app.os.environ,{},clear=True):
            with self.assertRaises(ValueError):app.ai_recipes({})
        self.assertEqual(app.snapshot()['items'][0]['qty'],100)

    def test_citation_tracking_is_ignored_but_recipe_identity_is_preserved(self):
        iid=self.item();pantry=app.snapshot()['items']
        recipe=dict(title='Pasta',url='https://example.com/recipe?id=7',summary='A meal.',minutes=20,missing=[],staples=[],deductions=[dict(item_id=iid,amount=30,unit='g',ingredient='Pasta')])
        self.assertEqual(len(app.validate_recipes([recipe],pantry,{'https://example.com/recipe?id=7&utm_source=openai'},6)),1)
        self.assertEqual(app.validate_recipes([recipe],pantry,{'https://example.com/recipe?id=8&utm_source=openai'},6),[])
        self.assertIsNone(app.canonical_recipe_url('javascript:alert(1)'))
        self.assertIsNone(app.canonical_recipe_url('https://user@example.com/recipe'))
    def test_mismatched_ingredient_name_cannot_deduct_another_item(self):
        iid=self.item();pantry=app.snapshot()['items']
        recipe=dict(title='Pasta',url='https://example.com/recipe',summary='A meal.',minutes=20,missing=[],staples=[],deductions=[dict(item_id=iid,amount=30,unit='g',ingredient='Dried basil')])
        self.assertEqual(app.validate_recipes([recipe],pantry,{recipe['url']},6),[])

    def test_recipe_rejection_diagnostics(self):
        iid=self.item();pantry=app.snapshot()['items'];diagnostics=[]
        recipe=dict(title='Pasta',url='https://example.com/recipe',summary='A meal.',minutes=20,
                    missing=['a','b','c'],staples=[],deductions=[dict(item_id=iid,amount=30,unit='g',ingredient='Pasta')])
        self.assertEqual(app.validate_recipes([recipe],pantry,{recipe['url']},6,diagnostics),[])
        self.assertEqual(diagnostics,['too_many_missing'])

    def test_approved_staples_do_not_consume_missing_limit(self):
        iid=self.item();pantry=app.snapshot()['items'];url='https://example.com/recipe'
        recipe=dict(title='Shrimp pasta',url=url,summary='A meal.',minutes=20,
                    missing=['shrimp','butter','garlic','pasta'],staples=[],
                    deductions=[dict(item_id=iid,amount=30,unit='g',ingredient='Pasta')])
        found=app.validate_recipes([recipe],pantry,{url},6)
        self.assertEqual(found[0]['missing'],['shrimp'])
        self.assertEqual(set(found[0]['staples']),{'garlic','pasta','butter'})

if __name__=='__main__':unittest.main()
