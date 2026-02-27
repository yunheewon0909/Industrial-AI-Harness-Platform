# Industrial AI Harness Platform

Week-1 MVP를 위한 초기 스켈레톤 저장소입니다.  
원칙은 `호스트(macOS) = Homebrew + uv 중심`, `위험 실행(OMX madmax/codex) = Docker sandbox 내부 전용`입니다.

## 1. 목적

- 산업용 AI 하네스 플랫폼의 최소 실행 뼈대를 만든다.
- API/FastAPI와 Worker를 분리해 이후 DB/큐를 단계적으로 붙일 수 있게 한다.
- 운영 규칙(커밋 게이트, 문서 우선 업데이트)을 코드와 문서에 함께 강제한다.

## 2. Week-1 범위

- `apps/api`: FastAPI `/health`, `/jobs`(DB 조회) + Alembic jobs 마이그레이션
- `apps/worker`: DB heartbeat upsert + retry/backoff
- `shared/db/interface.py`: 다음 마일스톤용 DB 인터페이스 자리만 제공
- `Dockerfile`, `entrypoint.sh`, `compose.omx.yml`: OMX 격리 샌드박스
- `compose.yml`: api/worker/postgres 최소 실행 골격

## 2.1 마일스톤 진행 상태

- [x] M0: 레포 초기화 + 기본 문서/규칙 + 디렉토리 트리
- [x] M1: OMX 도커 샌드박스 파일 + 호스트 검증
- [x] M2: uv 기반 Python api/worker 스켈레톤
- [x] M3: Postgres 서비스 + API DB 설정 플럼빙 + Alembic 스캐폴드
- [x] M4: Alembic jobs 마이그레이션 + `/jobs` DB 조회
- [x] M5: worker heartbeat DB upsert + retry/backoff

## 3. 아키텍처(초기)

```text
macOS host
  ├─ uv / git / docker (host tools)
  ├─ repo working tree
  └─ Docker OMX sandbox
       ├─ Node 20+, @openai/codex, oh-my-codex
       ├─ forwarded SSH agent socket
       └─ host ~/.codex(ro) -> container $CODEX_HOME(rw, one-time copy)

Week-1 services
  ├─ api (FastAPI)
  └─ worker (heartbeat loop)
```

## 4. 호스트 사전 준비(필수)

아래는 **호스트(macOS)** 에서만 실행:

```bash
brew install uv || brew upgrade uv
uv --version

echo $SSH_AUTH_SOCK
ssh-add -l

ls -la ~/.codex
docker --version
docker compose version
```

## 5. 안전 실행 원칙

- `omx --madmax`, `codex` 실행은 **반드시 컨테이너 내부에서만** 수행한다.
- 호스트에서는 빌드/런/셸 진입/상태 확인까지만 수행한다.
- SSH 키 파일은 공유하지 않고 `SSH_AUTH_SOCK` 에이전트 포워딩만 사용한다.
- 호스트 `~/.codex`는 컨테이너에 read-only 마운트하고, 컨테이너 내부 `CODEX_HOME`에 1회 복사해 사용한다.

## 6. 마일스톤 커밋 게이트 규칙(필수)

각 마일스톤마다 아래 순서를 강제한다.

1. 변경사항 검증
2. README 업데이트 (이번 마일스톤 반영)
3. Conventional Commit으로 커밋
4. 다음 마일스톤 진행

권장 커밋 메시지:

- `chore: init repo skeleton and policies`
- `chore(omx): add docker sandbox for madmax execution`
- `chore(uv): scaffold api/worker python projects with uv`
- `chore(compose): add minimal compose for api/worker`

## 7. 실행/검증(호스트 기준)

### 7.1 OMX 샌드박스

```bash
docker compose -f compose.omx.yml build
docker compose -f compose.omx.yml run --rm omx-sandbox
```

`codex`와 `oh-my-codex`를 최신으로 강제 갱신하며 빌드하려면:

```bash
NPM_REFRESH=$(date +%s) docker compose -f compose.omx.yml build --pull
docker compose -f compose.omx.yml run --rm omx-sandbox
```

특정 npm 태그를 지정하고 싶다면:

```bash
CODEX_NPM_TAG=latest OMX_NPM_TAG=latest NPM_REFRESH=$(date +%s) docker compose -f compose.omx.yml build --pull
```

컨테이너 셸에 진입한 뒤 OMX 실행:

```bash
omx setup --scope project
omx --xhigh --madmax
```

참고:

- 엔트리포인트가 `~/.codex/config.toml`의 호스트 절대경로(예: `/Users/.../.omx/agents/...`)를 컨테이너 경로 `/workspace/.omx/agents/...`로 자동 보정한다.
- 따라서 호스트와 컨테이너를 오갈 때마다 `omx setup`을 매번 다시 할 필요는 없다.
- 단, 프로젝트의 `.omx`를 지웠거나 컨테이너의 Codex 상태 볼륨(`omx-codex-home`)을 초기화한 경우에는 컨테이너에서 `omx setup --scope project`를 1회 다시 실행한다.

기대 로그(요약):

- git user/email 설정 확인
- SSH agent 소켓 감지 성공
- `/host-codex` -> `$CODEX_HOME` 1회 복사 메시지

#### 7.1.1 다른 프로젝트에서 샌드박스 재사용

가능하다. 아래 3개 파일을 다른 프로젝트 루트로 복사하면 경로 매핑은 자동으로 맞춰진다.

- `Dockerfile`
- `entrypoint.sh`
- `compose.omx.yml`

복사 예시(호스트):

```bash
# 대상 프로젝트 루트로 이동
cd <target-project-root>

# 이 레포를 소스 템플릿으로 사용해 복사
cp <omx-sandbox-source>/Dockerfile .
cp <omx-sandbox-source>/entrypoint.sh .
cp <omx-sandbox-source>/compose.omx.yml .
chmod +x entrypoint.sh
```

자동 매핑되는 항목:

- 대상 프로젝트 루트(`./`) -> 컨테이너 `/workspace`
- 호스트 `~/.codex`(ro) -> 컨테이너 `/host-codex`
- SSH agent 소켓 -> 컨테이너 `/ssh-agent`
- `~/.codex/config.toml`의 호스트 절대경로(`/Users/.../.omx/...`) -> `/workspace/.omx/...`로 엔트리포인트가 자동 보정

재사용 시 실행 순서(호스트):

```bash
NPM_REFRESH=$(date +%s) docker compose -f compose.omx.yml build --pull
docker compose -f compose.omx.yml run --rm omx-sandbox
```

주의:

- 대상 프로젝트에 `.omx/agents`가 없으면 경로 보정은 스킵된다. 이 경우 컨테이너에서 `omx setup --scope project`를 1회 실행해 `.omx`를 먼저 생성한다.
- `.omx`를 삭제했거나 `omx-codex-home` 볼륨을 초기화했다면, 역시 컨테이너에서 `omx setup --scope project`를 1회 다시 실행한다.

### 7.2 API 단독 검증(호스트)

```bash
export API_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/industrial_ai

# jobs / worker_heartbeats 테이블 migration 적용
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head

uv run --project apps/api uvicorn api.main:app --host 0.0.0.0 --port 8000
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/jobs

# migration head 확인
uv run --project apps/api alembic -c apps/api/alembic.ini heads
```

기대 응답:

- `/health` -> `{"status":"ok"}`
- `/jobs` -> `jobs` 테이블 조회 결과(JSON 배열)

### 7.3 Worker 단독 검증(호스트)

```bash
export WORKER_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/industrial_ai
export WORKER_ID=worker-local
export WORKER_HEARTBEAT_SECONDS=30

uv run --project apps/worker python -m worker.main
```

기대 로그(요약):

- `worker_heartbeats` 테이블에 upsert heartbeat 수행
- DB 오류 시 exponential backoff + jitter로 재시도

### 7.4 Compose(api/worker/postgres) 검증(선택)

```bash
docker compose up --build

# 서비스명 확인
docker compose config --services

# 로그 확인 (서비스명은 postgres)
docker compose logs --tail=120 postgres api worker

# DB 스키마 확인
docker compose exec -T postgres psql -U postgres -d industrial_ai -c "\d worker_heartbeats"
docker compose exec -T postgres psql -U postgres -d industrial_ai -c "select worker_id, updated_at from worker_heartbeats order by updated_at desc limit 3;"
```

기대 로그(요약):

- `postgres` healthy 상태 진입
- `api` 서비스 기동 및 8000 포트 노출
- `worker` heartbeat upsert 반복 출력
- `jobs` 테이블 생성 확인
- `worker_heartbeats` 테이블 생성 확인

## 8. 디렉토리 구조

```text
.
├── AGENTS.md
├── Dockerfile
├── README.md
├── compose.omx.yml
├── compose.yml
├── entrypoint.sh
├── .python-version
├── pyproject.toml
├── uv.lock
├── apps
│   ├── api
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── alembic/
│   │   │   ├── env.py
│   │   │   ├── script.py.mako
│   │   │   └── versions/
│   │   │       └── 20260227_0001_create_jobs_table.py
│   │   │       └── 20260227_0002_create_worker_heartbeats_table.py
│   │   └── src/api/
│   │       ├── config.py
│   │       ├── db.py
│   │       ├── models.py
│   │       └── main.py
│   └── worker
│       ├── pyproject.toml
│       └── src/worker/main.py
└── shared
    └── db/interface.py
```
