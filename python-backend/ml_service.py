"""
ml_service.py — ML model training and user-dataset algorithms.
Ported from main.py with all sklearn/scipy logic preserved.
Returns structured results (metrics + optional Plotly chart JSON).
"""

import math
import random
import json
from collections import deque
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder

from sklearn.model_selection import train_test_split, KFold
from sklearn.preprocessing import StandardScaler, MinMaxScaler, OneHotEncoder, PolynomialFeatures, LabelEncoder
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge, Lasso
from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
from sklearn.ensemble import (
    RandomForestRegressor,
    RandomForestClassifier,
    GradientBoostingRegressor,
    GradientBoostingClassifier,
    AdaBoostRegressor,
    AdaBoostClassifier,
    BaggingRegressor,
    BaggingClassifier,
    StackingRegressor,
    StackingClassifier,
    IsolationForest,
)
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVR, SVC, OneClassSVM
from sklearn.neighbors import KNeighborsRegressor, KNeighborsClassifier
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA, FastICA
from sklearn.semi_supervised import SelfTrainingClassifier
from sklearn.metrics import (mean_squared_error, r2_score, accuracy_score,
                              classification_report, silhouette_score)
from sklearn.datasets import make_blobs, make_classification, make_moons, load_iris, load_breast_cancer, load_digits

from data_service import store


# ─── Model Training ─────────────────────────────────────────────────────────────

UNSUPERVISED_TRAINING_MODELS = {
    "kmeans",
    "dbscan",
    "pca_projection",
    "ica_projection",
    "zscore_anomaly",
    "isolation_forest",
    "one_class_svm",
}

REGRESSION_TRAINING_MODELS = {
    "linear_regression",
    "polynomial_regression",
    "ridge_regression",
    "lasso_regression",
    "decision_tree_regression",
    "random_forest_regression",
    "gradient_boosting_regression",
    "adaboost_regression",
    "bagging_regression",
    "stacking_regression",
    "svr",
    "knn_regression",
}

CLASSIFICATION_TRAINING_MODELS = {
    "logistic_regression",
    "naive_bayes",
    "decision_tree_classification",
    "random_forest_classification",
    "gradient_boosting_classification",
    "adaboost_classification",
    "bagging_classification",
    "stacking_classification",
    "svm_classification",
    "knn_classification",
}

SEMI_SUPERVISED_TRAINING_MODELS = {
    "self_training_classification",
}


def _numeric_features(df: pd.DataFrame, target: Optional[str]) -> pd.DataFrame:
    X = df.drop(columns=[target]) if target else df.copy()
    numeric_cols = X.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) == 0:
        raise ValueError("No numeric feature columns available for this model.")
    X = X[numeric_cols].replace([np.inf, -np.inf], np.nan)
    return X.fillna(X.mean(numeric_only=True)).fillna(0)


def _prepared_target(y: pd.Series, for_regression: bool) -> pd.Series:
    if for_regression:
        y_num = pd.to_numeric(y, errors="coerce")
        return y_num.fillna(y_num.mean())
    mode = y.mode(dropna=True)
    fallback = mode.iloc[0] if not mode.empty else "Unknown"
    return y.fillna(fallback)


def _scale_features(X_train, X_test, scale_data: bool, scale_type: str):
    if not scale_data:
        return X_train.values, X_test.values
    scaler = StandardScaler() if scale_type == "standard" else MinMaxScaler()
    return scaler.fit_transform(X_train), scaler.transform(X_test)


def _scale_all_features(X: pd.DataFrame, scale_data: bool, scale_type: str):
    if not scale_data:
        return X.values
    scaler = StandardScaler() if scale_type == "standard" else MinMaxScaler()
    return scaler.fit_transform(X)


def _safe_neighbors(n_neighbors: int, n_samples: int) -> int:
    return max(1, min(int(n_neighbors), max(1, int(n_samples) - 1)))


def _regression_metrics(y_test, y_pred) -> Dict[str, float]:
    mse = float(mean_squared_error(y_test, y_pred))
    return {
        "MSE": round(mse, 4),
        "RMSE": round(float(np.sqrt(mse)), 4),
        "R²": round(float(r2_score(y_test, y_pred)), 4),
    }


def _classification_metrics(y_test, y_pred) -> Dict[str, float]:
    return {"Accuracy": round(float(accuracy_score(y_test, y_pred)), 4)}


def train_model(
    model_type: str,
    target: Optional[str],
    test_size: float,
    scale_data: bool,
    scale_type: str,
    n_estimators: int,
    max_depth: int,
    n_neighbors: int,
    n_clusters: int,
) -> Dict[str, Any]:
    if store.df_cleaned is None:
        raise ValueError("No cleaned data available. Load data first.")
    if target and target not in store.df_cleaned.columns:
        raise ValueError(f"Target column '{target}' not found")

    df = store.df_cleaned
    needs_target = model_type not in UNSUPERVISED_TRAINING_MODELS
    if needs_target and not target:
        raise ValueError("Select a target column for supervised or semi-supervised models.")

    X = _numeric_features(df, target)

    results = {
        "model": model_type,
        "train_samples": len(X),
        "test_samples": 0,
        "metrics": {},
        "report": None,
    }

    # ── Unsupervised, dimensionality-reduction and anomaly models ──────────────
    if model_type in UNSUPERVISED_TRAINING_MODELS:
        X_s = _scale_all_features(X, scale_data, scale_type)

        if model_type == "kmeans":
            clusters = min(n_clusters, max(2, len(X_s) - 1))
            m = KMeans(n_clusters=clusters, n_init=10, random_state=42)
            labels = m.fit_predict(X_s)
            metrics = {
                "Clusters": int(len(set(labels))),
                "Inertia": round(float(m.inertia_), 4),
            }
            if len(set(labels)) > 1 and len(set(labels)) < len(labels):
                metrics["Silhouette Score"] = round(float(silhouette_score(X_s, labels)), 4)
            results["metrics"] = metrics

        elif model_type == "dbscan":
            min_samples = max(2, _safe_neighbors(n_neighbors, len(X_s)))
            eps = 0.8 if scale_type == "standard" else 0.12
            m = DBSCAN(eps=eps, min_samples=min_samples)
            labels = m.fit_predict(X_s)
            cluster_ids = {int(v) for v in labels if v != -1}
            metrics = {
                "Clusters": len(cluster_ids),
                "Noise Points": int(np.sum(labels == -1)),
                "Min Samples": min_samples,
            }
            if len(set(labels)) > 1 and len(set(labels)) < len(labels):
                metrics["Silhouette Score"] = round(float(silhouette_score(X_s, labels)), 4)
            results["metrics"] = metrics

        elif model_type == "pca_projection":
            components = min(2, X_s.shape[1])
            pca = PCA(n_components=components, random_state=42)
            pca.fit_transform(X_s)
            explained = pca.explained_variance_ratio_
            results["metrics"] = {
                "Components": components,
                "Explained Variance": round(float(explained.sum()), 4),
                "PC1 Variance": round(float(explained[0]), 4),
                "PC2 Variance": round(float(explained[1]), 4) if components > 1 else 0,
            }

        elif model_type == "ica_projection":
            components = min(2, X_s.shape[1])
            ica = FastICA(n_components=components, random_state=42, max_iter=600, whiten="unit-variance")
            transformed = ica.fit_transform(X_s)
            std = transformed.std(axis=0)
            std[std == 0] = 1
            kurtosis = np.mean(((transformed - transformed.mean(axis=0)) / std) ** 4, axis=0) - 3
            results["metrics"] = {
                "Components": components,
                "Mean Abs Kurtosis": round(float(np.mean(np.abs(kurtosis))), 4),
                "Iterations": int(getattr(ica, "n_iter_", 0)),
            }

        elif model_type == "zscore_anomaly":
            std = X_s.std(axis=0)
            std[std == 0] = 1
            z = np.abs((X_s - X_s.mean(axis=0)) / std)
            mask = (z > 3).any(axis=1)
            results["metrics"] = {
                "Anomalies": int(mask.sum()),
                "Anomaly Rate": round(float(mask.mean()), 4),
                "Threshold": 3,
            }

        elif model_type == "isolation_forest":
            contamination = 0.08
            m = IsolationForest(contamination=contamination, random_state=42)
            pred = m.fit_predict(X_s)
            anomalies = int(np.sum(pred == -1))
            results["metrics"] = {
                "Anomalies": anomalies,
                "Anomaly Rate": round(float(anomalies / len(pred)), 4),
                "Contamination": contamination,
            }

        elif model_type == "one_class_svm":
            m = OneClassSVM(nu=0.08, kernel="rbf", gamma="scale")
            pred = m.fit_predict(X_s)
            anomalies = int(np.sum(pred == -1))
            results["metrics"] = {
                "Anomalies": anomalies,
                "Anomaly Rate": round(float(anomalies / len(pred)), 4),
                "Nu": 0.08,
            }

        return results

    for_regression = model_type in REGRESSION_TRAINING_MODELS
    y = _prepared_target(df[target], for_regression)

    if for_regression and y.isna().all():
        raise ValueError("Target column must contain numeric values for regression models.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42
    )
    X_train_s, X_test_s = _scale_features(X_train, X_test, scale_data, scale_type)
    results["train_samples"] = len(X_train)
    results["test_samples"] = len(X_test)

    # ── Regression models ──────────────────────────────────────────────────────
    if model_type == "linear_regression":
        m = LinearRegression(); m.fit(X_train_s, y_train)
        y_pred = m.predict(X_test_s)
        results["metrics"] = _regression_metrics(y_test, y_pred)

    elif model_type == "polynomial_regression":
        poly = PolynomialFeatures(degree=2, include_bias=False)
        X_train_p = poly.fit_transform(X_train_s)
        X_test_p = poly.transform(X_test_s)
        m = LinearRegression(); m.fit(X_train_p, y_train)
        y_pred = m.predict(X_test_p)
        results["metrics"] = _regression_metrics(y_test, y_pred)
        results["metrics"]["Polynomial Features"] = int(X_train_p.shape[1])

    elif model_type == "ridge_regression":
        m = Ridge(); m.fit(X_train_s, y_train)
        y_pred = m.predict(X_test_s)
        results["metrics"] = _regression_metrics(y_test, y_pred)

    elif model_type == "lasso_regression":
        m = Lasso(); m.fit(X_train_s, y_train)
        y_pred = m.predict(X_test_s)
        results["metrics"] = _regression_metrics(y_test, y_pred)

    elif model_type == "decision_tree_regression":
        m = DecisionTreeRegressor(max_depth=max_depth, random_state=42); m.fit(X_train_s, y_train)
        y_pred = m.predict(X_test_s)
        results["metrics"] = _regression_metrics(y_test, y_pred)

    elif model_type == "random_forest_regression":
        m = RandomForestRegressor(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        m.fit(X_train_s, y_train); y_pred = m.predict(X_test_s)
        results["metrics"] = _regression_metrics(y_test, y_pred)

    elif model_type == "gradient_boosting_regression":
        depth = max(1, min(max_depth, 5))
        m = GradientBoostingRegressor(n_estimators=n_estimators, max_depth=depth, random_state=42)
        m.fit(X_train_s, y_train); y_pred = m.predict(X_test_s)
        results["metrics"] = _regression_metrics(y_test, y_pred)

    elif model_type == "adaboost_regression":
        base = DecisionTreeRegressor(max_depth=max(1, min(max_depth, 5)), random_state=42)
        m = AdaBoostRegressor(estimator=base, n_estimators=n_estimators, random_state=42)
        m.fit(X_train_s, y_train); y_pred = m.predict(X_test_s)
        results["metrics"] = _regression_metrics(y_test, y_pred)

    elif model_type == "bagging_regression":
        base = DecisionTreeRegressor(max_depth=max_depth, random_state=42)
        m = BaggingRegressor(estimator=base, n_estimators=n_estimators, random_state=42)
        m.fit(X_train_s, y_train); y_pred = m.predict(X_test_s)
        results["metrics"] = _regression_metrics(y_test, y_pred)

    elif model_type == "stacking_regression":
        safe_k = _safe_neighbors(n_neighbors, len(X_train_s))
        estimators = [
            ("ridge", Ridge()),
            ("rf", RandomForestRegressor(n_estimators=max(10, min(n_estimators, 120)), max_depth=max_depth, random_state=42)),
            ("knn", KNeighborsRegressor(n_neighbors=safe_k)),
        ]
        m = StackingRegressor(estimators=estimators, final_estimator=LinearRegression(), cv=3)
        m.fit(X_train_s, y_train); y_pred = m.predict(X_test_s)
        results["metrics"] = _regression_metrics(y_test, y_pred)

    elif model_type == "svr":
        m = SVR(); m.fit(X_train_s, y_train); y_pred = m.predict(X_test_s)
        results["metrics"] = _regression_metrics(y_test, y_pred)

    elif model_type == "knn_regression":
        m = KNeighborsRegressor(n_neighbors=_safe_neighbors(n_neighbors, len(X_train_s))); m.fit(X_train_s, y_train)
        y_pred = m.predict(X_test_s)
        results["metrics"] = _regression_metrics(y_test, y_pred)

    # ── Classification models ──────────────────────────────────────────────────
    elif model_type == "logistic_regression":
        m = LogisticRegression(max_iter=1000); m.fit(X_train_s, y_train)
        y_pred = m.predict(X_test_s)
        results["metrics"] = _classification_metrics(y_test, y_pred)
        results["report"] = classification_report(y_test, y_pred, zero_division=0)

    elif model_type == "naive_bayes":
        m = GaussianNB(); m.fit(X_train_s, y_train)
        y_pred = m.predict(X_test_s)
        results["metrics"] = _classification_metrics(y_test, y_pred)
        results["report"] = classification_report(y_test, y_pred, zero_division=0)

    elif model_type == "decision_tree_classification":
        m = DecisionTreeClassifier(max_depth=max_depth, random_state=42); m.fit(X_train_s, y_train)
        y_pred = m.predict(X_test_s)
        results["metrics"] = _classification_metrics(y_test, y_pred)
        results["report"] = classification_report(y_test, y_pred, zero_division=0)

    elif model_type == "random_forest_classification":
        m = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        m.fit(X_train_s, y_train); y_pred = m.predict(X_test_s)
        results["metrics"] = _classification_metrics(y_test, y_pred)
        results["report"] = classification_report(y_test, y_pred, zero_division=0)

    elif model_type == "gradient_boosting_classification":
        depth = max(1, min(max_depth, 5))
        m = GradientBoostingClassifier(n_estimators=n_estimators, max_depth=depth, random_state=42)
        m.fit(X_train_s, y_train); y_pred = m.predict(X_test_s)
        results["metrics"] = _classification_metrics(y_test, y_pred)
        results["report"] = classification_report(y_test, y_pred, zero_division=0)

    elif model_type == "adaboost_classification":
        base = DecisionTreeClassifier(max_depth=max(1, min(max_depth, 5)), random_state=42)
        m = AdaBoostClassifier(estimator=base, n_estimators=n_estimators, random_state=42)
        m.fit(X_train_s, y_train); y_pred = m.predict(X_test_s)
        results["metrics"] = _classification_metrics(y_test, y_pred)
        results["report"] = classification_report(y_test, y_pred, zero_division=0)

    elif model_type == "bagging_classification":
        base = DecisionTreeClassifier(max_depth=max_depth, random_state=42)
        m = BaggingClassifier(estimator=base, n_estimators=n_estimators, random_state=42)
        m.fit(X_train_s, y_train); y_pred = m.predict(X_test_s)
        results["metrics"] = _classification_metrics(y_test, y_pred)
        results["report"] = classification_report(y_test, y_pred, zero_division=0)

    elif model_type == "stacking_classification":
        safe_k = _safe_neighbors(n_neighbors, len(X_train_s))
        estimators = [
            ("lr", LogisticRegression(max_iter=1000)),
            ("rf", RandomForestClassifier(n_estimators=max(10, min(n_estimators, 120)), max_depth=max_depth, random_state=42)),
            ("knn", KNeighborsClassifier(n_neighbors=safe_k)),
        ]
        m = StackingClassifier(estimators=estimators, final_estimator=LogisticRegression(max_iter=1000), cv=3)
        m.fit(X_train_s, y_train); y_pred = m.predict(X_test_s)
        results["metrics"] = _classification_metrics(y_test, y_pred)
        results["report"] = classification_report(y_test, y_pred, zero_division=0)

    elif model_type == "svm_classification":
        m = SVC(); m.fit(X_train_s, y_train); y_pred = m.predict(X_test_s)
        results["metrics"] = _classification_metrics(y_test, y_pred)
        results["report"] = classification_report(y_test, y_pred, zero_division=0)

    elif model_type == "knn_classification":
        m = KNeighborsClassifier(n_neighbors=_safe_neighbors(n_neighbors, len(X_train_s))); m.fit(X_train_s, y_train)
        y_pred = m.predict(X_test_s)
        results["metrics"] = _classification_metrics(y_test, y_pred)
        results["report"] = classification_report(y_test, y_pred, zero_division=0)

    # ── Semi-supervised models ─────────────────────────────────────────────────
    elif model_type == "self_training_classification":
        le = LabelEncoder()
        y_enc = le.fit_transform(y.astype(str))
        X_train, X_test, y_train_enc, y_test_enc = train_test_split(
            X, y_enc, test_size=test_size, random_state=42
        )
        X_train_s, X_test_s = _scale_features(X_train, X_test, scale_data, scale_type)
        rng = np.random.default_rng(42)
        y_semi = np.full_like(y_train_enc, -1)
        label_count = max(len(le.classes_), int(len(y_train_enc) * 0.35))
        labeled_idx = set(rng.choice(len(y_train_enc), size=min(label_count, len(y_train_enc)), replace=False))
        for cls in np.unique(y_train_enc):
            cls_idx = np.where(y_train_enc == cls)[0]
            if len(cls_idx):
                labeled_idx.add(int(rng.choice(cls_idx)))
        labeled_idx = np.array(sorted(labeled_idx))
        y_semi[labeled_idx] = y_train_enc[labeled_idx]
        m = SelfTrainingClassifier(SVC(probability=True, gamma="scale", random_state=42), threshold=0.75, max_iter=10)
        m.fit(X_train_s, y_semi)
        y_pred = m.predict(X_test_s)
        results["metrics"] = {
            "Accuracy": round(float(accuracy_score(y_test_enc, y_pred)), 4),
            "Labeled Seed Rate": round(float(len(labeled_idx) / len(y_train_enc)), 4),
            "Inferred Labels": int(np.sum(getattr(m, "labeled_iter_", np.array([])) > 0)),
        }
        results["report"] = classification_report(y_test_enc, y_pred, target_names=le.classes_, zero_division=0)

    else:
        raise ValueError(f"Unknown model type: {model_type}")

    return results


# ─── Algorithms Lab ─────────────────────────────────────────────────────────────

def run_algorithm(name: str) -> Dict[str, Any]:
    """Returns {'output': str, 'chart': plotly_json_or_None}.

    The Algorithms tab is intentionally limited to the currently loaded user
    dataset. Older canned/demo algorithms are not exposed here.
    """
    if store.df_cleaned is None:
        raise ValueError("Load or enter a dataset before running algorithms.")

    funcs = {
        "dataset_profile":     _run_user_dataset_profile,
        "correlation_matrix":  _run_user_correlation_matrix,
        "pca_user":            _run_user_pca,
        "kmeans_user":         _run_user_kmeans,
        "dbscan_user":         _run_user_dbscan,
        "zscore_user":         _run_user_zscore,
        "isolation_user":      _run_user_isolation_forest,
    }
    if name not in funcs:
        raise ValueError("This algorithm is not available because Synthesis only runs algorithms on your loaded dataset.")
    return funcs[name]()


# ─── User dataset algorithms ──────────────────────────────────────────────────

def _user_df() -> pd.DataFrame:
    if store.df_cleaned is None:
        raise ValueError("Load or enter a dataset before running algorithms.")
    return store.df_cleaned.copy()


def _user_source() -> str:
    return store.source_name or "Current dataset"


def _user_numeric_frame(min_cols: int = 1, min_rows: int = 2) -> pd.DataFrame:
    df = _user_df()
    X = _numeric_features(df, None)
    X = X.loc[:, X.nunique(dropna=False) > 1]
    if len(X) < min_rows:
        raise ValueError(f"This algorithm needs at least {min_rows} rows.")
    if X.shape[1] < min_cols:
        raise ValueError(f"This algorithm needs at least {min_cols} numeric columns. Use Prepare to convert columns if needed.")
    return X


def _scaled_numeric_frame(min_cols: int = 1, min_rows: int = 2):
    X = _user_numeric_frame(min_cols=min_cols, min_rows=min_rows)
    return X, StandardScaler().fit_transform(X)


def _projection_from_scaled(X_scaled: np.ndarray) -> pd.DataFrame:
    if X_scaled.shape[1] >= 2:
        points = PCA(n_components=2, random_state=42).fit_transform(X_scaled)
        return pd.DataFrame({"Axis 1": points[:, 0], "Axis 2": points[:, 1]})
    return pd.DataFrame({"Axis 1": X_scaled[:, 0], "Axis 2": np.zeros(len(X_scaled))})


def _style_user_fig(fig, title: Optional[str] = None):
    if title:
        fig.update_layout(title=title)
    fig.update_layout(
        paper_bgcolor="#12151f",
        plot_bgcolor="#12151f",
        font=dict(color="#f2f5fb"),
        margin=dict(l=40, r=24, t=54, b=40),
    )
    return fig


def _run_user_dataset_profile() -> Dict[str, Any]:
    df = _user_df()
    dtype_counts = df.dtypes.astype(str).value_counts().sort_index()
    missing = df.isna().sum().sort_values(ascending=False)
    missing = missing[missing > 0].head(20)

    lines = [
        "Dataset Profile",
        f"Source: {_user_source()}",
        f"Rows: {len(df):,}",
        f"Columns: {len(df.columns):,}",
        "",
        "Column types:",
        *[f"- {dtype}: {count}" for dtype, count in dtype_counts.items()],
    ]
    if len(missing):
        lines.extend(["", "Top missing-value columns:", *[f"- {col}: {int(count):,}" for col, count in missing.items()]])
    else:
        lines.extend(["", "Missing values: none detected"])

    chart_data = missing.reset_index()
    if len(chart_data):
        chart_data.columns = ["Column", "Missing Values"]
        fig = px.bar(chart_data, x="Column", y="Missing Values", title="Missing Values by Column")
    else:
        chart_data = dtype_counts.reset_index()
        chart_data.columns = ["Type", "Columns"]
        fig = px.bar(chart_data, x="Type", y="Columns", title="Column Types")
    _style_user_fig(fig)
    return {"output": "\n".join(lines), "chart": _fig_json(fig)}


def _run_user_correlation_matrix() -> Dict[str, Any]:
    X = _user_numeric_frame(min_cols=2, min_rows=2)
    corr = X.corr(numeric_only=True).fillna(0)
    fig = go.Figure(go.Heatmap(
        z=corr.values,
        x=corr.columns,
        y=corr.index,
        colorscale="RdBu",
        zmin=-1,
        zmax=1,
        colorbar=dict(title="r"),
    ))
    _style_user_fig(fig, "Correlation Matrix")
    strongest = corr.where(~np.eye(len(corr), dtype=bool)).abs().stack().sort_values(ascending=False)
    top = strongest.head(5)
    lines = [
        "Correlation Matrix",
        f"Source: {_user_source()}",
        f"Numeric columns: {X.shape[1]}",
        "",
        "Strongest relationships:",
        *[f"- {a} vs {b}: {corr.loc[a, b]:.4f}" for (a, b), _ in top.items()],
    ]
    return {"output": "\n".join(lines), "chart": _fig_json(fig)}


def _run_user_pca() -> Dict[str, Any]:
    X, X_scaled = _scaled_numeric_frame(min_cols=2, min_rows=2)
    pca = PCA(n_components=2, random_state=42)
    points = pca.fit_transform(X_scaled)
    plot_df = pd.DataFrame({"PC1": points[:, 0], "PC2": points[:, 1]})
    fig = px.scatter(plot_df, x="PC1", y="PC2", title="PCA Projection")
    _style_user_fig(fig)
    explained = pca.explained_variance_ratio_
    output = "\n".join([
        "PCA Projection",
        f"Source: {_user_source()}",
        f"Rows analyzed: {len(X):,}",
        f"Numeric columns: {X.shape[1]}",
        f"Explained variance: {explained.sum():.4f}",
        f"PC1: {explained[0]:.4f}",
        f"PC2: {explained[1]:.4f}",
    ])
    return {"output": output, "chart": _fig_json(fig)}


def _run_user_kmeans() -> Dict[str, Any]:
    X, X_scaled = _scaled_numeric_frame(min_cols=1, min_rows=2)
    clusters = min(3, len(X_scaled))
    if clusters < 2:
        raise ValueError("K-Means needs at least two rows.")
    model = KMeans(n_clusters=clusters, n_init=10, random_state=42)
    labels = model.fit_predict(X_scaled)
    points = _projection_from_scaled(X_scaled)
    points["Cluster"] = labels.astype(str)
    fig = px.scatter(points, x="Axis 1", y="Axis 2", color="Cluster", title="K-Means Clustering")
    _style_user_fig(fig)
    metrics = [
        "K-Means Clustering",
        f"Source: {_user_source()}",
        f"Rows analyzed: {len(X):,}",
        f"Numeric columns: {X.shape[1]}",
        f"Clusters: {clusters}",
        f"Inertia: {model.inertia_:.4f}",
    ]
    if 1 < len(set(labels)) < len(labels):
        metrics.append(f"Silhouette score: {silhouette_score(X_scaled, labels):.4f}")
    return {"output": "\n".join(metrics), "chart": _fig_json(fig)}


def _run_user_dbscan() -> Dict[str, Any]:
    X, X_scaled = _scaled_numeric_frame(min_cols=1, min_rows=3)
    min_samples = max(2, min(8, len(X_scaled) // 10 or 2))
    model = DBSCAN(eps=0.8, min_samples=min_samples)
    labels = model.fit_predict(X_scaled)
    cluster_ids = {int(v) for v in labels if v != -1}
    points = _projection_from_scaled(X_scaled)
    points["Cluster"] = ["Noise" if label == -1 else f"Cluster {label}" for label in labels]
    fig = px.scatter(points, x="Axis 1", y="Axis 2", color="Cluster", title="DBSCAN Clustering")
    _style_user_fig(fig)
    lines = [
        "DBSCAN Clustering",
        f"Source: {_user_source()}",
        f"Rows analyzed: {len(X):,}",
        f"Numeric columns: {X.shape[1]}",
        f"Clusters: {len(cluster_ids)}",
        f"Noise points: {int(np.sum(labels == -1)):,}",
        f"Minimum samples: {min_samples}",
    ]
    if 1 < len(set(labels)) < len(labels):
        lines.append(f"Silhouette score: {silhouette_score(X_scaled, labels):.4f}")
    return {"output": "\n".join(lines), "chart": _fig_json(fig)}


def _run_user_zscore() -> Dict[str, Any]:
    X, X_scaled = _scaled_numeric_frame(min_cols=1, min_rows=2)
    z = np.abs(X_scaled)
    mask = (z > 3).any(axis=1)
    max_z = z.max(axis=1)
    points = _projection_from_scaled(X_scaled)
    points["Status"] = np.where(mask, "Anomaly", "Normal")
    points["Max Z"] = max_z
    fig = px.scatter(points, x="Axis 1", y="Axis 2", color="Status", size="Max Z", title="Z-Score Anomaly Scan")
    _style_user_fig(fig)
    output = "\n".join([
        "Z-Score Anomaly Scan",
        f"Source: {_user_source()}",
        f"Rows analyzed: {len(X):,}",
        f"Numeric columns: {X.shape[1]}",
        f"Threshold: 3.0",
        f"Anomalies: {int(mask.sum()):,}",
        f"Anomaly rate: {float(mask.mean()):.4f}",
    ])
    return {"output": output, "chart": _fig_json(fig)}


def _run_user_isolation_forest() -> Dict[str, Any]:
    X, X_scaled = _scaled_numeric_frame(min_cols=1, min_rows=4)
    contamination = min(0.2, max(1 / len(X_scaled), 0.08))
    model = IsolationForest(contamination=contamination, random_state=42)
    labels = model.fit_predict(X_scaled)
    anomaly_mask = labels == -1
    points = _projection_from_scaled(X_scaled)
    points["Status"] = np.where(anomaly_mask, "Anomaly", "Normal")
    fig = px.scatter(points, x="Axis 1", y="Axis 2", color="Status", title="Isolation Forest Anomaly Scan")
    _style_user_fig(fig)
    output = "\n".join([
        "Isolation Forest Anomaly Scan",
        f"Source: {_user_source()}",
        f"Rows analyzed: {len(X):,}",
        f"Numeric columns: {X.shape[1]}",
        f"Contamination: {contamination:.4f}",
        f"Anomalies: {int(anomaly_mask.sum()):,}",
        f"Anomaly rate: {float(anomaly_mask.mean()):.4f}",
    ])
    return {"output": output, "chart": _fig_json(fig)}


# ─── Legacy algorithm implementations, no longer exposed in the app ──────────

def _run_alpha_beta() -> Dict[str, Any]:
    scores = [2, 3, 5, 9, 0, 1, 7, 5]
    target_depth = int(math.log2(len(scores)))
    INF = 1000

    def minimax(depth, idx, maximizing, alpha, beta):
        if depth == target_depth:
            return scores[idx]
        if maximizing:
            best = -INF
            for i in range(2):
                val = minimax(depth + 1, idx * 2 + i, False, alpha, beta)
                best = max(best, val); alpha = max(alpha, best)
                if beta <= alpha: break
            return best
        best = INF
        for i in range(2):
            val = minimax(depth + 1, idx * 2 + i, True, alpha, beta)
            best = min(best, val); beta = min(beta, best)
            if beta <= alpha: break
        return best

    optimal = minimax(0, 0, True, -INF, INF)
    return {"output": f"Alpha-Beta Minimax\nScores: {scores}\nOptimal path value: {optimal}", "chart": None}


def _run_astar() -> Dict[str, Any]:
    adjacency = {"A": [("B", 1), ("C", 3), ("D", 7)], "B": [("D", 5)], "C": [("D", 12)], "D": []}
    heuristic = {"A": 1, "B": 1, "C": 1, "D": 1}

    open_set = {"A"}; closed_set = set(); cost = {"A": 0}; parent = {"A": "A"}
    while open_set:
        node = min(open_set, key=lambda v: cost[v] + heuristic.get(v, 0))
        if node == "D":
            path = []
            while parent[node] != node:
                path.append(node); node = parent[node]
            path.append("A"); path.reverse()
            return {"output": f"A* Search\nPath found: {path}\nTotal cost: {cost['D']}", "chart": None}
        for neighbor, weight in adjacency.get(node, []):
            tentative = cost[node] + weight
            if neighbor not in cost or tentative < cost[neighbor]:
                cost[neighbor] = tentative; parent[neighbor] = node
                closed_set.discard(neighbor); open_set.add(neighbor)
        open_set.remove(node); closed_set.add(node)
    return {"output": "A* Search\nPath does not exist", "chart": None}


def _run_bfs_dfs() -> Dict[str, Any]:
    graph = {"A": ["B","C"],"B": ["D","E"],"C": ["F","G"],"D": [],"E": ["H","I"],
             "F": [],"G": ["J","K"],"H": ["L","M","N"],"I": ["O","P"],"J": [],
             "K": ["Q"],"L": [],"M": [],"N": [],"O": [],"P": [],"Q": []}
    bfs = []; visited_b = {"A"}; q = deque(["A"])
    while q:
        n = q.popleft(); bfs.append(n)
        for c in graph[n]:
            if c not in visited_b: visited_b.add(c); q.append(c)
    dfs = []; visited_d = set()
    def _dfs(n):
        visited_d.add(n); dfs.append(n)
        for c in graph[n]:
            if c not in visited_d: _dfs(c)
    _dfs("A")
    return {"output": f"BFS and DFS\nBFS: {' -> '.join(bfs)}\nDFS: {' -> '.join(dfs)}", "chart": None}


def _run_decision_tree_demo() -> Dict[str, Any]:
    import os
    data_path = os.path.join(os.path.dirname(__file__), "..", "..", "Testing", "data.csv")
    if not os.path.exists(data_path):
        # Generate synthetic data
        df_tree = pd.DataFrame({
            "Color": np.random.choice(["Red","Green","Yellow"], 30),
            "Size": np.random.choice(["Small","Medium","Large"], 30),
            "Shape": np.random.choice(["Round","Oval"], 30),
            "Edible": np.random.choice(["Yes","No"], 30),
        })
    else:
        df_tree = pd.read_csv(data_path)

    mappings = {
        "Color": {"Red": 0,"Green": 1,"Yellow": 2},
        "Size": {"Small": 0,"Medium": 1,"Large": 2},
        "Shape": {"Round": 0,"Oval": 1},
        "Edible": {"No": 0,"Yes": 1},
    }
    for col, m in mappings.items():
        if col in df_tree.columns:
            df_tree[col] = df_tree[col].map(m)

    features = ["Color","Size","Shape"]; target = "Edible"
    X = df_tree[features]; y = df_tree[target]
    clf = DecisionTreeClassifier(random_state=42); clf.fit(X, y)
    sample = pd.DataFrame([[1, 1, 1]], columns=features)
    pred = clf.predict(sample)[0]
    pred_label = "Yes" if pred == 1 else "No"

    # Feature importance chart
    fi = pd.DataFrame({"Feature": features, "Importance": clf.feature_importances_})
    fig = px.bar(fi, x="Feature", y="Importance", color="Importance",
                 color_continuous_scale="Blues", title="Decision Tree Feature Importance")
    fig.update_layout(paper_bgcolor="#282830", plot_bgcolor="#1e1e23",
                      font=dict(color="#f0f0f0"))

    return {
        "output": f"Decision Tree Classifier\nDataset rows: {len(df_tree)}\nSample (Green,Medium,Oval) → {pred_label}",
        "chart": json.dumps(fig, cls=PlotlyJSONEncoder),
    }


def _run_genetic_algorithm() -> Dict[str, Any]:
    random.seed(42); np.random.seed(42)
    target = "I love GeeksforGeeks"
    genes = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ 1234567890, .-;:_!\"#%&/()=?@S{[]}"

    class Indv:
        def __init__(self, ch): self.ch = ch; self.fit = sum(1 for a,b in zip(ch,target) if a!=b)
        @staticmethod
        def rand_gene(): return random.choice(genes)
        @classmethod
        def create(cls): return cls([cls.rand_gene() for _ in range(len(target))])
        def mate(self, o):
            ch = []
            for g1,g2 in zip(self.ch, o.ch):
                p = random.random()
                ch.append(g1 if p<0.45 else g2 if p<0.90 else self.rand_gene())
            return Indv(ch)

    pop = [Indv.create() for _ in range(100)]; gen = 1; logs = []; fits = []
    while gen <= 16:
        pop.sort(key=lambda x: x.fit)
        best = pop[0]
        logs.append(f"Gen {gen}: {''.join(best.ch)} | Fitness={best.fit}")
        fits.append(best.fit)
        if best.fit == 0: break
        elite = pop[:10]
        new = elite[:]
        for _ in range(90):
            p1,p2 = random.choice(pop[:50]), random.choice(pop[:50])
            new.append(p1.mate(p2))
        pop = new; gen += 1

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=fits, mode="lines+markers", name="Best Fitness",
                             line=dict(color="#64c8ff", width=2)))
    fig.update_layout(title="Genetic Algorithm — Fitness over Generations",
                      xaxis_title="Generation", yaxis_title="Fitness (lower=better)",
                      paper_bgcolor="#282830", plot_bgcolor="#1e1e23",
                      font=dict(color="#f0f0f0"))
    return {"output": "Genetic Algorithm\n" + "\n".join(logs), "chart": json.dumps(fig, cls=PlotlyJSONEncoder)}


def _run_hill_climbing() -> Dict[str, Any]:
    np.random.seed(42); random.seed(42)
    coords = np.array([[1,2],[30,21],[56,23],[8,18],[20,50],[3,4],[11,34]])
    n = len(coords)
    mat = np.zeros((n,n))
    for i in range(n):
        for j in range(n):
            mat[i][j] = np.linalg.norm(coords[i]-coords[j])

    def length(sol): return sum(mat[sol[i]][sol[i-1]] for i in range(len(sol)))

    sol = list(range(n)); random.shuffle(sol)
    cur_len = length(sol); improved = True
    while improved:
        improved = False
        for i in range(n):
            for j in range(i+1, n):
                cand = sol[:]; cand[i],cand[j] = cand[j],cand[i]
                if length(cand) < cur_len:
                    sol = cand; cur_len = length(cand); improved = True

    # Route visualization
    route_coords = coords[sol + [sol[0]]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=route_coords[:,0], y=route_coords[:,1],
                             mode="lines+markers", line=dict(color="#4a90d9"),
                             marker=dict(size=10, color="#64c8ff")))
    for i, (x,y) in enumerate(coords):
        fig.add_annotation(x=x, y=y, text=str(i), showarrow=False, font=dict(color="white"))
    fig.update_layout(title="Hill Climbing TSP Route", paper_bgcolor="#282830",
                      plot_bgcolor="#1e1e23", font=dict(color="#f0f0f0"))
    return {"output": f"Hill Climbing (TSP)\nBest route: {sol}\nRoute length: {cur_len:.4f}",
            "chart": json.dumps(fig, cls=PlotlyJSONEncoder)}


def _run_kfold() -> Dict[str, Any]:
    data = np.arange(0.1, 2.1, 0.1)
    kf = KFold(n_splits=10, shuffle=True, random_state=1)
    lines = ["K-Fold Validation (10 splits)"]
    for idx, (train, test) in enumerate(kf.split(data), 1):
        lines.append(f"Fold {idx}: train={np.round(data[train],1).tolist()} | test={np.round(data[test],1).tolist()}")
    return {"output": "\n".join(lines), "chart": None}


def _run_kmeans_demo() -> Dict[str, Any]:
    X, _ = make_blobs(n_samples=300, centers=3, random_state=42)
    m = KMeans(n_clusters=3, random_state=42, n_init=10)
    labels = m.fit_predict(X)
    centroids = m.cluster_centers_

    fig = go.Figure()
    for cluster_id in range(3):
        mask = labels == cluster_id
        fig.add_trace(go.Scatter(x=X[mask,0], y=X[mask,1], mode="markers",
                                 name=f"Cluster {cluster_id}", opacity=0.8))
    fig.add_trace(go.Scatter(x=centroids[:,0], y=centroids[:,1], mode="markers",
                             marker=dict(symbol="x", size=16, color="red", line=dict(width=3)),
                             name="Centroids"))
    fig.update_layout(title="K-Means Clustering", paper_bgcolor="#282830",
                      plot_bgcolor="#1e1e23", font=dict(color="#f0f0f0"))

    score = float(silhouette_score(X, labels))
    return {"output": f"K-Means Clustering\nInertia: {m.inertia_:.4f}\nSilhouette Score: {score:.4f}",
            "chart": json.dumps(fig, cls=PlotlyJSONEncoder)}


def _run_logistic_iris() -> Dict[str, Any]:
    iris = load_iris()
    X_tr, X_te, y_tr, y_te = train_test_split(iris.data, iris.target, test_size=0.2, random_state=42)
    m = LogisticRegression(max_iter=200); m.fit(X_tr, y_tr)
    acc = accuracy_score(y_te, m.predict(X_te))
    return {"output": f"Logistic Regression (Iris)\nAccuracy: {acc:.4f}", "chart": None}


def _run_logistic_breast() -> Dict[str, Any]:
    X, y = load_breast_cancer(return_X_y=True)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=23)
    m = LogisticRegression(max_iter=10000, random_state=0); m.fit(X_tr, y_tr)
    acc = accuracy_score(y_te, m.predict(X_te))
    return {"output": f"Logistic Regression (Breast Cancer)\nAccuracy: {acc*100:.2f}%", "chart": None}


def _run_logistic_digits() -> Dict[str, Any]:
    d = load_digits()
    X_tr, X_te, y_tr, y_te = train_test_split(d.data, d.target, test_size=0.4, random_state=1)
    m = LogisticRegression(max_iter=10000, random_state=0); m.fit(X_tr, y_tr)
    acc = accuracy_score(y_te, m.predict(X_te))
    return {"output": f"Logistic Regression (Digits)\nAccuracy: {acc*100:.2f}%", "chart": None}


def _run_onehot() -> Dict[str, Any]:
    data = {"Employee id": [10,20,15,25,30], "Gender": ["M","F","F","M","F"],
            "Remarks": ["Good","Nice","Good","Great","Nice"]}
    df = pd.DataFrame(data)
    cat_cols = ["Gender","Remarks"]
    enc = OneHotEncoder(sparse_output=False)
    encoded = enc.fit_transform(df[cat_cols])
    enc_df = pd.DataFrame(encoded, columns=enc.get_feature_names_out(cat_cols))
    result = pd.concat([df[["Employee id"]], enc_df], axis=1)
    return {"output": f"One-Hot Encoding\nOriginal: {list(df.columns)}\nEncoded: {list(result.columns)}\n\n{result.to_string(index=False)}", "chart": None}


def _run_svm_demo() -> Dict[str, Any]:
    X, y = make_classification(n_samples=1000, n_features=2, n_classes=2,
                                n_informative=2, n_redundant=0, random_state=42, class_sep=1.5)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=42)
    sc = StandardScaler()
    X_tr_s = sc.fit_transform(X_tr); X_te_s = sc.transform(X_te)
    m = SVC(kernel="linear", random_state=42); m.fit(X_tr_s, y_tr)
    train_acc = accuracy_score(y_tr, m.predict(X_tr_s))
    test_acc = accuracy_score(y_te, m.predict(X_te_s))

    # Decision boundary
    x_min, x_max = X_te[:,0].min()-1, X_te[:,0].max()+1
    y_min, y_max = X_te[:,1].min()-1, X_te[:,1].max()+1
    xx, yy = np.meshgrid(np.arange(x_min, x_max, 0.08), np.arange(y_min, y_max, 0.08))
    zz = m.predict(sc.transform(np.c_[xx.ravel(), yy.ravel()])).reshape(xx.shape)

    fig = go.Figure()
    fig.add_trace(go.Contour(x=xx[0], y=yy[:,0], z=zz, opacity=0.4,
                             colorscale=[[0,"#4a90d9"],[1,"#f06292"]], showscale=False))
    for cls, color, name in [(0,"#4a90d9","Class 0"), (1,"#f06292","Class 1")]:
        mask = y_te == cls
        fig.add_trace(go.Scatter(x=X_te[mask,0], y=X_te[mask,1], mode="markers",
                                 marker=dict(color=color, size=7, line=dict(color="white",width=1)),
                                 name=name))
    fig.update_layout(title="SVM Decision Boundary", paper_bgcolor="#282830",
                      plot_bgcolor="#1e1e23", font=dict(color="#f0f0f0"))

    report = classification_report(y_te, m.predict(X_te_s))
    return {
        "output": f"SVM Classification\nTrain Accuracy: {train_acc:.4f}\nTest Accuracy: {test_acc:.4f}\n\n{report}",
        "chart": json.dumps(fig, cls=PlotlyJSONEncoder),
    }


def _style_demo_fig(fig, title: Optional[str] = None):
    if title:
        fig.update_layout(title=title)
    fig.update_layout(
        paper_bgcolor="#282830",
        plot_bgcolor="#1e1e23",
        font=dict(color="#f0f0f0"),
        margin=dict(l=40, r=24, t=54, b=40),
    )
    return fig


def _fig_json(fig) -> str:
    return json.dumps(fig, cls=PlotlyJSONEncoder)


def _run_ml_taxonomy() -> Dict[str, Any]:
    ids = [
        "ml",
        "supervised", "classification", "regression", "ensemble", "timeseries",
        "unsupervised", "clustering", "dimred", "association", "anomaly",
        "semi", "selftraining", "cotraining",
        "reinforcement", "learningtasks", "gameai", "realtime", "explore",
    ]
    labels = [
        "Machine Learning",
        "Supervised", "Classification", "Regression", "Ensemble Methods", "Time Series Prediction",
        "Unsupervised", "Clustering", "Dimensionality Reduction", "Association Rules", "Anomaly Detection",
        "Semi-Supervised", "Self-Training", "Co-Training",
        "Reinforcement", "Learning Tasks", "Game AI", "Real-Time Decisions", "Exploration Balance",
    ]
    parents = [
        "",
        "ml", "supervised", "supervised", "supervised", "supervised",
        "ml", "unsupervised", "unsupervised", "unsupervised", "unsupervised",
        "ml", "semi", "semi",
        "ml", "reinforcement", "reinforcement", "reinforcement", "reinforcement",
    ]
    values = [0, 4, 1, 1, 1, 1, 4, 1, 1, 1, 1, 2, 1, 1, 4, 1, 1, 1, 1]
    colors = [
        "#6c8fef",
        "#4ade80", "#58c878", "#58c878", "#58c878", "#58c878",
        "#fbbf24", "#f4a62a", "#f4a62a", "#f4a62a", "#f4a62a",
        "#a3a3a3", "#b8b8b8", "#b8b8b8",
        "#60a5fa", "#74b7ff", "#74b7ff", "#74b7ff", "#74b7ff",
    ]
    fig = go.Figure(go.Treemap(
        ids=ids,
        labels=labels,
        parents=parents,
        values=values,
        branchvalues="total",
        marker=dict(colors=colors),
        textinfo="label",
    ))
    _style_demo_fig(fig, "Machine Learning Taxonomy")

    output = "\n".join([
        "Machine Learning Taxonomy from ML1 / ML2",
        "",
        "Supervised: classification, regression, ensemble methods, time-series prediction.",
        "Unsupervised: clustering, dimensionality reduction, association rules, anomaly detection.",
        "Semi-Supervised: self-training and co-training.",
        "Reinforcement: learning tasks, game AI, real-time decisions, exploration-exploitation balance.",
        "",
        "Added runnable demos/training entries for the missing practical items: Naive Bayes, DBSCAN, PCA, ICA, Apriori/FP-growth, Z-score, Isolation Forest, One-Class SVM, Self-Training, Co-Training, Q-Learning, policy optimization, dynamic programming, ensemble comparison, and time-series baselines.",
    ])
    return {"output": output, "chart": _fig_json(fig)}


def _run_naive_bayes_demo() -> Dict[str, Any]:
    iris = load_iris()
    X_tr, X_te, y_tr, y_te = train_test_split(iris.data, iris.target, test_size=0.25, random_state=42)
    m = GaussianNB(); m.fit(X_tr, y_tr)
    pred = m.predict(X_te)
    acc = accuracy_score(y_te, pred)
    cm = pd.crosstab(pd.Series(y_te, name="Actual"), pd.Series(pred, name="Predicted"), dropna=False)
    fig = go.Figure(go.Heatmap(
        z=cm.values,
        x=[iris.target_names[i] for i in cm.columns],
        y=[iris.target_names[i] for i in cm.index],
        colorscale="Blues",
        showscale=True,
    ))
    fig.update_xaxes(title="Predicted")
    fig.update_yaxes(title="Actual")
    _style_demo_fig(fig, "Gaussian Naive Bayes Confusion Matrix")
    return {
        "output": f"Naive Bayes Classification\nDataset: Iris\nAccuracy: {acc:.4f}\n\n{classification_report(y_te, pred, target_names=iris.target_names, zero_division=0)}",
        "chart": _fig_json(fig),
    }


def _run_ensemble_methods_demo() -> Dict[str, Any]:
    X, y = make_classification(
        n_samples=700,
        n_features=12,
        n_informative=7,
        n_redundant=2,
        random_state=42,
        class_sep=1.2,
    )
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=42)
    models = {
        "Random Forest": RandomForestClassifier(n_estimators=140, random_state=42),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=120, max_depth=3, random_state=42),
        "Bagging": BaggingClassifier(estimator=DecisionTreeClassifier(random_state=42), n_estimators=120, random_state=42),
        "AdaBoost": AdaBoostClassifier(estimator=DecisionTreeClassifier(max_depth=2, random_state=42), n_estimators=120, random_state=42),
        "Stacking": StackingClassifier(
            estimators=[
                ("lr", LogisticRegression(max_iter=1000)),
                ("rf", RandomForestClassifier(n_estimators=80, random_state=42)),
                ("nb", GaussianNB()),
            ],
            final_estimator=LogisticRegression(max_iter=1000),
            cv=3,
        ),
    }
    scores = []
    for label, model in models.items():
        model.fit(X_tr, y_tr)
        scores.append((label, accuracy_score(y_te, model.predict(X_te))))

    fig = px.bar(
        pd.DataFrame(scores, columns=["Model", "Accuracy"]),
        x="Model",
        y="Accuracy",
        color="Model",
        title="Ensemble Methods Accuracy",
    )
    _style_demo_fig(fig)
    lines = ["Ensemble Methods Comparison"] + [f"{name}: {score:.4f}" for name, score in scores]
    return {"output": "\n".join(lines), "chart": _fig_json(fig)}


def _run_dbscan_demo() -> Dict[str, Any]:
    X, _ = make_moons(n_samples=320, noise=0.055, random_state=42)
    X_s = StandardScaler().fit_transform(X)
    m = DBSCAN(eps=0.3, min_samples=6)
    labels = m.fit_predict(X_s)
    clusters = {int(v) for v in labels if v != -1}
    fig = px.scatter(x=X[:, 0], y=X[:, 1], color=labels.astype(str), title="DBSCAN on Nonlinear Clusters")
    _style_demo_fig(fig)
    score = silhouette_score(X_s, labels) if len(set(labels)) > 1 and len(set(labels)) < len(labels) else None
    output = [
        "DBSCAN Clustering",
        f"Clusters found: {len(clusters)}",
        f"Noise points: {int(np.sum(labels == -1))}",
    ]
    if score is not None:
        output.append(f"Silhouette score: {score:.4f}")
    return {"output": "\n".join(output), "chart": _fig_json(fig)}


def _run_pca_demo() -> Dict[str, Any]:
    iris = load_iris()
    X_s = StandardScaler().fit_transform(iris.data)
    pca = PCA(n_components=2, random_state=42)
    projected = pca.fit_transform(X_s)
    df = pd.DataFrame({
        "PC1": projected[:, 0],
        "PC2": projected[:, 1],
        "Class": [iris.target_names[i] for i in iris.target],
    })
    fig = px.scatter(df, x="PC1", y="PC2", color="Class", title="PCA Projection")
    _style_demo_fig(fig)
    return {
        "output": f"PCA Dimensionality Reduction\nExplained variance: {pca.explained_variance_ratio_.sum():.4f}\nPC1: {pca.explained_variance_ratio_[0]:.4f}\nPC2: {pca.explained_variance_ratio_[1]:.4f}",
        "chart": _fig_json(fig),
    }


def _run_ica_demo() -> Dict[str, Any]:
    rng = np.random.default_rng(42)
    t = np.linspace(0, 8, 500)
    sources = np.c_[
        np.sin(2.2 * t),
        np.sign(np.sin(3.1 * t)),
        2 * (t / np.pi - np.floor(0.5 + t / np.pi)),
    ]
    sources += 0.03 * rng.normal(size=sources.shape)
    sources /= sources.std(axis=0)
    mixing = np.array([[1, 1, 0.5], [0.5, 2, 1], [1.5, 1, 2]])
    observed = sources.dot(mixing.T)
    ica = FastICA(n_components=3, random_state=42, whiten="unit-variance", max_iter=600)
    recovered = ica.fit_transform(observed)

    fig = go.Figure()
    for idx in range(3):
        fig.add_trace(go.Scatter(x=t, y=recovered[:, idx] + idx * 4, mode="lines", name=f"Recovered {idx + 1}"))
    _style_demo_fig(fig, "Independent Component Analysis")
    return {
        "output": f"Independent Component Analysis\nMixed signals: 3\nRecovered components: 3\nIterations: {ica.n_iter_}",
        "chart": _fig_json(fig),
    }


def _mine_frequent_itemsets(transactions, min_support_count: int):
    from itertools import combinations
    item_pool = sorted(set().union(*transactions))
    max_len = max(len(t) for t in transactions)
    supports = {}
    frequent = []
    for size in range(1, max_len + 1):
        for combo in combinations(item_pool, size):
            itemset = frozenset(combo)
            support = sum(itemset.issubset(t) for t in transactions)
            supports[itemset] = support
            if support >= min_support_count:
                frequent.append((itemset, support))
    return frequent, supports


def _association_rules(frequent, supports, n_transactions: int, min_confidence: float = 0.55):
    from itertools import combinations
    rules = []
    for itemset, support in frequent:
        if len(itemset) < 2:
            continue
        items = sorted(itemset)
        for size in range(1, len(items)):
            for lhs_items in combinations(items, size):
                lhs = frozenset(lhs_items)
                rhs = itemset - lhs
                confidence = support / supports[lhs]
                lift = confidence / (supports[rhs] / n_transactions)
                if confidence >= min_confidence:
                    rules.append((lhs, rhs, support / n_transactions, confidence, lift))
    rules.sort(key=lambda r: (r[3], r[4], r[2]), reverse=True)
    return rules


def _run_apriori_demo() -> Dict[str, Any]:
    transactions = [
        {"milk", "bread", "butter"},
        {"bread", "butter", "jam"},
        {"milk", "bread"},
        {"milk", "diapers", "bread", "butter"},
        {"diapers", "beer", "chips"},
        {"milk", "diapers", "bread", "beer"},
        {"bread", "butter"},
        {"milk", "bread", "jam"},
        {"diapers", "bread", "butter"},
        {"milk", "diapers", "bread", "butter"},
    ]
    frequent, supports = _mine_frequent_itemsets(transactions, min_support_count=3)
    rules = _association_rules(frequent, supports, len(transactions))
    top_itemsets = sorted(frequent, key=lambda x: (len(x[0]), x[1]), reverse=True)[:8]
    fig = px.bar(
        pd.DataFrame({
            "Itemset": [", ".join(sorted(s)) for s, _ in top_itemsets],
            "Support Count": [c for _, c in top_itemsets],
        }),
        x="Itemset",
        y="Support Count",
        title="Apriori Frequent Itemsets",
    )
    _style_demo_fig(fig)
    lines = ["Apriori Association Rules", "Frequent itemsets mined with minimum support count = 3", ""]
    for lhs, rhs, support, confidence, lift in rules[:6]:
        lines.append(f"{', '.join(sorted(lhs))} -> {', '.join(sorted(rhs))} | support={support:.2f}, confidence={confidence:.2f}, lift={lift:.2f}")
    return {"output": "\n".join(lines), "chart": _fig_json(fig)}


def _run_fpgrowth_demo() -> Dict[str, Any]:
    transactions = [
        {"classification", "decision tree", "random forest"},
        {"classification", "logistic regression", "svm"},
        {"regression", "linear regression", "lasso"},
        {"clustering", "k-means", "pca"},
        {"clustering", "dbscan", "anomaly"},
        {"classification", "naive bayes", "svm"},
        {"regression", "random forest", "gradient boosting"},
        {"anomaly", "isolation forest", "z-score"},
        {"dimensionality", "pca", "ica"},
        {"classification", "random forest", "gradient boosting"},
    ]
    frequent, _ = _mine_frequent_itemsets(transactions, min_support_count=2)
    patterns = sorted(frequent, key=lambda x: (x[1], len(x[0])), reverse=True)[:10]
    fig = px.bar(
        pd.DataFrame({
            "Pattern": [", ".join(sorted(s)) for s, _ in patterns],
            "Frequency": [c for _, c in patterns],
        }),
        x="Pattern",
        y="Frequency",
        title="Frequent Pattern Growth Demo",
    )
    _style_demo_fig(fig)
    lines = ["FP-Growth Frequent Pattern Mining", "Top compact patterns:"] + [
        f"{', '.join(sorted(s))}: {c}" for s, c in patterns
    ]
    return {"output": "\n".join(lines), "chart": _fig_json(fig)}


def _run_zscore_anomaly_demo() -> Dict[str, Any]:
    rng = np.random.default_rng(42)
    normal = rng.normal(0, 1, size=(180, 2))
    outliers = rng.normal(5.0, 0.35, size=(12, 2))
    X = np.vstack([normal, outliers])
    z = np.abs((X - X.mean(axis=0)) / X.std(axis=0))
    anomaly = (z > 3).any(axis=1)
    fig = px.scatter(x=X[:, 0], y=X[:, 1], color=np.where(anomaly, "Anomaly", "Normal"), title="Z-Score Anomaly Detection")
    _style_demo_fig(fig)
    return {
        "output": f"Z-Score Anomaly Detection\nThreshold: 3 standard deviations\nDetected anomalies: {int(anomaly.sum())} of {len(X)}",
        "chart": _fig_json(fig),
    }


def _run_isolation_forest_demo() -> Dict[str, Any]:
    rng = np.random.default_rng(42)
    normal = rng.normal(0, 1, size=(240, 2))
    outliers = rng.uniform(low=-6, high=6, size=(24, 2))
    X = np.vstack([normal, outliers])
    model = IsolationForest(contamination=0.1, random_state=42)
    pred = model.fit_predict(X)
    fig = px.scatter(x=X[:, 0], y=X[:, 1], color=np.where(pred == -1, "Anomaly", "Normal"), title="Isolation Forest")
    _style_demo_fig(fig)
    return {
        "output": f"Isolation Forest Anomaly Detection\nContamination: 0.10\nDetected anomalies: {int(np.sum(pred == -1))}",
        "chart": _fig_json(fig),
    }


def _run_one_class_svm_demo() -> Dict[str, Any]:
    rng = np.random.default_rng(7)
    normal = rng.normal(0, 0.75, size=(220, 2))
    outliers = rng.normal(3.2, 0.55, size=(20, 2))
    X = np.vstack([normal, outliers])
    X_s = StandardScaler().fit_transform(X)
    model = OneClassSVM(nu=0.09, kernel="rbf", gamma="scale")
    pred = model.fit_predict(X_s)
    fig = px.scatter(x=X[:, 0], y=X[:, 1], color=np.where(pred == -1, "Anomaly", "Normal"), title="One-Class SVM")
    _style_demo_fig(fig)
    return {
        "output": f"One-Class SVM Anomaly Detection\nNu: 0.09\nDetected anomalies: {int(np.sum(pred == -1))}",
        "chart": _fig_json(fig),
    }


def _run_self_training_demo() -> Dict[str, Any]:
    X, y = make_classification(n_samples=520, n_features=8, n_informative=5, n_redundant=1, random_state=42)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=42)
    sc = StandardScaler()
    X_tr = sc.fit_transform(X_tr); X_te = sc.transform(X_te)
    rng = np.random.default_rng(42)
    y_semi = np.full_like(y_tr, -1)
    labeled = set()
    for cls in np.unique(y_tr):
        cls_idx = np.where(y_tr == cls)[0]
        labeled.update(rng.choice(cls_idx, size=18, replace=False).tolist())
    labeled = np.array(sorted(labeled))
    y_semi[labeled] = y_tr[labeled]
    model = SelfTrainingClassifier(SVC(probability=True, gamma="scale", random_state=42), threshold=0.78, max_iter=10)
    model.fit(X_tr, y_semi)
    pred = model.predict(X_te)
    inferred = int(np.sum(getattr(model, "labeled_iter_", np.array([])) > 0))
    return {
        "output": f"Self-Training Classification\nSeed labels: {len(labeled)} of {len(y_tr)} training rows\nInferred labels: {inferred}\nAccuracy: {accuracy_score(y_te, pred):.4f}",
        "chart": None,
    }


def _run_co_training_demo() -> Dict[str, Any]:
    X, y = make_classification(n_samples=520, n_features=6, n_informative=5, n_redundant=0, random_state=42, class_sep=1.1)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=42)
    sc = StandardScaler()
    X_tr = sc.fit_transform(X_tr); X_te = sc.transform(X_te)
    X1_tr, X2_tr = X_tr[:, :3], X_tr[:, 3:]
    X1_te, X2_te = X_te[:, :3], X_te[:, 3:]
    rng = np.random.default_rng(42)
    labeled = set()
    for cls in np.unique(y_tr):
        cls_idx = np.where(y_tr == cls)[0]
        labeled.update(rng.choice(cls_idx, size=16, replace=False).tolist())
    history = [len(labeled)]
    rounds = 0
    for _ in range(8):
        rounds += 1
        labeled_idx = np.array(sorted(labeled))
        unlabeled_idx = np.array([i for i in range(len(y_tr)) if i not in labeled])
        if len(unlabeled_idx) == 0:
            break
        m1 = GaussianNB().fit(X1_tr[labeled_idx], y_tr[labeled_idx])
        m2 = GaussianNB().fit(X2_tr[labeled_idx], y_tr[labeled_idx])
        p1 = m1.predict_proba(X1_tr[unlabeled_idx])
        p2 = m2.predict_proba(X2_tr[unlabeled_idx])
        pred1 = m1.classes_[np.argmax(p1, axis=1)]
        pred2 = m2.classes_[np.argmax(p2, axis=1)]
        confidence = np.minimum(np.max(p1, axis=1), np.max(p2, axis=1))
        candidate_mask = (pred1 == pred2) & (confidence >= 0.88)
        candidates = unlabeled_idx[candidate_mask]
        if len(candidates) == 0:
            break
        best = candidates[np.argsort(confidence[candidate_mask])[-24:]]
        labeled.update(best.tolist())
        history.append(len(labeled))

    labeled_idx = np.array(sorted(labeled))
    m1 = GaussianNB().fit(X1_tr[labeled_idx], y_tr[labeled_idx])
    m2 = GaussianNB().fit(X2_tr[labeled_idx], y_tr[labeled_idx])
    probs = (m1.predict_proba(X1_te) + m2.predict_proba(X2_te)) / 2
    pred = m1.classes_[np.argmax(probs, axis=1)]
    acc = accuracy_score(y_te, pred)
    fig = go.Figure(go.Scatter(y=history, mode="lines+markers", name="Labeled rows"))
    fig.update_xaxes(title="Round")
    fig.update_yaxes(title="Labeled Training Rows")
    _style_demo_fig(fig, "Co-Training Label Growth")
    return {
        "output": f"Co-Training Classification\nViews: first 3 features and last 3 features\nRounds: {rounds}\nLabels grew from {history[0]} to {history[-1]}\nAccuracy: {acc:.4f}",
        "chart": _fig_json(fig),
    }


def _grid_step(state: int, action: int, grid_size: int = 4) -> int:
    row, col = divmod(state, grid_size)
    if action == 0:
        row = max(0, row - 1)
    elif action == 1:
        col = min(grid_size - 1, col + 1)
    elif action == 2:
        row = min(grid_size - 1, row + 1)
    elif action == 3:
        col = max(0, col - 1)
    return row * grid_size + col


def _run_q_learning_demo() -> Dict[str, Any]:
    rng = np.random.default_rng(42)
    grid_size = 4
    n_states = grid_size * grid_size
    goal = 15
    holes = {5, 7, 11}
    q = np.zeros((n_states, 4))
    alpha, gamma, epsilon = 0.25, 0.92, 0.22
    rewards = []
    for _ in range(420):
        state = 0
        total = 0
        for _ in range(60):
            action = int(rng.integers(4)) if rng.random() < epsilon else int(np.argmax(q[state]))
            nxt = _grid_step(state, action, grid_size)
            reward = 1.0 if nxt == goal else -1.0 if nxt in holes else -0.04
            done = nxt == goal or nxt in holes
            q[state, action] += alpha * (reward + gamma * np.max(q[nxt]) - q[state, action])
            state = nxt
            total += reward
            if done:
                break
        rewards.append(total)

    path = [0]
    state = 0
    for _ in range(16):
        state = _grid_step(state, int(np.argmax(q[state])), grid_size)
        path.append(state)
        if state == goal or state in holes:
            break

    values = q.max(axis=1).reshape(grid_size, grid_size)
    for h in holes:
        r, c = divmod(h, grid_size)
        values[r, c] = -1
    values[-1, -1] = 1
    fig = go.Figure(go.Heatmap(z=values, colorscale="RdYlGn", zmin=-1, zmax=1, showscale=True))
    _style_demo_fig(fig, "Q-Learning State Values")
    return {
        "output": f"Q-Learning Grid World\nEpisodes: {len(rewards)}\nGreedy path: {' -> '.join(map(str, path))}\nMean reward over last 50 episodes: {np.mean(rewards[-50:]):.4f}",
        "chart": _fig_json(fig),
    }


def _softmax(values):
    values = values - np.max(values)
    exp = np.exp(values)
    return exp / exp.sum()


def _run_policy_optimization_demo() -> Dict[str, Any]:
    rng = np.random.default_rng(42)
    true_rewards = np.array([0.25, 0.55, 0.8])
    preferences = np.zeros(3)
    baseline = 0.0
    alpha = 0.08
    rewards = []
    for step in range(1, 260):
        probs = _softmax(preferences)
        action = int(rng.choice(3, p=probs))
        reward = rng.normal(true_rewards[action], 0.18)
        baseline += (reward - baseline) / step
        grad = -probs
        grad[action] += 1
        preferences += alpha * (reward - baseline) * grad
        rewards.append(reward)

    final_probs = _softmax(preferences)
    moving_avg = pd.Series(rewards).rolling(20, min_periods=1).mean()
    fig = go.Figure(go.Scatter(y=moving_avg, mode="lines", name="20-step average reward"))
    _style_demo_fig(fig, "Policy Optimization on a Bandit")
    return {
        "output": "Policy Optimization\n" + "\n".join([
            f"Action {i}: probability={p:.3f}, true mean reward={true_rewards[i]:.2f}"
            for i, p in enumerate(final_probs)
        ]),
        "chart": _fig_json(fig),
    }


def _run_dynamic_programming_demo() -> Dict[str, Any]:
    grid_size = 4
    n_states = grid_size * grid_size
    goal = 15
    holes = {5, 7, 11}
    gamma = 0.92
    V = np.zeros(n_states)
    for iteration in range(80):
        delta = 0
        for state in range(n_states):
            if state == goal or state in holes:
                continue
            old = V[state]
            action_values = []
            for action in range(4):
                nxt = _grid_step(state, action, grid_size)
                reward = 1 if nxt == goal else -1 if nxt in holes else -0.04
                action_values.append(reward + gamma * V[nxt])
            V[state] = max(action_values)
            delta = max(delta, abs(old - V[state]))
        if delta < 1e-4:
            break
    values = V.reshape(grid_size, grid_size)
    fig = go.Figure(go.Heatmap(z=values, colorscale="RdYlGn", zmin=-1, zmax=1))
    _style_demo_fig(fig, "Dynamic Programming Value Iteration")
    return {
        "output": f"Dynamic Programming / Value Iteration\nIterations: {iteration + 1}\nStart-state value: {V[0]:.4f}\nGoal-state value: {V[goal]:.4f}",
        "chart": _fig_json(fig),
    }


def _run_time_series_demo() -> Dict[str, Any]:
    rng = np.random.default_rng(42)
    t = np.arange(72)
    series = 48 + 0.45 * t + 7 * np.sin(2 * np.pi * t / 12) + rng.normal(0, 1.4, size=len(t))

    alpha = 0.32
    smooth = [series[0]]
    for value in series[1:]:
        smooth.append(alpha * value + (1 - alpha) * smooth[-1])
    smooth = np.array(smooth)

    diff = np.diff(series)
    denom = float(np.dot(diff[:-1], diff[:-1]))
    phi = float(np.dot(diff[1:], diff[:-1]) / denom) if denom else 0.0
    next_diff = diff[-1]
    forecast = []
    last = series[-1]
    seasonal_profile = pd.Series(series - pd.Series(series).rolling(12, center=True, min_periods=1).mean()).groupby(t % 12).mean()
    for step in range(12):
        next_diff = phi * next_diff
        seasonal = float(seasonal_profile.iloc[(len(series) + step) % 12])
        last = last + next_diff + 0.18 + 0.18 * seasonal
        forecast.append(last)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=series, mode="lines", name="Observed"))
    fig.add_trace(go.Scatter(x=t, y=smooth, mode="lines", name="Exponential smoothing"))
    fig.add_trace(go.Scatter(x=np.arange(72, 84), y=forecast, mode="lines+markers", name="AR-style seasonal forecast"))
    _style_demo_fig(fig, "Time Series Baselines")
    output = "\n".join([
        "Time Series Prediction",
        f"Exponential smoothing alpha: {alpha:.2f}",
        f"AR-style differencing phi: {phi:.3f}",
        f"Next forecast: {forecast[0]:.2f}",
        "Includes native baselines for ARIMA-style differencing, seasonal decomposition, and exponential smoothing.",
    ])
    return {"output": output, "chart": _fig_json(fig)}
