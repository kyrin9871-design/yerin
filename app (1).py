# -*- coding: utf-8 -*-
"""
지역별 공연 수요 트렌드 분석 대시보드
=====================================
Streamlit Cloud 배포용 앱.

실행 방법:
    streamlit run app.py

데이터 우선순위:
    1) data_collector.py로 만든 'kopis_region_monthly.csv'가 있으면 그걸 사용
    2) 없으면 데모용 샘플 데이터를 자동 생성해서 보여줌
       (실제 KOPIS API 키를 받기 전에도 화면 구성/기능을 미리 확인할 수 있음)
"""

import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="지역별 공연 수요 분석", layout="wide")

CSV_PATH = "kopis_region_monthly.csv"

# 광역시도 대략적인 위경도 (지도 시각화용)
SIDO_COORDS = {
    "서울": (37.5665, 126.9780), "부산": (35.1796, 129.0756),
    "대구": (35.8714, 128.6014), "인천": (37.4563, 126.7052),
    "광주": (35.1595, 126.8526), "대전": (36.3504, 127.3845),
    "울산": (35.5384, 129.3114), "세종": (36.4801, 127.2891),
    "경기": (37.4138, 127.5183), "강원": (37.8228, 128.1555),
    "충북": (36.6357, 127.4917), "충남": (36.5184, 126.8000),
    "전북": (35.7175, 127.1530), "전남": (34.8161, 126.4629),
    "경북": (36.4919, 128.8889), "경남": (35.4606, 128.2132),
    "제주": (33.4996, 126.5312),
}


@st.cache_data
def load_data() -> pd.DataFrame:
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
        df["데이터출처"] = "KOPIS 실제 데이터"
        return df

    # ---- 데모용 샘플 데이터 생성 (실제 API 연결 전 화면 확인용) ----
    rng = np.random.default_rng(42)
    months = pd.date_range("2024-01-01", "2024-12-01", freq="MS").strftime("%Y-%m")
    base_scale = {  # 지역별 대략적인 공연 규모 가중치 (수도권 > 광역시 > 기타)
        "서울": 12, "경기": 6, "부산": 4, "인천": 3, "대구": 3,
        "대전": 2.5, "광주": 2.3, "울산": 1.8, "경남": 2, "경북": 1.8,
        "충남": 1.7, "충북": 1.5, "전남": 1.5, "전북": 1.5,
        "강원": 1.6, "제주": 1.4, "세종": 1.0,
    }
    records = []
    for m in months:
        for sido, scale in base_scale.items():
            count = max(1, int(rng.normal(loc=scale * 15, scale=scale * 3)))
            records.append({"년월": m, "지역": sido, "지역코드": "", "공연건수": count})
    df = pd.DataFrame(records)
    df["데이터출처"] = "샘플(데모) 데이터 — 실제 KOPIS 데이터 아님"
    return df


df = load_data()
is_demo = "샘플" in df["데이터출처"].iloc[0]

# ------------------------------------------------------------------
# 헤더
# ------------------------------------------------------------------
st.title("🎭 지역별 공연 수요 트렌드 분석")
st.caption("KOPIS(공연예술통합전산망) 데이터 기반 · 광역시도 단위 · 전체 장르")

if is_demo:
    st.warning(
        "⚠️ 현재 화면은 **샘플(데모) 데이터**로 채워져 있습니다. "
        "`data_collector.py`로 실제 KOPIS 데이터를 수집해서 "
        "`kopis_region_monthly.csv` 파일로 저장하면 자동으로 실제 데이터가 표시됩니다."
    )

# ------------------------------------------------------------------
# 사이드바 필터
# ------------------------------------------------------------------
st.sidebar.header("필터")
all_months = sorted(df["년월"].unique())
month_range = st.sidebar.select_slider(
    "기간 선택", options=all_months, value=(all_months[0], all_months[-1])
)
selected_regions = st.sidebar.multiselect(
    "지역 선택 (비워두면 전체)", options=sorted(df["지역"].unique()), default=[]
)

mask = (df["년월"] >= month_range[0]) & (df["년월"] <= month_range[1])
if selected_regions:
    mask &= df["지역"].isin(selected_regions)
fdf = df[mask].copy()

# ------------------------------------------------------------------
# 탭 구성
# ------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🗺️ 전국 개요", "📊 지역별 비교", "📈 시계열 추이"])

# ---- 탭 1: 전국 개요 (지도 + 요약 지표) ----
with tab1:
    st.subheader("전국 공연 현황 개요")

    total_by_region = fdf.groupby("지역", as_index=False)["공연건수"].sum()
    total_by_region["위도"] = total_by_region["지역"].map(lambda x: SIDO_COORDS.get(x, (36.5, 127.8))[0])
    total_by_region["경도"] = total_by_region["지역"].map(lambda x: SIDO_COORDS.get(x, (36.5, 127.8))[1])

    col1, col2, col3 = st.columns(3)
    col1.metric("총 공연건수", f"{int(total_by_region['공연건수'].sum()):,}건")
    top_region = total_by_region.loc[total_by_region["공연건수"].idxmax(), "지역"]
    col2.metric("공연이 가장 많은 지역", top_region)
    col3.metric("분석 대상 지역 수", f"{total_by_region['지역'].nunique()}개")

    fig_map = px.scatter_geo(
        total_by_region,
        lat="위도", lon="경도",
        size="공연건수", color="공연건수",
        hover_name="지역",
        scope="asia",
        projection="natural earth",
        color_continuous_scale="Sunset",
        title="지역별 공연건수 분포",
    )
    fig_map.update_geos(
        center=dict(lat=36.5, lon=127.8),
        projection_scale=6,
        showland=True, landcolor="rgb(240,240,240)",
    )
    st.plotly_chart(fig_map, use_container_width=True)

# ---- 탭 2: 지역별 비교 ----
with tab2:
    st.subheader("지역별 공연건수 비교")

    total_by_region_sorted = (
        fdf.groupby("지역", as_index=False)["공연건수"].sum()
        .sort_values("공연건수", ascending=False)
    )
    fig_bar = px.bar(
        total_by_region_sorted, x="지역", y="공연건수",
        color="공연건수", color_continuous_scale="Blues",
        title="지역별 총 공연건수 (선택 기간 합계)",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("**수도권 vs 비수도권 비교**")
    capital = ["서울", "경기", "인천"]
    fdf["권역"] = fdf["지역"].apply(lambda x: "수도권" if x in capital else "비수도권")
    region_group = fdf.groupby("권역", as_index=False)["공연건수"].sum()
    fig_pie = px.pie(region_group, names="권역", values="공연건수", hole=0.4,
                      title="수도권 vs 비수도권 공연건수 비중")
    st.plotly_chart(fig_pie, use_container_width=True)

# ---- 탭 3: 시계열 추이 ----
with tab3:
    st.subheader("월별 공연건수 추이 및 증감률")

    monthly = fdf.groupby(["년월", "지역"], as_index=False)["공연건수"].sum()
    fig_line = px.line(
        monthly, x="년월", y="공연건수", color="지역", markers=True,
        title="지역별 월간 공연건수 추이",
    )
    st.plotly_chart(fig_line, use_container_width=True)

    st.markdown("**전월 대비 증감률**")
    monthly_sorted = monthly.sort_values(["지역", "년월"])
    monthly_sorted["증감률(%)"] = (
        monthly_sorted.groupby("지역")["공연건수"].pct_change() * 100
    ).round(1)
    latest_month = monthly_sorted["년월"].max()
    latest = monthly_sorted[monthly_sorted["년월"] == latest_month].dropna(subset=["증감률(%)"])
    latest = latest.sort_values("증감률(%)", ascending=False)
    st.dataframe(
        latest[["지역", "공연건수", "증감률(%)"]].reset_index(drop=True),
        use_container_width=True,
    )

st.markdown("---")
st.caption("데이터 출처: KOPIS 공연예술통합전산망 (kopis.or.kr) · 학교 AI융합프로그램 프로젝트")
