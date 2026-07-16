# -*- coding: utf-8 -*-
"""
서울특별시 종로구 공공시설 태양광 설치현황 분석 대시보드
------------------------------------------------------
실행 방법:
    1) pip install streamlit plotly pandas
    2) 이 파일과 CSV를 같은 폴더에 두고
    3) streamlit run solar_dashboard.py
"""

import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ──────────────────────────────────────────────
# 기본 설정
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="종로구 공공시설 태양광 설치현황",
    page_icon="☀️",
    layout="wide",
)

CSV_FILE = "서울특별시_종로구_공공시설_태양광_설치현황_20210423.csv"

# 브랜드 컬러 (태양광 테마: 옐로우~그린 계열)
COLOR_SEQ = ["#F6C445", "#F39C12", "#27AE60", "#2E86C1",
             "#8E44AD", "#E74C3C", "#16A085", "#D35400"]


# ──────────────────────────────────────────────
# 데이터 로드 & 전처리
# ──────────────────────────────────────────────
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8")
    df.columns = [c.strip() for c in df.columns]

    cap_col = "설치용량(킬로와트)"
    df[cap_col] = pd.to_numeric(df[cap_col], errors="coerce")
    df["설치년도"] = pd.to_numeric(df["설치년도"], errors="coerce").astype("Int64")

    df["시설유형"] = df["시설명"].apply(classify_facility)
    df["행정동"] = df["도로명 주소"].apply(extract_dong)
    return df


def classify_facility(name: str) -> str:
    """시설명 키워드로 유형을 분류한다."""
    n = str(name)
    if any(k in n for k in ["어린이집", "육아"]):
        return "보육시설"
    if any(k in n for k in ["복지관", "복지센터", "경로당", "노인", "재활"]):
        return "복지시설"
    if "주차" in n:
        return "주차시설"
    if any(k in n for k in ["화장실", "공원"]):
        return "공원·화장실"
    if any(k in n for k in ["구민회관", "문화체육", "체육"]):
        return "문화체육시설"
    return "행정·기타시설"


def extract_dong(addr: str) -> str:
    """도로명 주소에서 괄호 안 법정동 또는 '종로구 XX동' 패턴을 추출한다."""
    a = str(addr)
    m = re.search(r"[(（]([^)）]*?동)[)）]", a)
    if m:
        return m.group(1)
    m = re.search(r"종로구\s*([가-힣0-9]+동)", a)
    if m:
        return m.group(1)
    return "기타"


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────
df = load_data(CSV_FILE)
CAP = "설치용량(킬로와트)"

st.title("☀️ 서울특별시 종로구 공공시설 태양광 설치현황")
st.caption("데이터 기준일자: 2021-04-23 · 출처: 공공데이터")

# ── 사이드바: 필터 & 추정 가정 ──
with st.sidebar:
    st.header("🔎 필터")
    types = st.multiselect(
        "시설유형",
        options=sorted(df["시설유형"].unique()),
        default=sorted(df["시설유형"].unique()),
    )
    yr_min, yr_max = int(df["설치년도"].min()), int(df["설치년도"].max())
    yr_range = st.slider("설치년도", yr_min, yr_max, (yr_min, yr_max))

    st.divider()
    st.header("⚙️ 발전량 추정 가정")
    st.caption("실제 발전량이 아닌 추정치입니다.")
    daily_hours = st.slider("일 평균 발전시간 (h)", 3.0, 4.5, 3.5, 0.1)
    co2_factor = st.number_input(
        "전력 배출계수 (kgCO₂/kWh)", value=0.4594, step=0.01, format="%.4f"
    )

# ── 필터 적용 ──
mask = (
    df["시설유형"].isin(types)
    & df["설치년도"].between(yr_range[0], yr_range[1])
)
fdf = df[mask].copy()

if fdf.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# ── 파생 지표 ──
total_cap = fdf[CAP].sum()
annual_gen = total_cap * daily_hours * 365          # kWh/년 (추정)
co2_saved = annual_gen * co2_factor / 1000          # tCO₂/년 (추정)

# ── KPI 카드 ──
c1, c2, c3, c4 = st.columns(4)
c1.metric("총 시설 수", f"{len(fdf):,}개")
c2.metric("총 설치용량", f"{total_cap:,.1f} kW")
c3.metric("연간 추정 발전량", f"{annual_gen:,.0f} kWh")
c4.metric("연간 CO₂ 저감(추정)", f"{co2_saved:,.1f} tCO₂")

st.divider()

# ──────────────────────────────────────────────
# 1행: 시설유형별 + 연도별
# ──────────────────────────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("시설유형별 설치용량")
    g = (
        fdf.groupby("시설유형")
        .agg(총용량=(CAP, "sum"), 건수=("시설명", "count"))
        .reset_index()
        .sort_values("총용량", ascending=True)
    )
    fig = px.bar(
        g, x="총용량", y="시설유형", orientation="h",
        text="총용량", color="시설유형",
        color_discrete_sequence=COLOR_SEQ,
        hover_data={"건수": True},
    )
    fig.update_traces(texttemplate="%{text:.1f} kW", textposition="outside")
    fig.update_layout(showlegend=False, height=380,
                      xaxis_title="설치용량 합계 (kW)", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.subheader("연도별 설치 추이")
    y = (
        fdf.groupby("설치년도")
        .agg(용량=(CAP, "sum"), 건수=("시설명", "count"))
        .reset_index()
    )
    fig = go.Figure()
    fig.add_bar(x=y["설치년도"], y=y["용량"], name="설치용량(kW)",
                marker_color="#F39C12", yaxis="y1")
    fig.add_trace(go.Scatter(
        x=y["설치년도"], y=y["건수"], name="설치 건수",
        mode="lines+markers", line=dict(color="#27AE60", width=3),
        yaxis="y2",
    ))
    fig.update_layout(
        height=380,
        xaxis=dict(title="설치년도", dtick=1),
        yaxis=dict(title="설치용량 (kW)"),
        yaxis2=dict(title="건수", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=1.12, x=0),
    )
    st.plotly_chart(fig, use_container_width=True)

# ──────────────────────────────────────────────
# 2행: 유형 비중 + 용량 분포
# ──────────────────────────────────────────────
col_c, col_d = st.columns(2)

with col_c:
    st.subheader("시설유형별 용량 비중")
    fig = px.pie(
        g, names="시설유형", values="총용량", hole=0.45,
        color_discrete_sequence=COLOR_SEQ,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=380, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col_d:
    st.subheader("시설별 설치용량 분포")
    fig = px.box(
        fdf, x="시설유형", y=CAP, points="all",
        color="시설유형", color_discrete_sequence=COLOR_SEQ,
        hover_name="시설명",
    )
    fig.update_layout(height=380, showlegend=False,
                      xaxis_title="", yaxis_title="설치용량 (kW)")
    st.plotly_chart(fig, use_container_width=True)

# ──────────────────────────────────────────────
# 3행: 시설별 순위 (전체)
# ──────────────────────────────────────────────
st.subheader("시설별 설치용량 순위")
rank = fdf.sort_values(CAP, ascending=True)
fig = px.bar(
    rank, x=CAP, y="시설명", orientation="h",
    color="시설유형", color_discrete_sequence=COLOR_SEQ,
    text=CAP,
)
fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
fig.update_layout(height=max(400, 22 * len(rank)),
                  xaxis_title="설치용량 (kW)", yaxis_title="",
                  legend_title="시설유형")
st.plotly_chart(fig, use_container_width=True)

# ──────────────────────────────────────────────
# 원본 데이터 & 다운로드
# ──────────────────────────────────────────────
with st.expander("📋 원본 데이터 보기"):
    st.dataframe(
        fdf[["시설명", "시설유형", "행정동", CAP, "발전유형", "설치년도"]]
        .sort_values(CAP, ascending=False),
        use_container_width=True, hide_index=True,
    )
    st.download_button(
        "필터링된 데이터 CSV 다운로드",
        fdf.to_csv(index=False).encode("utf-8-sig"),
        file_name="종로구_태양광_필터결과.csv",
        mime="text/csv",
    )

# ──────────────────────────────────────────────
# 자동 인사이트
# ──────────────────────────────────────────────
st.divider()
st.subheader("💡 핵심 인사이트")

top = fdf.loc[fdf[CAP].idxmax()]
top_type = g.iloc[-1]
peak_year = y.loc[y["용량"].idxmax()]

st.markdown(
    f"""
- **총 {len(fdf)}개 시설, {total_cap:.1f}kW**가 설치되어 있으며, 발전유형은 전부 **태양광**입니다.
- 시설유형 중 **{top_type['시설유형']}**의 설치용량이 **{top_type['총용량']:.1f}kW**로 가장 큽니다.
- 단일 시설 최대 용량은 **{top['시설명']}({top[CAP]:.1f}kW)** 입니다.
- 설치용량이 가장 많았던 해는 **{int(peak_year['설치년도'])}년({peak_year['용량']:.1f}kW)** 입니다.
- 위 가정(일 {daily_hours}시간 발전) 기준 연간 약 **{annual_gen:,.0f}kWh**를 생산해
  약 **{co2_saved:.1f}톤**의 CO₂를 저감하는 것으로 추정됩니다.
"""
)
