# 구조 및 검증 근거

```text
사용자 Python CLI (신뢰 경계 바깥 호스트)
  ├─ doctor / preview / prepare: offline, no OpenCode process
  └─ run --execute
       ├─ trial TemporaryDirectory
       │    ├─ task/workspace: TASK.md + solution.py + public_test.py
       │    └─ isolated: HOME / USERPROFILE / XDG_* / APPDATA / temp
       ├─ npm shim -> official opencode-ai manifest bin -> node.exe/native exe
       ├─ OpenCode --version (1.2.27 exact) -> run --format json --model lab/ID
       ├─ parent parses terminal completion/errors/usage; raw output discarded
       ├─ separate temporary grader cwd: copy solution only -> CLI JSON comparisons
       └─ host output: manifest + results.json/csv + REPORT.md, failures included
```

## 왜 이 경계인가

OpenCode는 설정을 병합하므로 OPENCODE_CONFIG 하나만 지정해도 글로벌 auth/plugin/config가 사라지지 않습니다. 환경은 allowlist로 구성하고 HOME/USERPROFILE/XDG/config dir와 OpenCode home을 전부 격리합니다. project/외부 skill/default plugin/model fetch/autoupdate를 비활성화하고 inline config를 전달합니다. managed config도 테스트 전용 경로로 돌립니다. 글로벌 파일은 쓰지 않습니다. 이 방식은 **실험 오염 완화**이며 호스트 접근 차단이 아닙니다.

Windows에서는 npm .cmd를 셸 문자열로 실행하지 않습니다. manifest의 package name/bin, package 내부 target 경계, shim 연관성을 확인한 후 node.exe/entry를 argv로 실행합니다. Node가 실제 OpenCode Windows native package를 선택합니다. 임의 .bat wrapper는 지원하지 않습니다. 실제 Windows 검증은 사용자 실행/CI 결과에 의존하며 모의 테스트가 실기기 검증을 대신하지 않습니다.

## 핀된 upstream 계약

아래는 v1.2.27 태그 commit `4ee426ba549131c4903a71dfb6259200467aca81`에서 읽어 확인한 소스 계약입니다. 런타임 추론/설치를 이 개발 세션에서 실행한 것은 아닙니다.

- [run.ts](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/cli/cmd/run.ts): `run`, `--model`, `--agent`, `--format json`; step_finish/tool_use/error 이벤트. 요청된 permission은 자동 거부될 수 있으므로 config에서 tool permission을 명시적으로 allow.
- [config.ts](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/config/config.ts): provider 모델/옵션, build steps, permission, share, enabled_providers, managed precedence.
- [provider.ts](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/provider/provider.ts): 내장 `@ai-sdk/openai-compatible`, baseURL/options 해석.
- [global/index.ts](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/global/index.ts), [config/paths.ts](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/config/paths.ts), [flag.ts](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/flag/flag.ts): XDG roots, OPENCODE_TEST_HOME, DISABLE_PROJECT_CONFIG, managed test directory.
- [message-v2.ts](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/session/message-v2.ts): step-finish tokens.total은 optional. 누락시 unknown 유지.
- [npm 1.2.27 metadata](https://registry.npmjs.org/opencode-ai/1.2.27): bin=bin/opencode, Windows x64/arm64 optional packages 1.2.27. 메타데이터 조회만 했고 설치하지 않음.

런타임 계약이 바뀌면 version pin, resolver, event tests, docs를 함께 수정해야 합니다. 최신 버전을 자동 수용하지 않습니다.

## 범위/라이선스

모든 runner 코드는 이 저장소에서 독립 작성. 기존 local-model-quality-benchmark PR14의 목적/격리 경계를 참조했지만 소스 파일을 복사하지 않았습니다. OpenCode 소스를 vendoring하거나 upstream fork로 표시하지 않습니다. 이 프로젝트 MIT; upstream OpenCode 사용/재배포 시 [upstream license](https://github.com/anomalyco/opencode/blob/v1.2.27/LICENSE)를 별도로 따르세요. 현재 최적화/위키/코어 변경 코드는 없습니다.
