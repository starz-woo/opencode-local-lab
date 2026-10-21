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

## 출력 plugin의 실제 model-bound 경로 (v1.2.27)

검토한 태그는 위 commit과 동일합니다. OpenCode 전체를 실행하거나 provider를 호출하지 않고 다음 소스 흐름을 확인했습니다:

1. [plugin API](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/plugin/src/index.ts): `tool.execute.after(input, output)`의 output shape은 `{title, output: string, metadata}`. 반환값 교체가 아니라 **인자로 받은 객체의 `output`을 mutation**해야 합니다.
2. [plugin loader/trigger](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/plugin/index.ts): 모듈의 모든 export를 plugin 함수로 호출하고 hook에 같은 output 객체를 전달합니다. 이 때문에 `compact.mjs`는 default plugin 함수 하나만 export합니다. config의 file URL로 opt-in하며 SDK import가 필요 없습니다.
3. [tool wrapper](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/tool/tool.ts): 기본 native `Truncate.output`이 먼저 적용됩니다. [native 한도](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/tool/truncation.ts)는 2,000 lines / 50 KiB이며 원래 tool이 자체 처리하면 이를 건너뜁니다. plugin archive는 **이후 hook이 받은 문자열**이지 전체 subprocess bytes를 복원하는 기능이 아닙니다.
4. [prompt.resolveTools](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/session/prompt.ts): builtin `item.execute(args,ctx)` 결과를 `output` 객체로 만들고 `await Plugin.trigger("tool.execute.after", ..., output)` 후 **같은 `output`을 AI SDK tool execute 결과로 반환**합니다. UI metadata만 변경하는 hook이 아닙니다. MCP는 별도 content shape이므로 이 plugin은 건드리지 않습니다.
5. [processor](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/session/processor.ts)의 `tool-result`는 `value.output.output`을 `part.state.output`에 저장합니다. [message-v2.toModelMessages](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/session/message-v2.ts)는 completed tool의 `part.state.output`을 model message에 사용합니다. native session compaction/pruning은 이후 별도 처리입니다.
6. [bash](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/tool/bash.ts)의 exit는 `metadata.exit`입니다. plugin은 이 metadata를 변경하지 않고 exit가 정확히 0인 허용 명령만 줄입니다. nonzero/timeout/abort/unknown exit는 원문입니다.

오프라인 검증은 실제 `compact.mjs` default export를 Node에서 로드하고 실제 hook을 호출합니다. Python이 생성/실행한 noisy bugfix fixture의 stdout도 같은 hook에 전달해 진단/exit/UTF-8 archive를 확인합니다. mock hook으로 대체하지 않습니다. **전체 OpenCode runtime의 plugin 로딩/모델 턴, Windows native, 실모델 A/B는 사용자 실행 검증 대기**입니다. 소스 검토와 exported-hook 실행을 실제 런타임 성능 측정으로 혼동하지 마세요.

## 범위/라이선스

모든 runner 코드는 이 저장소에서 독립 작성. 기존 local-model-quality-benchmark PR14의 목적/격리 경계를 참조했지만 소스 파일을 복사하지 않았습니다. OpenCode 소스를 vendoring하거나 upstream fork로 표시하지 않습니다. 이 프로젝트 MIT; upstream OpenCode 사용/재배포 시 [upstream license](https://github.com/anomalyco/opencode/blob/v1.2.27/LICENSE)를 별도로 따르세요. 선택적 출력 plugin은 구현했고, wiki/core fork는 미구현입니다.
