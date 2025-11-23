"""
app.py
건설법령 챗봇 Streamlit
"""

import streamlit as st
import os
from dotenv import load_dotenv
from s4_EmbeddingManager import EmbeddingManager
from s5_LegalSearchEngine import LegalSearchEngine
from enhanced_legal_qa_system import EnhancedLegalQASystem
import json

load_dotenv()

st.set_page_config(
    page_title="건설법령 챗봇",
    page_icon="🏗️",
    layout="wide"
)

# 스타일
st.markdown("""
<style>
    .main-title {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .query-badge {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 15px;
        font-size: 0.9rem;
        font-weight: bold;
        background-color: #4ecdc4;
        color: white;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_system():
    """시스템 로드"""
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    if not OPENAI_API_KEY:
        st.error("⚠️ OPENAI_API_KEY 필요")
        st.stop()
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    vector_store_dir = os.path.join(project_root, "data", "vector_store", "construction_law")
    cache_dir = os.path.join(project_root, "data", "cache")
    
    with st.spinner("🔧 시스템 로딩..."):
        em = EmbeddingManager(OPENAI_API_KEY, "construction_law", cache_dir=cache_dir)
        
        index = em.load_index(os.path.join(vector_store_dir, "faiss_index.bin"))
        metadata = em.load_metadata(os.path.join(vector_store_dir, "metadata.json"))
        
        if not index or not metadata:
            st.error("⚠️ 인덱스 파일 없음")
            st.stop()
        
        engine = LegalSearchEngine(index, metadata, em)
        qa_system = EnhancedLegalQASystem(engine, OPENAI_API_KEY)
    
    return qa_system


# 메인
st.markdown('<p class="main-title">🏗️ 건설법령 AI 챗봇</p>', unsafe_allow_html=True)

qa_system = load_system()

# 사이드바
with st.sidebar:
    st.header("📖 사용 가이드")
    st.markdown("""
    **질문 유형:**
    - 🔴 법조문: "제36조 내용"
    - 🟢 정보: "비계 안전 기준"
    - 🔵 컨설팅: "3m 비계 괜찮아?"
    - 🟡 절차: "용도변경 절차"
    - 🟠 문서: "체크리스트 만들어"
    - 🟣 비교: "A법과 B법 차이"
    """)
    
    st.markdown("---")
    show_details = st.checkbox("상세 정보 표시", value=True)

# 채팅
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("질문을 입력하세요 (예: 비계 안전 기준은?)"):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("🤔 답변 생성 중..."):
            
            # QA 실행
            answer = qa_system.generate_response(prompt, verbose=False)
            
            meta = answer.get("_meta", {})
            classification = meta.get("classification", {})
            
            # 유형 표시
            query_type = classification.get("query_type", "일반_정보_검색")
            confidence = classification.get("confidence", 0)
            
            st.markdown(f"""
            <span class="query-badge">{query_type}</span>
            <span style="color: gray;"> (확신도: {confidence:.0%})</span>
            """, unsafe_allow_html=True)
            
            # 답변 표시
            st.markdown("---")
            
            # 유형별 렌더링
            if query_type == "법조문_조회":
                법조문 = answer.get("법조문", {})
                st.markdown(f"### 📜 {법조문.get('법령명', 'N/A')} {법조문.get('조항', 'N/A')}")
                st.info(법조문.get("조문_내용", ""))
                if 법조문.get("간단_해설"):
                    st.write("**해설:**", 법조문["간단_해설"])
            
            elif query_type == "일반_정보_검색":
                주제 = answer.get("주제", "")
                법적_근거 = answer.get("법적_근거", {})
                
                if 주제:
                    st.markdown(f"### 📋 {주제}")
                
                if 법적_근거.get("핵심_요구사항"):
                    st.write("**핵심 요구사항:**", 법적_근거["핵심_요구사항"])
                
                if 법적_근거.get("준수_방법"):
                    st.write("**준수 방법:**")
                    for m in 법적_근거["준수_방법"]:
                        st.write(f"- {m}")
            
            elif query_type == "상황별_컨설팅":
                법적_판단 = answer.get("법적_판단", {})
                결론 = 법적_판단.get("결론", "")
                
                if "적법" in 결론:
                    st.success(f"**결론:** {결론}")
                elif "부적법" in 결론:
                    st.error(f"**결론:** {결론}")
                else:
                    st.warning(f"**결론:** {결론}")
                
                if 법적_판단.get("근거"):
                    st.write("**근거:**", 법적_판단["근거"])
            
            else:
                # 기본 JSON 표시
                st.json(answer)
            
            # 상세 정보
            if show_details:
                with st.expander("📚 참조 문서"):
                    for i, s in enumerate(meta.get("sources", []), 1):
                        st.write(f"**[{i}]** {s['doc_name']} (p.{s['page']}) - 관련도: {s['relevance_score']:.3f}")
            
            # 저장
            response_text = json.dumps(answer, ensure_ascii=False)
            st.session_state.messages.append({"role": "assistant", "content": response_text})