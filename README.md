# opencode-local-lab

**OpenCode를 그대로 실행하면서 로컬 모델 최적화를 단계별로 검증하는 실험 레이어**입니다. OpenCode 전체 fork나 완성된 GLM 최적화 엔진이 아닙니다. 벤치마크/추론은 사용자가 자신의 Windows PC에서 실행합니다.

## 연결/도구 호출이 이미 된다면: 바로 출력 최적화 사용

연결 검사를 다시 할 필요 없습니다. **실제 `tool.execute.after` plugin이 모델에 전달되는 긴 도구 출력 문자열을 선택적으로 줄입니다.** OpenCode **1.2.27** 소스 계약 기준이며, 설치된 다른 버전의 호환성을 주장하지 않습니다.

1. 이 저장소를 유지할 경로에 clone합니다. plugin과 `scripts/recover.mjs`를 함께 유지하세요.
2. **기존 프로젝트의 `opencode.json`/`opencode.jsonc`에 아래 `plugin` 항목만 수동 병합**하세요. 기존 provider/model/permissions 및 다른 plugin은 유지합니다. 글로벌 설정을 자동 변경하지 않습니다.

```json
{
  "plugin": ["file:///C:/Users/YOU/opencode-local-lab/plugins/compact.mjs"]
}
```

POSIX 예: `file:///home/you/opencode-local-lab/plugins/compact.mjs`. 공백/비ASCII 경로는 URL 인코딩한 file URL을 사용하세요. 정확한 URL은 repo에서 `python -c "from pathlib import Path; print(Path('plugins/compact.mjs').resolve().as_uri())"`로 출력할 수 있습니다.

3. 기존에 잘 되던 `opencode` 세션을 새로 시작해 같은 작업을 진행하세요. 추가 SDK/npm 의존성·요약용 LLM 호출은 없습니다. 해제하려면 추가한 plugin 항목만 제거하고 새 세션을 시작합니다. 다른 output-transform plugin과 함께 쓰면 순서/결과가 달라질 수 있으므로 단독 A/B부터 권장합니다.

**동작**: 8,000 UTF-16 character 초과인 `grep`/`glob` 및 제한된 test/build 명령(`python public_test.py`, `npm test`, `npm run test/build`, `pnpm run test/build`, `pytest`, `cargo test/build`, `go test`; 단순 `--flag`만 허용)에만 적용합니다. shell 복합 명령·일반 source read·patch 결과는 건드리지 않습니다. head/tail과 진단 행 주변을 남기며 compact 결과는 안내문 포함 **6,000 characters 이하**입니다. 이미 native truncated 표시가 있는 출력, 비영 exit/알 수 없는 exit의 bash 출력, 진단이 너무 많거나 길어 안전 예산을 넘는 경우, 아카이브 실패는 **원문 그대로**입니다. title/metadata/exit/attachments는 변경하지 않습니다. 요약/추정 token 수가 아닙니다.

**복구/보안**: 기본 원문은 프로젝트 밖 `$HOME/.opencode-compact/output-*/raw.txt`에 UTF-8로 정확히 저장합니다. `OPENCODE_COMPACT_STATE`로 별도 private 경로를 지정할 수 있습니다(작업공간 내부 경로는 거부). POSIX 디렉터리 0700/파일 0600, 고유 디렉터리+배타적 쓰기를 사용합니다. Windows ACL은 자동 설정하지 않으므로 사용자 전용 위치와 ACL을 확인하세요. **원문에는 비밀이 있을 수 있으며 암호화·자동 삭제·용량 제한은 없습니다.** 사용 후 아카이브 디렉터리를 직접 삭제하고 버전 관리/공유에 넣지 마세요. 모델은 안내된 경로/범위 명령으로 원문을 추가 조회할 수 있지만 새 tool을 자동 등록한 것은 아닙니다. 외부 디렉터리 읽기 권한은 기존 OpenCode 정책을 따릅니다.

```powershell
# 실제 출력의 Archive 경로로 교체. code-point offset 0부터 최대 4000개씩.
node scripts/recover.mjs 'C:\Users\YOU\.opencode-compact\output-EXAMPLE\raw.txt' 0 2000
```

OpenCode의 **기존 native truncation 이후 hook이 실행**됩니다. 따라서 저장하는 원문은 hook 입력 그대로이지, native 단계가 이미 버린 전체 셸 로그를 복원하는 것이 아닙니다. 기존 native `outputPath` metadata/안내문은 유지됩니다. 모든 의미적 증거를 자동 보존한다는 보장은 없으므로 정답률과 복구 필요성을 같이 측정하세요.

## 같은 과제로 baseline / compact A/B

추론은 **여기서 실행하지 않았습니다**. 아래 명령은 사용자가 자신의 모델로 실행하는 단계입니다. 기존 연결 값을 그대로 넣으면 됩니다. `compare` 기본값은 프로세스/파일/추론 없는 dry-run입니다.

```powershell
python lab.py compare
python lab.py compare --execute --model $model --base-url $endpoint --runtime $runtime --repeats 4 --output results/compact-ab-01
# 단일 variant만 필요하면:
python lab.py run --variant compact --execute --model $model --base-url $endpoint --runtime $runtime --output results/compact-01
```

`compare`는 같은 모델/과제/starter/권한/step/timeout으로 plugin 한 가지만 다르게 실행합니다. 반복 순서는 AB/BA/AB/BA이고 매 trial fresh state입니다. `ranges-noisy-bugfix-v2`는 중복 입력 버그를 고치는 과제입니다. 공개 reporter는 긴 로그 중간에 `ERROR solution.py:4` 진단을 내며 **의도적으로 exit 0**입니다(진짜 pass 판정은 외부 grader 6케이스). 공개 과제를 건너뛰거나 다른 명령을 쓰면 압축 이벤트가 없을 수 있습니다. 그 경우 최적화가 실측되었다고 해석하지 마세요.

JSON/CSV에는 variant, plugin event 수, input/output UTF-16 characters, reduced event 수, 기존 성공/실패/시간/token 결과가 기록됩니다. plugin metric이 없으면 `null`/`unknown`이며 토큰 수/속도 향상으로 환산하지 않습니다. trial archive/state는 종료 시 삭제하고 숫자만 남깁니다. 단일 과제의 문자 절감은 모델 속도/품질 개선 증거가 아닙니다. **plugin 구현·오프라인 실행 검증 완료 / 사용자 실모델 A/B 측정 대기**를 구분합니다.

## 지금 가능한 것

- **Stage 0 구현**: stdlib Python 오프라인 doctor, task prepare, 설정 preview, 자체 테스트.
- **Stage 1 구현 / 실모델 검증 대기**: 실제 OpenCode CLI baseline runner, trial별 새 작업공간/상태, 외부 정답 평가, 실패 포함 JSON/CSV/Markdown 보고서.
- **선택적 도구 출력 최적화 구현 / 실모델 측정 대기**: pure JS plugin, 원문 복구 CLI, 같은 과제 AB/BA 비교 runner.
- **미구현**: GLM 런타임 튜닝, 근거 기반 프로젝트 wiki, core fork. 연결이 이미 되는 사용자는 이들을 선행 gate로 기다릴 필요가 없습니다.

현재 검증은 macOS의 오프라인 테스트 및 Windows npm shim 모의 테스트입니다. **Windows 네이티브 실기기와 GLM endpoint 호환성/성능은 아직 검증하지 않았습니다.** 어떠한 품질 향상·속도 향상 수치도 주장하지 않습니다.

## Windows PowerShell: 먼저 오프라인

필수: Python **3.10+** (`python` 명령), Git for Windows, Node.js/npm. WSL 및 `py` 런처는 필요 없습니다. OpenCode의 bash 도구는 Git for Windows의 `bash.exe`가 필요합니다. PowerShell 실행 정책으로 npm.ps1이 차단되면 아래처럼 `npm.cmd`를 사용합니다.

새 환경에서만 필요한 준비입니다. 기존 연결이 되면 위 plugin 사용부터 시작하세요:

```powershell
git clone https://github.com/starz-woo/opencode-local-lab.git
cd opencode-local-lab
python scripts/run_tests.py
python lab.py doctor
python lab.py prepare --output prepared/task-01
python lab.py run
```

`doctor`는 PATH만 확인하며 OpenCode도 실행하지 않습니다. `prepare`는 공개 과제/동일 starter/public test를 새 디렉터리에 생성합니다. `run` 기본값은 **파일 생성·외부 프로세스·추론 없는 dry-run**입니다. `prepare`의 결과는 연습용이며 실제 run은 이를 재사용하지 않고 매 trial 새 starter를 만듭니다.

## 사용자가 선택해서 실험 실행

> **주의: `--execute`는 도구 실행을 자동 허용합니다. 샌드박스가 아닙니다.** 읽기/쓰기 및 셸은 호스트 권한으로 실행됩니다. 비밀/개인 파일이 없는 **일회용 Windows VM**, 제한된 계정, loopback 로컬 endpoint를 사용하세요. state 격리는 보안 경계가 아닙니다. 실행된 모델이 임의 코드를 만들 수 있으며 외부 grader 역시 공격 방지 sandbox가 아닙니다.

이 저장소는 OpenCode를 설치하거나 서버/모델을 자동 다운로드하지 않습니다. 아래 설치 명령은 **사용자가 VM에서 직접** 실행합니다:

```powershell
npm.cmd install -g opencode-ai@1.2.27
```

별도 터미널에서 원하는 로컬 서버를 시작하세요. 서버는 OpenAI-compatible chat completions와 도구 호출을 지원해야 하지만 실제 지원 여부는 런타임별 검증 대상입니다. 아래 값은 **실제 값으로 교체**하세요. 모델 별칭/GLM 버전을 추측하지 않습니다.

```powershell
$model = "REPLACE_WITH_EXACT_API_MODEL_ID"
$endpoint = "http://127.0.0.1:8000/v1"
$runtime = "REPLACE_WITH_ENGINE_VERSION_QUANTIZATION_GPU_CONTEXT"
python lab.py preview --model $model --base-url $endpoint
python lab.py run --execute --model $model --base-url $endpoint --runtime $runtime --output results/baseline-01
python lab.py report --output results/baseline-01
```

키가 필요한 서버는 `LOCAL_MODEL_API_KEY` 환경변수를 OS의 안전한 방식으로 설정하세요. 다른 변수명을 쓰면 `--key-env MY_KEY_VARIABLE`로 지정합니다. 키 자체는 CLI 인자/프로필에 넣지 마세요. 무인증 서버에는 기본적으로 빈 키를 전달합니다. 서버가 dummy key를 요구하면 사용자 환경변수에 설정해야 합니다.

`--opencode "C:\path\to\opencode.cmd"`로 경로 지정 가능. 공식 npm shim은 `cmd /c` 없이 package manifest의 Node entry/native exe로 해석합니다. 전역·프로젝트 `.bin` 설치를 지원하며 임의 batch wrapper는 지원하지 않습니다. Git bash가 자동 발견되지 않으면 사용자 환경의 `OPENCODE_GIT_BASH_PATH`를 실제 bash.exe 경로로 설정하세요.

## 출력 / 판정

새 output 폴더에 `manifest.json`, `results.json`, `results.csv`, `REPORT.md`가 생성됩니다. 기존 디렉터리는 덮어쓰지 않습니다. 실패도 분모에 포함됩니다. 정상 OpenCode 종료 + terminal `step_finish` + 외부 평가 **6/6** + 과제 무결성이 모두 충족되어야 pass입니다. 수정된 public test나 모델의 성공 선언은 평가에 사용하지 않습니다. 숨은 정답은 agent 작업공간 밖의 runner에 있으며 공개 저장소라 비밀 벤치마크는 아닙니다.

토큰 total이 제공되지 않으면 JSON `null` / CSV `unknown`입니다. 0으로 추정하거나 비용/속도를 조작하지 않습니다. `seconds`는 버전 확인·초기화·모델 실행·평가를 포함한 end-to-end 시간이며 tokens/sec가 아닙니다. 기본 180초는 **OpenCode 실행당** 제한, 버전 확인 최대 30초, 외부 평가 케이스당 3초가 별도입니다. `--max-steps 10`은 OpenCode build agent의 steps 설정이며 하드 token/cost 제한은 아닙니다.

runner는 원시 모델 출력/오류/셸 출력을 결과 보고서에 저장·표시하지 않습니다. compact plugin의 원문 archive는 disposable trial 내에만 저장 후 삭제됩니다. OpenCode 자체 state/log는 일회용 trial 폴더에서 생성되고 종료 후 삭제됩니다. manifest의 model/endpoint/runtime에는 비밀을 입력하지 마세요. 실패 종류는 `version_mismatch`, `launch_error`, `process_error`, `timeout`, `protocol_error`, `grade_failed`, `runner_error`로 구분됩니다. 결과 코드: 전체 pass/dry-run 0, trial 실패 1, 입력/파일 오류 2.

## 다음 단계

- [단계별 범위와 진입/완료 조건](docs/ROADMAP.md)
- [실험 프로토콜과 공정 비교](docs/PROTOCOL.md)
- [구조·upstream 근거·한계](docs/ARCHITECTURE.md)
- [미검증 프로필 체크리스트](profiles/glm-candidate.json)

실행 예: `python lab.py --help`. 테스트: Windows `python scripts/run_tests.py`, POSIX `sh scripts/run_tests.sh`. 테스트는 Python stdlib + Node.js 18.16+ 사용; npm 의존성 없음. upstream OpenCode와 독립적으로 구현했으며 upstream 소스를 vendoring하지 않습니다.
