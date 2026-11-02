"""비교 엔진 — 화면·서버와 무관하게 Document 만 받아 결과(dict, JSON 가능)를 돌려준다."""
from .differ import TYPE_LABELS, compare_documents
from .history import build_history, order_documents
from .options import CompareOptions

__all__ = ["compare_documents", "build_history", "order_documents", "CompareOptions", "TYPE_LABELS"]
