# weather-forecast-mcp

기상청 단기예보 조회서비스(VilageFcstInfoService_2.0)를 MCP(Model Context Protocol) 서버로
제공합니다. 초단기실황, 초단기예보, 단기예보, 예보버전 4개 오퍼레이션을 지역명 또는 격자
좌표(nx, ny)로 조회할 수 있습니다.

## Dataset Registry

| 화면 표시명 | 제공부서 | 이 MCP 포함 여부 | 서비스명(SERVICE) |
|---|---|---|---|
| 기상청 단기예보 조회서비스(2.0) | 기상청 | 포함 | VilageFcstInfoService_2.0 |

이 MCP는 단일 API(오퍼레이션 4종)로 구성되며, 별도 데이터셋 통합은 없습니다.

## 제공 툴

| 툴 이름 | 오퍼레이션 | 설명 |
|---|---|---|
| `get_ultra_srt_ncst` | getUltraSrtNcst (초단기실황조회) | 현재 시각 기준 실황(관측값) |
| `get_ultra_srt_fcst` | getUltraSrtFcst (초단기예보조회) | 6시간 이내 단기 예보 |
| `get_vilage_fcst` | getVilageFcst (단기예보조회) | 최대 5일 예보 |
| `get_fcst_version` | getFcstVersion (예보버전조회) | 예보 파일 최신 버전 확인 |

## 설치 및 배포

```bash
pip install -r requirements.txt
cp .env.example .env  # WEATHER_FORECAST_SERVICE_KEY 값 입력
python server.py
```

fly.io 배포:
```bash
fly launch --no-deploy
fly secrets set WEATHER_FORECAST_SERVICE_KEY=발급받은키
flyctl deploy
```

## 환경변수

| 변수명 | 설명 |
|---|---|
| `WEATHER_FORECAST_SERVICE_KEY` | 공공데이터포털에서 발급받은 인증키(Decoding 키 사용) |

## 지역 지정 방식

`area_name`(예: "서울 중구", "종로구 청운효자동") 또는 `nx`/`ny` 격자 좌표 중 하나를 입력합니다.
`area_name` 사용 시 내장된 격자 매핑표(3,838개 행정구역)에서 3단계(읍면동) → 2단계(시군구) →
1단계(시도) 순으로 자동 매칭합니다.

## Rate Limit

공개 서버 특성상 아래 3단계 제한이 적용됩니다:
- 분당 3회 초과 → 429
- 1시간 내 5회 위반 → 24시간 차단
- 일일 30회 초과 → 429

fly.io 멀티머신(2대) 환경에서 rate limit 카운터가 머신별로 분리될 수 있는 점은 알려진
트레이드오프로 허용합니다(가용성 우선).

## 실측 확인 사항

- `get_vilage_fcst`의 `numOfRows` 기본값은 1000으로 설정(예제 응답 totalCount 742~944건 실측
  확인, 기본값 10이면 잘림)
- `dataType=JSON` 에러 응답은 실제로 JSON 형식으로 옴(잘못된 nx/ny 요청 시 `resultCode: "10"`
  JSON 정상 수신 확인). 단, 만약을 대비해 XML `<resultCode>`/`<resultMsg>` 정규식 폴백도 구현됨
- `get_vilage_fcst`에 유효하지 않은 base_time(예: 03시)을 지정하면 `resultCode: "03"`
  (NO_DATA) 에러가 반환됨(빈 응답이 아닌 명시적 에러)
- 단기예보 +4일 이후(연장기간) PCP/SNO/WSD는 정성정보 코드(1=적음/2=보통/3=많음)로 옴을
  실측 확인. 서버는 `baseDate` 대비 `fcstDate`가 +4일 이상이면 이 코드표를 적용하고
  응답에 `is_extended_period: true`를 표시함
- `get_fcst_version`은 `basedatetime`을 `base_time`과 동일한 `YYYYMMDDHHmm` 형식으로 주면
  정상 동작 확인(ftype=SHRT 기준)

## 라이선스

MIT

## 참고

- 원본 API 명세: 기상청 「단기예보 조회서비스(2.0) Open API 활용가이드」
- 격자-위경도 매핑표: 기상청 제공 엑셀 자료(2026년 7월 기준, 3,838개 행정구역)
- 남한 지역만 제공(북한·국외 미제공)
