# opencode-local-lab

**OpenCode를 그대로 실행하면서 로컬 모델 최적화를 단계별로 검증하는 실험 레이어**입니다. OpenCode 전체 fork나 완성된 GLM 최적화 엔진이 아닙니다. 벤치마크/추론은 사용자가 자신의 Windows PC에서 실행합니다.

## 지금 가능한 것

- **Stage 0 구현**: stdlib Python 오프라인 doctor, task prepare, 설정 preview, 자체 테스트.
- **Stage 1 구현 / 실모델 검증 대기**: 실제 OpenCode CLI baseline runner, trial별 새 작업공간/상태, 외부 정답 평가, 실패 포함 JSON/CSV/Markdown 보고서.
- **Stage 2–5 PLANNED / 미구현**: GLM 검증 프로필 → 선택적 도구 출력 최적화 → 근거 기반 프로젝트 wiki → 측정상 필요할 때만 최소 core fork.

현재 검증은 macOS의 오프라인 테스트 및 Windows npm shim 모의 테스트입니다. **Windows 네이티브 실기기와 GLM endpoint 호환성/성능은 아직 검증하지 않았습니다.** 어떠한 품질 향상·속도 향상 수치도 주장하지 않습니다.

## Windows PowerShell: 먼저 오프라인

필수: Python **3.10+** (`python` 명령), Git for Windows, Node.js/npm. WSL 및 `py` 런처는 필요 없습니다. OpenCode의 bash 도구는 Git for Windows의 `bash.exe`가 필요합니다. PowerShell 실행 정책으로 npm.ps1이 차단되면 아래처럼 `npm.cmd`를 사용합니다.

PR 미병합 동안 구현 코드는 feature branch에 있습니다:

```powershell
git clone --branch feat/local-model-lab https://github.com/starz-woo/opencode-local-lab.git
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

원시 모델 출력/오류/셸 출력은 비밀 유출 방지를 위해 저장·표시하지 않습니다. OpenCode 자체 state/log는 일회용 trial 폴더에서 생성되고 종료 후 삭제됩니다. manifest의 model/endpoint/runtime에는 비밀을 입력하지 마세요. 실패 종류는 `version_mismatch`, `launch_error`, `process_error`, `timeout`, `protocol_error`, `grade_failed`, `runner_error`로 구분됩니다. 결과 코드: 전체 pass/dry-run 0, trial 실패 1, 입력/파일 오류 2.

## 다음 단계

- [단계별 범위와 진입/완료 조건](docs/ROADMAP.md)
- [실험 프로토콜과 공정 비교](docs/PROTOCOL.md)
- [구조·upstream 근거·한계](docs/ARCHITECTURE.md)
- [미검증 프로필 체크리스트](profiles/glm-candidate.json)

실행 예: `python lab.py --help`. 테스트: Windows `python scripts/run_tests.py`, POSIX `sh scripts/run_tests.sh`. Python 외 테스트 의존성 없음. upstream OpenCode와 독립적으로 구현했으며 upstream 소스를 vendoring하지 않습니다.
