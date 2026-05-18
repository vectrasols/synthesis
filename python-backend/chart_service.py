"""
chart_service.py — Plotly JSON chart generation
Converts all matplotlib/seaborn chart logic to Plotly for interactive web rendering.
"""

from typing import Optional, Dict, Any
import json
import numpy as np
import pandas as pd
from scipy import stats
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder

from data_service import store


THEME_TEMPLATES = {
    "light": "plotly_white",
    "dark": "plotly_dark",
    "solarized_light": "plotly_white",
    "solarized_dark": "plotly_dark",
    "nord": "plotly_dark",
    "ocean_blue": "plotly_dark",
    "monokai": "plotly_dark",
    "dracula": "plotly_dark",
    "sepia": "plotly_white",
    "high_contrast": "plotly_dark",
}

THEME_COLORS = {
    "light":           {"bg": "#f0f0f5", "paper": "#ffffff", "text": "#1e1e23", "accent": "#4a90d9"},
    "dark":            {"bg": "#1e1e23", "paper": "#282830", "text": "#f0f0f0", "accent": "#64c8ff"},
    "solarized_light": {"bg": "#fdf6e3", "paper": "#eee8d5", "text": "#657b83", "accent": "#268bd2"},
    "solarized_dark":  {"bg": "#002b36", "paper": "#073642", "text": "#839496", "accent": "#268bd2"},
    "nord":            {"bg": "#2e3440", "paper": "#3b4252", "text": "#d8dee9", "accent": "#88c0d0"},
    "ocean_blue":      {"bg": "#0f2032", "paper": "#142c44", "text": "#c8dced", "accent": "#3282c8"},
    "monokai":         {"bg": "#272822", "paper": "#31322c", "text": "#f8f8f2", "accent": "#a6e22e"},
    "dracula":         {"bg": "#282a36", "paper": "#44475a", "text": "#f8f8f2", "accent": "#bd93f9"},
    "sepia":           {"bg": "#f5ebdc", "paper": "#fff8eb", "text": "#503c28", "accent": "#b48c5a"},
    "high_contrast":   {"bg": "#000000", "paper": "#0a0a0a", "text": "#ffffff", "accent": "#ffff00"},
}

COLOR_SEQUENCES = {
    "light": px.colors.qualitative.Set2,
    "dark": px.colors.qualitative.Bold,
    "nord": ["#88c0d0", "#81a1c1", "#5e81ac", "#b48ead", "#a3be8c", "#ebcb8b"],
    "dracula": ["#bd93f9", "#ff79c6", "#50fa7b", "#f1fa8c", "#ffb86c", "#8be9fd"],
    "monokai": ["#a6e22e", "#66d9e8", "#f92672", "#fd971f", "#ae81ff", "#e6db74"],
    "ocean_blue": ["#3282c8", "#5ab4d4", "#1e90ff", "#00bfff", "#87ceeb", "#4169e1"],
}


def _get_colors(theme: str):
    return COLOR_SEQUENCES.get(theme, px.colors.qualitative.Plotly)


def _make_layout(title: str, theme: str, x_label: str = "", y_label: str = "", show_grid: bool = True) -> dict:
    c = THEME_COLORS.get(theme, THEME_COLORS["dark"])
    return dict(
        title=dict(text=title, font=dict(size=18, color=c["text"])),
        paper_bgcolor=c["paper"],
        plot_bgcolor=c["bg"],
        font=dict(color=c["text"], family="Inter, Outfit, sans-serif"),
        xaxis=dict(title=x_label, gridcolor="rgba(128,128,128,0.15)", showgrid=show_grid, zeroline=show_grid, tickfont=dict(size=13), automargin=True),
        yaxis=dict(title=y_label, gridcolor="rgba(128,128,128,0.15)", showgrid=show_grid, zeroline=show_grid, tickfont=dict(size=12), automargin=True),
        margin=dict(l=50, r=30, t=60, b=50),
        showlegend=True,
        legend=dict(bgcolor="rgba(0,0,0,0.3)", bordercolor="rgba(255,255,255,0.1)", borderwidth=1),
    )


def _apply_axis_preferences(fig, show_grid: bool):
    fig.update_xaxes(showgrid=show_grid, zeroline=show_grid, tickfont=dict(size=13), automargin=True)
    fig.update_yaxes(showgrid=show_grid, zeroline=show_grid, tickfont=dict(size=12), automargin=True)
    try:
        fig.update_scenes(
            xaxis_showgrid=show_grid,
            yaxis_showgrid=show_grid,
            zaxis_showgrid=show_grid,
            xaxis_tickfont=dict(size=12),
            yaxis_tickfont=dict(size=12),
            zaxis_tickfont=dict(size=12),
        )
    except Exception:
        pass


def generate_chart(
    chart_type: str,
    x_col: Optional[str],
    y_col: Optional[str],
    z_col: Optional[str],
    title: str,
    bins: int,
    opacity: float,
    use_hue: bool,
    show_annotations: bool,
    show_grid: bool,
    theme: str,
) -> str:
    """Returns Plotly figure as JSON string."""
    plot_df = store.df_filtered if store.df_filtered is not None else store.df
    if plot_df is None:
        fig = go.Figure()
        fig.update_layout(title="No data loaded")
        return json.dumps(fig, cls=PlotlyJSONEncoder)

    colors = _get_colors(theme)
    layout = _make_layout(title, theme, x_col or "", y_col or "", show_grid)
    fig = None

    try:
        # ── Determine hue column ──────────────────────────────────────────────
        hue_col = None
        if use_hue and x_col and x_col in plot_df.columns:
            cat_cols = plot_df.select_dtypes(include=["object", "category"]).columns.tolist()
            candidates = [c for c in cat_cols if c != x_col]
            if candidates:
                hue_col = candidates[0]

        # ── 2D Charts ─────────────────────────────────────────────────────────
        if chart_type == "line":
            if x_col and y_col:
                if hue_col:
                    fig = px.line(plot_df, x=x_col, y=y_col, color=hue_col,
                                  color_discrete_sequence=colors, markers=True)
                else:
                    fig = px.line(plot_df, x=x_col, y=y_col,
                                  color_discrete_sequence=colors, markers=True)

        elif chart_type == "bar":
            if x_col and y_col:
                fig = px.bar(plot_df, x=x_col, y=y_col, color=hue_col,
                             color_discrete_sequence=colors, opacity=opacity,
                             barmode="group" if hue_col else "relative")

        elif chart_type == "scatter":
            if x_col and y_col:
                fig = px.scatter(plot_df, x=x_col, y=y_col, color=hue_col,
                                 color_discrete_sequence=colors, opacity=opacity,
                                 size_max=12)

        elif chart_type == "histogram":
            if x_col:
                fig = px.histogram(plot_df, x=x_col, nbins=bins, opacity=opacity,
                                   color_discrete_sequence=colors)

        elif chart_type == "box":
            if y_col:
                fig = px.box(plot_df, y=y_col, color=hue_col,
                             color_discrete_sequence=colors)

        elif chart_type == "violin":
            if y_col:
                fig = px.violin(plot_df, y=y_col, color=hue_col,
                                color_discrete_sequence=colors, box=True)

        elif chart_type == "pie":
            if x_col:
                vc = plot_df[x_col].value_counts()
                fig = px.pie(values=vc.values, names=vc.index,
                             color_discrete_sequence=colors)

        elif chart_type == "heatmap":
            numeric_df = plot_df.select_dtypes(include=[np.number])
            if not numeric_df.empty:
                corr = numeric_df.corr()
                fig = px.imshow(corr, text_auto=".2f", aspect="auto",
                                color_continuous_scale="RdBu_r", zmin=-1, zmax=1)

        elif chart_type == "kde":
            if x_col:
                data = pd.to_numeric(plot_df[x_col], errors="coerce").dropna()
                kde = stats.gaussian_kde(data)
                x_range = np.linspace(data.min(), data.max(), 300)
                y_range = kde(x_range)
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=x_range, y=y_range, mode="lines",
                                         fill="tozeroy", line=dict(color=colors[0], width=2)))

        # ── 3D Charts ─────────────────────────────────────────────────────────
        elif chart_type == "scatter3d":
            if x_col and y_col and z_col:
                xs = pd.to_numeric(plot_df[x_col], errors="coerce")
                ys = pd.to_numeric(plot_df[y_col], errors="coerce")
                zs = pd.to_numeric(plot_df[z_col], errors="coerce")
                idx = xs.dropna().index.intersection(ys.dropna().index).intersection(zs.dropna().index)
                fig = go.Figure(data=[go.Scatter3d(
                    x=xs[idx], y=ys[idx], z=zs[idx],
                    mode="markers",
                    marker=dict(size=5, color=zs[idx], colorscale="Viridis",
                                opacity=opacity, showscale=True),
                )])
                fig.update_layout(scene=dict(
                    xaxis_title=x_col, yaxis_title=y_col, zaxis_title=z_col))

        elif chart_type == "surface3d":
            if x_col and y_col and z_col:
                from scipy.interpolate import griddata
                xs = pd.to_numeric(plot_df[x_col], errors="coerce").dropna()
                ys = pd.to_numeric(plot_df[y_col], errors="coerce").dropna()
                zs = pd.to_numeric(plot_df[z_col], errors="coerce").dropna()
                idx = xs.index.intersection(ys.index).intersection(zs.index)
                xi = np.linspace(xs[idx].min(), xs[idx].max(), 30)
                yi = np.linspace(ys[idx].min(), ys[idx].max(), 30)
                XI, YI = np.meshgrid(xi, yi)
                ZI = griddata((xs[idx].values, ys[idx].values), zs[idx].values,
                              (XI, YI), method="cubic")
                fig = go.Figure(data=[go.Surface(x=XI, y=YI, z=ZI,
                                                 colorscale="Viridis", opacity=opacity)])
                fig.update_layout(scene=dict(
                    xaxis_title=x_col, yaxis_title=y_col, zaxis_title=z_col))

        elif chart_type == "wireframe3d":
            if x_col and y_col and z_col:
                from scipy.interpolate import griddata
                xs = pd.to_numeric(plot_df[x_col], errors="coerce").dropna()
                ys = pd.to_numeric(plot_df[y_col], errors="coerce").dropna()
                zs = pd.to_numeric(plot_df[z_col], errors="coerce").dropna()
                idx = xs.index.intersection(ys.index).intersection(zs.index)
                xi = np.linspace(xs[idx].min(), xs[idx].max(), 20)
                yi = np.linspace(ys[idx].min(), ys[idx].max(), 20)
                XI, YI = np.meshgrid(xi, yi)
                ZI = griddata((xs[idx].values, ys[idx].values), zs[idx].values,
                              (XI, YI), method="cubic")
                traces = []
                for i in range(ZI.shape[0]):
                    traces.append(go.Scatter3d(x=XI[i], y=YI[i], z=ZI[i],
                                               mode="lines", line=dict(color="#4a90d9", width=2),
                                               showlegend=False))
                for j in range(ZI.shape[1]):
                    traces.append(go.Scatter3d(x=XI[:, j], y=YI[:, j], z=ZI[:, j],
                                               mode="lines", line=dict(color="#4a90d9", width=2),
                                               showlegend=False))
                fig = go.Figure(data=traces)
                fig.update_layout(scene=dict(
                    xaxis_title=x_col, yaxis_title=y_col, zaxis_title=z_col))

        elif chart_type == "bar3d":
            if x_col and y_col:
                data_col = pd.to_numeric(plot_df[y_col], errors="coerce").dropna()
                categories = plot_df[x_col].dropna()
                idx = data_col.index.intersection(categories.index)
                cats = categories[idx].unique()[:20]
                means = [float(data_col[categories[idx] == c].mean()) for c in cats]
                fig = go.Figure(data=[go.Bar(
                    x=list(cats), y=means,
                    marker_color=colors[:len(cats)],
                    opacity=opacity,
                )])

    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(text=f"Chart error: {str(e)}", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(size=14))

    if fig is None:
        fig = go.Figure()
        fig.add_annotation(text="Select columns to generate chart",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(size=16))

    # Apply layout
    c = THEME_COLORS.get(theme, THEME_COLORS["dark"])
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color=c["text"])),
        paper_bgcolor=c["paper"],
        plot_bgcolor=c["bg"],
        font=dict(color=c["text"], family="Inter, Outfit, sans-serif"),
        margin=dict(l=50, r=30, t=60, b=50),
    )
    _apply_axis_preferences(fig, show_grid)

    # Statistical annotations
    if show_annotations and x_col and y_col and chart_type in ("scatter", "line", "histogram", "kde"):
        _add_stat_annotations(fig, plot_df, x_col, y_col, chart_type)

    return json.dumps(fig, cls=PlotlyJSONEncoder)


def _add_stat_annotations(fig, plot_df, x_col, y_col, chart_type):
    try:
        if y_col in plot_df.columns:
            data = pd.to_numeric(plot_df[y_col], errors="coerce").dropna()
            if len(data) > 0:
                mean_val = float(data.mean())
                median_val = float(data.median())
                std_val = float(data.std())
                skew_val = float(data.skew())

                annotation_text = (
                    f"Mean: {mean_val:.2f}<br>"
                    f"Median: {median_val:.2f}<br>"
                    f"Std: {std_val:.2f}<br>"
                    f"Skew: {skew_val:.2f}"
                )

                if chart_type in ("scatter", "line"):
                    fig.add_hline(y=mean_val, line_dash="dash", line_color="red",
                                  annotation_text=f"Mean: {mean_val:.2f}")
                    fig.add_hline(y=median_val, line_dash="dash", line_color="green",
                                  annotation_text=f"Median: {median_val:.2f}")

                if chart_type == "scatter" and x_col in plot_df.columns:
                    x_data = pd.to_numeric(plot_df[x_col], errors="coerce").dropna()
                    idx = x_data.index.intersection(data.index)
                    if len(idx) > 2:
                        r, p = stats.pearsonr(x_data[idx], data[idx])
                        annotation_text += f"<br>r = {r:.3f} (p={p:.2e})"
                        z = np.polyfit(x_data[idx], data[idx], 1)
                        p_line = np.poly1d(z)
                        x_sorted = np.sort(x_data[idx])
                        fig.add_trace(go.Scatter(
                            x=x_sorted, y=p_line(x_sorted),
                            mode="lines", name="Trend",
                            line=dict(color="red", dash="dash", width=1.5)
                        ))

                fig.add_annotation(
                    text=annotation_text, xref="paper", yref="paper",
                    x=0.02, y=0.98, showarrow=False, align="left",
                    bgcolor="rgba(0,0,0,0.5)", bordercolor="rgba(255,255,255,0.3)",
                    borderwidth=1, font=dict(size=11),
                )
    except Exception:
        pass
