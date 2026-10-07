# Phase 1: Google 로그인 및 브랜드 관리

## 구현 완료
- Google OIDC Authorization Code + PKCE, state/nonce 및 ID token 검증
- Google sub 기반 사용자 생성·갱신, DB 기반 세션, 로그아웃
- 사용자 소유권을 적용한 브랜드 CRUD, 입력 길이·빈 값 검사, Origin 검사
- DESIGN.md의 단일 파란색 액션, 흑백 섹션, 시스템 글꼴, 여백과 버튼 형태 반영
- 반응형 로그인 소개 화면, 빈 워크스페이스, 브랜드 카드, 등록·편집·삭제 확인 대화상자
- 기존 브랜드를 보존하는 0002 마이그레이션

## 검증 결과
- 인증·브랜드 API 자동 테스트 10개 통과
- 정상 및 잘못된 서명/nonce/audience/issuer/만료/이메일 검증을 테스트용 RSA 토큰으로 확인
- OAuth state 재사용 차단, PKCE 전달, 세션 만료/폐기, 소유권 격리, CSRF Origin 및 입력 검증 확인
- Docker production build 통과, 세 서비스 healthy
- MySQL 마이그레이션 적용 및 Alembic check 통과
- TypeScript 검사 통과
- 임시 SQLite 테스트 환경에서 브라우저로 등록·수정·삭제 확인 창·로그아웃 확인
- 삭제 실행은 API 자동 테스트로 검증
- 데스크톱 워크스페이스와 좁은 화면의 로그인 레이아웃 확인

## 남은 설정
실제 Google 클라이언트 ID와 비밀키가 제공되지 않아 실계정 로그인 완료는 미검증입니다. `docs/google-login.md`에 따라 `.env` 설정 후 재시작하세요. 현재 포트는 3100이며 콜백은 `http://localhost:3100/api/auth/google/callback`입니다.

AI 생성·캠페인·게시 채널 인증 및 실제 게시는 다음 단계입니다.
