# 단계별 로드맵

각 단계는 앞 단계의 사용자 측 측정 결과를 gate로 사용합니다. 날짜별 완성 약속이나 미구현 기능의 성능 주장이 아닙니다.

| 단계 | 상태 | 범위 / 비목표 | 진입·완료 조건 / 측정 |
|---|---|---|---|
| 0 환경 | IMPLEMENTED (offline verified) | Windows 명령, doctor, preview, prepare, stdlib tests. 자동 설치/추론 금지 | 오프라인 테스트 통과, 설치 경로/환경 확인; doctor는 버전 검증을 주장하지 않음 |
| 1 baseline | IMPLEMENTED, USER RUNTIME VALIDATION PENDING | 원본 OpenCode 1.2.27 + 사용자 endpoint, ranges-v1 과제. 모델 최적화 없음 | Windows VM에서 버전 gate 통과, 실제 성공/실패 모두 기록, 실제 hidden cases 6개 실행, 최소 3회 baseline 반복. 단일 과제 성능 일반화 금지 |
| 2 GLM profile | PLANNED / NOT IMPLEMENTED | 정확한 GLM ID, engine/version, quantization, template, context, reasoning/tool-call parsing 검증. 임의 GLM 호환 주장 금지 | Stage1 결과 확보 후 동일 endpoint 설정 변경 하나씩 비교. tool format 오류율/완수율/시간/token/memory 기록. 같은 모델/과제/budget; 품질 하락 없고 오류 감소가 재현되어야 validated 승격 |
| 3 tool output | PLANNED / NOT IMPLEMENTED | 필요한 도구 출력만 구조화·예산화·중복 제거. 전역 무조건 자르기 금지 | Stage2 고정; raw vs selective 비교. 필요한 증거 손실률 0을 목표로 테스트, hidden pass 회귀 없음, 입력 토큰/시간 감소를 반복 측정; 손실 사례를 실패로 보존 |
| 4 grounded wiki | PLANNED / NOT IMPLEMENTED | 파일/심볼/commit 출처가 있는 project wiki와 선택적 검색. 생성된 요약을 사실로 취급하지 않음 | Stage3 고정; wiki off/on, stale/change refresh 실험, 근거 정확도·retrieval 누락·품질·indexing 비용 측정. repo revision 변경 시 invalidation 검증 |
| 5 minimal fork | PLANNED / NOT IMPLEMENTED | config/plugin 경계로 해결 불가한 병목만 OpenCode core 최소 수정. full fork 선행 금지 | 이전 단계 ablation으로 core 병목 재현 및 profiler 증거 확보, 유지보수/업스트림 기여 계획, fork off/on 동일 실험, 회귀·license 확인 |

## 단계 진행 순서

1. Stage0 명령만 먼저 실행하고 환경 이슈 해결.
2. Stage1 실험은 사용자가 VM에서 실행. 모델·서버 실행은 이 repo가 대신하지 않음.
3. manifest/report를 검토해 baseline이 신뢰 가능한지 먼저 확인. 실패를 삭제하거나 성공한 trial만 골라내지 않음.
4. Stage2부터는 기능을 **추가 구현하는 별도 PR**에서 테스트/측정/비교 runner를 같이 제출. 현재 CLI에는 optimized mode가 없음.
5. A=baseline, B=최적화 한 가지만 적용. A/B 순서를 AB/BA로 균형화하고 같은 조건으로 최소 3회씩 반복. 실험 수가 적으면 유의미한 향상을 주장하지 않음.

목표 지표는 완수율/정답률, 실패 유형, end-to-end 시간 분포, 알려진 token total, peak memory/VRAM(외부 도구), 근거 손실/오염입니다. 성공률이 baseline보다 떨어지는 최적화는 기본 승격하지 않습니다. 시간/token 개선 목표치는 baseline 측정 후 사전 등록합니다. 이 문서에는 측정되지 않은 절감률이 없습니다.
