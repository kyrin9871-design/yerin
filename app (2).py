# -*- coding: utf-8 -*-
"""
지역별 공연 수요 트렌드 분석 대시보드 (v2 - 실제 KOPIS 데이터 반영)
=====================================================================
Streamlit Cloud 배포용 앱.

데이터 우선순위:
    1) 'kopis_region_monthly.csv' (data_collector.py로 직접 수집한 월별 실데이터) 있으면 최우선 사용
    2) real_kopis_data.py의 실제 연간 데이터(2021~2025, KOPIS 공식 보고서 기반) 사용 ← 기본값
       (2025년까지의 전국 지역별 공연건수/공연회차/티켓예매수/티켓판매액 실제 수치)

실행: streamlit run app.py
"""

import os
import pandas as pd
import streamlit as st
import plotly.express as px

from real_kopis_data import load_real_kopis_data

st.set_page_config(page_title="지역별 공연 수요 분석", layout="wide")

MONTHLY_CSV_PATH = "kopis_region_monthly.csv"

# 광역시도 대략적인 위경도 (지도 시각화용)
SIDO_COORDS = {
    "서울특별시": (37.5665, 126.9780), "부산광역시": (35.1796, 129.0756),
    "대구광역시": (35.8714, 128.6014), "인천광역시": (37.4563, 126.7052),
    "광주광역시": (35.1595, 126.8526), "대전광역시": (36.3504, 127.3845),
    "울산광역시": (35.5384, 129.3114), "세종": (36.4801, 127.2891),
    "경기도": (37.4138, 127.5183), "강원": (37.8228, 128.1555),
    "충청북도": (36.6357, 127.4917), "충청남도": (36.5184, 126.8000),
    "전북": (35.7175, 127.1530), "전남": (34.8161, 126.4629),
    "경상북도": (36.4919, 128.8889), "경상남도": (35.4606, 128.2132),
    "제주": (33.4996, 126.5312),
}
CAPITAL_REGION = ["서울특별시", "경기도", "인천광역시"]


@st.cache_data
def load_data():
    """
    반환값: (df, granularity, source_label)
    - granularity: 'monthly' | 'yearly'
    """
    if os.path.exists(MONTHLY_CSV_PATH):
        df = pd.read_csv(MONTHLY_CSV_PATH, encoding="utf-8-sig")
        return df, "monthly", "KOPIS API 직접 수집 데이터 (월별)"

    df = load_real_kopis_data()
    return df, "yearly", "KOPIS 공식 발행 「2025년 공연시장 티켓판매 현황 분석보고서」 기반 실제 데이터 (2021~2025, 연도별)"


df, granularity, source_label = load_data()

st.title("🎭 지역별 공연 수요 트렌드 분석")
st.caption("KOPIS(공연예술통합전산망) 데이터 기반 · 광역시도 단위 · 전체 장르")
st.info(f"📊 데이터 출처: {source_label}", icon="📊")

# ------------------------------------------------------------------
# 사이드바 필터
# ------------------------------------------------------------------
st.sidebar.header("필터")

time_col = "년월" if granularity == "monthly" else "연도"
all_periods = sorted(df[time_col].unique())
period_range = st.sidebar.select_slider(
    "기간 선택", options=all_periods, value=(all_periods[0], all_periods[-1])
)
selected_regions = st.sidebar.multiselect(
    "지역 선택 (비워두면 전체)", options=sorted(df["지역"].unique()), default=[]
)

metric_options = {
    "공연건수": "공연건수",
    "공연회차": "공연회차",
    "티켓예매수": "티켓예매수",
}
if "티켓판매액(천원)" in df.columns:
    metric_options["티켓판매액(천원)"] = "티켓판매액(천원)"
selected_metric = st.sidebar.selectbox("분석 지표", options=list(metric_options.keys()), index=0)

mask = (df[time_col] >= period_range[0]) & (df[time_col] <= period_range[1])
if selected_regions:
    mask &= df["지역"].isin(selected_regions)
fdf = df[mask].copy()

# ------------------------------------------------------------------
# 탭 구성
# ------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🗺️ 전국 개요", "📊 지역별 비교", "📈 추이 (연도별)"])

# ---- 탭 1: 전국 개요 (지도 + 요약 지표) ----
with tab1:
    st.subheader("전국 공연 현황 개요")

    total_by_region = fdf.groupby("지역", as_index=False)[selected_metric].sum()
    total_by_region["위도"] = total_by_region["지역"].map(lambda x: SIDO_COORDS.get(x, (36.5, 127.8))[0])
    total_by_region["경도"] = total_by_region["지역"].map(lambda x: SIDO_COORDS.get(x, (36.5, 127.8))[1])

    col1, col2, col3 = st.columns(3)
    total_val = total_by_region[selected_metric].sum()
    col1.metric(f"총 {selected_metric}", f"{int(total_val):,}")
    top_region = total_by_region.loc[total_by_region[selected_metric].idxmax(), "지역"]
    col2.metric(f"{selected_metric} 1위 지역", top_region)

    capital_sum = total_by_region[total_by_region["지역"].isin(CAPITAL_REGION)][selected_metric].sum()
    capital_share = (capital_sum / total_val * 100) if total_val > 0 else 0
    col3.metric("수도권 비중", f"{capital_share:.1f}%")

    fig_map = px.scatter_geo(
        total_by_region,
        lat="위도", lon="경도",
        size=selected_metric, color=selected_metric,
        hover_name="지역",
        scope="asia",
        projection="natural earth",
        color_continuous_scale="Sunset",
        title=f"지역별 {selected_metric} 분포",
    )
    fig_map.update_geos(
        center=dict(lat=36.5, lon=127.8),
        projection_scale=6,
        showland=True, landcolor="rgb(240,240,240)",
    )
    st.plotly_chart(fig_map, use_container_width=True)

# ---- 탭 2: 지역별 비교 ----
with tab2:
    st.subheader(f"지역별 {selected_metric} 비교")

    total_by_region_sorted = (
        fdf.groupby("지역", as_index=False)[selected_metric].sum()
        .sort_values(selected_metric, ascending=False)
    )
    fig_bar = px.bar(
        total_by_region_sorted, x="지역", y=selected_metric,
        color=selected_metric, color_continuous_scale="Blues",
        title=f"지역별 총 {selected_metric} (선택 기간 합계)",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("**수도권 vs 비수도권 비교**")
    fdf["권역"] = fdf["지역"].apply(lambda x: "수도권" if x in CAPITAL_REGION else "비수도권")
    region_group = fdf.groupby("권역", as_index=False)[selected_metric].sum()
    fig_pie = px.pie(region_group, names="권역", values=selected_metric, hole=0.4,
                      title=f"수도권 vs 비수도권 {selected_metric} 비중")
    st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("**지역별 상세 표**")
    st.dataframe(total_by_region_sorted.reset_index(drop=True), use_container_width=True)

# ---- 탭 3: 추이 ----
with tab3:
    st.subheader(f"{time_col}별 {selected_metric} 추이")

    trend = fdf.groupby([time_col, "지역"], as_index=False)[selected_metric].sum()
    fig_line = px.line(
        trend, x=time_col, y=selected_metric, color="지역", markers=True,
        title=f"지역별 {time_col}별 {selected_metric} 추이",
    )
    st.plotly_chart(fig_line, use_container_width=True)

    if granularity == "yearly":
        st.markdown("**전년 대비 증감률 (최신 연도)**")
        trend_sorted = trend.sort_values(["지역", time_col])
        trend_sorted["증감률(%)"] = (
            trend_sorted.groupby("지역")[selected_metric].pct_change() * 100
        ).round(1)
        latest = trend_sorted[trend_sorted[time_col] == trend_sorted[time_col].max()]
        latest = latest.dropna(subset=["증감률(%)"]).sort_values("증감률(%)", ascending=False)
        st.dataframe(
            latest[["지역", selected_metric, "증감률(%)"]].reset_index(drop=True),
            use_container_width=True,
        )

st.markdown("---")
st.caption("데이터 출처: KOPIS 공연예술통합전산망 (kopis.or.kr), (재)예술경영지원센터 「공연시장 티켓판매 현황 분석보고서」 · 학교 AI융합프로그램 프로젝트")
