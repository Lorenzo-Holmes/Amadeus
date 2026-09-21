"""Read-only, lossless R043 import preflight; never repairs or reinstalls it."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from provider import digest
from transcript_store import ensure,file_sha

VERSION='LEGACY_R043_GENESIS_ONLY_IMPORT_V1'
FILES=('RUNTIME_META.json','SELF_STATE.json','AFFECT_STATE.json','RELATIONSHIP_STATE.json',
       'DECISION_STATE.json','EXPERIENCE_LEDGER.jsonl','genesis/GENESIS_SNAPSHOT_R035.json')

def inspect_legacy(root:Path, expected_genesis_sha256:str) -> dict:
    """Reject nonempty legacy state until an explicit lossless importer exists.

This is a compatibility boundary, not data deletion. Original files and the
non-supported runtime can still be opened by its original read-only tooling.
"""
    root=root.resolve()
    raw={name:(root/name).read_bytes() for name in FILES}
    parsed={name:json.loads(data.decode('utf-8')) for name,data in raw.items() if name.endswith('.json')}
    genesis=parsed['genesis/GENESIS_SNAPSHOT_R035.json']
    genesis_hash=hashlib.sha256(raw['genesis/GENESIS_SNAPSHOT_R035.json']).hexdigest()
    ensure(genesis_hash==expected_genesis_sha256,'Legacy Genesis hash mismatch')
    meta=parsed['RUNTIME_META.json']
    ensure(meta['genesis_sha256']==genesis_hash and meta['genesis_id']==genesis['genesis_id'],'Legacy identity mismatch')
    rows=[json.loads(line) for line in raw['EXPERIENCE_LEDGER.jsonl'].decode('utf-8').splitlines() if line.strip()]
    ensure(rows and rows[0]['event_type']=='GENESIS_EVENT','Legacy ledger has no Genesis root')
    previous=None
    seen=set()
    for i,row in enumerate(rows):
        ensure(row['sequence']==i and row['previous_event_sha256']==previous,'Legacy ledger sequence/chain mismatch')
        ensure(row['event_id'] not in seen,'Legacy duplicate event ID')
        expected=digest({k:v for k,v in row.items() if k!='event_sha256'})
        ensure(expected==row['event_sha256'],'Legacy event content hash mismatch')
        previous=row['event_sha256']; seen.add(row['event_id'])
    ensure(meta['next_sequence']==len(rows) and meta['last_event_sha256']==previous,'Legacy meta/ledger mismatch')
    ensure(rows[0]['genesis_id']==genesis['genesis_id'] and rows[0]['genesis_sha256']==genesis_hash,'Legacy event identity mismatch')
    mapping={'self':'SELF_STATE.json','affect':'AFFECT_STATE.json','relationship':'RELATIONSHIP_STATE.json','decision':'DECISION_STATE.json'}
    ensure(meta.get('state_hashes') is not None,'Legacy state integrity references required')
    for key,name in mapping.items():
        ensure(hashlib.sha256(raw[name]).hexdigest()==meta['state_hashes'][key],'Legacy state byte mismatch: '+name)
        ensure(parsed[name]['genesis_id']==genesis['genesis_id'],'Legacy state Genesis mismatch')
    relationship=parsed['RELATIONSHIP_STATE.json']
    affect=parsed['AFFECT_STATE.json']
    ensure(len(rows)==1 and relationship['product_entities']=={} and relationship['state_version']==0,
           'Nonempty legacy experience is unsupported by this importer; preserve it read-only rather than silently resetting')
    ensure(affect['state_version']==0 and all(v==0 for v in affect['deviation_from_baseline'].values()),
           'Nonbaseline legacy affect cannot be discarded during migration')
    for component in genesis['frozen_components']:
        path=root/'genesis/frozen'/Path(component['path']).name
        ensure(file_sha(path)==component['sha256'],'Frozen component mismatch')
    return {'import_policy':VERSION,'genesis_id':genesis['genesis_id'],'genesis_sha256':genesis_hash,
            'legacy_event_count':len(rows),'legacy_event_tail_sha256':previous,
            'product_entities_imported':0,'source_relationship_roots':relationship['source_relationship_roots'],
            'legacy_state_objects':{k:parsed[v] for k,v in mapping.items()},
            'preserved_files':[{'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in raw.items()],
            'source_bytes_modified':False,'genesis_reinstalled':False}
