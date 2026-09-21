"""No-network fixtures for staged spend gates and one candidate lineage."""
import copy, json, unittest
from pathlib import Path
import governance_v2 as g
import structural_governance as sg
import test_governance_v2 as base
import test_new_candidate_governance as old


class StructuralGovernanceTests(unittest.TestCase):
    setUp=base.GovernanceTests.setUp
    write=base.GovernanceTests.write
    payload=base.GovernanceTests.payload
    sync=base.GovernanceTests.sync

    def ready(self):
        value=old.NewCandidateGovernanceTests.ready(self,False)
        pointer=g.load(self.root/g.CANONICAL)
        self.write('code/calibration.py',{'fixed_second_stage':True})
        cfg=g.load(self.root/'new_config.json');cfg.pop('generation_calibration')
        cfg['structural_calibration']={'mechanism_version':'APCORE_FIXED_TWO_STAGE_PIPELINE_1','max_stages':2,
            'implementation':[g.reference(self.root,'code/calibration.py')],
            'integration':[g.reference(self.root,'code/expression.py')]}
        self.write('new_config.json',cfg)
        value['configuration']=g.reference(self.root,'new_config.json')
        value['draw_lineage']['configuration_sha256']=value['configuration']['sha256']
        source=g.load(self.root/'new_source.json');source['files']['code/calibration.py']=g.reference(self.root,'code/calibration.py')['sha256']
        self.write('new_source.json',source);value['source_freeze']=g.reference(self.root,'new_source.json')
        self.write('tests.json',{'status':'PASS','source_files':source['files'],'results':[{'tests':1,'exit_code':0,'skipped':0}]})
        value['test_receipt']=g.reference(self.root,'tests.json')
        self.write('full_path.json',{'status':'PASS','source_files':source['files']})
        value['full_path_receipt']=g.reference(self.root,'full_path.json')
        actual=g.ROOT/g.G6/'structural_calibration_20260921_01/TASK_AUTHORIZATION.json'
        auth=g.load(actual);auth.update(candidate_id='new-product',parent_checkpoint=pointer['checkpoint'])
        self.write('structural_auth.json',auth)
        value.update(active_task=sg.TASK,task_authorization=g.reference(self.root,'structural_auth.json'),
            status='READY_FOR_STRUCTURAL_SMOKE',paid_phase='SMOKE',paid_cycle_closed=False,paid_requests_allowed=True,
            r19_parent_checkpoint=pointer['checkpoint'],active_paid_scope_sha256='a'*64,
            formal_attempt={'kind':'POST_FAIL_PRODUCT_REPAIR_NEW_CANDIDATE','allocations':0,'revision':None},
            integrity_manifests=[value['source_freeze']],
            smoke_attempt={'allocations':1,'max_requests':50,'scope_sha256':'a'*64,
                           'source_manifest':value['source_freeze'],'configuration':value['configuration']})
        self.write('smoke_inputs.json',{'authored':True})
        self.write('smoke_prereg.json',{'inputs':g.reference(self.root,'smoke_inputs.json')})
        value['smoke_preregistration']=g.reference(self.root,'smoke_prereg.json')
        pre={'status':'READY','kind':'ZERO_PROVIDER_SMOKE_PREFLIGHT','candidate_id':'new-product',
            'source_manifest':value['source_freeze'],'configuration':value['configuration'],
            'scope_sha256':'a'*64,'pipeline_max_stages':2,'stage_request_limits':{'draft':1,'calibration':1},
            'max_requests':50,
            **{k:0 for k in ('provider_call_invocations','provider_call_rows','calibration_call_invocations',
                 'calibration_call_rows','generation_request_invocations','readiness_requests','token_count_request_invocations',
                 'automatic_paid_retries','active_paid_driver_count')}}
        self.write('structural_preflight.json',pre)
        value['preflight']=g.reference(self.root,'structural_preflight.json')
        return value

    def formal(self,value,status='PASS'):
        self.write('smoke_receipt.json',{'status':status,'end_to_end_reviewed':20,'authored_probes_reviewed':10,
            'unclear':0,'failed':0,'source_manifest':value['source_freeze'],'configuration':value['configuration'],
            'independent_from_product_calibration_step':True})
        value['smoke_receipt']=g.reference(self.root,'smoke_receipt.json')
        pre=g.pinned_json(self.root,value['preflight']);pre.update(kind='ZERO_PROVIDER_FORMAL_BINDING_PREFLIGHT',
            max_requests=88,scope_contract_sha256='b'*64,denominators={'turns':44,'criteria':176,'gate_a':176,'gate_b':132})
        self.write('formal_preflight.json',pre);value['preflight']=g.reference(self.root,'formal_preflight.json')
        value.update(status='READY_FOR_SINGLE_NEW_CANDIDATE_ATTEMPT',paid_phase='FORMAL',active_paid_scope_contract_sha256='b'*64,
            formal_attempt={'kind':'POST_FAIL_PRODUCT_REPAIR_NEW_CANDIDATE','allocations':1,'revision':'single-formal'})
        return value

    def test_smoke_can_activate_without_formal_draw(self):
        value=self.ready();self.sync(value)
        self.assertTrue(g.resume(self.root)['paid_requests_allowed'])
        self.assertEqual(value['formal_attempt']['allocations'],0)

    def test_formal_only_after_smoke_pass(self):
        value=self.ready();self.sync(value);self.formal(value);self.sync(value)
        self.assertTrue(g.resume(self.root)['paid_requests_allowed'])

    def test_failed_smoke_cannot_activate_formal(self):
        value=self.ready();self.sync(value);self.formal(value,'FAIL')
        with self.assertRaisesRegex(g.GovernanceError,'SMOKE_PASS_REQUIRED'):self.sync(value)

    def test_unclear_smoke_cannot_activate_formal(self):
        value=self.ready();self.sync(value);self.formal(value,'UNCLEAR')
        with self.assertRaisesRegex(g.GovernanceError,'SMOKE_PASS_REQUIRED'):self.sync(value)

    def test_closed_paid_cycle_cannot_reopen(self):
        value=self.ready();self.sync(value)
        value.update(paid_cycle_closed=True,paid_requests_allowed=False,status='SMOKE_FAILED_NO_FORMAL_DRAW')
        self.sync(value);value.update(paid_cycle_closed=False,paid_requests_allowed=True,status='READY_FOR_STRUCTURAL_SMOKE')
        with self.assertRaisesRegex(g.GovernanceError,'CANNOT_REOPEN'):self.sync(value)

    def test_second_formal_revision_forbidden(self):
        value=self.ready();self.sync(value);self.formal(value);self.sync(value)
        value['formal_attempt']['revision']='second'
        with self.assertRaisesRegex(g.GovernanceError,'REPLACEMENT_FORBIDDEN'):self.sync(value)

    def test_smoke_scope_cannot_be_replaced(self):
        value=self.ready();self.sync(value);value.update(paid_requests_allowed=False)
        value['smoke_attempt']['scope_sha256']='c'*64
        with self.assertRaisesRegex(g.GovernanceError,'SMOKE_REPLACEMENT'):self.sync(value)

    def test_integration_change_required_not_prompt_marker(self):
        value=self.ready()
        cfg=g.pinned_json(self.root,value['configuration']);cfg['structural_calibration']['integration']=[]
        self.write('new_config.json',cfg);value['configuration']=g.reference(self.root,'new_config.json')
        value['draw_lineage']['configuration_sha256']=value['configuration']['sha256']
        value['paid_requests_allowed']=False
        with self.assertRaisesRegex(g.GovernanceError,'IMPLEMENTATION_REQUIRED'):self.sync(value)


def rejected_preflight(field,value):
    def test(self):
        v=self.ready();p=g.pinned_json(self.root,v['preflight']);p[field]=value
        self.write('structural_preflight.json',p);v['preflight']=g.reference(self.root,'structural_preflight.json')
        with self.assertRaises(g.GovernanceError):self.sync(v)
    return test
for field,value in [('calibration_call_invocations',1),('calibration_call_rows',1),('generation_request_invocations',1),
                    ('active_paid_driver_count',1),('max_requests',51),('pipeline_max_stages',3),
                    ('stage_request_limits',{'draft':1,'calibration':2}),('configuration',{})]:
    setattr(StructuralGovernanceTests,'test_preflight_reject_'+field,rejected_preflight(field,value))

if __name__=='__main__':unittest.main(verbosity=2)
