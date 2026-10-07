# Google 로그인 설정

로그인은 Google OpenID Connect Authorization Code + PKCE 방식입니다. OAuth state·nonce와 ID token의 서명·발급자·대상·만료를 Authlib가 검증합니다. 사용자 식별에는 이메일이 아닌 Google `sub`를 사용합니다.

## Google Cloud 설정

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트를 선택합니다.
2. Google Auth Platform의 Branding / Audience / Data Access를 설정합니다. 기본 프로필과 이메일(`openid email profile`)만 사용합니다. 테스트 모드라면 로그인할 계정을 테스트 사용자에 추가합니다.
3. Clients에서 **웹 애플리케이션** OAuth 클라이언트를 생성합니다.
4. 승인된 리디렉션 URI에 다음 주소를 정확히 등록합니다.

```text
http://localhost:3100/api/auth/google/callback
```

이 프로젝트의 현재 `.env`는 3100번 포트입니다. 기본 `.env.example`은 3000이므로 사용 포트에 따라 `FRONTEND_PORT`, `APP_ORIGIN`, Google의 리디렉션 URI를 함께 맞추세요. `localhost`와 `127.0.0.1`도 구분됩니다. 서버 측 리디렉션 방식을 사용하므로 JavaScript origin 설정은 이 구현에 필요하지 않습니다.

## 로컬 비밀 설정

루트 `.env`에 아래 값을 채우세요. 비밀키는 브라우저용 변수나 저장소에 넣지 않습니다.

```dotenv
APP_ORIGIN=http://localhost:3100
GOOGLE_CLIENT_ID=발급받은_클라이언트_ID
GOOGLE_CLIENT_SECRET=발급받은_클라이언트_비밀키
SESSION_SECRET=32자_이상의_무작위_문자열
COOKIE_SECURE=false
```

현재 작업 폴더의 `SESSION_SECRET`은 이미 무작위 값으로 생성했습니다. 새 환경에서는 다음 명령으로 별도 생성합니다.

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
./run.sh dev
```

Google 클라이언트 ID/비밀키 또는 충분히 긴 세션 키가 없으면 로그인 버튼이 비활성화됩니다. 임시 사용자나 인증 우회 기능은 포함하지 않습니다. 설정 후 컨테이너 또는 로컬 백엔드를 재시작하세요.

HTTPS 배포에서는 `APP_ORIGIN=https://실제호스트`, `COOKIE_SECURE=true`를 설정하고 실제 콜백 URI도 Google에 등록합니다. APP_ORIGIN에는 후행 `/`를 붙이지 않습니다.

## 세션과 접근 제어

- OAuth 임시 상태 쿠키: 10분, HttpOnly, SameSite=Lax, 서명됨.
- 로그인 쿠키: 7일, HttpOnly, SameSite=Lax. 무작위 토큰의 SHA-256 해시만 DB에 저장.
- Google 액세스 토큰과 리프레시 토큰은 저장하지 않음. 채널 게시 권한은 별도 구현 단계.
- 로그아웃 시 DB 세션 폐기. 다시 로그인하면 현재 브라우저의 이전 세션 교체.
- 브랜드 API는 모든 요청에 로그인 필요. 조회·수정·삭제는 소유자 조건 적용.
- POST/PUT/DELETE에는 설정한 APP_ORIGIN과 정확히 일치하는 Origin 필수.
- 기존 소유자 없는 브랜드는 보존하지만 누구에게도 자동 배정하지 않음. 이전 데이터가 있다면 운영자가 소유자를 명시적으로 배정해야 함.

## API

| 경로 | 용도 |
|---|---|
| GET /api/auth/config | 로그인 설정 완료 여부 |
| GET /api/auth/google/login | Google 인증 시작 |
| GET /api/auth/google/callback | Google 인증 콜백 |
| GET /api/auth/me | 현재 사용자 |
| POST /api/auth/logout | 현재 세션 종료 |
| GET /api/brands | 본인 브랜드 목록 |
| POST /api/brands | 브랜드 등록 |
| GET /api/brands/{id} | 본인 브랜드 상세 |
| PUT /api/brands/{id} | 브랜드 수정 |
| DELETE /api/brands/{id} | 브랜드 삭제 |

## 검증

```bash
.venv/bin/pip install -r backend/requirements-dev.txt
cd backend
../.venv/bin/python -m pytest -q
```

테스트에서는 임시 SQLite DB와 테스트용 RSA 서명 토큰을 사용하며 외부 Google 계정에 접속하지 않습니다. OAuth state/PKCE 전달, 정상 ID token, 잘못된 서명·nonce·issuer·audience·만료·미검증 이메일, 로그아웃과 소유자 격리, 입력 검증을 확인합니다. 실제 Google 계정 로그인 완료는 클라이언트 자격 증명 설정 후 브라우저에서 별도로 확인해야 합니다.

참고: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect), [Authlib Starlette](https://docs.authlib.org/en/stable/oauth2/client/web/starlette.html).
