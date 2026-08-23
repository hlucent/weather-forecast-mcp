"""기상청 단기예보 조회서비스 코드값 매핑 상수."""

SKY_CODE = {
    "1": "맑음",
    "3": "구름많음",
    "4": "흐림",
}

# 초단기실황/초단기예보 PTY (0~7)
PTY_CODE_ULTRA = {
    "0": "없음",
    "1": "비",
    "2": "비/눈",
    "3": "눈",
    "4": "소나기",
    "5": "빗방울",
    "6": "빗방울눈날림",
    "7": "눈날림",
}

# 단기예보 PTY (0~4)
PTY_CODE_SHRT = {
    "0": "없음",
    "1": "비",
    "2": "비/눈",
    "3": "눈",
    "4": "소나기",
}

# 연장기간(+4~5일) 정성정보 코드 — PCP/SNO/WSD 공통 체계, 2-3절 코드값과 별개
EXTENDED_QUALITATIVE_CODE = {
    "1": "적음",
    "2": "보통",
    "3": "많음",
}

WIND_DIRECTIONS_16 = [
    "북", "북북동", "북동", "동북동",
    "동", "동남동", "남동", "남남동",
    "남", "남남서", "남서", "서남서",
    "서", "서북서", "북서", "북북서",
]


def vec_to_direction(vec):
    """풍향(VEC, 도) -> 16방위 한글 문자열. vec이 None이면 None 반환."""
    if vec is None:
        return None
    idx = int((vec + 22.5 * 0.5) / 22.5) % 16
    return WIND_DIRECTIONS_16[idx]


def sky_to_text(code):
    if code is None:
        return None
    return SKY_CODE.get(str(code), f"알수없음({code})")


def pty_ultra_to_text(code):
    if code is None:
        return None
    return PTY_CODE_ULTRA.get(str(code), f"알수없음({code})")


def pty_shrt_to_text(code):
    if code is None:
        return None
    return PTY_CODE_SHRT.get(str(code), f"알수없음({code})")


def extended_qualitative_to_text(code):
    if code is None:
        return None
    return EXTENDED_QUALITATIVE_CODE.get(str(code), f"알수없음({code})")
