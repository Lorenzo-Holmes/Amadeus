from __future__ import annotations
import json,sqlite3,unittest
import upgrade_continuity_r047 as u
class Tests(unittest.TestCase):
    def test_old_day1_session_exists_and_is_displayed(self):
        cp=u.load(u.OLD_CP); sid=cp['session_ids'][0]; db=sqlite3.connect((u.OLD/'runtime.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
        try:
            row=db.execute('SELECT user_text,assistant_text,status FROM turns WHERE session_id=? ORDER BY seq LIMIT 1',(sid,)).fetchone(); self.assertIsNotNone(row); self.assertEqual(row[0],'<kurisu hello>'); self.assertEqual(row[2],'DISPLAYED')
        finally: db.close()
    def test_old_runtime_schema_supported_by_current_store(self):
        db=sqlite3.connect((u.OLD/'runtime.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
        try: self.assertIn(db.execute('PRAGMA user_version').fetchone()[0],(45,46))
        finally: db.close()
def main():
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests)); print(json.dumps({'tests':r.testsRun,'passed':r.wasSuccessful(),'target_calls':0})); return 0 if r.wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
