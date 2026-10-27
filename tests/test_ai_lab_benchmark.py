import json
from backend.design.ai_lab import benchmark


def test_partial_provider_configuration_records_blocked_hybrid(monkeypatch,tmp_path):
    monkeypatch.setattr('sys.argv',['benchmark','--case','ye-medium','--gemini-model','only-gemini','--output',str(tmp_path)])
    monkeypatch.setattr(benchmark,'run',lambda *a,**k:{'status':'BLOCKED','origin':'NO_API_RESULT','candidates':[],
        'attempted_search_options':0,'telemetry':{},'comparison':[],'pairwise_diversity':[]})
    benchmark.main()
    rows=json.loads((tmp_path/'benchmark.json').read_text())['rows']
    assert len(rows)==4
    assert next(r for r in rows if r['provider']=='HYBRID')['status']=='BLOCKED'
