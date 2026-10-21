# 실험 프로토콜

## 현재 baseline

- Python 3.10+ 표준 라이브러리; OpenCode 정확히 1.2.27. `--execute`에서 동일 격리 환경으로 `--version` 확인 후에만 실행.
- ranges-noisy-bugfix-v2 (이전 ranges-v1 결과와 직접 비교 금지): stdin JSON 정수 배열 → 중복 제거/정렬/연속 구간 JSON. public task와 starter는 매 trial 동일. prepare 폴더 수정은 실제 run에 영향 없음.
- public example은 연습용. trusted runner는 별도 cwd에 solution.py만 snapshot하고 `python -I candidate.py` 실행 결과를 독립적인 6개 정답과 비교. 정상 exit만으로 합격하지 않음. empty/duplicates/negative/gaps/large integers/reverse contiguous 포함.
- runner/test/report는 작업공간에 복사하지 않음. TASK.md 변경, symlink solution, 출력 없음, 잘못된 JSON, timeout은 실패. public_test.py의 변경이나 0 tests/위조 report는 성공 증거가 아님.
- 공개된 평가 케이스이므로 비밀 test corpus가 아니며 악성 agent에 대한 보안 보장도 아님. agent는 호스트 filesystem에 접근 가능. disposable VM을 반드시 사용할 것.

## 재현성 기록

manifest의 모델 ID, base URL(비밀 금지), runtime 기록은 필수. runtime에 엔진/버전, 모델 파일·quantization, GPU/VRAM, context, chat template, sampling, seed(지원할 때), 서버 옵션을 기록하거나 별도 비밀 없는 실험 노트와 연결. endpoint가 원격이면 네트워크 지연을 구분. API 키는 환경변수로만 전달하고 환경 전체를 덤프하지 않음.

현재 output은 artifact/code snapshot을 보존하지 않음(비밀·임의코드 보존 최소화). 재현성은 동일 입력/설정/코드 revision의 반복 실행 수준이며 토큰별 deterministic replay가 아님. 초기화/버전/평가 시간이 wall time에 포함됨. process 로그를 생략하므로 오류 상세 분석에는 VM 안에서 사용자 수동 재현이 필요할 수 있음.

## 예산과 실패 처리

기본 repeats=1은 smoke용. baseline 기록은 `--repeats 3` 이상 권장. 기본 `--timeout 180`, `--max-steps 10`. model/tool 호출당 token 하드 한도나 비용 한도는 아님; 서버 측 한도도 사용자가 설정. timeout은 POSIX process group, Windows `taskkill /T /F`로 자식 프로세스를 종료. 탈출한/detached 프로세스에 대한 OS sandbox 보장은 없음. grader는 6개 × 최대 3초, version probe 최대 30초 별도. 중단되면 이미 끝난 trial report는 남고 미완료 trial은 완성된 결과로 기록하지 않음; 결과의 trial 수와 manifest repeats를 함께 확인.

정상 exit, terminal step_finish, 외부 정답, 과제 무결성 모두 통과한 경우만 passed. OpenCode session error event는 exit 0이어도 실패. usage total이 하나라도 누락되면 tokens=unknown. 서로 다른 서버의 token 계산은 직접 비교하지 말 것. 실패 포함 전체 분모와 trial별 raw status를 보고한다.

## 구현된 출력 A/B

`compare --execute --repeats 4`는 AB/BA/AB/BA 순서로 baseline/compact 각각 4회 실행합니다. plugin만 다르고 모델/endpoint/과제/starter/권한/steps/timeout은 같습니다. 모든 실패를 분모에 남기고 숫자-only plugin metrics를 별도 열에 기록합니다. 누락/손상 metrics는 unknown으로 남기며 실패를 성공 처리하지 않습니다. 짧은 출력/적용 범위 밖 명령만 실행했으면 reduced events가 0일 수 있으므로 문자 절감이 실제 관측되었는지 확인하세요.

공개 noisy reporter는 진단을 남기고 exit 0으로 종료하는 **의도적 실험 fixture**입니다. stderr/진짜 비영 실패를 무조건 압축하는 정책이 아니며, plugin은 비영 exit 결과를 그대로 유지합니다. 외부 6케이스 grader가 실제 성공을 판정합니다. fixture 로그는 native 한도 2,000 lines/50 KiB보다 작고 plugin threshold보다 커서 기존 native truncation과 구분됩니다. single-task 실험이며 일반화/속도 증명의 근거가 아닙니다.

## 후속 ablation (GLM tuning/wiki는 PLANNED)

같은 OpenCode revision/모델/endpoint/모델 파일/샘플링/과제/starter/steps/wall-time를 고정하고 한 요소만 변경. baseline vs GLM profile, profile vs selective tool output, output vs wiki를 별도 비교. AB/BA 순서로 최소 3회/조건, 규모 확대 시 task 묶음과 통계 계획을 먼저 고정. 성공만의 평균이 아니라 전체 완수율·실패율·시간 분포를 같이 보고한다.

각 trial은 새 OpenCode config/data/cache/state/home이다. **서버의 KV/prefix cache, OS page cache, GPU model residency는 초기화하지 않는다.** 따라서 'cold model benchmark'라 부르지 않는다. cache cold/warm 별 측정은 서버를 사용자 측에서 재시작/리셋한 증거와 함께 구분하고 model load 시간을 별도로 기록. fresh OpenCode는 dependency bootstrap 네트워크/초기화 비용을 일으킬 수 있음. offline doctor/tests와 달리 --execute의 무네트워크를 보장하지 않는다.
