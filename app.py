import streamlit as st
import feedparser
import google.generativeai as genai
import json
import ssl
import urllib.parse
import requests
from datetime import datetime

# 1. 시스템 설정 (맥북 SSL 및 뉴스 연결 에러 방지)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

st.set_page_config(page_title="가림 랩 | 전문 커뮤니티 & 랭킹", layout="wide")

# 2. 디자인 (시독성 극대화 및 모바일 최적화 CSS)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@700&family=Noto+Serif+KR:wght@400;700&display=swap');
    
    /* 배경 및 기본 텍스트 설정 */
    .stApp { background-color: #f8f5f0; }
    html, body, [data-testid="stWidgetLabel"], .stMarkdown p {
        color: #1a1a1a !important;
    }

    /* 메인 헤더 */
    .main-header { 
        text-align: center; 
        border-bottom: 3px solid #000; 
        padding: 15px 0; 
        margin-bottom: 20px; 
    }
    .main-header h1 { color: #000 !important; font-family: 'Nanum Myeongjo', serif; font-size: 2.5rem; }

    /* 뉴스 카드 */
    .news-card { 
        background: white; 
        padding: 15px; 
        border: 2px solid #333; 
        margin-bottom: 10px; 
        border-radius: 5px; 
    }
    .news-card b { color: #000 !important; font-size: 1.1rem; }
    .news-card small { color: #444 !important; font-weight: 600; }

    /* AI 분석 박스 */
    .analysis-box { 
        background: white; 
        padding: 20px; 
        border: 3px solid #000; 
        font-family: 'Noto Serif KR', serif;
        color: #000 !important;
        line-height: 1.6;
    }
    .analysis-box p, .analysis-box h4 { color: #000 !important; }
    .impact-box { 
        background: #f0f0f0; 
        border-left: 5px solid #000; 
        color: #111 !important;
        padding: 10px;
        margin-top: 10px;
    }

    /* 게시판 카드 */
    .board-card { 
        background: #fff; 
        padding: 12px; 
        border: 1px solid #000; 
        margin-bottom: 8px; 
        color: #000 !important;
        border-radius: 5px;
    }
    .board-card b { color: #b22222 !important; }
    .board-card small { color: #333 !important; font-weight: bold; }

    /* 유저 랭킹 박스 */
    .ranking-box { 
        background: #1a1a1a; 
        color: #ffffff !important; 
        padding: 15px; 
        border-radius: 10px; 
        margin-top: 20px; 
    }
    .ranking-box b, .ranking-box span { color: #ffffff !important; }
    .rank-item { 
        display: flex; 
        justify-content: space-between; 
        border-bottom: 1px solid #444; 
        padding: 8px 0; 
    }

    /* 사이드바 설정 */
    [data-testid="stSidebar"] { background-color: #efede8; }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #000 !important;
    }

    /* 📱 모바일 최적화 (화면 너비 768px 이하) */
    @media only screen and (max-width: 768px) {
        .main-header h1 { font-size: 1.8rem; }
        .news-card b { font-size: 1.2rem; }
        .stButton button { width: 100%; height: 3.5rem; font-size: 1.1rem; border: 2px solid #000; }
        .analysis-box { font-size: 1.1rem; }
    }
    </style>
    """, unsafe_allow_html=True)

# 3. 데이터 초기화 (세션 상태 유지)
if 'saved_articles' not in st.session_state: st.session_state.saved_articles = []
if 'votes' not in st.session_state: st.session_state.votes = {}
if 'categorized_posts' not in st.session_state: 
    st.session_state.categorized_posts = {"정치": [], "경제": [], "사회": []}
if 'user_rank' not in st.session_state: 
    st.session_state.user_rank = {"가림마스터": 150, "경제탐정": 120, "법률왕": 90}

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
        # 사용 가능한 모델 자동 탐색 (404 방지)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_model = next((m for m in models if "1.5-flash" in m), models[0])
        model = genai.GenerativeModel(target_model)
        prompt = f"뉴스 '{title}'({source}) 분석. JSON만 답변: {{'bias':'...','score':85,'reason':'...','impact':'...'}}"
        response = model.generate_content(prompt)
        res_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(res_text), target_model
    except Exception as e: return str(e), None

# 5. 메인 레이아웃 (3컬럼)
st.markdown('<div class="main-header"><h1>가 림 랩 (GARIM LAB)</h1><p><b>분야별 전문 게시판 & AI 정밀 분석</b></p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.title("⚙️ 마이 페이지")
    api_key_input = st.text_input("Gemini API Key", type="password")
    if api_key_input:
        try:
            genai.configure(api_key=api_key_input); genai.list_models()
            st.markdown('<p style="color:green; font-weight:bold;">✅ API 연결 활성화됨</p>', unsafe_allow_html=True)
            st.session_state.api_ready = True
        except:
            st.markdown('<p style="color:red; font-weight:bold;">❌ API 키 확인 필요</p>', unsafe_allow_html=True)
            st.session_state.api_ready = False
    
    st.divider()
    st.subheader("🔖 스크랩 보관함")
    if not st.session_state.saved_articles: st.write("저장된 기사가 없습니다.")
    else:
        for idx, item in enumerate(st.session_state.saved_articles):
            st.caption(f"• {item['title'][:20]}...")

col_news, col_report, col_comm = st.columns([1, 1, 1.2])

# --- [컬럼 1: 뉴스 목록] ---
with col_news:
    st.subheader("📰 실시간 섹션")
    main_cat = st.radio("분야", ["정치", "경제", "사회"], horizontal=True)
    news_list = get_news_stable(main_cat)
    if news_list:
        for i, news in enumerate(news_list):
            with st.container():
                st.markdown(f'<div class="news-card"><b>{news["title"]}</b><br><small>{news["source"]}</small></div>', unsafe_allow_html=True)
                if st.button(f"🔍 분석하기", key=f"n_{i}"):
                    if api_key_input and st.session_state.get('api_ready'):
                        with st.spinner('분석 중...'):
                            res, _ = analyze_with_ai(news['title'], news['source'], api_key_input)
                            if res:
                                st.session_state.analysis_res = res
                                st.session_state.analysis_title = news['title']
                    else: st.error("API 키를 확인해 주세요.")

# --- [컬럼 2: AI 정밀 리포트] ---
with col_report:
    st.subheader("⚖️ 가림 리포트")
    if 'analysis_res' in st.session_state:
        res = st.session_state.analysis_res
        title = st.session_state.analysis_title
        if title not in st.session_state.votes: st.session_state.votes[title] = {"up": 0, "down": 0}
        
        st.markdown(f"""
            <div class="analysis-box">
                <h4 style="margin:0;">{title}</h4>
                <hr style="border:1px solid #000;">
                <p><b>신뢰도: {res['score']}% | 성향: {res['bias']}</b></p>
                <p>{res['reason']}</p>
                <div class="impact-box">
                    <b>💼 실무/생활 영향:</b><br>{res['impact']}
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔖 이 리포트 스크랩"):
            st.session_state.saved_articles.append({"title": title})
            st.toast("보관함에 저장되었습니다!")
    else: st.info("왼쪽에서 기사를 선택해 주세요.")

# --- [컬럼 3: 분야별 게시판 & 랭킹] ---
with col_comm:
    st.subheader("👥 커뮤니티")
    board_tab = st.selectbox("게시판 이동", ["정치 토론장", "국내 주식", "미국 주식", "부동산/재테크", "법률/세금 상담"])
    
    with st.expander("✍️ 의견 나누기 (포인트 +10)", expanded=False):
        with st.form("post_form", clear_on_submit=True):
            u_name = st.text_input("닉네임")
            u_content = st.text_area("내용")
            if st.form_submit_button("등록"):
                if u_name and u_content:
                    st.session_state.user_rank[u_name] = st.session_state.user_rank.get(u_name, 0) + 10
                    cat_key = "경제" if "주식" in board_tab or "부동산" in board_tab else "정치" if "정치" in board_tab else "사회"
                    st.session_state.categorized_posts[cat_key].append({"name": u_name, "text": u_content, "board": board_tab})
                    st.rerun()

    current_cat = "경제" if "주식" in board_tab or "부동산" in board_tab else "정치" if "정치" in board_tab else "사회"
    posts = [p for p in st.session_state.categorized_posts[current_cat] if p['board'] == board_tab]
    for p in reversed(posts[-5:]):
        st.markdown(f'<div class="board-card"><b>{p["name"]}</b>: {p["text"]}</div>', unsafe_allow_html=True)

    # 🏆 랭킹 보드
    st.markdown('<div class="ranking-box"><b>🏆 명예의 전당</b>', unsafe_allow_html=True)
    sorted_rank = sorted(st.session_state.user_rank.items(), key=lambda x: x[1], reverse=True)
    for i, (name, score) in enumerate(sorted_rank[:5]):
        medal = "🥇" if i==0 else "🥈" if i==1 else "🥉" if i==2 else "•"
        st.markdown(f'<div class="rank-item"><span>{medal} {name}</span> <b>{score} pts</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
