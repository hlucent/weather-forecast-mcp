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
- [x] numOfRows 기본값(10)으로 getVilageFcst 응답이 잘리는지
  → 잘림 확인(totalCount 944건 vs 기본 10건). numOfRows 기본값을 1000으로 변경.
- [x] dataType=JSON 에러 응답이 실제로 JSON으로 오는지 여부
  → JSON으로 정상 수신 확인(잘못된 nx/ny 요청 시 resultCode "10" JSON 응답). XML 폴백은
    안전장치로 유지.
- [x] base_time을 발표시각 목록 외 값으로 요청 시 반응
  → 명시적 에러(resultCode "03", NO_DATA) 반환 확인. 빈 응답이 아님.
- [x] 연장기간(+4~5일) PCP/SNO/WSD 코드값 실제 응답 형태
  → 정성정보 코드(1/2/3)로 옴 확인(WSD=1 "적음" 실측). server.py에서 baseDate 대비
    fcstDate +4일 이상이면 별도 코드표 적용, is_extended_period 플래그로 구분.
- [x] get_fcst_version의 basedatetime이 각 ftype의 base_time과 정확히 일치해야 하는지
  → YYYYMMDDHHmm 형식(정시 기준값)으로 정상 응답 확인(ftype=SHRT).

## 2026-08-23 — Claude Code 구현
- DEVPLAN.md 기준 전체 구현 완료: requirements.txt, scripts/convert_area_codes.py,
  api_client.py, code_tables.py, server.py, Dockerfile, fly.toml
- 격자-위경도 엑셀(Downloads 폴더, 3,838행)을 area_codes.json으로 변환, 실제 3,838건 확인
- area_name 매칭은 공백 기준 토큰 부분포함 방식으로 구현("서울 중구" -> 서울특별시 중구,
  단순 문자열 포함 방식은 "서울특별시"처럼 접미사가 붙은 데이터와 불일치해 실패했음)
- FastMCP 3.4.5 기준 `@app.middleware("http")` 데코레이터가 StarletteWithLifespan에 없어
  `BaseHTTPMiddleware` 서브클래스 + `add_middleware()`로 교체
- 로컬 스모크 테스트: initialize 핸드셰이크 200 OK, OPTIONS(CORS preflight) 200 OK,
  분당 3회 초과 시 4번째 요청 429 확인(rate limit 미들웨어 정상 동작)
- 실제 API 키로 4개 오퍼레이션 모두 호출 성공 확인(위 "확인 필요" 항목 실측 결과 참고)
