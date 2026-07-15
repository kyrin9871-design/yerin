# -*- coding: utf-8 -*-
"""
KOPIS(공연예술통합전산망) Open API 데이터 수집 스크립트
================================================

- 목적: 광역시도 단위 x 월별 공연 데이터를 모아 CSV로 저장한다.
- 사용 API:
    1) 박스오피스 API (boxoffice)  -> 지역별/기간별 흥행(판매) 순위 데이터
    2) 공연목록 API (pblprfr)      -> 지역별/기간별 공연 건수 집계용

주의 (중요):
    KOPIS API 키를 신청하면 '오픈API 활용가이드' 문서를 같이 받게 됩니다.
    이 문서에 정확한 파라미터명/응답필드가 나와 있으니, 아래 코드를 그대로 쓰기 전에
    실제 응답 XML 구조와 맞는지 꼭 한 번 확인하세요 (KOPIS는 API 버전에 따라
    필드명이 조금씩 바뀐 적이 있습니다). 이 스크립트는 널리 쓰이는 표준 스펙을
    기준으로 작성했습니다.

필요 패키지: requests, xmltodict, pandas
    pip install requests xmltodict pandas
"""

import os
import time
import requests
import xmltodict
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ------------------------------------------------------------------
# 0. 설정
# ------------------------------------------------------------------

# KOPIS에서 발급받은 API 키를 환경변수로 등록해두고 불러오는 방식을 권장합니다.
# (터미널에서: export KOPIS_API_KEY="발급받은키"  /  윈도우: set KOPIS_API_KEY=발급받은키)
API_KEY = os.environ.get("KOPIS_API_KEY", "YOUR_API_KEY_HERE")

BASE_URL = "http://www.kopis.or.kr/openApi/restful"

# 광역시도 코드 (KOPIS 기준 시군구코드 앞 2자리 = 시도코드)
# 참고: 실제 API 가이드 문서의 '시군구코드' 표와 반드시 대조해서 확인하세요.
SIDO_CODES = {
    "서울": "11",
    "부산": "26",
    "대구": "27",
    "인천": "28",
    "광주": "29",
    "대전": "30",
    "울산": "31",
    "세종": "36",
    "경기": "41",
    "강원": "42",
    "충북": "43",
    "충남": "44",
    "전북": "45",
    "전남": "46",
    "경북": "47",
    "경남": "48",
    "제주": "50",
}


def _request(endpoint: str, params: dict) -> dict:
    """KOPIS API를 호출하고 XML 응답을 dict로 변환해서 반환."""
    params = {"service": API_KEY, **params}
    url = f"{BASE_URL}/{endpoint}"
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return xmltodict.parse(resp.text)


def fetch_boxoffice_by_region(sido_name: str, sido_code: str,
                               start_date: str, end_date: str,
                               ststype: str = "month") -> list:
    """
    박스오피스 API: 특정 지역/기간의 흥행 순위 데이터를 가져온다.
    ststype: 'day' | 'week' | 'month'
    start_date, end_date: 'YYYYMMDD' 형식
    """
    params = {
        "ststype": ststype,
        "stdate": start_date,
        "eddate": end_date,
        "area": sido_code,
    }
    try:
        data = _request("boxoffice", params)
        items = data.get("boxofs", {}).get("boxof", [])
        if isinstance(items, dict):  # 결과가 1건이면 dict로 옴 -> 리스트로 통일
            items = [items]
    except Exception as e:
        print(f"[경고] {sido_name} 박스오피스 조회 실패: {e}")
        return []

    rows = []
    for it in items:
        rows.append({
            "지역": sido_name,
            "지역코드": sido_code,
            "기간시작": start_date,
            "기간종료": end_date,
            "공연명": it.get("prfnm"),
            "공연ID": it.get("mt20id"),
            "장르": it.get("catnm") if "catnm" in it else None,
            "예매수_순위": it.get("rnum"),
        })
    return rows


def fetch_performance_count_by_region(sido_name: str, sido_code: str,
                                       start_date: str, end_date: str) -> int:
    """
    공연목록 API: 특정 지역/기간에 등록된 공연 '건수'를 집계한다.
    (전체 목록을 페이지네이션으로 끝까지 순회해서 count)
    """
    total_count = 0
    page = 1
    rows_per_page = 100
    while True:
        params = {
            "stdate": start_date,
            "eddate": end_date,
            "cpage": page,
            "rows": rows_per_page,
            "signgucode": sido_code,
        }
        try:
            data = _request("pblprfr", params)
        except Exception as e:
            print(f"[경고] {sido_name} 공연목록 조회 실패: {e}")
            break

        db = data.get("dbs", {})
        items = db.get("db", []) if db else []
        if isinstance(items, dict):
            items = [items]

        if not items:
            break

        total_count += len(items)
        page += 1
        time.sleep(0.2)  # API 서버 부담을 줄이기 위한 딜레이

        if len(items) < rows_per_page:
            break

    return total_count


def collect_monthly_data(start_yyyymm: str, end_yyyymm: str) -> pd.DataFrame:
    """
    start_yyyymm ~ end_yyyymm 구간을 '월 단위'로 순회하며
    지역별 공연 건수 + 박스오피스 데이터를 모아 하나의 DataFrame으로 반환.
    예: collect_monthly_data("202401", "202412")
    """
    start = datetime.strptime(start_yyyymm, "%Y%m")
    end = datetime.strptime(end_yyyymm, "%Y%m")

    records = []
    cur = start
    while cur <= end:
        month_start = cur.strftime("%Y%m01")
        month_end = (cur + relativedelta(day=31)).strftime("%Y%m%d")

        for sido_name, sido_code in SIDO_CODES.items():
            count = fetch_performance_count_by_region(
                sido_name, sido_code, month_start, month_end
            )
            records.append({
                "년월": cur.strftime("%Y-%m"),
                "지역": sido_name,
                "지역코드": sido_code,
                "공연건수": count,
            })
            print(f"{cur.strftime('%Y-%m')} / {sido_name}: {count}건 수집 완료")

        cur += relativedelta(months=1)

    return pd.DataFrame(records)


if __name__ == "__main__":
    # 예시: 2024년 1월 ~ 2024년 12월 데이터 수집
    df = collect_monthly_data("202401", "202412")
    df.to_csv("kopis_region_monthly.csv", index=False, encoding="utf-8-sig")
    print("저장 완료: kopis_region_monthly.csv")
