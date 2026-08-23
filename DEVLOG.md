# DEVLOG.md — weather-forecast-mcp

## 2026-08-23 — 프로젝트 시작
- Claude(웹챗)에서 DEVPLAN/CLAUDE/README/DEVLOG 4종 문서 작성 완료.
- 기존 "기상청 생활기상지수 MCP"(자외선지수 등)에 통합할지 신규 분리할지 사용자에게 문의 →
  "잘 모르겠음, 추천해줘" 응답 → Claude가 분리를 추천하고 사용자가 확정(1-7절 판단 조언 절차).
  근거: 지역 지정 방식 상이(areaNo vs nx/ny), 툴 개수 증가(3→7개) 시 tools/list 크기 우려,
  활용 빈도 차이. 인증키는 재사용 가능하나 분리 여부와는 무관.
- 명세서(DOCX) 및 격자-위경도 매핑 엑셀(3,838행) 분석 완료. 오퍼레이션 4개(초단기실황/
  초단기예보/단기예보/예보버전) 전부 1:1 툴 매핑 확정.
- DEVPLAN.md 작성 직후 자체검증(1-2절) 완료: "저장소 설명", "ENV_KEY:" 항목 grep 확인됨.

## 확인 필요 (구현 전 실측 대상, DEVPLAN.md 5절과 동일)
- [ ] numOfRows 기본값(10)으로 getVilageFcst 응답이 잘리는지
- [ ] dataType=JSON 에러 응답이 실제로 JSON으로 오는지 여부
- [ ] base_time을 발표시각 목록 외 값으로 요청 시 반응
- [ ] 연장기간(+4~5일) PCP/SNO/WSD 코드값 실제 응답 형태
- [ ] get_fcst_version의 basedatetime 형식이 각 ftype의 base_time과 정확히 일치하는지

<!-- 이후 진행 기록은 Claude Code 작업 시 이어서 추가 -->
