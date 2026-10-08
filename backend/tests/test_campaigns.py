from uuid import uuid4
import json
import httpx
import pytest
from sqlalchemy import select, func
from app import campaigns
from app.ai import OpenAIProvider, AIError, schema_for, Ideas
from app.models import Campaign, Generation, Content, ContentRevision
from app.config import settings
from app.auth import COOKIE
from test_auth_brands import setup, seed

HEADERS = {'Origin':'http://testserver'}
BRIEF = {'topic':'가을 여행','goal':'방문 유도','keywords':'오션뷰','direction':'정보 중심','channels':['blog','instagram','linkedin']}

class FakeProvider:
    def __init__(self): self.calls=[]
    def generate(self, kind, context):
        self.calls.append((kind,context))
        if kind=='ideas':
            return {'ideas':[{'title':f'여행 아이디어 {i}','angle':'브랜드를 알리는 여행 이야기','rationale':'타깃의 관심사 반영'} for i in range(3)]}, {'total_tokens':100}
        return {'contents':[{'channel':channel,'title':channel+' 초안','body':'테스트 초안 본문'} for channel in context['channels']]}, {'total_tokens':200}

@pytest.fixture
def studio(setup, monkeypatch):
    client,factory=setup
    seed(factory)
    client.cookies.set(COOKIE,'owner-token')
    brand=client.post('/api/brands',headers=HEADERS,json={'name':'Oceanview','description':'여행 검색','target_audience':'여행객','tone':'친근함'}).json()
    provider=FakeProvider()
    monkeypatch.setattr(campaigns,'get_provider',lambda:provider)
    return client,factory,brand['id'],provider

def test_full_workflow_history_and_retry(studio):
    client,factory,bid,provider=studio
    payload={**BRIEF,'request_key':str(uuid4())}
    result=client.post(f'/api/brands/{bid}/ideas',headers=HEADERS,json=payload)
    assert result.status_code==200
    batch=result.json()
    repeat=client.post(f'/api/brands/{bid}/ideas',headers=HEADERS,json=payload)
    assert repeat.json()['id']==batch['id'] and len(provider.calls)==1
    assert client.post(f'/api/brands/{bid}/ideas',headers=HEADERS,json={**payload,'topic':'다른 주제'}).status_code==409
    assert client.get(f'/api/brands/{bid}/ideas').json()[0]['result']==batch['result']
    data={**BRIEF,'title':'첫 캠페인','source_generation_id':batch['id'],'idea_index':0}
    campaign=client.post(f'/api/brands/{bid}/campaigns',headers=HEADERS,json=data).json()
    assert client.post(f'/api/brands/{bid}/campaigns',headers=HEADERS,json=data).json()['id']==campaign['id']
    url=f"/api/campaigns/{campaign['id']}/generate"
    generated=client.post(url,headers=HEADERS,json={'request_key':str(uuid4())})
    assert generated.status_code==200
    contents=generated.json()['contents']; assert len(contents)==3
    assert client.post(url,headers=HEADERS,json={'request_key':str(uuid4())}).json()['contents']==contents
    assert len(provider.calls)==2
    c=contents[0]
    edit={'title':'수정 제목','body':'수정 본문','revision':1}
    saved=client.put(f"/api/contents/{c['id']}",headers=HEADERS,json=edit)
    assert saved.status_code==200 and saved.json()['revision']==2
    assert client.put(f"/api/contents/{c['id']}",headers=HEADERS,json=edit).status_code==409
    history=client.get(f"/api/contents/{c['id']}/revisions").json()
    assert [h['revision'] for h in history]==[2,1]
    assert history[1]['body']=='테스트 초안 본문'
    assert client.post(url,headers=HEADERS,json={'request_key':str(uuid4())}).json()['contents'][0]['body']=='수정 본문'
    assert client.delete(f'/api/brands/{bid}',headers=HEADERS).status_code==409

def test_access_control_and_validation(studio):
    client,factory,bid,_=studio
    campaign=client.post(f'/api/brands/{bid}/campaigns',headers=HEADERS,json={**BRIEF,'title':'직접 기획'}).json()
    cid=campaign['id']
    result=client.post(f'/api/campaigns/{cid}/generate',headers=HEADERS,json={'request_key':str(uuid4())}).json()
    content=result['contents'][0]
    assert client.post(f'/api/brands/{bid}/ideas',json={**BRIEF,'request_key':str(uuid4())}).status_code==403
    assert client.post(f'/api/brands/{bid}/ideas',headers=HEADERS,json={**BRIEF,'channels':['tiktok'],'request_key':str(uuid4())}).status_code==422
    assert client.post(f'/api/brands/{bid}/campaigns',headers=HEADERS,json={**BRIEF,'title':'x','channels':[]}).status_code==422
    assert client.post(f'/api/brands/{bid}/campaigns',headers=HEADERS,json={**BRIEF,'title':'x','channels':['blog','blog']}).status_code==422
    seed(factory,token='other-token',sub='other');client.cookies.set(COOKIE,'other-token')
    for path in (f'/brands/{bid}/ideas',f'/brands/{bid}/campaigns',f'/campaigns/{cid}',f"/contents/{content['id']}/revisions"):
        assert client.get('/api'+path).status_code==404
    assert client.post(f'/api/brands/{bid}/ideas',headers=HEADERS,json={**BRIEF,'request_key':str(uuid4())}).status_code==404
    assert client.post(f'/api/brands/{bid}/campaigns',headers=HEADERS,json={**BRIEF,'title':'x'}).status_code==404
    assert client.post(f'/api/campaigns/{cid}/generate',headers=HEADERS,json={'request_key':str(uuid4())}).status_code==404
    assert client.put(f"/api/contents/{content['id']}",headers=HEADERS,json={'title':'x','body':'x','revision':1}).status_code==404
    client.cookies.clear();assert client.get('/api/ai/config').status_code==401

def test_failures_atomicity_quota_and_missing_config(studio,monkeypatch):
    client,factory,bid,provider=studio
    def fail(*args): raise AIError('시간 초과',504)
    monkeypatch.setattr(provider,'generate',fail)
    campaign=client.post(f'/api/brands/{bid}/campaigns',headers=HEADERS,json={**BRIEF,'title':'실패 테스트'}).json()
    assert client.post(f"/api/campaigns/{campaign['id']}/generate",headers=HEADERS,json={'request_key':str(uuid4())}).status_code==504
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Content))==0
        assert db.scalar(select(func.count()).select_from(ContentRevision))==0
        assert db.scalar(select(Generation)).error=='시간 초과'
    monkeypatch.setattr(settings,'ai_daily_limit',1)
    assert client.post(f'/api/brands/{bid}/ideas',headers=HEADERS,json={**BRIEF,'request_key':str(uuid4())}).status_code==429
    monkeypatch.setattr(settings,'ai_daily_limit',30)
    from app.ai import get_provider
    monkeypatch.setattr(campaigns,'get_provider',get_provider)
    monkeypatch.setattr(settings,'ai_provider','openai')
    monkeypatch.setattr(settings,'openai_api_key','')
    assert client.get('/api/ai/config').json()['enabled'] is False
    assert client.post(f'/api/brands/{bid}/ideas',headers=HEADERS,json={**BRIEF,'request_key':str(uuid4())}).status_code==503
    assert client.post(f'/api/brands/{bid}/campaigns',headers=HEADERS,json={**BRIEF,'title':'키 없이 직접 기획'}).status_code==201

@pytest.mark.parametrize('failure',['timeout','auth','rate','bad_json','refusal','incomplete','channels','length',None])
def test_provider_contract(monkeypatch,failure):
    RealClient=httpx.Client
    def handler(request):
        data=json.loads(request.content)
        assert data['store'] is False and data['text']['format']['strict'] is True
        assert 'brand' in json.loads(data['input'])
        if failure=='timeout':raise httpx.ReadTimeout('test')
        if failure=='auth':return httpx.Response(401,json={'error':'secret should not leak'})
        if failure=='rate':return httpx.Response(429,json={})
        channels=['blog'] if failure=='channels' else ['instagram']
        output={'contents':[{'channel':c,'title':'제목','body':'x'*2201 if failure=='length' else '본문'} for c in channels]}
        part={'type':'refusal','refusal':'no'} if failure=='refusal' else {'type':'output_text','text':'bad' if failure=='bad_json' else json.dumps(output)}
        return httpx.Response(200,json={'status':'incomplete' if failure=='incomplete' else 'completed','output':[{'type':'message','content':[part]}], 'usage':{'total_tokens':10}})
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:RealClient(transport=httpx.MockTransport(handler),**kwargs))
    if failure:
        with pytest.raises(AIError) as exc: OpenAIProvider().generate('drafts',{'brand':{},'channels':['instagram']})
        assert 'secret' not in str(exc.value)
    else:
        data,usage=OpenAIProvider().generate('drafts',{'brand':{},'channels':['instagram']})
        assert data['contents'][0]['body']=='본문' and usage['total_tokens']==10

@pytest.mark.parametrize('failure', ['', 'timeout', 'connect', 'missing', 'length', 'channels', 'json', 'truncated'])
def test_ollama_contract(monkeypatch, failure):
    from app.ai import OllamaProvider
    RealClient = httpx.Client
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.path == '/api/chat'
        assert payload['stream'] is False and payload['format']['additionalProperties'] is False
        if failure == 'timeout': raise httpx.ReadTimeout('private')
        if failure == 'connect': raise httpx.ConnectError('private')
        if failure == 'missing': return httpx.Response(404, json={'error':'private'})
        output = {'contents':[{'channel':'blog' if failure=='channels' else 'instagram',
                              'title':'제목', 'body':'x'*2201 if failure=='length' else '본문'}]}
        return httpx.Response(200, json={'done':True, 'done_reason':'length' if failure=='truncated' else 'stop',
            'message':{'content':'bad' if failure=='json' else json.dumps(output)},
            'prompt_eval_count':10, 'eval_count':20})
    monkeypatch.setattr(httpx, 'Client', lambda **kw: RealClient(transport=httpx.MockTransport(handler), **kw))
    if failure:
        with pytest.raises(AIError) as exc:
            OllamaProvider().generate('drafts', {'channels':['instagram']})
        assert 'private' not in str(exc.value)
    else:
        result, usage = OllamaProvider().generate('drafts', {'channels':['instagram']})
        assert result['contents'][0]['body'] == '본문' and usage['total_tokens'] == 30

def test_ollama_configuration(studio, monkeypatch):
    from app.ai import get_provider, OllamaProvider, active_model
    monkeypatch.setattr(settings, 'ai_provider', 'ollama')
    monkeypatch.setattr(settings, 'ollama_model', 'llama3:latest')
    assert isinstance(get_provider(), OllamaProvider)
    assert active_model() == 'llama3:latest'

    client, factory, bid, _ = studio
    config = client.get('/api/ai/config').json()
    assert config['enabled'] and config['model'] == 'llama3:latest'
    response = client.post(f'/api/brands/{bid}/ideas', headers=HEADERS,
                           json={**BRIEF, 'request_key':str(uuid4())})
    assert response.status_code == 200
    with factory() as db:
        generation = db.scalar(select(Generation).where(Generation.id == response.json()['id']))
        assert generation.provider == 'ollama' and generation.model == 'llama3:latest'
