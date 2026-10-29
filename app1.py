import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
import matplotlib.font_manager as fm
import os
from collections import Counter
import re

# ==========================================
# 1. 페이지 기본 설정 및 한글 폰트 설정
# ==========================================
st.set_page_config(
    page_title="캠퍼스 라이프 데이터 분석기",
    page_icon="🎓",
    layout="wide"
)


# Matplotlib 및 Seaborn 한글 폰트 깨짐 방지 설정
def setup_korean_font():
    if os.name == 'nt':  # Windows
        plt.rc('font', family='Malgun Gothic')
    elif os.name == 'posix':  # Mac or Linux
        plt.rc('font', family='AppleGothic')
    else:
        plt.rc('font', family='NanumGothic')

    # 마이너스 기호 깨짐 방지
    plt.rc('axes', unicode_minus=False)


setup_korean_font()

# ==========================================
# 2. 메인 화면 타이틀 및 정보 안내
# ==========================================
st.title("🎓 대학생 캠퍼스 라이프 설문 데이터 분석기")
st.markdown("""
안녕하세요! 이 프로그램은 1학년 대학생 여러분의 설문 데이터를 바탕으로 **학과별 생활 습관, 공부/수면시간과 만족도의 관계, 한 줄 의견 키워드 및 감성 분석**을 제공하는 스트림릿 앱입니다.
왼쪽 사이드바에서 CSV 파일을 업로드하고 **'분석 시작'** 버튼을 눌러보세요!
""")

st.divider()

# ==========================================
# 3. 사이드바 - CSV 파일 업로드 기능
# ==========================================
st.sidebar.header("📁 데이터 업로드")
uploaded_file = st.sidebar.file_uploader("학생 설문 CSV 파일을 선택하세요", type=["csv"])

st.sidebar.markdown("---")
st.sidebar.subheader("💡 가이드")
st.sidebar.write("CSV 파일 필수 포함 컬럼:")
st.sidebar.caption("- 학과, 학년, 통학시간, 공부시간, 수면시간, 만족도, 한줄의견")

# ==========================================
# 4. 분석 로직 수행 (파일이 업로드되었을 때)
# ==========================================
if uploaded_file is not None:
    # 4-1. 데이터 로드 (EUC-KR 및 UTF-8 예외 처리)
    try:
        df_raw = pd.read_csv(uploaded_file, encoding='utf-8')
    except UnicodeDecodeError:
        uploaded_file.seek(0)
        df_raw = pd.read_csv(uploaded_file, encoding='euc-kr')

    # 분석 시작 버튼 생성
    if st.sidebar.button("🚀 분석 시작", type="primary"):
        st.session_state['start_analysis'] = True

    # '분석 시작' 버튼이 눌렸거나 이미 진행 중인 경우 실행
    if st.session_state.get('start_analysis', False):

        # ------------------------------------------
        # 5. 데이터 정제 및 이상치/결측치 검사
        # ------------------------------------------
        st.subheader("🧹 1. 데이터 정제 및 이상치 점검")

        # 필수 컬럼 검사
        required_cols = ['학과', '학년', '통학시간', '공부시간', '수면시간', '만족도', '한줄의견']
        missing_cols = [col for col in required_cols if col not in df_raw.columns]

        if missing_cols:
            st.error(f"⚠️ 다음 필수 컬럼이 파일에 없습니다: {', '.join(missing_cols)}")
        else:
            total_raw_count = len(df_raw)

            # 수치 데이터 강제 숫자 형변환
            num_cols = ['만족도', '통학시간', '공부시간', '수면시간']
            for col in num_cols:
                df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce')

            # 학과 컬럼 공백 정리
            df_raw['학과'] = df_raw['학과'].astype(str).str.strip()

            # 잘못된 데이터 조건 검사 (만족도 1~10 범주)
            invalid_mask = (
                    df_raw['학과'].isna() | (df_raw['학과'] == '') | (df_raw['학과'] == 'nan') |
                    df_raw['만족도'].isna() |
                    (df_raw['만족도'] < 1) | (df_raw['만족도'] > 10) |
                    df_raw['통학시간'].isna() | (df_raw['통학시간'] < 0) |
                    df_raw['공부시간'].isna() | (df_raw['공부시간'] < 0) |
                    df_raw['수면시간'].isna() | (df_raw['수면시간'] < 0)
            )

            df_invalid = df_raw[invalid_mask]
            df_clean = df_raw[~invalid_mask].copy()

            invalid_count = len(df_invalid)
            clean_count = len(df_clean)

            # 정제 결과 표기
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("전체 수집 데이터", f"{total_raw_count} 건")
            col_m2.metric("정상 데이터 건수", f"{clean_count} 건", delta="분석 가능")
            col_m3.metric("제거된 잘못된 데이터", f"{invalid_count} 건", delta="-손실 데이터", delta_color="inverse")

            if invalid_count > 0:
                with st.expander("❌ 제거된 잘못된 데이터 상세보기 (클릭)"):
                    st.dataframe(df_invalid)
            else:
                st.success("✨ 모든 데이터가 정상적인 유효 범주(만족도 1~10) 안에 있습니다!")

            st.divider()

            # ------------------------------------------
            # 6. 학과 선택 필터링 및 요약 지표
            # ------------------------------------------
            st.subheader("🎯 2. 학과별 선택 및 평균 만족도")

            # 파일 내 학과 목록 추출
            unique_depts = sorted([dept for dept in df_clean['학과'].unique() if dept])
            dept_list = ["전체 학과"] + unique_depts

            selected_dept = st.selectbox("분석하고자 하는 학과를 선택하세요:", dept_list, key="dept_select_main")

            if selected_dept == "전체 학과":
                df_filtered = df_clean
            else:
                df_filtered = df_clean[df_clean['학과'] == selected_dept]

            avg_satisfaction = df_filtered['만족도'].mean()
            avg_study = df_filtered['공부시간'].mean()

            res_col1, res_col2, res_col3 = st.columns(3)
            res_col1.metric("선택 대상 학생 수", f"{len(df_filtered)} 명")
            res_col2.metric("평균 학교생활 만족도", f"{avg_satisfaction:.2f} / 10.0 점")
            res_col3.metric("평균 하루 공부시간", f"{avg_study:.1f} 시간")

            st.divider()

            # ------------------------------------------
            # 7. 핵심 그래프 3종 시각화
            # ------------------------------------------
            st.subheader("📊 3. 상세 데이터 시각화 (3종 분석 그래프)")

            # --- [그래프 1] 막대그래프: 학과별 생활 습관 비교 ---
            st.markdown("##### 1️⃣ 학과별 학생들의 생활 습관엔 어떤 차이가 있을까? (막대그래프)")
            fig1, ax1 = plt.subplots(figsize=(10, 5))

            dept_habits = df_clean.groupby('학과')[['통학시간', '공부시간', '수면시간']].mean().reset_index()
            dept_habits_melted = pd.melt(dept_habits, id_vars=['학과'], var_name='항목', value_name='평균값')

            sns.barplot(data=dept_habits_melted, x='학과', y='평균값', hue='항목', ax=ax1, palette='Set2')
            ax1.set_title("학과별 학생 생활 습관 (통학/공부/수면 시간) 비교", fontsize=14, fontweight='bold')
            ax1.set_xlabel("학과 (Department)", fontsize=12)
            ax1.set_ylabel("평균 수치 (통학: 분, 공부/수면: 시간)", fontsize=12)
            ax1.grid(axis='y', linestyle='--', alpha=0.7)

            st.pyplot(fig1)

            # --- [그래프 2] 산점도: 공부/수면시간과 만족도의 관계 ---
            st.markdown("##### 2️⃣ 공부시간, 수면시간 등은 학교생활 만족도와 어떤 관계가 있을까? (산점도)")

            col_p1, col_p2 = st.columns(2)

            with col_p1:
                fig2_1, ax2_1 = plt.subplots(figsize=(6, 4))
                sns.scatterplot(
                    data=df_filtered,
                    x='공부시간',
                    y='만족도',
                    hue='학년',
                    palette='viridis',
                    s=100,
                    ax=ax2_1
                )
                sns.regplot(data=df_filtered, x='공부시간', y='만족도', scatter=False, ax=ax2_1, color='gray')
                ax2_1.set_title(f"[{selected_dept}] 공부시간 vs 학교생활 만족도", fontsize=12, fontweight='bold')
                ax2_1.set_xlabel("일일 평균 공부시간 (단위: 시간)", fontsize=10)
                ax2_1.set_ylabel("학교생활 만족도 (단위: 점수 1~10)", fontsize=10)
                ax2_1.set_ylim(0, 11)
                ax2_1.grid(True, linestyle=':', alpha=0.6)
                st.pyplot(fig2_1)

            with col_p2:
                fig2_2, ax2_2 = plt.subplots(figsize=(6, 4))
                sns.scatterplot(
                    data=df_filtered,
                    x='수면시간',
                    y='만족도',
                    color='coral',
                    s=100,
                    ax=ax2_2
                )
                sns.regplot(data=df_filtered, x='수면시간', y='만족도', scatter=False, ax=ax2_2, color='red')
                ax2_2.set_title(f"[{selected_dept}] 수면시간 vs 학교생활 만족도", fontsize=12, fontweight='bold')
                ax2_2.set_xlabel("일일 평균 수면시간 (단위: 시간)", fontsize=10)
                ax2_2.set_ylabel("학교생활 만족도 (단위: 점수 1~10)", fontsize=10)
                ax2_2.set_ylim(0, 11)
                ax2_2.grid(True, linestyle=':', alpha=0.6)
                st.pyplot(fig2_2)

            # --- [그래프 3] 워드클라우드: 한 줄 의견 키워드 분석 ---
            st.markdown("##### 3️⃣ 학생들이 작성해 둔 한 줄 의견엔 어떤 단어들이 많이 등장할까? (워드클라우드)")

            text_data = " ".join(df_filtered['한줄의견'].dropna().astype(str).tolist())

            if text_data.strip():
                font_path = "C:/Windows/Fonts/malgun.ttf" if os.name == 'nt' else "/Library/Fonts/Arial Unicode.ttf"

                try:
                    wordcloud = WordCloud(
                        font_path=font_path,
                        width=800,
                        height=400,
                        background_color='white',
                        colormap='Dark2'
                    ).generate(text_data)

                    fig3, ax3 = plt.subplots(figsize=(10, 5))
                    ax3.imshow(wordcloud, interpolation='bilinear')
                    ax3.axis('off')
                    ax3.set_title(f"[{selected_dept}] 학생들의 한 줄 의견 핵심 단어 구름 (단위: 키워드 빈도수)", fontsize=14,
                                  fontweight='bold', pad=15)
                    st.pyplot(fig3)
                except Exception as e:
                    st.warning("워드클라우드를 생성하기 위한 한국어 폰트를 로드하지 못했습니다.")
            else:
                st.warning("선택된 데이터에 작성된 한 줄 의견이 없습니다.")

            st.divider()

            # ------------------------------------------
            # 8. 학과별 한 줄 의견 단어 상세 분석 & 긍정/부정 감성 분석
            # ------------------------------------------
            st.subheader("📝 4. 학과별 한 줄 의견 상세 단어 분석 (빈도수 & 긍부정 분석)")

            # 학과 전용 선택 셀렉트박스 (독립된 선택 칸)
            text_dept = st.selectbox("상세 단어 분석을 진행할 학과를 선택하세요:", unique_depts, key="dept_select_text")

            # 선택된 학과 텍스트 추출
            df_text_dept = df_clean[df_clean['학과'] == text_dept]
            comments = df_text_dept['한줄의견'].dropna().astype(str).tolist()

            # 단어 추출 및 빈도 계산
            words = []
            for comment in comments:
                # 특수문자 제거 후 2글자 이상 단어 추출
                cleaned = re.sub(r'[^가-힣a-zA-Z\s]', '', comment)
                tokens = [w for w in cleaned.split() if len(w) >= 2]
                words.extend(tokens)

            if words:
                word_counts = Counter(words)
                df_words = pd.DataFrame(word_counts.items(), columns=['단어', '등장 횟수']).sort_values(by='등장 횟수',
                                                                                                  ascending=False).reset_index(
                    drop=True)
                df_words.index = df_words.index + 1  # 순위 1부터 시작

                # 레이아웃 분할: 왼쪽(1등~끝 표) / 오른쪽(Top 10 막대그래프)
                col_w1, col_w2 = st.columns([1, 1.2])

                with col_w1:
                    st.markdown(f"##### 📌 [{text_dept}] 단어 등장 순위 (1위 ~ {len(df_words)}위)")
                    st.dataframe(df_words, use_container_width=True, height=350)

                with col_w2:
                    st.markdown(f"##### 📊 [{text_dept}] 자주 등장하는 단어 Top 10")
                    top10_df = df_words.head(10)

                    fig_top10, ax_top10 = plt.subplots(figsize=(7, 4.5))
                    sns.barplot(data=top10_df, x='등장 횟수', y='단어', palette='Blues_r', ax=ax_top10)
                    ax_top10.set_title(f"[{text_dept}] 한 줄 의견 최빈 단어 Top 10", fontsize=12, fontweight='bold')
                    ax_top10.set_xlabel("등장 횟수 (단위: 회)", fontsize=10)
                    ax_top10.set_ylabel("단어", fontsize=10)
                    ax_top10.grid(axis='x', linestyle=':', alpha=0.6)
                    st.pyplot(fig_top10)

                # --- 긍정/부정 단어 자동 감성 판별 사전 및 계산 ---
                pos_keywords = ['좋다', '좋아요', '좋음', '재미', '재밌', '도움', '예뻐', '예쁨', '만족', '최고', '친절', '맛있', '깔끔', '충분',
                                '쾌적']
                neg_keywords = ['부족', '불편', '피곤', '길어', '멀다', '아쉽', '힘듦', '힘들어', '어려움', '어렵', '나쁨', '싫음', '복잡', '지루']

                pos_count = 0
                neg_count = 0

                for word, count in word_counts.items():
                    if any(pos in word for pos in pos_keywords):
                        pos_count += count
                    elif any(neg in word for neg in neg_keywords):
                        neg_count += count

                # 감성 분석 결과 출력
                st.markdown("##### ⚖️ 한 줄 의견 긍정/부정 단어 등장 횟수")
                s_col1, s_col2, s_col3 = st.columns(3)
                s_col1.metric("총 추출된 핵심 단어 수", f"{sum(word_counts.values())} 개")
                s_col2.metric("사용된 긍정 단어", f"{pos_count} 개", delta="긍정적 표현")
                s_col3.metric("사용된 부정 단어", f"{neg_count} 개", delta="-개선 필요 표현", delta_color="inverse")

                st.info(f"💡 **[{text_dept}] 감성 분석 총평:** 사용된 긍정 단어: {pos_count}개, 사용된 부정 단어: {neg_count}개")

            else:
                st.warning(f"[{text_dept}] 학과의 한 줄 의견에서 분석할 수 있는 단어가 부족합니다.")

else:
    st.info("👈 왼쪽 사이드바에서 분석할 학생 CSV 파일을 업로드해 주세요!")