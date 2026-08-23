"""기상청 단기예보 조회서비스(VilageFcstInfoService_2.0) API 클라이언트."""

import os
import re
import json as jsonlib

import httpx

BASE_URL = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"

# 공공데이터포털 공통 에러코드(00~34)
ERROR_CODE_MESSAGES = {
    "00": "정상",
    "01": "APPLICATION_ERROR",
    "02": "DB_ERROR",
    "03": "NODATA_ERROR",
    "04": "HTTP_ERROR",
    "05": "SERVICETIMEOUT_ERROR",
    "10": "INVALID_REQUEST_PARAMETER_ERROR",
    "11": "NO_MANDATORY_REQUEST_PARAMETERS_ERROR",
    "12": "NO_OPENAPI_SERVICE_ERROR",
    "20": "SERVICE_ACCESS_DENIED_ERROR",
    "21": "TEMPORARILY_DISABLE_THE_SERVICEKEY_ERROR",
    "22": "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR",
    "30": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR",
    "31": "DEADLINE_HAS_EXPIRED_ERROR",
    "32": "UNREGISTERED_IP_ERROR",
    "33": "UNSIGNED_CALL_ERROR",
    "34": "TOO_MANY_REQUEST_ERROR",
}

_MISSING_STRINGS = {"-", ""}


def _safe_int(value):
    """결측(+900 이상/-900 이하, '-', None) -> None. 그 외 int 변환."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in _MISSING_STRINGS:
        return None
    try:
        num = int(float(value))
    except (TypeError, ValueError):
        return None
    if num >= 900 or num <= -900:
        return None
    return num


def _safe_float(value):
    """결측(+900 이상/-900 이하, '-', None) -> None. 그 외 float 변환."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in _MISSING_STRINGS:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num >= 900 or num <= -900:
        return None
    return num


class WeatherApiError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def _get_service_key():
    key = os.environ.get("WEATHER_FORECAST_SERVICE_KEY")
    if not key:
        raise WeatherApiError("NO_KEY", "WEATHER_FORECAST_SERVICE_KEY 환경변수가 설정되지 않았습니다.")
    return key


def _parse_xml_error(text):
    """XML 에러 응답에서 resultCode/resultMsg 추출. 못 찾으면 (None, None)."""
    code_match = re.search(r"<resultCode>\s*([^<]+)\s*</resultCode>", text)
    msg_match = re.search(r"<resultMsg>\s*([^<]+)\s*</resultMsg>", text)
    code = code_match.group(1).strip() if code_match else None
    msg = msg_match.group(1).strip() if msg_match else None
    return code, msg


def _request(endpoint, params):
    service_key = _get_service_key()
    query = dict(params)
    query["serviceKey"] = service_key
    query.setdefault("dataType", "JSON")
    query.setdefault("pageNo", 1)

    url = f"{BASE_URL}/{endpoint}"

    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url, params=query)

    try:
        data = resp.json()
    except (jsonlib.JSONDecodeError, ValueError):
        code, msg = _parse_xml_error(resp.text)
        if code is not None and code != "00":
            raise WeatherApiError(code, msg or ERROR_CODE_MESSAGES.get(code, "알 수 없는 오류"))
        raise WeatherApiError("PARSE_ERROR", f"응답을 JSON/XML로 해석할 수 없습니다: {resp.text[:200]}")

    header = data.get("response", {}).get("header", {})
    result_code = header.get("resultCode")
    result_msg = header.get("resultMsg")
    if result_code is not None and result_code != "00":
        raise WeatherApiError(result_code, result_msg or ERROR_CODE_MESSAGES.get(result_code, "알 수 없는 오류"))

    return data


def _extract_items(data):
    body = data.get("response", {}).get("body", {})
    items = body.get("items", {})
    if not items:
        return [], body.get("totalCount")
    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]
    return item_list, body.get("totalCount")


def get_ultra_srt_ncst(base_date, base_time, nx, ny, num_of_rows=10, page_no=1):
    """초단기실황조회(getUltraSrtNcst)."""
    params = {
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
    }
    data = _request("getUltraSrtNcst", params)
    items, total_count = _extract_items(data)
    return items, total_count


def get_ultra_srt_fcst(base_date, base_time, nx, ny, num_of_rows=60, page_no=1):
    """초단기예보조회(getUltraSrtFcst)."""
    params = {
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
    }
    data = _request("getUltraSrtFcst", params)
    items, total_count = _extract_items(data)
    return items, total_count


def get_vilage_fcst(base_date, base_time, nx, ny, num_of_rows=1000, page_no=1):
    """단기예보조회(getVilageFcst). 응답 항목이 많아 numOfRows 기본값을 1000으로 둔다(DEVPLAN 5-① 실측 근거)."""
    params = {
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
    }
    data = _request("getVilageFcst", params)
    items, total_count = _extract_items(data)
    return items, total_count


def get_fcst_version(ftype, base_datetime, num_of_rows=10, page_no=1):
    """예보버전조회(getFcstVersion)."""
    params = {
        "ftype": ftype,
        "basedatetime": base_datetime,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
    }
    data = _request("getFcstVersion", params)
    items, total_count = _extract_items(data)
    return items, total_count
