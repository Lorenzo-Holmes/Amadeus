"""Offline route selection, IPC, journal quarantine and consumer binding tests."""
from __future__ import annotations
import copy, json, ssl, sys, unittest, urllib.request, uuid
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
CODE=ROOT/'persona_core/operational_runtime_v1'
sys.path[:0]=[str(CODE),str(ROOT/'persona_core/operational_build_v1/tools')]
import provider, provider_transport as pt, provider_network_route as nr
import candidate_day_v2 as gates
import evaluation_runner as runner
import test_responses_provider_integration as fixtures
import test_provider_v2_r047 as old

DIRECT={'version':nr.VERSION,'mode':'DIRECT_NO_PROXY','host':nr.HOST}
SYSTEM={**DIRECT,'mode':'SYSTEM_PROXY'}

def scope(route=DIRECT):
    s=old.scope()
    s.update(schema_version='apcore-provider-scope-5',endpoint=provider.RESPONSES_ENDPOINT,api_protocol='responses',
             network_route_policy=copy.deepcopy(route),stream=True,request_timeout_seconds=5,
             transport_policy=fixtures.POLICY,capacity_policy_id='EXTENDED_MAX_REASONING_20260911',
             output_budget_includes_reasoning=True,automatic_capacity_escalation=False)
    return s


class RouteTests(unittest.TestCase):
    def test_direct_never_discovers_system_proxy_or_bypass(self):
        with (patch.object(urllib.request,'getproxies',side_effect=AssertionError('proxy discovery')),
              patch.object(urllib.request,'proxy_bypass',side_effect=AssertionError('bypass discovery'))):
            opener=pt.route_opener(pt.Lifecycle(policy=fixtures.POLICY),DIRECT)
            req=urllib.request.Request('https://api.deepseek.com/models')
            with patch.object(urllib.request.AbstractHTTPHandler,'do_open',return_value='intercept') as do:
                self.assertEqual(opener._open(req,None),'intercept')
                self.assertEqual(do.call_args.args[1].host,'api.deepseek.com')
                self.assertIsNone(req._tunnel_host)

    def test_system_proxy_preserves_windows_environment_discovery(self):
        with (patch.object(urllib.request,'getproxies',return_value={'https':'http://127.0.0.1:10808'}) as discovery,
              patch.object(urllib.request,'proxy_bypass',return_value=False)):
            opener=pt.route_opener(pt.Lifecycle(policy=fixtures.POLICY),SYSTEM)
            req=urllib.request.Request('https://api.deepseek.com/models')
            with patch.object(urllib.request.AbstractHTTPHandler,'do_open',return_value='intercept'):
                opener._open(req,None)
            discovery.assert_called_once_with()
            self.assertEqual(req.host,'127.0.0.1:10808');self.assertEqual(req._tunnel_host,'api.deepseek.com')

    def test_legacy_route_retains_original_discovery(self):
        with patch.object(urllib.request,'getproxies',return_value={}) as discovery:
            pt.route_opener(pt.Lifecycle(policy=fixtures.POLICY))
            discovery.assert_called_once_with()

    def test_policy_rejects_other_hosts_versions_credentials_and_modes(self):
        for edit in ({'host':'other.example'},{'version':'unknown'},{'mode':'AUTO'},{'proxy':'http://user:secret@host'}):
            with self.subTest(edit=edit),self.assertRaises(ValueError):nr.check_route_policy({**DIRECT,**edit})

    def test_default_tls_certificate_and_hostname_verification_are_preserved(self):
        for route in (DIRECT,SYSTEM):
            with patch.object(urllib.request,'getproxies',return_value={}):
                opener=pt.route_opener(pt.Lifecycle(policy=fixtures.POLICY),route)
                req=urllib.request.Request('https://api.deepseek.com/models')
                with patch.object(urllib.request.AbstractHTTPHandler,'do_open',return_value='intercept') as do:
                    opener._open(req,None)
                connection=do.call_args.args[0]('api.deepseek.com')
                self.assertEqual(connection._context.verify_mode,ssl.CERT_REQUIRED)
                self.assertTrue(connection._context.check_hostname)

    def test_scope5_requires_route_and_legacy_cannot_silently_ignore_it(self):
        provider.scope_check(scope())
        missing=scope();del missing['network_route_policy']
        with self.assertRaises(ValueError):provider.scope_check(missing)
        legacy=scope();legacy['schema_version']='apcore-provider-scope-4'
        with self.assertRaises(ValueError):provider.scope_check(legacy)
        del legacy['network_route_policy'];provider.scope_check(legacy)

    def test_scope_and_generation_hashes_distinguish_routes(self):
        self.assertNotEqual(provider.digest(scope(DIRECT)),provider.digest(scope(SYSTEM)))
        a=gates.generation_settings(scope(DIRECT));b=gates.generation_settings(scope(SYSTEM))
        self.assertEqual(a['network_route_policy'],DIRECT)
        with self.assertRaisesRegex(ValueError,'GENERATION_SETTINGS_NOT_IDENTICAL'):gates.require_same_generation([a,b])
        changed=scope();del changed['network_route_policy']
        with self.assertRaises(ValueError):gates.generation_settings(changed)

    def test_worker_ipc_preserves_exact_route_in_private_frame(self):
        child=('import sys;sys.path[:0]='+repr([str(CODE),str(Path(__file__).parent)])+';'
               'import provider_transport as p,provider_http_worker as w;'
               'from test_responses_provider_integration import responses_wire,normalized;'
               'expected='+repr(DIRECT)+';'
               'p.responses_http_exchange=lambda payload,key,policy,sink,network_route_policy: '
               '(p.TransportResult(200,normalized(),responses_wire()) if network_route_policy==expected else (_ for _ in ()).throw(ValueError("ROUTE_CHANGED")));'
               'raise SystemExit(w.main())')
        result=pt.worker_exchange(pt.encode({'stream':True}),'DUMMY',5,fixtures.POLICY,
            [sys.executable,'-X','utf8','-B','-c',child],ROOT,responses=True,network_route_policy=DIRECT)
        self.assertEqual(result.body,fixtures.normalized())

    def test_evaluation_scope_builder_versions_and_copies_route(self):
        policy=dict(DIRECT)
        s=runner.build_scope('AUTHOR_ROUTE',{'slots':old.scope()['slots']},runner.checked_pricing(None,True),
            'deepseek-v4-pro','deepseek-flash',max_output_tokens=32768,transport_policy=fixtures.POLICY,
            api_protocol='responses',network_route_policy=policy)
        self.assertEqual(s['schema_version'],'apcore-provider-scope-5')
        policy['mode']='SYSTEM_PROXY';self.assertEqual(s['network_route_policy'],DIRECT)
        self.assertEqual(s['automatic_paid_retries'],0)

    def test_blind_context_rejects_unbound_route_before_reading_dialogue(self):
        import blind_review_v2 as blind
        bad=scope();del bad['network_route_policy']
        with self.assertRaisesRegex(ValueError,'NETWORK_ROUTE_POLICY_INVALID'):
            blind._verify_call_context({}, {}, {}, {}, bad)

    def test_formal_readiness_binds_freeze_route_and_refuses_second_request_scope(self):
        import shutil
        import responses_formal_readiness as formal
        token='AUTHOR_ROUTE_'+uuid.uuid4().hex
        root=runner.GOAL/('formal_responses_readiness_'+token)
        second=runner.GOAL/(root.name+'_second')
        freeze_root=ROOT/'work'/token;freeze_root.mkdir()
        freeze=freeze_root/'SOURCE_MANIFEST.json'
        runner.write_new(freeze,{'core_status':'FROZEN_FOR_VALIDATION','offline_integration_passed':True,
            'files':runner.source_bindings(),'network_route_policy':DIRECT})
        try:
            with patch.object(runner,'checked_pricing',return_value=runner.checked_pricing(None,True)):
                self.assertEqual(formal.prepare(root,freeze,None)['provider_requests'],0)
                actual=runner.read(root/'SCOPE.json')
                self.assertEqual(actual['network_route_policy'],DIRECT)
                self.assertEqual(actual['schema_version'],'apcore-provider-scope-5')
                self.assertEqual(runner.read(root/'BINDING.json')['scope_sha256'],provider.digest(actual))
                with self.assertRaisesRegex(ValueError,'ONE_FORMAL_READINESS_PER_FREEZE'):formal.prepare(second,freeze,None)
        finally:
            for path in (root,formal.runtime_root(root).parent,freeze_root):
                self.assertTrue(path.resolve().is_relative_to(ROOT.resolve()));self.assertIn(token,path.name)
                if path.exists():shutil.rmtree(path)

    def test_direct_opener_keeps_process_environment_and_global_opener_unchanged(self):
        import os
        before=dict(os.environ);global_opener=urllib.request._opener
        pt.route_opener(pt.Lifecycle(policy=fixtures.POLICY),DIRECT)
        self.assertEqual(dict(os.environ),before);self.assertIs(urllib.request._opener,global_opener)


class JournalRouteTests(unittest.TestCase):
    def setUp(self):
        self.root=old.create_sandbox(old.OUT/('route_'+uuid.uuid4().hex))
        self.store=old.TranscriptStore(self.root);self.handle=self.store.open_session('OFFLINE_OPERATOR','A')
        self.journal=provider.ProviderJournal(self.store);self.scope=scope();self.journal.register_batch(self.scope)
        self.turn=self.store.begin_turn(self.handle,'第一轮问题','one')
        self.context=old.build_context(self.store,self.handle,self.turn['turn_id'])
    def tearDown(self):self.store.close()
    def call(self):return self.journal.call(self.handle,self.turn['turn_id'],self.scope['batch_id'],'one',self.context,credential_reader=lambda:'DUMMY')

    def test_journal_scope_route_is_immutable(self):
        altered=copy.deepcopy(self.scope);altered['network_route_policy']=SYSTEM
        with self.assertRaisesRegex(ValueError,'immutable'):self.journal.register_batch(altered)

    def test_journal_sends_route_to_worker_but_not_provider_payload(self):
        seen={}
        def worker(payload,key,total,policy,command,cwd,sink,**kw):
            seen.update(kw);seen['payload']=json.loads(payload)
            self.assertEqual(self.store.db.execute('SELECT status FROM provider_calls').fetchone()[0],'SUBMITTED_STATUS_UNKNOWN')
            return pt.TransportResult(200,fixtures.normalized(),fixtures.responses_wire())
        with patch.object(pt,'worker_exchange',worker):row=self.call()
        self.assertEqual(row['status'],'RESPONSE_CAPTURED');self.assertEqual(seen['network_route_policy'],DIRECT)
        self.assertNotIn('network_route_policy',seen['payload'])
        record=dict(self.store.db.execute('SELECT * FROM provider_calls').fetchone())
        pt.verify_responses_wire(self.store.db,record,self.scope)

    def test_unknown_stays_unknown_and_no_paid_retry_or_second_slot(self):
        with patch.object(pt,'worker_exchange',side_effect=pt.TransportFault('CONNECT_TIMEOUT')) as worker:
            first=self.call();second=self.call()
            self.assertEqual(first['status'],'SUBMITTED_STATUS_UNKNOWN');self.assertEqual(first['call_id'],second['call_id'])
            self.assertEqual(worker.call_count,1)
            self.assertEqual(self.store.db.execute('SELECT stopped FROM call_batches').fetchone()[0],1)
            turn=self.store.begin_turn(self.handle,'第二轮追问','two')
            context=old.build_context(self.store,self.handle,turn['turn_id'])
            with self.assertRaises(ValueError):self.journal.call(self.handle,turn['turn_id'],self.scope['batch_id'],'two',context,credential_reader=lambda:'DUMMY')
            self.assertEqual(worker.call_count,1)

if __name__=='__main__':unittest.main(verbosity=2)
