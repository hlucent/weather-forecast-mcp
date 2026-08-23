# DEVPLAN.md — weather-forecast-mcp

## 0. 프로젝트 개요
기상청 단기예보 조회서비스(VilageFcstInfoService_2.0)를 MCP로 개발한다. 초단기실황, 초단기예보,
단기예보, 예보버전 4개 오퍼레이션을 포함하며, 격자 좌표(nx, ny) 기반 예보 시스템이다.

**기존 "기상청 생활기상지수 MCP"(자외선지수 등, areaNo 기반)와는 별도 신규 MCP로 분리한다.**
판단 근거(1-7절 조언 기준, 사용자 확정):
- 지역 지정 방식이 다름(areaNo vs nx/ny 격자좌표) — 하나의 MCP에 섞으면 혼동 위험
- 오퍼레이션 4개 추가 시 기존 MCP 툴 개수가 3→7개로 증가, tools/list 응답 크기 우려
- 활용 빈도가 다름(자외선은 참고용 저빈도, 단기예보는 핵심 데이터 고빈도)
- 인증키는 공공데이터포털 계열로 재사용 가능(분리와 무관한 이점, 별도 발급 불필요)

## 1. API 서비스 정보
- API명(영문): VilageFcstInfoService_2.0
- API명(국문): 단기예보 조회서비스(2.0)
- 제공기관: 기상청
- 플랫폼: 공공데이터포털(data.go.kr)
- 서비스 URL: `http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0`
- 인증: ServiceKey 방식(쿼리 파라미터 `serviceKey`)
- 응답형식: XML(기본) / JSON(`dataType=JSON` 지정)
- 데이터 갱신주기: 수시(일 8회, 단기예보 기준)
- 남한 지역만 제공(북한·국외 미제공)

## 2. 오퍼레이션 4종 및 MCP 툴 설계

**최소 툴 개수 원칙에 따라 오퍼레이션 4개 = 툴 4개로 1:1 매핑한다.**

| 툴 이름(제안) | 원본 오퍼레이션(영문) | 국문명 | 설명 |
|---|---|---|---|
| `get_ultra_srt_ncst` | getUltraSrtNcst | 초단기실황조회 | 예보구역 대표 AWS 관측값(현재 실황) |
| `get_ultra_srt_fcst` | getUltraSrtFcst | 초단기예보조회 | 예보시점부터 6시간 이내 예보(30분 간격 갱신) |
| `get_vilage_fcst` | getVilageFcst | 단기예보조회 | 최대 5일 예보(1~3시간 간격, 시공간 세분화) |
| `get_fcst_version` | getFcstVersion | 예보버전조회 | 각 오퍼레이션 예보 파일의 최신 버전(생성시간) 확인 |

### 2-1. `get_ultra_srt_ncst` (초단기실황조회)
- 요청 파라미터: `base_date`(필수, YYYYMMDD), `base_time`(필수, HHmm 정시), `nx`(필수), `ny`(필수),
  `numOfRows`(기본 10), `pageNo`(기본 1), `dataType`(기본 XML)
- 매시각 10분 이후 호출 권장(자료 생성 시각)
- 응답 category: T1H(기온), RN1(1시간강수량), UUU/VVV(풍속성분), REH(습도), PTY(강수형태),
  VEC(풍향), WSD(풍속)

### 2-2. `get_ultra_srt_fcst` (초단기예보조회)
- 요청 파라미터: `base_date`(필수), `base_time`(필수, HHmm, 30분 단위), `nx`(필수), `ny`(필수),
  `numOfRows`, `pageNo`, `dataType`
- 매시각 30분 기준 생성, 45분 이후 호출 권장, 10분마다 갱신(기온/습도/바람)
- 응답 category: T1H, RN1, SKY, UUU, VVV, REH, PTY, POP(강수확률), LGT(낙뢰), VEC, WSD
- **자외선·오존 예보 보완 목적으로 가장 자주 쓰일 오퍼레이션**(하늘상태/강수형태로 산책 적합
  시간대 판단 가능)

### 2-3. `get_vilage_fcst` (단기예보조회)
- 요청 파라미터: `base_date`(필수), `base_time`(필수, 02/05/08/11/14/17/20/23시), `nx`(필수),
  `ny`(필수), `numOfRows`(기본 50 권장, 응답 항목 많음), `pageNo`, `dataType`
- 응답 category: POP, PTY, PCP, REH, SNO, SKY, TMP, TMN, TMX, UUU, VVV, WAV, VEC, WSD
- 5일 연장 예보 제공: +1~+3일은 1시간 간격, +4~+5일은 3시간 간격(연장기간 PCP/SNO/WSD는
  정성정보 코드값으로 제공, 코드값 매핑표 3절 참고)
- 최고/최저기온은 발표시각별로 제공 여부가 다름(DEVPLAN 부록 표 참고, 코드 내 주석 처리)

### 2-4. `get_fcst_version` (예보버전조회)
- 요청 파라미터: `ftype`(필수, ODAM=초단기실황/VSRT=초단기예보/SHRT=단기예보),
  `basedatetime`(필수, YYYYMMDDHHmm), `numOfRows`, `pageNo`, `dataType`
- 용도: 예보 파일 갱신 여부 확인(캐싱 판단 등에 활용 가능, 필수 기능은 아니나 명세에 포함되어
  있으므로 1:1 매핑 원칙에 따라 포함)

## 3. 좌표(nx, ny) 변환 — area_name 자동 매핑
- 첨부 엑셀(`기상청41_단기예보_조회서비스_오픈API활용가이드_격자_위경도_2607_.xlsx`, 3,838행)을
  `area_codes.json`으로 변환해 서버에 내장한다(자외선지수 MCP의 area_codes.json 패턴과 동일).
- 컬럼: 행정구역코드, 1단계(시도)/2단계(시군구)/3단계(읍면동), 격자 X, 격자 Y, 경위도
- `area_name`(예: "서울 중구", "종로구 청운효자동") 입력 시 3단계까지 매칭 시도 → 실패 시 2단계 →
  1단계 순으로 폴백, 매칭 결과가 여러 개면 첫 번째 사용하고 그 사실을 응답에 명시(자외선지수 MCP
  `get_uv_forecast`의 기존 처리 방식과 동일하게 통일)
- `nx`/`ny` 직접 입력도 지원(area_name 미입력 시 nx/ny 필수)

## 4. 코드값 처리 (docstring 및 파싱 로직에 반영 필수)
- 하늘상태(SKY): 맑음(1), 구름많음(3), 흐림(4)
- 강수형태(PTY): 초단기 - 없음(0)/비(1)/비눈(2)/눈(3)/소나기(4)/빗방울(5)/빗방울눈날림(6)/눈날림(7),
  단기 - 없음(0)/비(1)/비눈(2)/눈(3)/소나기(4)
- 강수량(PCP)·신적설(SNO): 범주형 문자열 표시 규칙 있음(예: "1mm 미만", "30.0~50.0mm") — 원본
  값과 사람이 읽기 쉬운 문자열을 함께 반환
- 연장기간(+4~5일) PCP/SNO/WSD: 정성정보 코드값(1/2/3 등) → 용어 매핑표 별도 적용 필요(2-3절
  코드값과 혼동 주의, 서로 다른 코드 체계)
- 결측치: +900 이상/-900 이하 값은 Missing 처리(관측장비 없음 또는 결측)
- 해상 지역: 기온군/강수확률/강수량·적설/습도 제공 안 함(마스킹, null)
- 풍향(VEC) 16방위 변환식: `((풍향값 + 22.5*0.5) / 22.5)`를 정수부만 취해 16방위 코드 매핑
  (매핑표 DEVPLAN 부록 참고)

## 5. 실측 필요 항목 (1-4절 기준)
- ① `numOfRows` 기본값(10)으로는 단기예보(getVilageFcst) 응답이 잘리는지 확인 — 예제 응답
  totalCount 742건 확인됨, 실사용 시 numOfRows=1000 이상 권장 여부 실측
- ② `dataType=JSON` 요청 시 정상 응답되는지, 에러 시에도 JSON으로 오는지 확인(다른 서울시 API는
  에러가 XML로만 오는 사례 있었음 — XML `<resultCode>`/`<resultMsg>` 정규식 폴백 필수 적용)
- ③ base_time을 발표시각 목록(예: 02,05,08,11,14,17,20,23시)이 아닌 임의 시각으로 요청 시 반응
  (빈 응답 vs 에러)
- ④ 연장기간(+4~5일) 응답에서 PCP/SNO/WSD가 실제로 코드값(1/2/3)으로 오는지, 아니면 정량값과
  혼재되는지 실측 확인 후 파싱 분기 로직 검증
- ⑤ `get_fcst_version`의 `basedatetime`이 각 ftype의 base_time 형식과 정확히 일치해야 하는지
  (문서상 "각각의 base_time으로 검색"이라고만 되어 있어 모호함)

## 6. 기술 스택
- Python, FastMCP, `stateless_http=True`
- 격자 매핑: `area_codes.json` (엑셀 3,838행 → JSON 변환, 서버 내장)
- 응답 파싱: JSON 우선 요청 + 실패 시 XML `<resultCode>`/`<resultMsg>` 정규식 폴백
- 숫자 필드 안전 변환: `_safe_int()`/`_safe_float()`, 결측(+900/-900, "-") → `None`

## 7. 디렉토리 구조
```
weather-forecast-mcp/
├── server.py
├── api_client.py       # VilageFcstInfoService_2.0 API 클라이언트
├── area_codes.json      # 격자 좌표 매핑표(3,838행)
├── code_tables.py       # SKY/PTY/PCP/SNO/VEC 등 코드값 매핑 상수
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── fly.toml
├── README.md
├── CLAUDE.md
└── DEVLOG.md
```

## 8. 진행 순서
1. 이 문서 4종(zip) 전달 → 사용자 부트스트랩 실행
2. Claude Code: `area_codes.json` 변환 스크립트 작성 및 실행(엑셀 → JSON, 1단계/2단계/3단계
   지역명 조합 키로 저장)
3. API 클라이언트 구현(4개 오퍼레이션, JSON우선/XML폴백, 코드값 매핑)
4. server.py(4개 툴, stateless_http=True, rate limit 미들웨어)
5. 로컬 실측(5절 항목 우선 확인)
6. README/DEVLOG 갱신, git commit/push
7. (사용자) PowerShell에서 fly 배포
8. 커넥터 연결(`/mcp`) 및 새 대화창 확인

## 9. 저장소 설명(Description 제안)
> 기상청 단기예보 조회서비스(VilageFcstInfoService_2.0) MCP — 초단기실황, 초단기예보, 단기예보, 예보버전 조회를 격자 좌표 또는 지역명으로 제공

## 10. 환경변수
- ENV_KEY: WEATHER_FORECAST_SERVICE_KEY
