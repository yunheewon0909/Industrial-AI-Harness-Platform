# AGENTS.md

## 운영 원칙

- 호스트(macOS)에서는 패키지/도구 관리를 `Homebrew + uv` 중심으로 수행한다.
- `omx --madmax`, `codex` 같은 위험 실행은 **컨테이너 내부에서만** 수행한다.
- Git 인증은 SSH agent forwarding만 사용하며, SSH 키 파일 직접 마운트/복사는 금지한다.
- 호스트 `~/.codex`는 read-only로만 공유하고, 컨테이너 내부 `CODEX_HOME`으로 최초 1회 복사해 사용한다.

## 커밋 게이트(필수)

모든 작업은 마일스톤 단위로 아래 순서를 반드시 지킨다.

1. 변경사항 검증
2. README 업데이트
3. 커밋
4. 다음 마일스톤 진행

즉, **커밋 전 README 업데이트는 필수**다.

## 커밋 규칙

- Conventional Commits 형식을 사용한다.
- 메시지는 변경 의도를 바로 이해할 수 있게 짧고 명확하게 작성한다.

권장 예시:

- `chore: init repo skeleton and policies`
- `chore(omx): add docker sandbox for madmax execution`
- `chore(uv): scaffold api/worker python projects with uv`
- `chore(compose): add minimal compose for api/worker`
