import streamlit as st
import feedparser
import google.generativeai as genai
import json
import ssl
import urllib.parse
import requests
from datetime import datetime

# 1. 시스템 설정
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

st.set_page_config(page_title="가림 랩 | 시각화 분석 포털", layout="wide")

# 2. 디자인 (고대비 & 시각화 요소 추가)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@700&family=Noto+Serif+KR:wght@400;700&display=swap');
    .stApp { background-color: #f8f5f0; }
    html, body, [data-testid="stWidgetLabel"], .stMarkdown p { color: #1a1a1a !important; }
    .main-header { text-align: center; border-bottom: 3px solid #000; padding: 15px 0; margin-bottom: 20px; }
    .main-header h1 { font-family: 'Nanum Myeongjo', serif; font-size: 2.5rem; }
    .news-card { background: white; padding: 15px; border: 2px solid #333; margin-bottom: 10px; border-radius: 5px; }
    .report-container { background: white; padding: 25px; border: 3px solid #000; font-family: 'Noto Serif KR', serif; }
    .fact-check-card { background: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 5px; border-left: 5px solid #007bff; }
    .metric-label { font-size: 0.9rem; font-weight: bold; color: #555; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #000; }
    </style>
    """, unsafe_allow_html=True)

# 3. 데이터 초기화
if 'categorized_posts' not in st.session_state: 
    st.session_state.categorized_posts = {"정치": [], "경제": [], "사회": []}
if 'user_rank' not in st.session_state: 
    st.session_state.user_rank = {"가림마스터": 150, "경제탐정": 120}

# 4. 기능 함수들
@st.cache_data(ttl=300)
def get_news_stable(category):
    query = urllib.parse.quote(category)
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        feed = feedparser.parse(resp.content)
        return [{"title": e.title, "source": e.source.title, "link": e.link} for e in feed.entries[:6]]
    except: return []

def analyze_with_ai(title, source, api_key):
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_model = next((m for m in models if "1.5-flash" in m), models[0])
        model = genai.GenerativeModel(target_model)
        
        # 한국어 답변 및 상세 분석을 위한 프롬프트 강화
        prompt = f"""
        뉴스 제목: {title}
        언론사: {source}
        
        위 뉴스를 분석하여 다음 JSON 형식으로 한국어로 답변하세요. 
        'bias_score'는 0(진보)에서 100(보수) 사이의 숫자입니다. 50은 중립입니다.
        'reporter_reliability'는 기자의 과거 이력이나 문체를 고려한 가상의 신뢰도 점수(0~100)입니다.
        'fact_checks'는 기사 내용 중 팩트체크가 필요한 항목들을 리스트로 만들고 관련 근거 링크(실제 혹은 권장 검색어)를 포함하세요.

        {{
            "bias_label": "진보/보수/중도 등",
            "bias_score": 50,
            "overall_score": 85,
            "reporter_reliability": 75,
            "analysis_summary": "기사의 핵심 비평 요약",
            "fact_checks": [
                {{"point": "팩트체크 항목 1", "status": "참/거짓/판단유보", "reference_link": "관련 근거 링크 또는 검색 키워드"}},
                {{"point": "팩트체크 항목 2", "status": "참/거짓/판단유보", "reference_link": "관련 근거 링크 또는 검색 키워드"}}
            ],
            "impact": "생활에 미치는 영향"
        }}
        """
        response = model.generate_content(prompt)
        return json.loads(response.text.strip().replace('```json', '').replace('```', ''))
    except Exception as e: return str(e)

# 5. 메인 레이아웃
st.markdown('<div class="main-header"><h1>가 림 랩 (GARIM LAB)</h1><p><b>팩트체크 & 시각화 정밀 분석 시스템</b></p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.title("⚙️ 설정")
    api_key_input = st.text_input("Gemini API Key", type="password")
    if api_key_input:
        st.success("API 연결됨")

col_news, col_report, col_comm = st.columns([1, 1.2, 0.8])

# --- [컬럼 1: 뉴스 목록] ---
with col_news:
    st.subheader("📰 뉴스 섹션")
    main_cat = st.radio("분야", ["정치", "경제", "사회"], horizontal=True)
    news_list = get_news_stable(main_cat)
    if news_list:
        for i, news in enumerate(news_list):
            with st.container():
                st.markdown(f'<div class="news-card"><b>{news["title"]}</b><br><small>{news["source"]}</small></div>', unsafe_allow_html=True)
                if st.button(f"🔍 정밀 분석하기", key=f"n_{i}"):
                    if api_key_input:
                        with st.spinner('가림 AI가 정밀 분석 중...'):
                            st.session_state.analysis_res = analyze_with_ai(news['title'], news['source'], api_key_input)
                            st.session_state.analysis_title = news['title']
                    else: st.error("사이드바에 API 키를 입력하세요.")

# --- [컬럼 2: 시각화 리포트] ---
with col_report:
    st.subheader("⚖️ 가림 AI 정밀 리포트")
    if 'analysis_res' in st.session_state:
        res = st.session_state.analysis_res
        if isinstance(res, dict):
            st.markdown(f"""<div class="report-container"><h4>{st.session_state.analysis_title}</h4><hr>""", unsafe_allow_html=True)
            
            # 상단 지표 (기사 신뢰도, 기자 신뢰도)
            m1, m2 = st.columns(2)
            with m1:
                st.markdown(f'<p class="metric-label">기사 종합 점수</p><p class="metric-value">{res["overall_score"]}점</p>', unsafe_allow_html=True)
                st.progress(res["overall_score"] / 100)
            with m2:
                st.markdown(f'<p class="metric-label">기자 신뢰도 점수</p><p class="metric-value">{res["reporter_reliability"]}점</p>', unsafe_allow_html=True)
                st.progress(res["reporter_reliability"] / 100)
            
            st.divider()

            # 정치적 편향성 게이지 시각화
            st.markdown(f"**정치적 성향: {res['bias_label']}**")
            # 0(진보) ~ 100(보수) 게이지
            bias_val = res['bias_score']
            st.markdown(f"""
                <div style="width:100%; background-color:#ddd; height:20px; border-radius:10px;">
                    <div style="width:{bias_val}%; background-color:{'#007bff' if bias_val < 45 else '#dc3545' if bias_val > 55 else '#6c757d'}; 
                    height:20px; border-radius:10px; text-align:right; padding-right:5px; color:white; font-size:12px;">{bias_val}%</div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:0.8rem; margin-top:5px;">
                    <span>← 진보적</span><span>중도</span><span>보수적 →</span>
                </div>
            """, unsafe_allow_html=True)

            # 비평 요약
            st.markdown(f"**AI 비평:** {res['analysis_summary']}")
            
            # 팩트체크 섹션 (리스트화)
            st.markdown("---")
            st.markdown("🕵️ **핵심 팩트체크**")
            for fc in res['fact_checks']:
                st.markdown(f"""
                <div class="fact-check-card">
                    <b>• {fc['point']}</b><br>
                    결과: <span style="color:#007bff;">{fc['status']}</span><br>
                    <a href="{fc['reference_link']}" target="_blank" style="font-size:12px;">[근거 자료 확인]</a>
                </div>
                """, unsafe_allow_html=True)
            
            st.info(f"💼 **생활 영향:** {res['impact']}")
            st.markdown("</div>", unsafe_allow_html=True)
        else: st.error(f"분석 중 오류 발생: {res}")
    else: st.info("왼쪽에서 기사를 선택해 분석을 시작하세요.")

# --- [컬럼 3: 랭킹 및 게시판] ---
with col_comm:
    st.subheader("🏆 명예의 전당")
    sorted_rank = sorted(st.session_state.user_rank.items(), key=lambda x: x[1], reverse=True)
    for i, (name, score) in enumerate(sorted_rank[:3]):
        st.markdown(f"**{['🥇','🥈','🥉'][i]} {name}** ({score} pts)")
    
    st.divider()
    st.subheader("💬 분야별 게시판")
    board_tab = st.selectbox("게시판 선택", ["정치 토론장", "국내/미국 주식", "부동산/재테크"])
    # (게시판 글쓰기 및 출력 코드는 이전 버전과 동일하게 유지하거나 간소화)
    st.caption("커뮤니티 기능을 통해 의견을 나눠보세요.")
