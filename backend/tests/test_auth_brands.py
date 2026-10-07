import time
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from joserfc import jwt
from joserfc.jwk import RSAKey
from app.main import app
from app.db import Base, get_db
from app.models import User, LoginSession, Brand
from app.auth import oauth, token_hash, COOKIE
from app.config import settings

@pytest.fixture
def setup(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    def db():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = db
    monkeypatch.setattr(settings, 'app_origin', 'http://testserver')
    monkeypatch.setattr(settings, 'google_client_id', 'test-client')
    monkeypatch.setattr(settings, 'google_client_secret', 'test-secret')
    monkeypatch.setattr(settings, 'session_secret', 's' * 48)
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    engine.dispose()

def seed(factory, token='owner-token', sub='owner', expired=False):
    with factory() as db:
        user = User(google_sub=sub, email=f'{sub}@example.com', name=sub)
        db.add(user); db.flush()
        db.add(LoginSession(token_hash=token_hash(token), user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(days=-1 if expired else 1)))
        db.commit()
        return user.id

def test_crud_ownership_validation_and_csrf(setup):
    client, factory = setup
    assert client.get('/api/brands').status_code == 401
    seed(factory)
    client.cookies.set(COOKIE, 'owner-token')
    payload = dict(name=' Oceanview ', description='여행 검색', target_audience='여행객', tone='친근함')
    assert client.post('/api/brands', json=payload).status_code == 403
    assert client.post('/api/brands', json=payload, headers={'Origin':'https://evil.example'}).status_code == 403
    headers = {'Origin':'http://testserver'}
    assert client.post('/api/brands', json={**payload, 'name':'  '}, headers=headers).status_code == 422
    response = client.post('/api/brands', json=payload, headers=headers)
    assert response.status_code == 201
    brand = response.json(); assert brand['name'] == 'Oceanview'
    assert len(client.get('/api/brands').json()) == 1
    url = f"/api/brands/{brand['id']}"
    assert client.put(url, json={**payload, 'name':'Updated'}, headers=headers).json()['name'] == 'Updated'
    seed(factory, token='other-token', sub='other')
    client.cookies.set(COOKIE, 'other-token')
    assert client.get('/api/brands').json() == []
    assert client.get(url).status_code == 404
    assert client.put(url, json=payload, headers=headers).status_code == 404
    assert client.delete(url, headers=headers).status_code == 404
    client.cookies.set(COOKIE, 'owner-token')
    assert client.delete(url, headers=headers).status_code == 204
    assert client.get(url).status_code == 404

def test_expiry_logout_and_unowned_records(setup):
    client, factory = setup
    seed(factory, expired=True)
    client.cookies.set(COOKIE, 'owner-token')
    assert client.get('/api/auth/me').status_code == 401
    seed(factory, token='valid', sub='valid')
    with factory() as db:
        db.add(Brand(name='legacy', description='preserved', tone='plain', target_audience='all'));db.commit()
    client.cookies.set(COOKIE,'valid')
    assert client.get('/api/brands').json() == []
    assert client.post('/api/auth/logout',headers={'Origin':'http://testserver'}).status_code == 204
    client.cookies.set(COOKIE,'valid')
    assert client.get('/api/auth/me').status_code == 401

def test_missing_configuration_and_invalid_state(setup, monkeypatch):
    client, _ = setup
    assert client.get('/api/auth/google/callback?code=fake&state=invalid', follow_redirects=False).headers['location'].endswith('login_failed')
    monkeypatch.setattr(settings,'google_client_id','')
    assert client.get('/api/auth/config').json() == {'google_enabled':False}
    assert client.get('/api/auth/google/login',follow_redirects=False).headers['location'].endswith('not_configured')

@pytest.mark.parametrize('invalid', [None, 'nonce', 'aud', 'iss', 'exp', 'signature', 'email'])
def test_oidc_flow_validates_signed_tokens(setup, monkeypatch, invalid):
    client, factory = setup
    key = RSAKey.generate_key(2048)
    key.ensure_kid()
    google = oauth.google
    monkeypatch.setattr(google, 'client_id', 'test-client')
    metadata = {'issuer':'https://accounts.google.com',
        'authorization_endpoint':'https://accounts.google.com/o/oauth2/v2/auth',
        'token_endpoint':'https://oauth2.googleapis.com/token',
        'jwks':{'keys':[key.as_dict(private=False)]},
        'id_token_signing_alg_values_supported':['RS256'], '_loaded_at':time.time()}
    monkeypatch.setattr(google,'server_metadata',metadata)
    response = client.get('/api/auth/google/login', follow_redirects=False)
    assert response.status_code == 302
    params = parse_qs(urlparse(response.headers['location']).query)
    assert params['code_challenge_method'] == ['S256']
    claims = {'iss':'https://accounts.google.com','sub':'google-123','aud':'test-client',
        'iat':int(time.time()),'exp':int(time.time())+3600,'nonce':params['nonce'][0],
        'email':'verified@example.com','email_verified':True,'name':'Tester'}
    if invalid in ('nonce','aud','iss'): claims[invalid] = 'wrong'
    if invalid == 'exp': claims['exp'] = int(time.time()) - 3600
    if invalid == 'email': claims['email_verified'] = False
    signing_key = RSAKey.generate_key(2048) if invalid == 'signature' else key
    encoded = jwt.encode({'alg':'RS256','kid':key.kid},claims,signing_key)
    async def fetch(**kwargs):
        assert kwargs.get('code_verifier')
        return {'id_token':encoded}
    monkeypatch.setattr(google,'fetch_access_token',fetch)
    response = client.get('/api/auth/google/callback',params={'code':'test-code','state':params['state'][0]},follow_redirects=False)
    assert response.status_code == 303
    if invalid:
        assert response.headers['location'].endswith('login_failed')
        assert client.get('/api/auth/me').status_code == 401
    else:
        assert client.get('/api/auth/me').json()['email'] == 'verified@example.com'
        assert 'HttpOnly' in response.headers['set-cookie']
        with factory() as db:
            assert db.scalar(select(User)).google_sub == 'google-123'
            assert db.scalar(select(LoginSession)).token_hash != client.cookies.get(COOKIE)
        # OAuth state is consumed; a repeated callback cannot establish a new session.
        replay = client.get('/api/auth/google/callback',params={'code':'test-code','state':params['state'][0]},follow_redirects=False)
        assert replay.headers['location'].endswith('login_failed')
