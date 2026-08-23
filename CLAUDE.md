# CLAUDE.md — weather-forecast-mcp (Claude Code 작업 지침)

## 절대 규칙
- DEVPLAN.md만 먼저 읽고 시작한다. 다른 문서 재탐색 금지. 웹서치 금지.
- 불확실하면 기본값 1개로 구현 후 DEVLOG.md에 "확인 필요"로 기록한다.
- 동일 오류 최대 3회 재시도, 3회 실패 시 기록 후 사용자에게 보고한다.
- **`fly launch`/`fly secrets set`/`flyctl deploy`/`fly logs` 등 fly.io 명령을 절대 직접
  실행하지 않는다.**
- 구현 + 로컬 테스트 + git commit/push까지 끝나면 아래 "작업 순서" 10번에서 정지하고
  배포 안내문구를 출력한다.

## 기술 필수 사항
- `.env`: BOM 없는 UTF-8로 저장
- `server.py`의 `mcp.run()`에는 항상 `stateless_http=True`를 지정한다(누락 시 fly.io
  멀티머신 환경에서 세션 404 발생)
- 응답 파싱: `dataType=JSON` 요청이 기본이나, 에러 응답이 XML로 올 수 있으므로
  `response.json()` 실패 시 XML `<resultCode>`/`<resultMsg>` 정규식 폴백을 반드시 구현한다
- 숫자 필드는 안전 변환 함수를 통해서만 다룬다. 결측치(+900 이상, -900 이하, 문자열 "-")는
  0이 아니라 `None`으로 반환한다(기온·강수량 등은 결측과 실측 0을 구분해야 하는 데이터).
- IP 추출: `Fly-Client-IP` 헤더 최우선, 없을 때만 `X-Forwarded-For` 폴백
- CORS preflight(OPTIONS)는 rate limit 카운터에서 제외한다

## API 키 취급
- 항상 `os.environ`으로 읽는다. 하드코딩 금지.
- 환경변수명은 DEVPLAN.md의 `ENV_KEY: WEATHER_FORECAST_SERVICE_KEY`를 그대로 사용한다.
- `.env` 갱신 여부를 사용자가 주장하면, 재테스트 전 파일 크기/내용이 실제로 바뀌었는지
  먼저 확인한다.
- 키를 표준출력에 찍지 않는다. 필요하면 앞 4자리 + "..." + 길이만 출력한다.

## 오퍼레이션 4종 → 툴 매핑 (DEVPLAN.md 2절 참고, 1:1 최소 매핑 원칙)
- `get_ultra_srt_ncst` (getUltraSrtNcst, 초단기실황조회)
- `get_ultra_srt_fcst` (getUltraSrtFcst, 초단기예보조회)
- `get_vilage_fcst` (getVilageFcst, 단기예보조회)
- `get_fcst_version` (getFcstVersion, 예보버전조회)

각 툴의 docstring에는 반드시:
- 필수/선택 파라미터, base_time이 정시/30분 단위 등 발표시각 제약이 있다는 점
- 응답 category 코드값(단위 포함, 예: TMP=℃, REH=%, WSD=m/s)
- 코드값 필드(SKY/PTY 등)는 숫자가 아니라 사람이 읽을 수 있는 한글 설명을 함께 반환

## area_name → nx/ny 자동 매핑
- `area_codes.json`(엑셀 3,838행 변환, 프로젝트 루트에 내장)을 로드해 사용
- 자외선지수 MCP의 기존 `get_uv_forecast` 처리 방식과 동일하게: `area_name` 입력 시
  3단계(읍면동) → 2단계(시군구) → 1단계(시도) 순으로 매칭 시도, 여러 후보 있으면 첫 번째
  사용하고 그 사실을 응답에 명시
- `nx`/`ny` 직접 입력도 지원(둘 중 하나는 필수)
- 변환 스크립트는 1회성이므로 `scripts/convert_area_codes.py` 등으로 별도 보관 가능(최종
  산출물인 area_codes.json만 배포에 포함)

## 코드값 매핑 (DEVPLAN.md 4절 참고, code_tables.py에 상수로 정리)
- SKY: 1=맑음, 3=구름많음, 4=흐림
- PTY(초단기): 0=없음, 1=비, 2=비/눈, 3=눈, 4=소나기, 5=빗방울, 6=빗방울눈날림, 7=눈날림
- PTY(단기): 0=없음, 1=비, 2=비/눈, 3=눈, 4=소나기
- PCP/SNO 범주 문자열 변환 규칙 적용(원본값 + 문자열 설명 함께 반환)
- 연장기간(+4~5일) PCP/SNO/WSD 정성정보 코드(1/2/3)는 위 코드값과 별개 체계이므로 혼동하지
  않도록 별도 필드로 구분
- VEC(풍향) → 16방위 변환 공식 적용: `int((풍향값 + 22.5*0.5) / 22.5) % 16` → 방위 매핑표

## 작업 순서
1. `requirements.txt` 작성
2. `scripts/convert_area_codes.py` 작성 → 첨부 엑셀을 `area_codes.json`으로 변환(1회 실행
   후 산출물만 유지)
3. `api_client.py` 구현: 4개 오퍼레이션 호출 함수, JSON우선/XML폴백, 에러코드(00~34) 매핑
4. `code_tables.py`: SKY/PTY/PCP/SNO/VEC 매핑 상수
5. `server.py`: 4개 툴 등록(stateless_http=True), rate limit 미들웨어
6. `.env.example`, `.gitignore` 작성
7. 로컬 테스트: DEVPLAN.md 5절 실측 필요 항목 우선 확인 → numOfRows 기본값 적정성 →
   base_time 형식 오류 시 반응 → 연장기간 코드값 실측 → dataType=JSON 에러 응답 형식
8. FastMCP 스모크 테스트(initialize까지)
9. Dockerfile / fly.toml(표준 `[http_service]` 템플릿 직접 작성, `fly launch` 결과 대기 안 함)
10. README.md / DEVLOG.md 실측 기준 갱신 → git add/commit/push
11. **여기서 정지.** 아래 안내문구를 사용자에게 출력한다:
```
개발 + 로컬 테스트 + git push까지 완료했습니다.
이제 PowerShell(이 창 아님)에서 배포를 진행해주세요:

cd "C:\Users\hwang\Projects\weather-forecast-mcp"
fly launch --no-deploy
⚠️ flyctl deploy 전에 fly.toml의 [[services]] 블록 확인 — 있으면 http_service 방식으로 교체
fly secrets set WEATHER_FORECAST_SERVICE_KEY=발급받은키
flyctl deploy

배포 후 https://<앱이름>.fly.dev/mcp 를 Claude.ai 커넥터에 연결하세요.
```

## 하지 말 것
- 툴 개수를 DEVPLAN 범위(4개) 초과해서 만들지 않는다
- 인증키 하드코딩 금지
- `stateless_http=True` 누락 금지
- fly.io 명령 자동 실행 금지
- rate limit 미들웨어 누락 금지(공개서버이므로 필수)
- fly.toml 구버전(`[[services]]`) 방치 금지
- `X-Forwarded-For`를 `Fly-Client-IP`보다 우선 신뢰하지 않는다
- OPTIONS 요청을 rate limit 카운터에 포함하지 않는다

## 실측 필요 항목 처리 절차
재현 확인(최소 2회) → 원인 분리(코드 문제 vs API 특이동작) → 코드레벨 자체검증(3회 재시도
원칙 안에서) → DEVLOG.md에 시도/확인/미확인 기록 → 코드에 사전검증 로직 추가 → README/DEVPLAN
실동작 기준 갱신 + 커밋

## Rate Limit 미들웨어
분당 3회 초과→429 / 1시간 내 5회 위반→24시간 차단 / 일일 30회 초과→429. in-memory만 사용,
Fly-Client-IP 우선, OPTIONS 제외. 멀티머신 카운터 분리는 허용된 트레이드오프(README에 명시).
