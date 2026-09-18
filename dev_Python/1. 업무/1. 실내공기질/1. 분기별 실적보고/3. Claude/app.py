import streamlit as st
import pandas as pd
from io import BytesIO
from openpyxl import load_workbook
from openpyxl.styles import Font

st.set_page_config(page_title="실내공기질 데이터 처리", layout="wide")

SELECTED_COLUMNS = [
    '의뢰기관', '시설군', '배출시설', '시설명', '채취장소_x', '시료명_x',
    'PM10', 'PM2.5', 'CO2', '폼알데하이드', '부유세균', '일산화탄소',
    '라돈', '라돈(밀폐)', '벤젠', '톨루엔', '에틸벤젠', '자일렌', '스틸렌',
    '부적합항목', '확인일', '검사결과', '접수번호', '접수일자'
]

RENAME_MAP = {
    '의뢰기관': '시군명',
    '배출시설': '세부시설군',
    '채취장소_x': '주소',
    'PM10': '미세먼지(PM10)',
    'PM2.5': '초미세먼지(PM2.5)',
    'CO2': '이산화탄소',
    '부유세균': '총부유세균',
    '시료명_x': '시료명'
}

AVG_COLS = ['미세먼지(PM10)', '초미세먼지(PM2.5)', '이산화탄소', '폼알데하이드', '총부유세균', '일산화탄소', '라돈']


def to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output


def to_excel_multi(dfs, names):
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        for df, name in zip(dfs, names):
            df.to_excel(writer, index=False, sheet_name=name)
    out.seek(0)
    return out


def format_excel(file_bytes):
    wb = load_workbook(file_bytes)
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        for row in ws.iter_rows():
            for cell in row:
                cell.font = Font(size=10)
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 11
    formatted = BytesIO()
    wb.save(formatted)
    formatted.seek(0)
    return formatted


def check_columns(df, required, file_label):
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(
            f"❌ '{file_label}' 파일에 다음 열이 없습니다: {', '.join(missing)}\n\n"
            "파일 서식이 바뀌었는지 확인해주세요."
        )
        st.stop()


st.title("📊 실내공기질 데이터 처리 (1~6단계)")

with st.sidebar:
    st.markdown("### ℹ️ 사용 안내")
    st.markdown(
        "- 이 프로그램은 **브라우저 안에서만** 실행되며, "
        "업로드한 엑셀 데이터는 어디로도 전송되지 않습니다.\n"
        "- 실험노트, 조회통계 두 개의 엑셀 파일을 업로드하면 자동으로 처리됩니다.\n"
        "- 최종 결과는 상단의 '최종 통합 데이터' 다운로드 버튼을 사용하세요.\n"
        "- 중간 단계별 파일이 필요하면 아래 단계별 항목을 펼쳐서 받을 수 있습니다."
    )

uploaded_note = st.file_uploader("1️⃣ 실험노트 파일 업로드", type="xlsx", key="note")
uploaded_stat = st.file_uploader("2️⃣ 조회통계 파일 업로드", type="xlsx", key="stat")

if not (uploaded_note and uploaded_stat):
    st.info("👆 실험노트와 조회통계 파일을 모두 업로드해주세요.")
    st.stop()

try:
    data_df = pd.read_excel(uploaded_note)
    result_df = pd.read_excel(uploaded_stat)
except Exception as e:
    st.error(f"엑셀 파일을 읽는 중 오류가 발생했습니다: {e}")
    st.stop()

check_columns(data_df, ['접수번호'], "실험노트")
check_columns(result_df, ['접수번호'], "조회통계")

# 1단계: 병합
merged_df = pd.merge(data_df, result_df, on='접수번호', how='inner')
if merged_df.empty:
    st.warning("⚠️ '접수번호' 기준으로 일치하는 데이터가 없습니다. 두 파일의 접수번호를 확인해주세요.")
    st.stop()

check_columns(merged_df, ['검체유형_x'], "실험노트/조회통계 병합 결과")

# 2단계: 실내공기질 필터링
filtered_df = merged_df[merged_df['검체유형_x'].str.contains('실내공기질', na=False)].copy()
if filtered_df.empty:
    st.warning("⚠️ '실내공기질' 항목이 포함된 데이터가 없습니다.")
    st.stop()

# 3단계: 변수 추출
filtered_df['시설군'] = filtered_df['검체유형_x'].str.split('/').str[2]
missing_cols = [c for c in SELECTED_COLUMNS if c not in filtered_df.columns]
if missing_cols:
    st.error(f"❌ 다음 열을 찾을 수 없습니다: {', '.join(missing_cols)}\n\n원본 파일의 열 이름을 확인해주세요.")
    st.stop()

extracted_df = filtered_df[SELECTED_COLUMNS].copy()

# 공통 전처리
df = extracted_df.rename(columns=RENAME_MAP)
df['접수번호_10자리'] = df['접수번호'].astype(str).str[:10]
df['채취지점'] = df.groupby('시설명')['시료명'].transform(lambda x: ', '.join(x.unique()))
df_clean = df.copy()

# 4단계: 기존/신축공동주택 필터링
apart_df = df_clean[df_clean['시설군'].isin(['기존공동주택', '신축공동주택'])].copy()

# 5단계: 다중이용시설 처리
for col in AVG_COLS:
    if col in df_clean.columns:
        df_clean[col] = df_clean[col].replace("불검출", None)
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

avg_df = df_clean.groupby(['시설명', '접수번호_10자리'])[AVG_COLS].mean().reset_index()
reduced = df_clean.drop(columns=AVG_COLS, errors='ignore').drop_duplicates(['시설명', '접수번호_10자리'])
merged = avg_df.merge(reduced, on=['시설명', '접수번호_10자리'])
merged.loc[merged['검사결과'] == '적합', '부적합항목'] = ""
multi_df = merged[~merged['시설군'].isin(['기존공동주택', '신축공동주택'])].copy()

# 6단계: 통합
apart_df['확인일'] = pd.to_datetime(apart_df['확인일'], errors='coerce').dt.date
multi_df['확인일'] = pd.to_datetime(multi_df['확인일'], errors='coerce').dt.date
apart_df.sort_values('확인일', inplace=True)
multi_df.sort_values('확인일', inplace=True)
multi_df_final = multi_df.drop(columns='접수번호', errors='ignore')

combined = to_excel_multi([multi_df_final, apart_df], ['다중이용시설', '기존신축공동주택'])
styled_final = format_excel(combined)

st.success("✅ 처리가 완료되었습니다.")
st.download_button(
    "📥 최종 통합 데이터.xlsx 다운로드",
    styled_final,
    file_name="6.통합 데이터.xlsx",
    type="primary",
)

st.divider()
st.markdown("#### 단계별 중간 결과 (필요할 때만 펼쳐보세요)")

with st.expander("1단계: 병합 데이터"):
    st.download_button("📥 1.병합 데이터.xlsx", to_excel_bytes(merged_df), file_name="1.병합 데이터.xlsx", key="dl1")
    st.dataframe(merged_df.head())

with st.expander("2단계: 실내공기질 필터링 데이터"):
    st.download_button("📥 2.실내공기질 필터링 데이터.xlsx", to_excel_bytes(filtered_df), file_name="2.실내공기질 필터링 데이터.xlsx", key="dl2")
    st.dataframe(filtered_df.head())

with st.expander("3단계: 추출 데이터"):
    st.download_button("📥 3.추출 데이터.xlsx", to_excel_bytes(extracted_df), file_name="3.추출 데이터.xlsx", key="dl3")
    st.dataframe(extracted_df.head())

with st.expander("4단계: 기존/신축공동주택 데이터"):
    st.download_button("📥 4.기존신축공동주택 데이터.xlsx", to_excel_bytes(apart_df), file_name="4.기존신축공동주택 데이터.xlsx", key="dl4")
    st.dataframe(apart_df.head())

with st.expander("5단계: 다중이용시설 데이터"):
    st.download_button("📥 5.다중이용시설 데이터.xlsx", to_excel_bytes(multi_df), file_name="5.다중이용시설 데이터.xlsx", key="dl5")
    st.dataframe(multi_df.head())
