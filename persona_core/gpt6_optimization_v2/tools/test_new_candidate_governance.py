"""Synthetic fixtures for narrowly authorized post-failure product transitions."""
import copy,zipfile,unittest
import governance_v2 as g
import test_governance_v2 as fixtures

class NewCandidateGovernanceTests(unittest.TestCase):
    setUp=fixtures.GovernanceTests.setUp
    write=fixtures.GovernanceTests.write
    payload=fixtures.GovernanceTests.payload
    sync=fixtures.GovernanceTests.sync

    def ready(self,paid=True):
        self.write('code/expression.py',{'generation':'old'})
        old_bytes=(self.root/'code/expression.py').read_bytes()
        self.write('old_source.json',{'files':{'code/expression.py':g.sha(old_bytes)}})
        old=self.payload(status='HARD_STOP_REQUIRED_CONVERSATION_CRITERION_FAIL',r18={'quality':'FAIL','original_verdict_preserved':True},
                         source_freeze=g.reference(self.root,'old_source.json'))
        pointer=self.sync(old)
        with zipfile.ZipFile(self.root/'archive.zip','x') as z:z.writestr('code/expression.py',old_bytes)
        self.write('code/expression.py',{'generation':'new_generic_rule'})
        implementation=g.reference(self.root,'code/expression.py')
        self.write('new_config.json',{'candidate_id':'new-product','generation_calibration':{'implementation':implementation}})
        cfg=g.reference(self.root,'new_config.json')
        files={'code/expression.py':implementation['sha256']}
        self.write('new_source.json',{'files':files,'parent_manifest':old['source_freeze']})
        freeze=g.reference(self.root,'new_source.json')
        self.write('auth.json',dict(kind='POST_FAIL_PRODUCT_REPAIR_NEW_CANDIDATE',status='PROJECT_COMPLETION_SPEND_AUTHORIZED_AS_NEEDED',
            source='CURRENT_EXPLICIT_USER_REQUEST_20260921',task='new-task',candidate_id='new-product',
            parent_checkpoint=pointer['checkpoint'],paid_validation_allowed=True,max_fresh_revisions=1,max_generation_requests=44,
            automatic_paid_retries=0,readiness_requests=0,count_api_requests=0,fallback_allowed=False,replacement_draw=False,
            historical_draw_refunded=False,r18_preserved=True,r18_resume_replay_resend=False))
        self.write('preflight.json',dict(status='READY',kind='ZERO_PROVIDER_FORMAL_BINDING_PREFLIGHT',candidate_id='new-product',
            denominators=dict(turns=44,criteria=176,gate_a=176,gate_b=132),source_manifest=freeze,
            **{k:0 for k in ('provider_call_invocations','provider_call_rows','generation_request_invocations','readiness_requests',
                'token_count_request_invocations','automatic_paid_retries','active_paid_driver_count')}))
        self.write('tests.json',dict(status='PASS',source_files=files,results=[dict(exit_code=0,tests=1,skipped=0)]))
        value=self.payload(active_task='new-task',status='READY_FOR_SINGLE_NEW_CANDIDATE_ATTEMPT',paid_requests_allowed=paid,
            paid_validation_blockers=[],draw_lineage=dict(root_id='new-root',candidate_id='new-product',configuration_sha256=cfg['sha256'],
                benchmark_sha256=self.lineage['benchmark_sha256'],replacement_allocations=0),
            r18=old['r18'],historical_lineages=[old['draw_lineage']],source_freeze=freeze,configuration=cfg,
            integrity_manifests=[freeze],task_authorization=g.reference(self.root,'auth.json'),
            preflight=g.reference(self.root,'preflight.json'),test_receipt=g.reference(self.root,'tests.json'),
            formal_attempt=dict(allocations=1,revision='new-revision',kind='POST_FAIL_PRODUCT_REPAIR_NEW_CANDIDATE'),
            lineage_transition=dict(kind='POST_FAIL_PRODUCT_REPAIR_NEW_CANDIDATE',parent_checkpoint=pointer['checkpoint'],
                parent_lineage=old['draw_lineage'],parent_source_archive=g.reference(self.root,'archive.zip')))
        return value

    def test_authorized_new_product_can_commit_and_resume(self):
        value=self.ready();self.sync(value)
        self.assertTrue(g.resume(self.root)['paid_requests_allowed'])

    def test_new_lineage_keeps_prior_failed_checkpoint(self):
        value=self.ready(False);new=self.sync(value)
        old=g.pinned_json(self.root,new['previous_checkpoint'])
        self.assertEqual(old['r18'],value['r18'])
        self.assertEqual(old['draw_lineage'],value['historical_lineages'][0])

    def test_second_revision_cannot_replace_first(self):
        value=self.ready();self.sync(value);value['formal_attempt']['revision']='another'
        with self.assertRaisesRegex(g.GovernanceError,'FORMAL_ATTEMPT_REPLACEMENT'):self.sync(value)

    def test_fail_can_close_gate_but_cannot_erase_history(self):
        value=self.ready();self.sync(value)
        value.update(paid_requests_allowed=False,status='HARD_STOP_REQUIRED_CONVERSATION_CRITERION_FAIL')
        self.sync(value);value['r18']={'quality':'PASS'}
        with self.assertRaisesRegex(g.GovernanceError,'HISTORY_REWRITE'):self.sync(value)

    def test_authorization_cannot_reopen_failed_attempt(self):
        value=self.ready();value['status']='HARD_STOP_REQUIRED_CONVERSATION_CRITERION_FAIL'
        with self.assertRaisesRegex(g.GovernanceError,'PAID_GATE_BLOCKED'):self.sync(value)

def negative(name,mutate):
    def test(self):
        value=self.ready();mutate(self,value)
        with self.assertRaises((g.GovernanceError,KeyError,zipfile.BadZipFile)):self.sync(value)
    setattr(NewCandidateGovernanceTests,'test_reject_'+name,test)

def change_file(test,value,key,path,mutate):
    obj=g.load(test.root/path);mutate(obj);test.write(path,obj);value[key]=g.reference(test.root,path)

negative('missing_auth',lambda t,v:v.pop('task_authorization'))
negative('old_candidate',lambda t,v:v['draw_lineage'].update(candidate_id=t.lineage['candidate_id']))
negative('same_configuration',lambda t,v:v['draw_lineage'].update(configuration_sha256=t.lineage['configuration_sha256']))
negative('benchmark_change',lambda t,v:v['draw_lineage'].update(benchmark_sha256='f'*64))
negative('refunded_draw',lambda t,v:change_file(t,v,'task_authorization','auth.json',lambda a:a.update(historical_draw_refunded=True)))
negative('two_attempt_auth',lambda t,v:change_file(t,v,'task_authorization','auth.json',lambda a:a.update(max_fresh_revisions=2)))
negative('retry_auth',lambda t,v:change_file(t,v,'task_authorization','auth.json',lambda a:a.update(automatic_paid_retries=1)))
negative('wrong_parent',lambda t,v:v['lineage_transition'].update(parent_checkpoint={}))
negative('erased_failed_candidate',lambda t,v:v.update(historical_lineages=[]))
negative('rewritten_r18',lambda t,v:v.update(r18={'quality':'PASS'}))
negative('unready_preflight',lambda t,v:change_file(t,v,'preflight','preflight.json',lambda a:a.update(status='NOT_READY')))
negative('paid_preflight',lambda t,v:change_file(t,v,'preflight','preflight.json',lambda a:a.update(generation_request_invocations=1)))
negative('wrong_preflight_candidate',lambda t,v:change_file(t,v,'preflight','preflight.json',lambda a:a.update(candidate_id='wrong')))
negative('failed_test',lambda t,v:change_file(t,v,'test_receipt','tests.json',lambda a:a['results'][0].update(exit_code=1)))
negative('skip_test',lambda t,v:change_file(t,v,'test_receipt','tests.json',lambda a:a['results'][0].update(skipped=1)))
negative('empty_tests',lambda t,v:change_file(t,v,'test_receipt','tests.json',lambda a:a.update(results=[])))
negative('source_drift',lambda t,v:t.write('code/expression.py',{'tampered':True}))
negative('parent_archive_drift',lambda t,v:(t.root/'archive.zip').write_bytes(b'bad'))
negative('two_allocations',lambda t,v:v['formal_attempt'].update(allocations=2))
if __name__=='__main__':unittest.main(verbosity=2)
