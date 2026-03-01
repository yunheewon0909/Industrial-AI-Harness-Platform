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
- Week-2 R1-R3: 로컬 RAG ingestion + search + ask API (`data/sample_docs` -> chunk/embed -> `data/rag_index`, `/rag/search`, `/ask`)

## 2.1 마일스톤 진행 상태

- [x] M0: 레포 초기화 + 기본 문서/규칙 + 디렉토리 트리
- [x] M1: OMX 도커 샌드박스 파일 + 호스트 검증
- [x] M2: uv 기반 Python api/worker 스켈레톤
- [x] M3: Postgres 서비스 + API DB 설정 플럼빙 + Alembic 스캐폴드
- [x] M4: Alembic jobs 마이그레이션 + `/jobs` DB 조회
- [x] M5: worker heartbeat DB upsert + retry/backoff

## 2.2 Week-2 RAG v1 진행 상태

- [x] R1: `data/sample_docs` -> chunk -> embed -> `data/rag_index` ingestion
- [x] R2 (accepted): 로컬 인덱스 기반 `/rag/search` 조회 API
- [x] R3: `POST /ask` + Ollama(OpenAI-compatible) 생성 경로 + compose `ollama` 서비스

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

`compose.omx.yml`의 서비스명은 `omx-sandbox`다.

```bash
docker compose -f compose.omx.yml build
docker compose -f compose.omx.yml run --rm omx-sandbox
```

샌드박스 이미지는 빌드 시 `en_US.UTF-8`, `ko_KR.UTF-8`를 모두 생성하고 기본 로케일을 `ko_KR.UTF-8`로 고정한다. 또한 진단용 `python3`와 `python`(=`python3` symlink)을 포함한다.

UTF-8 locale + python 진단(컨테이너 내부):

```bash
locale | grep -E '^(LANG|LC_ALL|LC_CTYPE)='
python --version
python3 --version
python -c "print('한글 출력 테스트')"
```

호스트에서 한 번에 확인하려면:

```bash
docker compose -f compose.omx.yml build --no-cache
docker compose -f compose.omx.yml run --rm omx-sandbox bash -lc 'locale | egrep "^(LANG|LC_ALL|LC_CTYPE)="; python -c "print(\"한글 테스트: 가나다라마바사\")"'
```

캐시 무시 재빌드가 필요한 경우에만 `--no-cache`를 사용한다.

```bash
docker compose -f compose.omx.yml build --no-cache
```

orphan 컨테이너 정리는 `down/up` 계열에서만 `--remove-orphans`를 사용한다 (`run`에는 사용하지 않음).

```bash
docker compose -f compose.omx.yml down --remove-orphans
```

SSH agent 포워딩 문제(`ssh-add -l`가 `permission denied`)가 나오면 `compose.omx.yml`의 `omx-sandbox`에 아래 설정이 있어야 한다.

```yaml
group_add:
  - "0"
```

검증(호스트):

```bash
docker compose -f compose.omx.yml run --rm omx-sandbox bash -lc 'ls -l $SSH_AUTH_SOCK; ssh-add -l'
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
omx setup --scope project-local
omx --xhigh --madmax
```

프롬프트 카탈로그가 보이지 않으면 fallback으로 아래를 1회 실행한다.

```bash
omx setup --scope user
```

참고:

- 엔트리포인트가 `~/.codex/config.toml`의 호스트 절대경로(예: `/Users/.../.omx/agents/...`)를 컨테이너 경로 `/workspace/.omx/agents/...`로 자동 보정한다.
- 따라서 호스트와 컨테이너를 오갈 때마다 `omx setup`을 매번 다시 할 필요는 없다.
- 단, 프로젝트의 `.omx`를 지웠거나 컨테이너의 Codex 상태 볼륨(`omx-codex-home`)을 초기화한 경우에는 컨테이너에서 `omx setup --scope project-local`을 1회 다시 실행한다.

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

- 대상 프로젝트에 `.omx/agents`가 없으면 경로 보정은 스킵된다. 이 경우 컨테이너에서 `omx setup --scope project-local`을 1회 실행해 `.omx`를 먼저 생성한다.
- `.omx`를 삭제했거나 `omx-codex-home` 볼륨을 초기화했다면, 역시 컨테이너에서 `omx setup --scope project-local`을 1회 다시 실행한다.

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

### 7.4 Compose(postgres/api/worker/ollama) 검증(선택)

Compose 경로에서는 `api` 컨테이너가 시작 시 아래 순서로 자동 실행한다.

1. `uv run alembic upgrade head`
2. `uv run uvicorn api.main:app --host 0.0.0.0 --port 8000`

따라서 7.2(호스트 단독 검증)과 달리 Compose에서는 수동 migration 명령을 별도로 실행할 필요가 없다.

compose에서 명시적으로 사용하는 주요 환경변수:

- API DB: `API_DATABASE_URL`
- Worker DB: `WORKER_DATABASE_URL`
- RAG source dir (compose override): `RAG_SOURCE_DIR=/workspace/data/sample_docs`
- RAG index dir (compose override): `RAG_INDEX_DIR=/workspace/data/rag_index`
- Ollama base URL: `OLLAMA_BASE_URL=http://ollama:11434/v1`
- Ollama model: `OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M`
- Ollama fallback model: `OLLAMA_FALLBACK_MODEL=qwen2.5:3b-instruct-q4_K_M`
- Ollama timeout: `OLLAMA_TIMEOUT_SECONDS=30`

```bash
# run on host
docker compose up --build

# 서비스명 확인
docker compose config --services

# 모델 warm-up (초회 1회 권장; pull이 끝나야 /ask 응답이 빠르게 안정화됨)
docker compose exec -T ollama ollama pull qwen2.5:3b-instruct-q4_K_M
# (선택) 기본 모델을 미리 받을 경우
docker compose exec -T ollama ollama pull qwen2.5:7b-instruct-q4_K_M

# HTTP 라우트 확인
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/jobs
curl -sG "http://127.0.0.1:8000/rag/search" \
  --data-urlencode "q=maintenance automation" \
  --data-urlencode "k=3"
curl -s -X POST "http://127.0.0.1:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"What maintenance actions are recommended?","k":3}'

# 로그 확인
docker compose logs --tail=120 postgres api worker ollama

# DB 스키마 확인
docker compose exec -T postgres psql -U postgres -d industrial_ai -c "\d worker_heartbeats"
docker compose exec -T postgres psql -U postgres -d industrial_ai -c "select worker_id, updated_at from worker_heartbeats order by updated_at desc limit 3;"
```

기대 로그(요약):

- `postgres` healthy 상태 진입
- `api` 로그에 `[api] running alembic upgrade head` 출력 후 migration 적용
- `api` 서비스 기동 및 8000 포트 노출
- `worker` heartbeat upsert 반복 출력
- `ollama` 서비스 기동 (11434 포트)
- `/ask` 응답 JSON에 `answer`, `sources`, `meta` 필드 포함

### 7.5 How to run tests

테스트는 Docker/Postgres 없이 로컬에서 실행 가능하다.

```bash
uv run --project apps/api pytest -q apps/api/tests
uv run --project apps/worker pytest -q apps/worker/tests
```

위처럼 각 테스트 루트를 명시하면 api/worker 간 테스트 교차 탐색을 막을 수 있다.
특히 워크스페이스 루트에서 실행할 때도 의도한 스위트만 실행된다.
검증 로그와 실패 지점을 서비스 단위로 분리해 추적하기 쉽다.

### 7.6 Type-check (Pyright)

Pyright의 canonical 검증 명령은 아래 2줄이다.

```bash
uv sync --dev
uv run pyright -p pyrightconfig.json
```

`uvx --with pyright pyright ...`는 격리된 환경에서 실행되어 프로젝트 의존성을 보지 못할 수 있다.
이 경우 missing-import 오탐이 발생할 수 있으므로 공식 검증 증거로 사용하지 않는다.

### 7.7 Week-2 R1 RAG ingestion (호스트, hermetic)

기본 입력 경로는 `data/sample_docs`이며 `.txt`, `.md` 문서를 읽어 로컬 인덱스를 생성한다.

```bash
uv run --project apps/api rag-ingest
find data/rag_index -maxdepth 3 -type f | sort
```

기대 결과(요약):

- `[rag-ingest] completed documents=<N> chunks=<M> index=data/rag_index/index.json` (또는 절대경로 출력)
- `data/rag_index/index.json` 파일 생성
- Docker/Compose 없이 호스트에서 단독 실행 가능
- Compose 실행 시에는 `RAG_SOURCE_DIR`, `RAG_INDEX_DIR` 환경변수로 `/workspace/...` 경로를 명시 override한다.

### 7.8 Week-2 R2 RAG search API (호스트, hermetic)

R2는 R1에서 생성한 로컬 인덱스를 읽어 `GET /rag/search` 조회를 수행한다(포트 `8000`).

```bash
# 1) 인덱스 생성
uv run --project apps/api rag-ingest

# 2) API 실행
uv run --project apps/api uvicorn api.main:app --host 0.0.0.0 --port 8000

# 3) 검색 요청
curl -sG "http://127.0.0.1:8000/rag/search" \
  --data-urlencode "q=maintenance automation" \
  --data-urlencode "k=3"
```

기대 결과(요약):

- `/rag/search`가 `chunk_id`, `source_path`, `score`, `text` 필드를 포함한 JSON 배열 반환
- 인덱스가 없으면 503 + `rag-ingest` 실행 안내 메시지 반환
- Compose 실행 중에도 동일하게 `http://127.0.0.1:8000/rag/search`로 조회 가능

### 7.9 Week-2 R3 `/ask` (RAG + Ollama, fully local)

`POST /ask`는 기존 로컬 RAG 인덱스 검색 결과를 컨텍스트로 묶고, Ollama의 OpenAI-compatible chat completions API(`/v1/chat/completions`)를 호출해 답변을 생성한다.

요청/응답 요약:

- Request: `{"question":"...", "k":3}` (`question` 필드명 고정)
- Response: `{"answer": "...", "sources": [...], "meta": {...}}`
- `sources`에는 `chunk_id`, `source_path`, `score`, `text`가 포함된다.

#### 7.9.1 macOS 런타임 선택: Ollama vs LM Studio

> **macOS Docker has no GPU passthrough; Ollama-in-Docker is CPU-only and slow; Metal acceleration requires host runtime; recommend LM Studio host when Metal/GUI needed.**

- Compose 기본값은 `OLLAMA_BASE_URL=http://ollama:11434/v1` (컨테이너 내부 서비스 경로).
- 호스트에서 Ollama/LM Studio를 띄우고 API 컨테이너가 이를 바라보게 하려면 fallback으로 아래를 사용:
  - `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1`

#### 7.9.2 MacBook Air M2 16GB 권장 모델

- Chat (기본): `qwen2.5:7b-instruct-q4_K_M`
- Chat fallback(메모리/속도 우선): `qwen2.5:3b-instruct-q4_K_M`
- Embedding (향후 옵션 경로): `nomic-embed-text`

> 참고: R3 범위에서는 R1/R2 deterministic embedding 인덱스를 그대로 사용한다. Ollama embedding 전환은 후속 마일스톤에서 선택적으로 추가한다.

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
│   │       ├── ingest.py
│   │       ├── models.py
│   │       ├── main.py
│   │       └── services/rag/
│   │           ├── ingest.py
│   │           ├── query.py
│   │           └── ...
│   └── worker
│       ├── pyproject.toml
│       └── src/worker/main.py
├── data
│   ├── sample_docs/
│   └── rag_index/ (runtime output, git ignored)
└── shared
    └── db/interface.py
```
