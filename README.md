# AI Marketing Manager · Phase 1

Next.js + TypeScript / FastAPI / SQLAlchemy + Alembic / MySQL 기본 실행 환경입니다.
현재 구현 범위는 Google 로그인, 사용자별 브랜드 등록·조회·수정·삭제, DESIGN.md 기반 화면, API·DB readiness와 실행 환경입니다. AI 생성·대화형 편집·채널 인증·실제 게시는 아직 구현되지 않았습니다.

Google 로그인은 `.env`에 OAuth 클라이언트 정보를 입력한 뒤 사용할 수 있습니다. 자세한 내용은 [Google 로그인 설정](docs/google-login.md)을 참고하세요.

## 시작하기

Docker Desktop을 실행하세요. 로컬 개발에는 Node.js 20.9 이상(24 LTS 권장), Python 3.10 이상(3.12 권장)이 추가로 필요합니다.

```bash
./run.sh local
```

첫 실행 시 `.env`를 자동 생성하고 Python 가상환경과 npm 의존성을 설치합니다. MySQL만 Docker로 실행하고 DB 준비 후 마이그레이션을 적용합니다. Next.js와 FastAPI는 hot reload 모드로 실행됩니다. Ctrl+C로 두 개발 서버를 함께 종료하며 MySQL은 유지됩니다.

- 화면: http://localhost:3100
- API 문서: http://localhost:3200/docs
- Liveness: http://localhost:3200/api/health
- DB·스키마 readiness: http://localhost:3200/api/health/ready
- 프런트엔드에서 `/api/*` 요청은 Next.js를 거쳐 백엔드로 전달됩니다.

```bash
./run.sh dev
./run.sh stop
```

`dev`는 frontend/backend/mysql 세 컨테이너를 빌드하여 백그라운드 실행하고 healthcheck를 기다립니다. 프런트는 standalone production build, 백엔드는 reload 없이 실행합니다. 실패 시 `docker compose logs --tail=100`으로 확인하세요. `stop`은 컨테이너와 네트워크를 제거하되 DB 볼륨을 보존합니다. 모드를 바꾸기 전 기존 서버를 종료하세요.

현재 작업 환경에서는 3000번 포트가 사용 중이므로 생성된 `.env`의 `FRONTEND_PORT`를 **3100**으로 설정했습니다. 접속 주소는 http://localhost:3100 입니다. `.env.example` 기본값은 3000을 유지합니다.

## 설정

`.env.example`을 참고하세요. 개발용 기본 비밀번호는 공유 환경에서 변경해야 합니다. 포트는 기본값 3000/3200/3307이며 모두 호스트의 loopback에 바인딩합니다. 외부 공개 배포에는 인증, HTTPS, 비밀 관리가 추가로 필요합니다.

로컬의 기존 MySQL을 사용하려면 `LOCAL_DB_MODE=external`, `DB_HOST`, `DB_PORT`와 `MYSQL_*` 접속 정보를 지정하세요. DB와 사용자는 미리 생성되어 있어야 합니다. Docker 모드에서는 DB 호스트를 자동으로 설정합니다. Docker MySQL의 계정 초기화 값은 새 볼륨에서만 적용되므로 기존 볼륨의 비밀번호는 `.env` 수정만으로 변경되지 않습니다.

## 구조

```text
frontend/app/         초기 화면 및 스타일
frontend/Dockerfile  standalone 이미지
backend/app/         설정, DB 세션, 모델, API
backend/alembic/     스키마 버전 관리
scripts/local.py     로컬 프로세스 실행·종료 관리
run.sh               local / dev / stop
docker-compose.yml  3개 서비스와 DB 영구 볼륨
docs/planning.md    기획 및 다음 구현 순서
```

## 마이그레이션과 점검

```bash
cd backend
../.venv/bin/alembic revision --autogenerate -m "describe change"
../.venv/bin/alembic upgrade head
../.venv/bin/alembic check
```

자동 생성 마이그레이션은 검토 후 적용하세요. Docker에서는 `docker compose exec backend alembic current`로 확인할 수 있습니다. `dev` 시작 시 단일 백엔드가 마이그레이션을 적용한 뒤 API를 실행합니다. 다중 replica 배포로 확장할 때는 별도 migration job으로 옮기세요.

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run build
curl -f http://localhost:3200/api/health/ready
curl -f http://localhost:3100/api/health/ready
```

프런트 의존성은 package-lock.json으로 고정합니다. Python은 requirements.txt의 호환 범위를 사용합니다.

공식 참고: [Next.js 설치](https://nextjs.org/docs/app/getting-started/installation), [FastAPI Docker](https://fastapi.tiangolo.com/deployment/docker/).

## 인증 및 브랜드 관리 검증

`backend/requirements-dev.txt` 설치 후 `cd backend && ../.venv/bin/python -m pytest -q`로 실행합니다. 0002 마이그레이션은 사용자·세션 테이블과 브랜드 소유자 필드를 추가하며 기존 브랜드를 보존합니다.
