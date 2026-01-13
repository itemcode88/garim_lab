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

st.set_page_config(page_title="가림 랩 | 전문 커뮤니티 & 랭킹", layout="wide")

# 2. 디자인 (랭킹 및 게시판 스타일 추가)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@700&family=Noto+Serif+KR:wght@300;400;700&display=swap');
    .stApp { background-color: #f2efea; }
    .main-header { font-family: 'Nanum Myeongjo', serif; text-align: center; border-bottom: 3px double #333; padding: 20px 0; margin-bottom: 20px; }
    .news-card { background: white; padding: 12px; border: 1px solid #ccc; margin-bottom: 8px; border-radius: 5px; }
    .analysis-box { background: white; padding: 25px; border: 2px solid #000; }
    .board-card { background: #fff; padding: 10px; border-radius: 5px; border-left: 4px solid #333; margin-bottom: 8px; font-size: 13px; }
    .ranking-box { background: #333; color: #fff; padding: 15px; border-radius: 10px; margin-top: 20px; }
    .rank-item { display: flex; justify-content: space-between; border-bottom: 1px solid #444; padding: 5px 0; }
    </style>
    """, unsafe_allow_html=True)

# 3. 데이터 초기화
if 'saved_articles' not in st.session_state: st.session_state.saved_articles = []
if 'votes' not in st.session_state: st.session_state.votes = {}
# 게시판 데이터를 카테고리별로 저장
if 'categorized_posts' not in st.session_state: 
    st.session_state.categorized_posts = {"정치": [], "경제": [], "사회": []}
# 유저 랭킹 데이터 (닉네임: 점수)
if 'user_rank' not in st.session_state: 
    st.session_state.user_rank = {"가림마스터": 150, "경제탐정": 120, "법률왕": 90}

# 4. 함수 설정
@st.cache_data(ttl=300)
def get_news_stable(category):
    query = urllib.parse.quote(category)
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        feed = feedparser.parse(resp.content)
        return [{"title": e.title, "source": e.source.title} for e in feed.entries[:6]]
    except: return []

def analyze_ai(title, source, api_key):
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = next((m for m in models if "1.5-flash" in m), models[0])
        model = genai.GenerativeModel(target)
        prompt = f"뉴스 '{title}' 분석. JSON: {{'bias':'...','score':85,'reason':'...','impact':'...'}}"
        response = model.generate_content(prompt)
        return json.loads(response.text.strip().replace('```json', '').replace('```', '')), target
    except: return None, None

# 5. 메인 레이아웃
st.markdown('<div class="main-header"><h1>가 림 랩 (GARIM LAB)</h1><p><b>분야별 전문 게시판 & 유저 랭킹 시스템</b></p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.title("⚙️ 마이 페이지")
    api_key = st.text_input("Gemini API Key", type="password")
    if api_key:
        try:
            genai.configure(api_key=api_key); genai.list_models()
            st.success("✅ API 연결됨")
            st.session_state.api_ok = True
        except: st.error("❌ 키 확인 필요")
    st.divider()
    st.subheader("🔖 스크랩함")
    for idx, item in enumerate(st.session_state.saved_articles):
        st.caption(f"• {item['title'][:15]}...")

col_news, col_report, col_community = st.columns([1, 1, 1.2])

# --- [1. 뉴스 목록] ---
with col_news:
    st.subheader("📰 뉴스 섹션")
    main_cat = st.radio("대분류", ["정치", "경제", "사회"], horizontal=True)
    news_list = get_news_stable(main_cat)
    for i, news in enumerate(news_list):
        with st.container():
            st.markdown(f'<div class="news-card"><b>{news["title"]}</b><br><small>{news["source"]}</small></div>', unsafe_allow_html=True)
            if st.button(f"🔍 분석", key=f"n_{i}"):
                if api_key and st.session_state.get('api_ok'):
                    with st.spinner('AI 분석 중...'):
                        res, _ = analyze_ai(news['title'], news['source'], api_key)
                        if res:
                            st.session_state.analysis_res = res
                            st.session_state.analysis_title = news['title']
                else: st.error("API 키가 필요합니다.")

# --- [2. AI 리포트] ---
with col_report:
    st.subheader("⚖️ AI 정밀 리포트")
    if 'analysis_res' in st.session_state:
        res = st.session_state.analysis_res
        title = st.session_state.analysis_title
        st.markdown(f"""
            <div class="analysis-box">
                <h4 style="margin:0;">{title}</h4>
                <hr>
                <p><b>신뢰도: {res['score']}% | 성향: {res['bias']}</b></p>
                <p style="font-size:14px;">{res['reason']}</p>
                <div style="background:#f0f0f0; padding:10px; border-radius:5px; font-size:12px;">
                    <b>💼 영향:</b> {res['impact']}
                </div>
            </div>
        """, unsafe_allow_html=True)
        if st.button("🔖 이 기사 스크랩"):
            st.session_state.saved_articles.append({"title": title})
            st.toast("저장 완료!")
    else: st.info("왼쪽에서 분석할 기사를 선택하세요.")

# --- [3. 분야별 게시판 & 랭킹] ---
with col_community:
    st.subheader("👥 가림 커뮤니티")
    
    # 세부 게시판 선택
    board_tab = st.selectbox("분야별 게시판 선택", ["정치 토론장", "한국 주식", "미국 주식", "부동산/재테크", "법률/세금 상담"])
    
    # 글쓰기 폼
    with st.expander("✍️ 새 글 작성하기 (활동 포인트 +10)", expanded=False):
        with st.form("post_form", clear_on_submit=True):
            u_name = st.text_input("닉네임", placeholder="닉네임을 입력하세요")
            u_content = st.text_area("내용")
            if st.form_submit_button("게시물 등록"):
                if u_name and u_content:
                    # 점수 추가 (랭킹 반영)
                    st.session_state.user_rank[u_name] = st.session_state.user_rank.get(u_name, 0) + 10
                    # 게시글 저장 (여기서는 편의상 선택된 카테고리에 저장)
                    cat_key = "경제" if "주식" in board_tab or "부동산" in board_tab else "정치" if "정치" in board_tab else "사회"
                    st.session_state.categorized_posts[cat_key].append({"name": u_name, "text": u_content, "board": board_tab})
                    st.rerun()

    # 현재 게시판 글 출력
    current_cat = "경제" if "주식" in board_tab or "부동산" in board_tab else "정치" if "정치" in board_tab else "사회"
    display_posts = [p for p in st.session_state.categorized_posts[current_cat] if p['board'] == board_tab]
    
    for p in reversed(display_posts[-5:]): # 최근 5개만
        st.markdown(f'<div class="board-card"><b>{p["name"]}</b>: {p["text"]}</div>', unsafe_allow_html=True)

    # 🏆 유저 랭킹 영역
    st.markdown('<div class="ranking-box"><b>🏆 명예의 전당 (Top 5)</b>', unsafe_allow_html=True)
    sorted_rank = sorted(st.session_state.user_rank.items(), key=lambda x: x[1], reverse=True)
    for i, (name, score) in enumerate(sorted_rank[:5]):
        medal = "🥇" if i==0 else "🥈" if i==1 else "🥉" if i==2 else "•"
        st.markdown(f'<div class="rank-item"><span>{medal} {name}</span> <b>{score} pts</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)