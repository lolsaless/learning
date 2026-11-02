"""비교 옵션 — 대시보드에서 받은 값을 검사해 CompareOptions 로 만든다."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from .. import config


@dataclass(frozen=True)
class CompareOptions:
    ignore_whitespace: bool = config.DEFAULT_OPTIONS["ignore_whitespace"]
    include_format: bool = config.DEFAULT_OPTIONS["include_format"]
    include_tables: bool = config.DEFAULT_OPTIONS["include_tables"]
    granularity: str = config.DEFAULT_OPTIONS["granularity"]
    similarity: float = config.DEFAULT_OPTIONS["similarity"]

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "CompareOptions":
        d = dict(d or {})
        base = asdict(cls())
        for k, v in d.items():
            if k not in base:
                continue
            if isinstance(base[k], bool):
                v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
            elif isinstance(base[k], float):
                v = min(1.0, max(0.0, float(v)))
            elif k == "granularity":
                v = v if v in ("word", "char") else base[k]
            base[k] = v
        return cls(**base)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def cache_key(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)
