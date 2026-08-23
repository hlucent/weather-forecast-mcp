"""1회성 변환 스크립트: 기상청 격자-위경도 엑셀(3,838행) -> area_codes.json

사용법:
    python scripts/convert_area_codes.py <엑셀경로> [출력경로]

출력 산출물(area_codes.json)만 배포에 포함하고, 이 스크립트와 원본 엑셀은 배포 대상이 아니다.
openpyxl은 이 스크립트 실행 시에만 필요하며 requirements.txt에는 포함하지 않는다.
"""
import json
import sys
from pathlib import Path

import openpyxl

# 원본 엑셀 컬럼(헤더는 mojibake로 보일 수 있으나 위치는 고정):
# 0=관리, 1=행정구역코드, 2=1단계, 3=2단계, 4=3단계, 5=격자 X, 6=격자 Y, ...


def convert(xlsx_path: str, out_path: str) -> None:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.worksheets[0]

    entries = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or row[1] is None:
            continue
        code, lvl1, lvl2, lvl3, nx, ny = row[1], row[2], row[3], row[4], row[5], row[6]
        if nx is None or ny is None:
            continue
        lvl1 = (lvl1 or "").strip()
        lvl2 = (lvl2 or "").strip()
        lvl3 = (lvl3 or "").strip()
        entries.append(
            {
                "code": str(code),
                "level1": lvl1,
                "level2": lvl2,
                "level3": lvl3,
                "nx": int(nx),
                "ny": int(ny),
            }
        )

    Path(out_path).write_text(
        json.dumps(entries, ensure_ascii=False, indent=None), encoding="utf-8"
    )
    print(f"변환 완료: {len(entries)}건 -> {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/convert_area_codes.py <엑셀경로> [출력경로]")
        sys.exit(1)
    xlsx = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "area_codes.json"
    convert(xlsx, out)
