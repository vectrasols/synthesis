"""
server.py — FastAPI server for Synthesis Suite
Spawned by Electron main process, runs on localhost at a dynamic port.
"""

import sys
import os
import argparse
from typing import Optional

import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

# Add backend dir to path
sys.path.insert(0, os.path.dirname(__file__))

import data_service as ds
import chart_service as cs
import ml_service as ml

app = FastAPI(title="Synthesis Suite API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Electron renderer
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "Synthesis Suite"}


# ─── Data Loading ────────────────────────────────────────────────────────────────

@app.post("/api/data/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        df = ds.load_from_bytes(content, file.filename)
        ds.store.on_data_loaded(df, file.filename)
        return ds.store.get_info()
    except Exception as e:
        raise HTTPException(400, str(e))


class UrlRequest(BaseModel):
    url: str
    fmt: str = "auto"

@app.post("/api/data/load-url")
def load_url(req: UrlRequest):
    try:
        df = ds.load_from_url(req.url, req.fmt)
        ds.store.on_data_loaded(df, f"URL: {req.url[:60]}")
        return ds.store.get_info()
    except Exception as e:
        raise HTTPException(400, str(e))


class TextRequest(BaseModel):
    text: str
    source_name: str = "Clipboard Data"

@app.post("/api/data/load-text")
def load_text(req: TextRequest):
    try:
        df = ds.load_from_text(req.text)
        ds.store.on_data_loaded(df, req.source_name)
        return ds.store.get_info()
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/data/info")
def get_info():
    return ds.store.get_info()


@app.get("/api/data/preview")
def get_preview(n: int = 20, cleaned: bool = False):
    return ds.get_preview_rows(n, cleaned)


@app.get("/api/data/column-values")
def get_column_values(col: str):
    return {"values": ds.get_column_unique_values(col)}


# ─── Filtering ───────────────────────────────────────────────────────────────────

class FilterRequest(BaseModel):
    col: str
    condition: str
    value: str

@app.post("/api/data/filter")
def apply_filter(req: FilterRequest):
    try:
        return ds.apply_filter(req.col, req.condition, req.value)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/data/clear-filters")
def clear_filters():
    return ds.clear_filters()


# ─── Charts ─────────────────────────────────────────────────────────────────────

class ChartRequest(BaseModel):
    chart_type: str
    x_col: Optional[str] = None
    y_col: Optional[str] = None
    z_col: Optional[str] = None
    title: str = "Chart"
    bins: int = 20
    opacity: float = 0.7
    use_hue: bool = False
    show_annotations: bool = False
    show_grid: bool = True
    theme: str = "dark"

@app.post("/api/chart/plot")
def get_chart(req: ChartRequest):
    try:
        chart_json = cs.generate_chart(
            chart_type=req.chart_type,
            x_col=req.x_col,
            y_col=req.y_col,
            z_col=req.z_col,
            title=req.title,
            bins=req.bins,
            opacity=req.opacity,
            use_hue=req.use_hue,
            show_annotations=req.show_annotations,
            show_grid=req.show_grid,
            theme=req.theme,
        )
        return Response(content=chart_json, media_type="application/json")
    except Exception as e:
        raise HTTPException(400, str(e))


# ─── Cleaning ────────────────────────────────────────────────────────────────────

class CleanRequest(BaseModel):
    missing_method: str = "none"
    remove_outliers: bool = False
    outlier_threshold: float = 1.5
    dtype_column: Optional[str] = None
    dtype_convert: Optional[str] = None
    scale_method: Optional[str] = None
    binarize_column: Optional[str] = None
    binarize_threshold: float = 0.0
    encode_column: Optional[str] = None
    encode_method: Optional[str] = None
    selection_target: Optional[str] = None
    selection_method: Optional[str] = None
    selection_k: int = 5
    extraction_target: Optional[str] = None
    extraction_method: Optional[str] = None
    extraction_components: int = 2

@app.post("/api/clean/apply")
def apply_cleaning(req: CleanRequest):
    try:
        return ds.apply_cleaning(
            missing_method=req.missing_method,
            remove_outliers=req.remove_outliers,
            outlier_threshold=req.outlier_threshold,
            dtype_column=req.dtype_column,
            dtype_convert=req.dtype_convert,
            scale_method=req.scale_method,
            binarize_column=req.binarize_column,
            binarize_threshold=req.binarize_threshold,
            encode_column=req.encode_column,
            encode_method=req.encode_method,
            selection_target=req.selection_target,
            selection_method=req.selection_method,
            selection_k=req.selection_k,
            extraction_target=req.extraction_target,
            extraction_method=req.extraction_method,
            extraction_components=req.extraction_components,
        )
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/clean/remove-duplicates")
def remove_duplicates():
    try:
        return ds.remove_duplicates()
    except Exception as e:
        raise HTTPException(400, str(e))


class RollbackRequest(BaseModel):
    step_index: int

@app.get("/api/clean/history")
def get_cleaning_history():
    try:
        return ds.get_cleaning_history()
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/clean/rollback")
def rollback_cleaning(req: RollbackRequest):
    try:
        return ds.rollback_cleaning(req.step_index)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/clean/export")
def export_clean():
    try:
        csv_bytes = ds.export_cleaned_csv()
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=cleaned_data.csv"}
        )
    except Exception as e:
        raise HTTPException(400, str(e))


# ─── Model Training ──────────────────────────────────────────────────────────────

class TrainRequest(BaseModel):
    model_type: str
    target: Optional[str] = None
    test_size: float = 0.2
    scale_data: bool = True
    scale_type: str = "standard"
    n_estimators: int = 100
    max_depth: int = 10
    n_neighbors: int = 5
    n_clusters: int = 3

@app.post("/api/model/train")
def train_model(req: TrainRequest):
    try:
        return ml.train_model(
            model_type=req.model_type,
            target=req.target,
            test_size=req.test_size,
            scale_data=req.scale_data,
            scale_type=req.scale_type,
            n_estimators=req.n_estimators,
            max_depth=req.max_depth,
            n_neighbors=req.n_neighbors,
            n_clusters=req.n_clusters,
        )
    except Exception as e:
        raise HTTPException(400, str(e))


# ─── Algorithms ──────────────────────────────────────────────────────────────────

class AlgoRequest(BaseModel):
    name: str

@app.post("/api/algorithms/run")
def run_algorithm(req: AlgoRequest):
    try:
        result = ml.run_algorithm(req.name)
        return result
    except Exception as e:
        raise HTTPException(400, str(e))


# ─── Entry point ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8374)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
