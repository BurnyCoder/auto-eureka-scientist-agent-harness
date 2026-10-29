"""Evidence hashes must survive the same commit/checkout path used in publication."""
from auto_eureka_scientist.util import command, digest, write_json
from auto_eureka_scientist.science import snapshot_evidence
from auto_eureka_scientist.workspace import initialize


def test_publication_preserves_crlf_evidence_bytes(tmp_path):
    initialize(tmp_path)
    evidence = tmp_path/'cycles/001/research/observation.json'
    evidence.parent.mkdir(parents=True)
    original = b'{\r\n  "observed": true\r\n}\r\n'
    evidence.write_bytes(original)
    fingerprint = digest(evidence)
    command(['git','-c','core.autocrlf=true','add','--all'],tmp_path)
    command(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
             'commit','-m','Preserve evidence fixture'],tmp_path)
    evidence.write_text('modified working copy',encoding='utf-8')
    command(['git','-c','core.autocrlf=false','checkout','--','cycles/001/research/observation.json'],tmp_path)
    assert evidence.read_bytes()==original
    assert digest(evidence)==fingerprint
    private = tmp_path/'.eureka/private-transcript.txt'
    private.write_text('Local fixture transcript',encoding='utf-8')
    write_json(tmp_path/'cycles/001/research/evidence.json',[{'id':'private','path':'.eureka/private-transcript.txt',
               'sha256':digest(private),'analysis_kind':'not_applicable'}])
    snapshot_evidence(tmp_path/'cycles/001')
    assert not (tmp_path/'cycles/001/research/evidence-snapshots').exists()
