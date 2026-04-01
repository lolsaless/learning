from pathlib import Path
import pandas as pd


def ensure_output_dir(output_dir: str) -> Path:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_dataframe_csv(df: pd.DataFrame, filepath: str) -> None:
    df.to_csv(filepath, encoding="utf-8-sig", index=True)


def build_output_path(output_dir: str, filename: str) -> str:
    output_path = ensure_output_dir(output_dir)
    return str(output_path / filename)