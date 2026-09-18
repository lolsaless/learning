from __future__ import annotations

import streamlit as st

from .processor import (
    ProcessingError,
    build_dataframe_workbook,
    build_final_workbook,
    process_excel_files,
)


@st.cache_data(show_spinner=False)
def _process(note_bytes: bytes, stat_bytes: bytes):
    bundle = process_excel_files(note_bytes, stat_bytes)
    return bundle, build_final_workbook(bundle)


def render_app() -> None:
    st.set_page_config(page_title="실내공기질 실적 정리", page_icon="🏢", layout="wide")
    st.title("실내공기질 실적 정리")
    st.caption("실험노트와 조회통계를 검증·병합하고 다중이용시설 및 공동주택 실적을 생성합니다.")

    with st.sidebar:
        st.subheader("사용 안내")
        st.markdown(
            "1. **실험노트.xlsx**를 선택합니다.\n"
            "2. **조회통계.xlsx**를 선택합니다.\n"
            "3. 입력 검증이 통과하면 최종 Excel을 받습니다.\n\n"
            "브라우저/PC 배포판은 파일을 로컬에서 처리합니다."
        )

    left, right = st.columns(2)
    with left:
        uploaded_note = st.file_uploader("실험노트 파일", type=["xlsx"], key="note")
    with right:
        uploaded_stat = st.file_uploader("조회통계 파일", type=["xlsx"], key="stat")

    if not uploaded_note or not uploaded_stat:
        st.info("두 Excel 파일을 모두 선택하면 자동으로 검증과 처리를 시작합니다.")
        return

    try:
        with st.spinner("입력 파일을 검증하고 실적을 정리하는 중입니다."):
            bundle, final_excel = _process(uploaded_note.getvalue(), uploaded_stat.getvalue())
    except ProcessingError as exc:
        st.error(str(exc))
        return
    except Exception:
        st.error("처리 중 예상하지 못한 오류가 발생했습니다. 입력 파일의 서식을 확인해주세요.")
        return

    counts = dict(zip(bundle.summary["처리단계"], bundle.summary["건수"]))
    metric_columns = st.columns(4)
    metric_columns[0].metric("병합", f"{counts['접수번호 병합']:,}건")
    metric_columns[1].metric("실내공기질", f"{counts['실내공기질 필터']:,}건")
    metric_columns[2].metric("다중이용시설", f"{counts['다중이용시설 집계']:,}건")
    metric_columns[3].metric("공동주택", f"{counts['기존·신축공동주택']:,}건")

    warning_count = int((bundle.checks["수준"] == "경고").sum())
    if warning_count:
        st.warning(
            f"처리는 완료됐지만 {warning_count}개 검증 항목을 확인해야 합니다. "
            "최종 Excel의 '검증결과' 시트에도 같은 내용이 포함됩니다."
        )
    else:
        st.success("입력 검증과 처리가 완료됐습니다.")

    st.download_button(
        "최종 통합 데이터 다운로드",
        data=final_excel,
        file_name="실내공기질_실적_통합.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )

    summary_tab, check_tab, multi_tab, apartment_tab = st.tabs(
        ["처리 요약", "검증 결과", "다중이용시설 미리보기", "공동주택 미리보기"]
    )
    with summary_tab:
        st.dataframe(bundle.summary, hide_index=True, use_container_width=True)
    with check_tab:
        st.dataframe(bundle.checks, hide_index=True, use_container_width=True)
    with multi_tab:
        st.dataframe(bundle.multi_facilities.head(100), hide_index=True, use_container_width=True)
    with apartment_tab:
        st.dataframe(bundle.apartments.head(100), hide_index=True, use_container_width=True)

    with st.expander("중간 데이터 다운로드"):
        st.caption("검증이나 문제 확인이 필요할 때만 사용하세요.")
        frames = [
            ("1.병합_데이터.xlsx", bundle.merged, "병합"),
            ("2.실내공기질_필터.xlsx", bundle.filtered, "필터"),
            ("3.추출_데이터.xlsx", bundle.extracted, "추출"),
        ]
        for index, (filename, frame, sheet_name) in enumerate(frames):
            st.download_button(
                filename,
                data=build_dataframe_workbook(frame, sheet_name),
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"intermediate_{index}",
            )
