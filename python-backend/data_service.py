"""
data_service.py — Data loading, filtering, and cleaning logic
Extracted from main.py for the FastAPI backend.
"""

import os
import math
import random
import re
import html
from http.cookiejar import CookieJar
from io import BytesIO, StringIO
from collections import deque
from typing import Optional, Dict, Any, List
from urllib.error import URLError
from urllib.parse import parse_qs, unquote, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler, Binarizer, LabelEncoder
from sklearn.feature_selection import SelectKBest, chi2, mutual_info_classif, VarianceThreshold, RFE
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.datasets import load_iris, load_breast_cancer, load_digits
from sklearn.linear_model import LinearRegression, LogisticRegression, Lasso
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.neural_network import MLPRegressor


# ─── Global state (per-session, in-process) ────────────────────────────────────
class DataStore:
    def __init__(self):
        self.df: Optional[pd.DataFrame] = None
        self.df_cleaned: Optional[pd.DataFrame] = None
        self.df_filtered: Optional[pd.DataFrame] = None
        self.source_name: str = ""
        self.active_filters: Dict[str, str] = {}
        self.cleaning_snapshots: List[pd.DataFrame] = []
        self.cleaning_steps: List[Dict[str, Any]] = []
        self.cleaning_index: int = 0

    def reset(self):
        self.df = None
        self.df_cleaned = None
        self.df_filtered = None
        self.source_name = ""
        self.active_filters = {}
        self.cleaning_snapshots = []
        self.cleaning_steps = []
        self.cleaning_index = 0

    def on_data_loaded(self, df: pd.DataFrame, source_name: str):
        self.df = df
        self.df_cleaned = df.copy()
        self.df_filtered = df.copy()
        self.source_name = source_name
        self.active_filters = {}
        self.cleaning_snapshots = []
        self.cleaning_steps = []
        self.cleaning_index = 0
        self.push_cleaning_step("Original data", self.df_cleaned, reset=True)

    def get_info(self) -> Dict[str, Any]:
        if self.df is None:
            return {"loaded": False}
        df = self.df
        null_counts = df.isnull().sum().to_dict()
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
        return {
            "loaded": True,
            "source": self.source_name,
            "rows": len(df),
            "cols": len(df.columns),
            "columns": list(df.columns),
            "dtypes": dtypes,
            "null_counts": {k: int(v) for k, v in null_counts.items()},
            "unique_counts": self._unique_counts(df),
            "active_filters": self.active_filters,
            "filtered_rows": len(self.df_filtered) if self.df_filtered is not None else 0,
        }

    def frame_info(self, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        frame = self.df_cleaned if df is None else df
        if frame is None:
            return {"loaded": False}
        return {
            "loaded": True,
            "source": self.source_name,
            "rows": len(frame),
            "cols": len(frame.columns),
            "columns": list(frame.columns),
            "dtypes": {col: str(dtype) for col, dtype in frame.dtypes.items()},
            "null_counts": {k: int(v) for k, v in frame.isnull().sum().to_dict().items()},
            "unique_counts": self._unique_counts(frame),
        }

    def _unique_counts(self, df: pd.DataFrame) -> Dict[str, int]:
        return {col: int(df[col].nunique(dropna=True)) for col in df.columns}

    def push_cleaning_step(self, label: str, df: pd.DataFrame, reset: bool = False):
        if reset:
            self.cleaning_snapshots = []
            self.cleaning_steps = []
            self.cleaning_index = 0
        elif self.cleaning_index < len(self.cleaning_snapshots) - 1:
            self.cleaning_snapshots = self.cleaning_snapshots[: self.cleaning_index + 1]
            self.cleaning_steps = self.cleaning_steps[: self.cleaning_index + 1]

        self.df_cleaned = df.copy()
        index = len(self.cleaning_snapshots)
        self.cleaning_snapshots.append(self.df_cleaned.copy())
        self.cleaning_steps.append({
            "index": index,
            "label": label,
            "rows": len(self.df_cleaned),
            "cols": len(self.df_cleaned.columns),
        })
        self.cleaning_index = index

    def get_cleaning_history(self) -> Dict[str, Any]:
        return {
            "current": self.cleaning_index,
            "steps": [
                {**step, "current": step["index"] == self.cleaning_index}
                for step in self.cleaning_steps
            ],
        }

    def rollback_cleaning(self, step_index: int) -> Dict[str, Any]:
        if not self.cleaning_snapshots:
            raise ValueError("No cleaning history available")
        if step_index < 0 or step_index >= len(self.cleaning_snapshots):
            raise ValueError("Cleaning step not found")
        self.df_cleaned = self.cleaning_snapshots[step_index].copy()
        self.cleaning_snapshots = self.cleaning_snapshots[: step_index + 1]
        self.cleaning_steps = self.cleaning_steps[: step_index + 1]
        for index, step in enumerate(self.cleaning_steps):
            step["index"] = index
        self.cleaning_index = len(self.cleaning_snapshots) - 1
        return {
            "message": f"Rolled back to: {self.cleaning_steps[self.cleaning_index]['label']}",
            "history": self.get_cleaning_history(),
            "info": self.frame_info(self.df_cleaned),
        }


store = DataStore()


# ─── Loading ────────────────────────────────────────────────────────────────────

def load_from_path(file_path: str, ext: str = None) -> pd.DataFrame:
    if ext is None:
        ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(file_path)
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path)
    elif ext == ".json":
        return pd.read_json(file_path)
    elif ext == ".tsv":
        return pd.read_csv(file_path, sep="\t")
    elif ext == ".parquet":
        return pd.read_parquet(file_path)
    else:
        return pd.read_csv(file_path)


def load_from_bytes(content: bytes, filename: str) -> pd.DataFrame:
    ext = os.path.splitext(filename)[1].lower()
    bio = BytesIO(content)
    if ext == ".csv":
        return pd.read_csv(bio)
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(bio)
    elif ext == ".json":
        return pd.read_json(bio)
    elif ext == ".tsv":
        return pd.read_csv(bio, sep="\t")
    elif ext == ".parquet":
        return pd.read_parquet(bio)
    else:
        return pd.read_csv(bio)


def load_from_url(url: str, fmt: str = "auto") -> pd.DataFrame:
    if not url or not url.strip():
        raise ValueError("Enter a URL to import.")

    normalized_url = _normalize_dataset_url(url.strip(), fmt)
    try:
        content, headers, final_url = _fetch_url_bytes(normalized_url)
    except URLError as exc:
        raise ValueError(f"Could not download data from the URL: {exc.reason}") from exc

    resolved_fmt = _infer_url_format(url, final_url, headers, fmt)
    df = _read_url_content(content, resolved_fmt)
    _validate_url_frame(df, content)
    return df


def _normalize_dataset_url(url: str, fmt: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    query = parse_qs(parsed.query)

    if "drive.google.com" in host:
        file_id = None
        match = re.search(r"/file/d/([^/]+)", parsed.path)
        if match:
            file_id = match.group(1)
        elif query.get("id"):
            file_id = query["id"][0]
        if file_id:
            return f"https://drive.google.com/uc?export=download&id={file_id}"

    if "docs.google.com" in host and "/spreadsheets/" in parsed.path:
        match = re.search(r"/spreadsheets/d/([^/]+)", parsed.path)
        if match:
            sheet_id = match.group(1)
            gid = query.get("gid", ["0"])[0]
            export_fmt = "xlsx" if fmt == "excel" else "csv"
            return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format={export_fmt}&gid={gid}"

    return url


def _fetch_url_bytes(url: str):
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def read(current_url: str):
        request = Request(current_url, headers={
            "User-Agent": "Synthesis Suite/1.0 (+https://github.com/vectrasols/synthesis-suite)",
            "Accept": "text/csv,application/json,application/vnd.ms-excel,application/octet-stream,*/*",
        })
        with opener.open(request, timeout=45) as response:
            return response.read(), dict(response.headers), response.geturl()

    content, headers, final_url = read(url)
    confirm_url = _extract_google_drive_confirm_url(content, final_url)
    if confirm_url:
        content, headers, final_url = read(confirm_url)
    return content, headers, final_url


def _extract_google_drive_confirm_url(content: bytes, final_url: str) -> Optional[str]:
    parsed = urlparse(final_url)
    if "drive.google.com" not in parsed.netloc.lower() or not _looks_like_html(content):
        return None
    text = content[:300000].decode("utf-8", errors="ignore")
    match = re.search(r'href="([^"]*(?:uc|download)[^"]*confirm=[^"]+)"', text)
    if not match:
        return None
    return urljoin("https://drive.google.com", html.unescape(match.group(1)))


def _infer_url_format(original_url: str, final_url: str, headers: Dict[str, str], fmt: str) -> str:
    if fmt != "auto":
        return fmt

    candidates = [original_url, final_url, _content_disposition_filename(headers)]
    for candidate in candidates:
        ext = os.path.splitext(urlparse(candidate or "").path)[1].lower()
        if ext == ".json":
            return "json"
        if ext == ".tsv":
            return "tsv"
        if ext in (".xlsx", ".xls"):
            return "excel"
        if ext == ".csv":
            return "csv"

    content_type = (headers.get("Content-Type") or headers.get("content-type") or "").lower()
    if "json" in content_type:
        return "json"
    if "spreadsheet" in content_type or "excel" in content_type:
        return "excel"
    if "tab-separated" in content_type:
        return "tsv"
    return "csv"


def _content_disposition_filename(headers: Dict[str, str]) -> str:
    value = headers.get("Content-Disposition") or headers.get("content-disposition") or ""
    match = re.search(r"filename\*=UTF-8''([^;]+)|filename=\"?([^\";]+)", value)
    if not match:
        return ""
    return unquote(match.group(1) or match.group(2) or "")


def _read_url_content(content: bytes, fmt: str) -> pd.DataFrame:
    if _looks_like_html(content):
        raise ValueError(
            "The URL returned a web page instead of a downloadable data file. "
            "For Google Drive, make sure the file is shared with link access and points to a CSV, Excel, JSON, or TSV file."
        )

    bio = BytesIO(content)
    try:
        if fmt == "csv":
            return pd.read_csv(bio)
        if fmt == "json":
            return pd.read_json(bio)
        if fmt == "tsv":
            return pd.read_csv(bio, sep="\t")
        if fmt == "excel":
            return pd.read_excel(bio)
    except pd.errors.ParserError as exc:
        raise ValueError(
            "Could not parse the URL content as a dataset. "
            "Use a direct download link, or choose the correct format in the URL import dialog."
        ) from exc
    raise ValueError(f"Unknown format: {fmt}")


def _looks_like_html(content: bytes) -> bool:
    sample = content[:2048].lstrip().lower()
    return sample.startswith(b"<!doctype html") or sample.startswith(b"<html") or b"<html" in sample[:500]


def _validate_url_frame(df: pd.DataFrame, content: bytes):
    if df.empty or len(df.columns) == 0:
        raise ValueError("The URL did not contain any tabular data.")
    if len(df.columns) != 1:
        return
    text = " ".join([str(df.columns[0]), content[:1500].decode("utf-8", errors="ignore")]).lower()
    html_markers = ["<!doctype html", "<html", "google drive", "error 404", "access denied", "sign in"]
    if any(marker in text for marker in html_markers):
        raise ValueError(
            "The URL returned a message page, not a dataset. "
            "Use a public direct-download link for the file."
        )


def load_from_text(text: str) -> pd.DataFrame:
    if "\t" in text:
        return pd.read_csv(StringIO(text), sep="\t")
    elif "," in text:
        return pd.read_csv(StringIO(text))
    else:
        return pd.read_csv(StringIO(text), sep=r"\s+")


def load_sample(name: str) -> pd.DataFrame:
    """Return deterministic sample datasets used by demos and smoke tests."""
    key = name.strip().lower().replace("-", "_")

    if key == "iris":
        dataset = load_iris(as_frame=True)
        df = dataset.frame.copy()
        df["target"] = dataset.target
        return df

    if key == "breast_cancer":
        dataset = load_breast_cancer(as_frame=True)
        df = dataset.frame.copy()
        df["target"] = dataset.target
        return df

    if key == "digits":
        dataset = load_digits(as_frame=True)
        df = dataset.frame.copy()
        df["target"] = dataset.target
        return df

    rng = np.random.default_rng(42)

    if key == "sales":
        rows = 160
        marketing = rng.normal(5200, 1400, rows).clip(800, 9500)
        visits = rng.normal(26000, 7200, rows).clip(2500, 52000)
        discount = rng.uniform(0, 0.35, rows)
        support_score = rng.normal(82, 8, rows).clip(45, 100)
        sales = (
            18000
            + marketing * 2.4
            + visits * 0.72
            + support_score * 180
            - discount * 9000
            + rng.normal(0, 3500, rows)
        )
        return pd.DataFrame({
            "Marketing Spend": marketing.round(2),
            "Website Visits": visits.round(0).astype(int),
            "Discount Rate": discount.round(3),
            "Support Score": support_score.round(1),
            "Sales": sales.round(2),
        })

    if key == "weather":
        rows = 90
        days = pd.date_range("2026-01-01", periods=rows, freq="D")
        temperature = rng.normal(22, 7, rows)
        humidity = rng.normal(58, 15, rows).clip(20, 98)
        wind_speed = rng.gamma(2.2, 4.0, rows)
        rainfall = rng.gamma(1.4, 2.8, rows)
        conditions = np.array(["Sunny", "Cloudy", "Rain", "Storm", "Fog"])
        condition = rng.choice(conditions, rows, p=[0.36, 0.28, 0.22, 0.07, 0.07])
        df = pd.DataFrame({
            "Date": days.astype(str),
            "Temperature": temperature.round(1),
            "Humidity": humidity.round(1),
            "Wind Speed": wind_speed.round(1),
            "Rainfall": rainfall.round(1),
            "Condition": condition,
        })
        df.loc[df.index[::17], "Humidity"] = np.nan
        df.loc[df.index[::23], "Condition"] = np.nan
        return df

    if key == "ecommerce":
        rows = 140
        categories = np.array(["Books", "Electronics", "Home", "Beauty", "Sports"])
        channels = np.array(["Organic", "Ads", "Email", "Referral"])
        units = rng.integers(1, 9, rows)
        unit_price = rng.lognormal(mean=3.7, sigma=0.45, size=rows)
        return pd.DataFrame({
            "Order ID": [f"ORD-{10000 + i}" for i in range(rows)],
            "Category": rng.choice(categories, rows),
            "Channel": rng.choice(channels, rows),
            "Units": units,
            "Unit Price": unit_price.round(2),
            "Revenue": (units * unit_price).round(2),
            "Returned": rng.choice(["Yes", "No"], rows, p=[0.12, 0.88]),
        })

    raise ValueError(f"Unknown sample dataset: {name}")


# ─── Filtering ──────────────────────────────────────────────────────────────────

def apply_filter(col: str, condition: str, value: str) -> Dict[str, Any]:
    if store.df is None:
        raise ValueError("No data loaded")
    if col not in store.df.columns:
        raise ValueError(f"Column '{col}' not found")

    if store.df_filtered is None:
        store.df_filtered = store.df.copy()

    col_data = store.df_filtered[col]

    try:
        num_val = float(value)
        is_numeric = True
    except ValueError:
        num_val = None
        is_numeric = False

    if condition == "equals":
        mask = pd.to_numeric(col_data, errors="coerce") == num_val if is_numeric else col_data.astype(str) == value
    elif condition == "not_equals":
        mask = pd.to_numeric(col_data, errors="coerce") != num_val if is_numeric else col_data.astype(str) != value
    elif condition == "gt":
        mask = pd.to_numeric(col_data, errors="coerce") > num_val
    elif condition == "lt":
        mask = pd.to_numeric(col_data, errors="coerce") < num_val
    elif condition == "gte":
        mask = pd.to_numeric(col_data, errors="coerce") >= num_val
    elif condition == "lte":
        mask = pd.to_numeric(col_data, errors="coerce") <= num_val
    elif condition == "contains":
        mask = col_data.astype(str).str.contains(value, case=False, na=False)
    elif condition == "in_range":
        parts = value.split(",")
        lo, hi = float(parts[0].strip()), float(parts[1].strip())
        numeric_col = pd.to_numeric(col_data, errors="coerce")
        mask = (numeric_col >= lo) & (numeric_col <= hi)
    else:
        raise ValueError(f"Unknown condition: {condition}")

    store.df_filtered = store.df_filtered[mask].reset_index(drop=True)
    filter_desc = f"{col} {condition} '{value}'"
    store.active_filters[col] = filter_desc

    return {
        "filtered_rows": len(store.df_filtered),
        "filter_desc": filter_desc,
        "active_filters": store.active_filters,
    }


def clear_filters() -> Dict[str, Any]:
    if store.df is not None:
        store.df_filtered = store.df.copy()
    store.active_filters = {}
    return {"filtered_rows": len(store.df_filtered) if store.df_filtered is not None else 0}


def get_column_unique_values(col: str) -> List[str]:
    if store.df is None or col not in store.df.columns:
        return []
    unique = store.df[col].dropna().unique()
    if len(unique) <= 100:
        return [str(v) for v in sorted(unique, key=str)]
    return []


def get_preview_rows(n: int = 20, use_cleaned: bool = False) -> Dict[str, Any]:
    df = store.df_cleaned if use_cleaned else store.df
    if df is None:
        return {"columns": [], "rows": []}
    preview = df.head(n)
    return {
        "columns": list(preview.columns),
        "rows": [[str(v)[:50] for v in row] for row in preview.values.tolist()],
    }


# ─── Cleaning ───────────────────────────────────────────────────────────────────

def _numeric_frame(df: pd.DataFrame, exclude: Optional[str] = None) -> pd.DataFrame:
    cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if exclude in cols:
        cols.remove(exclude)
    X = df[cols].replace([np.inf, -np.inf], np.nan)
    return X.fillna(X.mean(numeric_only=True)).fillna(0)


def _prepare_target(series: pd.Series):
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(series.median())
    mode = series.mode(dropna=True)
    fallback = mode.iloc[0] if not mode.empty else "Unknown"
    return series.fillna(fallback)


def _is_classification_target(series: pd.Series) -> bool:
    if not pd.api.types.is_numeric_dtype(series):
        return True
    return series.nunique(dropna=True) <= min(20, max(2, int(len(series) * 0.2)))


def _as_class_labels(series: pd.Series) -> np.ndarray:
    return LabelEncoder().fit_transform(_prepare_target(series).astype(str))


def _safe_k(k: int, available: int) -> int:
    return max(1, min(int(k), int(available)))


def _rename_selected(columns: List[str], suffix: str) -> List[str]:
    return [f"{col}{suffix}" for col in columns]


def _distribution_fill(df: pd.DataFrame, log: List[str]) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    mean_cols, median_cols, mode_cols = [], [], []

    for col in numeric_cols:
        if not df[col].isna().any():
            continue
        skew = float(df[col].skew(skipna=True)) if df[col].notna().sum() > 2 else 0.0
        if abs(skew) <= 0.75:
            df[col] = df[col].fillna(df[col].mean())
            mean_cols.append(col)
        else:
            df[col] = df[col].fillna(df[col].median())
            median_cols.append(col)

    for col in df.columns.difference(numeric_cols):
        if not df[col].isna().any():
            continue
        mode = df[col].mode(dropna=True)
        df[col] = df[col].fillna(mode.iloc[0] if not mode.empty else "Unknown")
        mode_cols.append(col)

    if mean_cols:
        log.append(f"Filled near-normal numeric columns with mean: {', '.join(mean_cols)}")
    if median_cols:
        log.append(f"Filled skewed numeric columns with median: {', '.join(median_cols)}")
    if mode_cols:
        log.append(f"Filled categorical columns with mode: {', '.join(mode_cols)}")
    return df


def _smart_numeric_conversion(series: pd.Series, column_name: str):
    original = series.copy()
    text = original.astype("string").str.strip()
    non_empty = text.dropna()
    non_empty = non_empty[non_empty != ""]

    if non_empty.empty:
        return pd.to_numeric(original, errors="coerce"), "Converted empty/non-missing values to numeric"

    normalized = non_empty.str.lower().str.replace(r"[^a-z0-9.+-]", "", regex=True)
    binary_maps = [
        {
            "m": 1, "male": 1, "mmale": 1,
            "f": 0, "female": 0, "ffemale": 0,
        },
        {
            "yes": 1, "y": 1, "true": 1, "t": 1,
            "no": 0, "n": 0, "false": 0,
        },
    ]

    for mapping in binary_maps:
        unique_values = set(normalized.dropna().unique())
        if unique_values and unique_values.issubset(mapping.keys()):
            converted = normalized.map(mapping).astype("float")
            converted = converted.reindex(series.index)
            return converted, f"Mapped binary labels in '{column_name}' to numeric values"

    converted = pd.to_numeric(text, errors="coerce")
    invalid_mask = text.notna() & (text != "") & converted.isna()
    if invalid_mask.any():
        examples = sorted(set(text[invalid_mask].astype(str).head(5)))
        raise ValueError(
            f"Column '{column_name}' contains non-numeric values ({', '.join(examples)}). "
            "Use Encoding for categorical data, or clean the values before numeric conversion."
        )

    return converted, f"Converted '{column_name}' to numeric"


def _summarize_step(log: List[str]) -> str:
    if not log:
        return "No-op cleaning pass"
    label = "; ".join(log[:2])
    if len(log) > 2:
        label += f"; +{len(log) - 2} more"
    return label[:140]


def _feature_scores(df: pd.DataFrame, target_col: str, method: str, k: int):
    X = _numeric_frame(df, target_col)
    if X.empty:
        raise ValueError("Feature selection requires at least one numeric feature column.")

    target = _prepare_target(df[target_col])
    classification = _is_classification_target(target)
    y_class = _as_class_labels(target)
    y_reg = pd.to_numeric(target, errors="coerce").fillna(pd.to_numeric(target, errors="coerce").median())

    if method == "variance":
        selector = VarianceThreshold()
        selector.fit(X)
        scores = selector.variances_
    elif method == "correlation":
        y_num = y_class if classification else y_reg
        scores = np.array([abs(pd.Series(X[col]).corr(pd.Series(y_num))) for col in X.columns])
        scores = np.nan_to_num(scores, nan=0.0)
    elif method == "info_gain":
        scores = mutual_info_classif(X, y_class, random_state=42)
    elif method == "chi2":
        X_non_negative = MinMaxScaler().fit_transform(X)
        selector = SelectKBest(chi2, k=_safe_k(k, X.shape[1]))
        selector.fit(X_non_negative, y_class)
        scores = selector.scores_
    elif method == "fisher":
        scores = []
        overall_mean = X.mean(axis=0)
        for col in X.columns:
            between, within = 0.0, 0.0
            for cls in np.unique(y_class):
                values = X.loc[y_class == cls, col]
                if values.empty:
                    continue
                between += len(values) * float((values.mean() - overall_mean[col]) ** 2)
                within += float(((values - values.mean()) ** 2).sum())
            scores.append(between / (within + 1e-12))
        scores = np.array(scores)
    elif method == "wrapper_rfe":
        estimator = LogisticRegression(max_iter=1000) if classification else LinearRegression()
        selector = RFE(estimator, n_features_to_select=_safe_k(k, X.shape[1]))
        selector.fit(StandardScaler().fit_transform(X), y_class if classification else y_reg)
        scores = (X.shape[1] - selector.ranking_ + 1).astype(float)
    elif method == "embedded":
        if classification:
            estimator = RandomForestClassifier(n_estimators=160, random_state=42)
            estimator.fit(X, y_class)
            scores = estimator.feature_importances_
        else:
            estimator = Lasso(alpha=0.01, max_iter=5000)
            estimator.fit(StandardScaler().fit_transform(X), y_reg)
            scores = np.abs(estimator.coef_)
    else:
        raise ValueError(f"Unknown feature selection method: {method}")

    scores = np.nan_to_num(scores, nan=0.0, posinf=0.0, neginf=0.0)
    ranking = sorted(zip(X.columns, scores), key=lambda item: item[1], reverse=True)
    return ranking[:_safe_k(k, len(ranking))]


def _apply_feature_extraction(df: pd.DataFrame, method: str, target_col: Optional[str], components: int):
    X = _numeric_frame(df, target_col)
    if X.empty:
        raise ValueError("Feature extraction requires at least one numeric feature column.")

    X_scaled = StandardScaler().fit_transform(X)
    n_components = _safe_k(components, X.shape[1])
    metadata: Dict[str, Any] = {}

    if method == "pca":
        model = PCA(n_components=n_components, random_state=42)
        transformed = model.fit_transform(X_scaled)
        names = [f"pca_{i + 1}" for i in range(transformed.shape[1])]
        metadata["Explained variance"] = round(float(model.explained_variance_ratio_.sum()), 4)
    elif method == "lda":
        if not target_col or target_col not in df.columns:
            raise ValueError("LDA feature extraction requires a target column.")
        y = _as_class_labels(df[target_col])
        max_components = min(X.shape[1], max(1, len(np.unique(y)) - 1))
        n_components = _safe_k(components, max_components)
        model = LinearDiscriminantAnalysis(n_components=n_components)
        transformed = model.fit_transform(X_scaled, y)
        names = [f"lda_{i + 1}" for i in range(transformed.shape[1])]
        metadata["Explained variance"] = round(float(getattr(model, "explained_variance_ratio_", np.array([0])).sum()), 4)
    elif method == "autoencoder":
        hidden = n_components
        model = MLPRegressor(
            hidden_layer_sizes=(hidden,),
            activation="tanh",
            max_iter=700,
            random_state=42,
            learning_rate_init=0.01,
            early_stopping=True,
        )
        model.fit(X_scaled, X_scaled)
        hidden_layer = np.tanh(np.dot(X_scaled, model.coefs_[0]) + model.intercepts_[0])
        transformed = hidden_layer
        names = [f"autoencoder_{i + 1}" for i in range(transformed.shape[1])]
        reconstructed = model.predict(X_scaled)
        metadata["Reconstruction RMSE"] = round(float(np.sqrt(np.mean((X_scaled - reconstructed) ** 2))), 4)
    else:
        raise ValueError(f"Unknown feature extraction method: {method}")

    extracted = pd.DataFrame(transformed, columns=names, index=df.index)
    if target_col and target_col in df.columns:
        extracted[target_col] = df[target_col].values
    return extracted, metadata


def apply_cleaning(
    missing_method: str,
    remove_outliers: bool,
    outlier_threshold: float,
    dtype_column: Optional[str] = None,
    dtype_convert: Optional[str] = None,
    scale_method: Optional[str] = None,
    binarize_column: Optional[str] = None,
    binarize_threshold: float = 0.0,
    encode_column: Optional[str] = None,
    encode_method: Optional[str] = None,
    selection_target: Optional[str] = None,
    selection_method: Optional[str] = None,
    selection_k: int = 5,
    extraction_target: Optional[str] = None,
    extraction_method: Optional[str] = None,
    extraction_components: int = 2,
) -> Dict[str, Any]:
    if store.df_cleaned is None:
        raise ValueError("No data loaded")

    log = []
    df = store.df_cleaned.copy()
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    # Missing values
    if missing_method == "drop":
        before = len(df)
        df = df.dropna()
        log.append(f"Dropped {before - len(df)} rows with missing values")
    elif missing_method == "mean":
        df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].mean())
        log.append("Filled missing values with mean")
    elif missing_method == "median":
        df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
        log.append("Filled missing values with median")
    elif missing_method == "ffill":
        df = df.ffill()
        log.append("Filled missing values with forward fill")
    elif missing_method == "bfill":
        df = df.bfill()
        log.append("Filled missing values with backward fill")
    elif missing_method == "distribution":
        df = _distribution_fill(df, log)

    # Outliers (IQR)
    if remove_outliers:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        Q1 = df[numeric_cols].quantile(0.25)
        Q3 = df[numeric_cols].quantile(0.75)
        IQR = Q3 - Q1
        before = len(df)
        df = df[~((df[numeric_cols] < (Q1 - outlier_threshold * IQR)) |
                  (df[numeric_cols] > (Q3 + outlier_threshold * IQR))).any(axis=1)]
        removed = before - len(df)
        if removed > 0:
            log.append(f"Removed {removed} outliers (IQR method, threshold={outlier_threshold})")

    # Data type conversion
    if dtype_column and dtype_column in df.columns:
        if dtype_convert == "numeric":
            df[dtype_column], conversion_log = _smart_numeric_conversion(df[dtype_column], dtype_column)
            log.append(conversion_log)
        elif dtype_convert == "categorical":
            df[dtype_column] = df[dtype_column].astype("category")
            log.append(f"Converted '{dtype_column}' to categorical")

    # Binarization
    if binarize_column:
        target_cols = df.select_dtypes(include=[np.number]).columns.tolist() if binarize_column == "__all_numeric__" else [binarize_column]
        protected_cols = {col for col in (selection_target, extraction_target) if col}
        target_cols = [col for col in target_cols if col not in protected_cols]
        target_cols = [col for col in target_cols if col in df.columns and pd.api.types.is_numeric_dtype(df[col])]
        if target_cols:
            transformer = Binarizer(threshold=binarize_threshold)
            df[target_cols] = transformer.fit_transform(df[target_cols])
            log.append(f"Binarized {len(target_cols)} numeric column(s) at threshold {binarize_threshold:g}")

    # Encoding
    if encode_column and encode_column in df.columns and encode_method:
        source = df[encode_column].astype(str).fillna("Unknown")
        if encode_method == "label":
            df[encode_column] = LabelEncoder().fit_transform(source)
            log.append(f"Label encoded '{encode_column}'")
        elif encode_method == "factorize":
            df[encode_column] = pd.factorize(source)[0]
            log.append(f"Factorized '{encode_column}'")
        elif encode_method == "onehot":
            encoded = pd.get_dummies(source, prefix=encode_column, dtype=int)
            df = pd.concat([df.drop(columns=[encode_column]), encoded], axis=1)
            log.append(f"One-hot encoded '{encode_column}' into {len(encoded.columns)} columns")

    # Scaling
    if scale_method:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if scale_method == "standard":
            scaler = StandardScaler()
        else:
            scaler = MinMaxScaler()
        df[numeric_cols] = scaler.fit_transform(df[numeric_cols])
        log.append(f"Scaled numeric columns using {'Standard' if scale_method == 'standard' else 'MinMax'} Scaler")

    # Feature selection
    if selection_method and selection_target and selection_target in df.columns:
        selected = _feature_scores(df, selection_target, selection_method, selection_k)
        selected_cols = [col for col, _ in selected]
        keep_cols = selected_cols + ([selection_target] if selection_target not in selected_cols else [])
        df = df[keep_cols]
        score_text = ", ".join(f"{col}={score:.4g}" for col, score in selected[:5])
        log.append(f"Selected top {len(selected_cols)} features using {selection_method.replace('_', ' ')}: {score_text}")

    # Feature extraction
    if extraction_method:
        df, metadata = _apply_feature_extraction(df, extraction_method, extraction_target, extraction_components)
        details = ", ".join(f"{k}: {v}" for k, v in metadata.items())
        suffix = f" ({details})" if details else ""
        log.append(f"Extracted {extraction_method.upper()} features: {df.shape[1]} column(s){suffix}")

    if log:
        store.push_cleaning_step(_summarize_step(log), df)
    else:
        store.df_cleaned = df
        log.append("No cleaning changes selected")

    return {
        "log": log,
        "rows": len(df),
        "cols": len(df.columns),
        "history": store.get_cleaning_history(),
        "info": store.frame_info(df),
    }


def remove_duplicates() -> Dict[str, Any]:
    if store.df_cleaned is None:
        raise ValueError("No data loaded")
    before = len(store.df_cleaned)
    df = store.df_cleaned.drop_duplicates()
    removed = before - len(df)
    if removed:
        store.push_cleaning_step(f"Removed {removed} duplicate rows", df)
    else:
        store.df_cleaned = df
    return {
        "removed": removed,
        "rows": len(store.df_cleaned),
        "history": store.get_cleaning_history(),
        "info": store.frame_info(store.df_cleaned),
    }


def get_cleaning_history() -> Dict[str, Any]:
    return store.get_cleaning_history()


def rollback_cleaning(step_index: int) -> Dict[str, Any]:
    return store.rollback_cleaning(step_index)


def export_cleaned_csv() -> bytes:
    if store.df_cleaned is None:
        raise ValueError("No cleaned data available")
    return store.df_cleaned.to_csv(index=False).encode("utf-8")
