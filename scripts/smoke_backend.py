#!/usr/bin/env python
"""
Smoke-test the Python backend without starting Electron.

The checks intentionally exercise the same service functions used by FastAPI:
data loading, cleaning/preprocessing, chart generation, model training, and
algorithm demos. It is a fast confidence test for local development and release
prep, not a replacement for full unit tests.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "python-backend"
sys.path.insert(0, str(BACKEND))

import chart_service as charts  # noqa: E402
import data_service as data  # noqa: E402
import ml_service as ml  # noqa: E402


def check(name: str, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception as exc:  # noqa: BLE001 - smoke output should show exact failure
        print(f"FAIL {name}: {exc}")
        raise


def load_sample(name: str):
    df = data.load_sample(name)
    data.store.on_data_loaded(df, f"smoke:{name}")
    return df


def assert_chart_json(raw: str):
    payload = json.loads(raw)
    if "data" not in payload or "layout" not in payload:
        raise AssertionError("Plotly JSON missing data/layout")


def test_data_loading():
    for sample in ("iris", "breast_cancer", "digits", "sales", "weather", "ecommerce"):
        df = data.load_sample(sample)
        if df.empty:
            raise AssertionError(f"{sample} sample is empty")

    df = data.load_from_text("name,score\nAda,10\nGrace,12")
    if list(df.columns) != ["name", "score"] or len(df) != 2:
        raise AssertionError("CSV text parsing failed")


def test_url_loading():
    tmp_path = Path(tempfile.gettempdir()) / "synthesis_suite_smoke_url_import.csv"
    tmp_path.write_text("name,score\nAda,10\nGrace,12\n", encoding="utf-8")
    try:
        df = data.load_from_url(tmp_path.as_uri(), "csv")
    finally:
        tmp_path.unlink(missing_ok=True)

    if list(df.columns) != ["name", "score"] or len(df) != 2:
        raise AssertionError("URL CSV import failed")


def test_cleaning_features():
    base_kwargs = {
        "missing_method": "none",
        "remove_outliers": False,
        "outlier_threshold": 1.5,
        "dtype_column": None,
        "dtype_convert": None,
        "scale_method": None,
    }

    load_sample("iris")
    res = data.apply_cleaning(
        **base_kwargs,
        binarize_column="__all_numeric__",
        binarize_threshold=2.5,
        selection_target="target",
        selection_method="chi2",
        selection_k=3,
    )
    if res["cols"] != 4:
        raise AssertionError("Binarization + feature selection did not keep top 3 plus target")

    load_sample("iris")
    res = data.apply_cleaning(
        **base_kwargs,
        extraction_target="target",
        extraction_method="pca",
        extraction_components=2,
    )
    if res["cols"] != 3:
        raise AssertionError("PCA extraction did not produce 2 components plus target")

    load_sample("iris")
    res = data.apply_cleaning(
        **base_kwargs,
        extraction_target="target",
        extraction_method="lda",
        extraction_components=2,
    )
    if res["cols"] != 3:
        raise AssertionError("LDA extraction did not produce 2 components plus target")

    load_sample("iris")
    res = data.apply_cleaning(
        **base_kwargs,
        extraction_target="target",
        extraction_method="autoencoder",
        extraction_components=2,
    )
    if res["cols"] != 3:
        raise AssertionError("Autoencoder extraction did not produce 2 components plus target")

    load_sample("weather")
    weather_kwargs = {**base_kwargs, "missing_method": "distribution", "scale_method": "minmax"}
    res = data.apply_cleaning(
        **weather_kwargs,
        encode_column="Condition",
        encode_method="onehot",
    )
    if res["cols"] <= 5:
        raise AssertionError("Encoding did not expand categorical columns")


def test_charts():
    load_sample("iris")
    chart_cases = [
        ("line", "sepal length (cm)", "petal length (cm)", None),
        ("bar", "target", "petal length (cm)", None),
        ("scatter", "sepal length (cm)", "petal length (cm)", None),
        ("histogram", "sepal length (cm)", None, None),
        ("box", None, "petal length (cm)", None),
        ("violin", None, "petal width (cm)", None),
        ("pie", "target", None, None),
        ("heatmap", None, None, None),
        ("kde", "sepal length (cm)", None, None),
        ("scatter3d", "sepal length (cm)", "sepal width (cm)", "petal length (cm)"),
        ("surface3d", "sepal length (cm)", "sepal width (cm)", "petal length (cm)"),
        ("wireframe3d", "sepal length (cm)", "sepal width (cm)", "petal length (cm)"),
        ("bar3d", "target", "petal length (cm)", None),
    ]
    for chart_type, x_col, y_col, z_col in chart_cases:
        raw = charts.generate_chart(
            chart_type=chart_type,
            x_col=x_col,
            y_col=y_col,
            z_col=z_col,
            title=f"Smoke {chart_type}",
            bins=12,
            opacity=0.75,
            use_hue=True,
            show_annotations=True,
            show_grid=True,
            theme="dark",
        )
        assert_chart_json(raw)


def test_model_training():
    regression_models = [
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
    ]
    for model in regression_models:
        load_sample("sales")
        res = ml.train_model(model, "Sales", 0.2, True, "standard", 20, 4, 5, 3)
        if not res["metrics"]:
            raise AssertionError(f"{model} returned no metrics")

    classification_models = [
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
        "self_training_classification",
    ]
    for model in classification_models:
        load_sample("iris")
        res = ml.train_model(model, "target", 0.2, True, "standard", 20, 4, 5, 3)
        if not res["metrics"]:
            raise AssertionError(f"{model} returned no metrics")

    unsupervised_models = [
        "kmeans",
        "dbscan",
        "pca_projection",
        "ica_projection",
        "zscore_anomaly",
        "isolation_forest",
        "one_class_svm",
    ]
    for model in unsupervised_models:
        load_sample("iris")
        res = ml.train_model(model, "target", 0.2, True, "standard", 20, 4, 5, 3)
        if not res["metrics"]:
            raise AssertionError(f"{model} returned no metrics")


def test_algorithm_demos():
    names = [
        "ml_taxonomy",
        "alpha_beta",
        "astar",
        "bfs_dfs",
        "decision_tree_demo",
        "naive_bayes_demo",
        "ensemble_methods_demo",
        "genetic_algorithm",
        "hill_climbing",
        "kfold",
        "kmeans_demo",
        "dbscan_demo",
        "pca_demo",
        "ica_demo",
        "apriori_demo",
        "fpgrowth_demo",
        "zscore_anomaly_demo",
        "isolation_forest_demo",
        "one_class_svm_demo",
        "self_training_demo",
        "co_training_demo",
        "q_learning_demo",
        "policy_optimization_demo",
        "dynamic_programming_demo",
        "time_series_demo",
        "logistic_iris",
        "logistic_breast",
        "logistic_digits",
        "onehot",
        "svm_demo",
    ]
    for name in names:
        res = ml.run_algorithm(name)
        if not res.get("output"):
            raise AssertionError(f"{name} returned no output")
        if res.get("chart"):
            assert_chart_json(res["chart"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Skip slower model and algorithm sweeps.")
    args = parser.parse_args()

    check("data loading", test_data_loading)
    check("URL loading", test_url_loading)
    check("cleaning features", test_cleaning_features)
    check("charts", test_charts)
    if not args.quick:
        check("model training", test_model_training)
        check("algorithm demos", test_algorithm_demos)
    print("Backend smoke suite completed.")


if __name__ == "__main__":
    main()
