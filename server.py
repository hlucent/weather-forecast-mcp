"""기상청 단기예보 조회서비스(VilageFcstInfoService_2.0) MCP 서버."""

import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

import api_client
import code_tables
from api_client import WeatherApiError, _safe_float, _safe_int

load_dotenv()

mcp = FastMCP("weather-forecast-mcp")

_AREA_CODES_PATH = Path(__file__).parent / "area_codes.json"
with open(_AREA_CODES_PATH, encoding="utf-8") as f:
    _AREA_CODES = json.load(f)


def _tokens_match(tokens, *fields):
    """모든 토큰이 fields 중 어딘가에 부분포함되면 True (예: ['서울','중구'] -> level1='서울특별시', level2='중구')."""
    haystack = " ".join(f for f in fields if f)
    return all(tok in haystack for tok in tokens)


def _resolve_area_name(area_name):
    """area_name -> (nx, ny, matched_label, note).

    입력을 공백 기준 토큰으로 나눠 각 토큰이 지역명에 부분포함되는지로 매칭한다
    (예: "서울 중구" -> level1="서울특별시", level2="중구").
    3단계(읍면동) -> 2단계(시군구) -> 1단계(시도) 순으로 매칭 시도.
    여러 후보가 있으면 첫 번째를 사용하고 그 사실을 note로 명시한다.
    매칭 실패 시 (None, None, None, note) 반환.
    """
    name = area_name.strip()
    tokens = name.split()
    if not tokens:
        return None, None, None, "지역명이 비어 있습니다."

    # 3단계: 읍면동
    candidates = [
        e for e in _AREA_CODES
        if e["level3"] and _tokens_match(tokens, e["level1"], e["level2"], e["level3"])
    ]
    if candidates:
        matched = candidates[0]
        note = None
        if len(candidates) > 1:
            note = f"'{name}'에 해당하는 3단계(읍면동) 후보가 {len(candidates)}건 있어 첫 번째({matched['level1']} {matched['level2']} {matched['level3']})를 사용했습니다."
        return matched["nx"], matched["ny"], f"{matched['level1']} {matched['level2']} {matched['level3']}".strip(), note

    # 2단계: 시군구
    candidates = [
        e for e in _AREA_CODES
        if not e["level3"] and e["level2"] and _tokens_match(tokens, e["level1"], e["level2"])
    ]
    if candidates:
        matched = candidates[0]
        note = None
        if len(candidates) > 1:
            note = f"'{name}'에 해당하는 2단계(시군구) 후보가 {len(candidates)}건 있어 첫 번째({matched['level1']} {matched['level2']})를 사용했습니다."
        return matched["nx"], matched["ny"], f"{matched['level1']} {matched['level2']}".strip(), note

    # 1단계: 시도
    candidates = [
        e for e in _AREA_CODES
        if not e["level2"] and not e["level3"] and _tokens_match(tokens, e["level1"])
    ]
    if candidates:
        matched = candidates[0]
        note = None
        if len(candidates) > 1:
            note = f"'{name}'에 해당하는 1단계(시도) 후보가 {len(candidates)}건 있어 첫 번째({matched['level1']})를 사용했습니다."
        return matched["nx"], matched["ny"], matched["level1"], note

    return None, None, None, f"'{name}'에 해당하는 지역을 찾을 수 없습니다."


def _resolve_nx_ny(area_name, nx, ny):
    """area_name 또는 nx/ny 중 하나로 좌표를 확정. 반환: (nx, ny, area_note)."""
    if area_name:
        resolved_nx, resolved_ny, matched_label, note = _resolve_area_name(area_name)
        if resolved_nx is None:
            raise ValueError(note)
        result_note = f"'{area_name}' -> {matched_label} (nx={resolved_nx}, ny={resolved_ny})"
        if note:
            result_note += f" | {note}"
        return resolved_nx, resolved_ny, result_note
    if nx is None or ny is None:
        raise ValueError("area_name 또는 (nx, ny)를 지정해야 합니다.")
    return nx, ny, None


_EXTENDED_QUALITATIVE_CATEGORIES = {"PCP", "SNO", "WSD"}


def _is_extended_period(base_date, fcst_date):
    """fcst_date가 base_date로부터 +4일 이상이면 연장기간(정성정보 코드 체계)으로 판단."""
    if not base_date or not fcst_date:
        return False
    try:
        from datetime import datetime

        delta = (datetime.strptime(fcst_date, "%Y%m%d") - datetime.strptime(base_date, "%Y%m%d")).days
    except ValueError:
        return False
    return delta >= 4


def _build_item_dict(items, category_texts=None):
    """API item 리스트를 category별로 정리. 코드값은 사람이 읽을 수 있는 텍스트도 함께 반환.

    단기예보(getVilageFcst)의 PCP/SNO/WSD는 +4~5일 연장기간에서 정성정보 코드(1/2/3)로
    제공되므로, base_date 대비 fcst_date가 +4일 이상이면 별도 매핑을 적용한다(DEVPLAN 4절).
    """
    result = []
    for item in items:
        category = item.get("category")
        raw_value = item.get("obsrValue", item.get("fcstValue"))
        base_date = item.get("baseDate")
        fcst_date = item.get("fcstDate")
        entry = {
            "category": category,
            "value": raw_value,
            "fcstDate": fcst_date,
            "fcstTime": item.get("fcstTime"),
            "baseDate": base_date,
            "baseTime": item.get("baseTime"),
        }
        if category in _EXTENDED_QUALITATIVE_CATEGORIES and _is_extended_period(base_date, fcst_date):
            entry["value_text"] = code_tables.extended_qualitative_to_text(raw_value)
            entry["is_extended_period"] = True
        elif category_texts and category in category_texts:
            entry["value_text"] = category_texts[category](raw_value)
        result.append(entry)
    return result


def _category_text_map_ultra():
    return {
        "PTY": code_tables.pty_ultra_to_text,
        "SKY": code_tables.sky_to_text,
        "VEC": lambda v: code_tables.vec_to_direction(_safe_int(v)),
    }


def _category_text_map_shrt():
    return {
        "PTY": code_tables.pty_shrt_to_text,
        "SKY": code_tables.sky_to_text,
        "VEC": lambda v: code_tables.vec_to_direction(_safe_int(v)),
    }


@mcp.tool()
def get_ultra_srt_ncst(
    base_date: str,
    base_time: str,
    area_name: str = "",
    nx: int = None,
    ny: int = None,
    num_of_rows: int = 10,
    page_no: int = 1,
) -> dict:
    """초단기실황조회(getUltraSrtNcst) — 예보구역 대표 AWS 관측값(현재 실황).

    필수 파라미터:
    - base_date: 발표일자 YYYYMMDD
    - base_time: 발표시각 HHmm, **매시 정시**(예: "0600"). 자료는 매시각 10분 이후 생성되므로
      해당 시각 10분 이후 호출을 권장한다.
    - area_name 또는 (nx, ny) 중 하나 필수. area_name 입력 시 3단계(읍면동)->2단계(시군구)
      ->1단계(시도) 순으로 매칭하며, 후보가 여럿이면 첫 번째를 사용하고 응답 area_note에 명시한다.

    선택 파라미터: num_of_rows(기본 10), page_no(기본 1)

    응답 category(단위):
    - T1H: 기온(℃)
    - RN1: 1시간 강수량(mm)
    - UUU/VVV: 동서/남북 바람성분(m/s)
    - REH: 습도(%)
    - PTY: 강수형태 코드(사람이 읽을 수 있는 설명은 value_text에 포함)
    - VEC: 풍향(deg, value_text에 16방위 한글 설명 포함)
    - WSD: 풍속(m/s)

    숫자 필드는 결측치(+900 이상/-900 이하, "-")를 None으로 반환한다(실측 0과 구분).
    """
    resolved_nx, resolved_ny, area_note = _resolve_nx_ny(area_name, nx, ny)
    items, total_count = api_client.get_ultra_srt_ncst(
        base_date, base_time, resolved_nx, resolved_ny, num_of_rows, page_no
    )
    return {
        "nx": resolved_nx,
        "ny": resolved_ny,
        "area_note": area_note,
        "total_count": total_count,
        "items": _build_item_dict(items, _category_text_map_ultra()),
    }


@mcp.tool()
def get_ultra_srt_fcst(
    base_date: str,
    base_time: str,
    area_name: str = "",
    nx: int = None,
    ny: int = None,
    num_of_rows: int = 60,
    page_no: int = 1,
) -> dict:
    """초단기예보조회(getUltraSrtFcst) — 예보시점부터 6시간 이내 예보(30분 간격 갱신).

    필수 파라미터:
    - base_date: 발표일자 YYYYMMDD
    - base_time: 발표시각 HHmm, **매시 30분 단위**(예: "0630"). 매시각 30분 기준 생성,
      45분 이후 호출을 권장하며 기온/습도/바람은 10분마다 갱신된다.
    - area_name 또는 (nx, ny) 중 하나 필수. 매칭 규칙은 get_ultra_srt_ncst와 동일.

    선택 파라미터: num_of_rows(기본 60), page_no(기본 1)

    응답 category(단위):
    - T1H: 기온(℃), RN1: 1시간 강수량(mm), SKY: 하늘상태 코드(value_text 포함)
    - UUU/VVV: 바람성분(m/s), REH: 습도(%), PTY: 강수형태 코드(value_text 포함)
    - POP: 강수확률(%), LGT: 낙뢰(kA), VEC: 풍향(deg, value_text 16방위), WSD: 풍속(m/s)

    자외선/오존 예보 보완 목적(하늘상태·강수형태로 시간대별 야외활동 적합 여부 판단)으로
    가장 자주 쓰일 오퍼레이션이다.
    숫자 필드는 결측치(+900 이상/-900 이하, "-")를 None으로 반환한다.
    """
    resolved_nx, resolved_ny, area_note = _resolve_nx_ny(area_name, nx, ny)
    items, total_count = api_client.get_ultra_srt_fcst(
        base_date, base_time, resolved_nx, resolved_ny, num_of_rows, page_no
    )
    return {
        "nx": resolved_nx,
        "ny": resolved_ny,
        "area_note": area_note,
        "total_count": total_count,
        "items": _build_item_dict(items, _category_text_map_ultra()),
    }


@mcp.tool()
def get_vilage_fcst(
    base_date: str,
    base_time: str,
    area_name: str = "",
    nx: int = None,
    ny: int = None,
    num_of_rows: int = 1000,
    page_no: int = 1,
) -> dict:
    """단기예보조회(getVilageFcst) — 최대 5일 예보(1~3시간 간격, 시공간 세분화).

    필수 파라미터:
    - base_date: 발표일자 YYYYMMDD
    - base_time: 발표시각 HHmm, **02/05/08/11/14/17/20/23시 중 하나만 유효**(그 외 임의 시각은
      빈 응답 또는 에러가 될 수 있음 — 실측 필요, DEVLOG 참고)
    - area_name 또는 (nx, ny) 중 하나 필수. 매칭 규칙은 get_ultra_srt_ncst와 동일.

    선택 파라미터: num_of_rows(기본 1000 — 응답 항목이 많아 기본 10으로는 잘릴 수 있음),
    page_no(기본 1)

    응답 category(단위):
    - POP: 강수확률(%), PTY: 강수형태 코드(단기예보 체계 0~4, value_text 포함)
    - PCP: 1시간 강수량 범주 문자열(원본값+설명), REH: 습도(%)
    - SNO: 1시간 신적설 범주 문자열(원본값+설명), SKY: 하늘상태 코드(value_text 포함)
    - TMP: 1시간 기온(℃), TMN: 일 최저기온(℃, 발표시각별 제공 여부 다름)
    - TMX: 일 최고기온(℃, 발표시각별 제공 여부 다름)
    - UUU/VVV: 바람성분(m/s), WAV: 파고(m)
    - VEC: 풍향(deg, value_text 16방위), WSD: 풍속(m/s)

    5일 연장 예보: +1~+3일은 1시간 간격, +4~+5일은 3시간 간격이며 이 구간의 PCP/SNO/WSD는
    정성정보 코드(1=적음/2=보통/3=많음)로 제공될 수 있다(2절 코드값과 별개 체계, 혼동 주의).
    숫자 필드는 결측치를 None으로 반환한다. 해상 지역은 기온/강수확률/강수량·적설/습도가
    제공되지 않을 수 있다(마스킹).
    """
    resolved_nx, resolved_ny, area_note = _resolve_nx_ny(area_name, nx, ny)
    items, total_count = api_client.get_vilage_fcst(
        base_date, base_time, resolved_nx, resolved_ny, num_of_rows, page_no
    )
    return {
        "nx": resolved_nx,
        "ny": resolved_ny,
        "area_note": area_note,
        "total_count": total_count,
        "items": _build_item_dict(items, _category_text_map_shrt()),
    }


@mcp.tool()
def get_fcst_version(
    ftype: str,
    base_datetime: str,
    num_of_rows: int = 10,
    page_no: int = 1,
) -> dict:
    """예보버전조회(getFcstVersion) — 예보 파일의 최신 버전(생성시간) 확인.

    필수 파라미터:
    - ftype: "ODAM"(초단기실황) / "VSRT"(초단기예보) / "SHRT"(단기예보) 중 하나
    - base_datetime: YYYYMMDDHHmm 형식. 각 ftype에 대응하는 오퍼레이션의 base_time 발표시각
      제약(정시/30분단위/8회 발표시각)과 정확히 일치해야 하는지는 명세상 모호하여 실측 필요
      (DEVLOG "확인 필요" 참고).

    선택 파라미터: num_of_rows(기본 10), page_no(기본 1)

    용도: 예보 파일 갱신 여부 확인(캐싱 판단 등). 필수 기능은 아니지만 오퍼레이션 1:1 매핑
    원칙에 따라 포함한다.
    """
    items, total_count = api_client.get_fcst_version(ftype, base_datetime, num_of_rows, page_no)
    return {
        "total_count": total_count,
        "items": items,
    }


# ---------------------------------------------------------------------------
# Rate limit 미들웨어 (공개 서버이므로 필수)
# 분당 3회 초과 -> 429 / 1시간 내 5회 위반 -> 24시간 차단 / 일일 30회 초과 -> 429
# in-memory만 사용, Fly-Client-IP 우선(X-Forwarded-For는 그 헤더가 없을 때만 폴백),
# OPTIONS(CORS preflight)는 카운터에서 제외. 멀티머신 환경에서는 머신별로 카운터가
# 분리되는 트레이드오프를 허용한다(README에 명시).
# ---------------------------------------------------------------------------

_MINUTE_WINDOW = 60
_HOUR_WINDOW = 3600
_DAY_WINDOW = 86400
_MINUTE_LIMIT = 3
_HOUR_VIOLATION_LIMIT = 5
_DAY_LIMIT = 30
_BLOCK_DURATION = 86400

_request_log = defaultdict(deque)  # ip -> deque[timestamp]
_violation_log = defaultdict(deque)  # ip -> deque[violation timestamp]
_blocked_until = {}  # ip -> unblock timestamp


def _get_client_ip(request: Request) -> str:
    ip = request.headers.get("Fly-Client-IP")
    if ip:
        return ip
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune(dq: deque, now: float, window: float):
    while dq and now - dq[0] > window:
        dq.popleft()


def _check_rate_limit(ip: str):
    """반환: None이면 통과, 아니면 (status_code, message)."""
    now = time.time()

    if ip in _blocked_until:
        if now < _blocked_until[ip]:
            return 429, "24시간 차단 상태입니다. 잠시 후 다시 시도해주세요."
        del _blocked_until[ip]

    minute_log = _request_log[ip]
    _prune(minute_log, now, _DAY_WINDOW)

    minute_count = sum(1 for t in minute_log if now - t <= _MINUTE_WINDOW)
    day_count = sum(1 for t in minute_log if now - t <= _DAY_WINDOW)

    if minute_count >= _MINUTE_LIMIT:
        violations = _violation_log[ip]
        _prune(violations, now, _HOUR_WINDOW)
        violations.append(now)
        if len(violations) >= _HOUR_VIOLATION_LIMIT:
            _blocked_until[ip] = now + _BLOCK_DURATION
        return 429, "분당 요청 제한(3회)을 초과했습니다."

    if day_count >= _DAY_LIMIT:
        return 429, "일일 요청 제한(30회)을 초과했습니다."

    minute_log.append(now)
    return None


@mcp.custom_route("/mcp", methods=["OPTIONS"])
async def _cors_preflight(request: Request):
    return JSONResponse({}, status_code=200)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        ip = _get_client_ip(request)
        result = _check_rate_limit(ip)
        if result is not None:
            status_code, message = result
            return JSONResponse({"error": message}, status_code=status_code)

        return await call_next(request)


_original_http_app = mcp.http_app


def _rate_limited_app(*args, **kwargs):
    app = _original_http_app(*args, **kwargs)
    app.add_middleware(RateLimitMiddleware)
    return app


mcp.http_app = _rate_limited_app


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), stateless_http=True)
