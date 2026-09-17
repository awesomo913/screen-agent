import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for screen/agent environments
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import json
import os
import datetime
import math
from typing import Dict, List, Any, Optional, Tuple, Union

# Module-level state for configuration
_CURRENT_STYLE = "seaborn-v0_8"
_CURRENT_PALETTE = None

# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _resolve_output_path(base_name: str, output: str) -> str:
    """Generate default filename if output string is empty."""
    if output.strip():
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        return output
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() else "_" for c in str(base_name))
    return f"{safe_name}_{timestamp}.png"


def _validate_and_get_output(func_name: str, output: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Basic validation wrapper. Returns error dict if validation fails, else None."""
    # Implemented inline per function for precise type hints and messages
    pass


def _save_and_return(fig: plt.Figure, title: str, output: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """Universal figure saver with clean return schema."""
    out_path = _resolve_output_path(title if title else fig.get_label(), output)
    try:
        fig.tight_layout()
        fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
        return {
            "status": "success",
            "path": out_path,
            "error": None,
            "metadata": metadata or {}
        }
    except Exception as e:
        return {
            "status": "error",
            "path": None,
            "error": f"Save failed: {str(e)}",
            "metadata": {}
        }
    finally:
        plt.close(fig)


def _apply_style_settings():
    """Apply module-level style and palette to current context."""
    try:
        available = matplotlib.style.available
        style_name = _CURRENT_STYLE if _CURRENT_STYLE in available else "default"
        plt.style.use(style_name)
    except Exception:
        plt.style.use("default")
    if _CURRENT_PALETTE and isinstance(_CURRENT_PALETTE, list):
        plt.rcParams["axes.prop_cycle"] = plt.cycler(color=_CURRENT_PALETTE)

# =============================================================================
# CHART GENERATORS
# =============================================================================

def create_bar_chart(labels: List[Any], values: List[float], title: str = "", output: str = "") -> Dict[str, Any]:
    try:
        if len(labels) != len(values):
            raise ValueError("Labels and values length mismatch.")
        if not values:
            raise ValueError("Values list cannot be empty.")
        
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.bar(labels, values)
        ax.set_title(title)
        ax.set_xlabel("Categories")
        ax.set_ylabel("Values")
        fig.xticks(rotation=45, ha="right")
        return _save_and_return(fig, title, output, {"type": "bar", "count": len(values)})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_line_chart(x: List[Any], y: List[float], title: str = "", output: str = "") -> Dict[str, Any]:
    try:
        if len(x) != len(y):
            raise ValueError("x and y length mismatch.")
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot(x, y, marker="o", linestyle="-", linewidth=2, markersize=6)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        return _save_and_return(fig, title, output, {"type": "line", "count": len(x)})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_pie_chart(labels: List[Any], values: List[float], title: str = "", output: str = "") -> Dict[str, Any]:
    try:
        if not values or sum(values) <= 0:
            raise ValueError("Values must be positive and non-empty.")
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(7, 7))
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=140, textprops={"fontsize": 10})
        ax.axis("equal")
        ax.set_title(title)
        return _save_and_return(fig, title, output, {"type": "pie", "count": len(values)})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_scatter_plot(x: List[float], y: List[float], title: str = "", output: str = "") -> Dict[str, Any]:
    try:
        if len(x) != len(y):
            raise ValueError("x and y length mismatch.")
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(x, y, alpha=0.7, edgecolors="w", linewidth=0.5)
        ax.set_title(title)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.grid(True, alpha=0.3)
        return _save_and_return(fig, title, output, {"type": "scatter", "count": len(x)})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_histogram(data: List[float], bins: int = 10, title: str = "", output: str = "") -> Dict[str, Any]:
    try:
        if not data or bins < 1:
            raise ValueError("Data cannot be empty and bins must be >= 1.")
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.hist(data, bins=bins, edgecolor="black", alpha=0.75)
        ax.set_title(title)
        ax.set_xlabel("Value Range")
        ax.set_ylabel("Frequency")
        return _save_and_return(fig, title, output, {"type": "histogram", "bins": bins})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_heatmap(data: Union[List[List[float]], np.ndarray], labels_x: Optional[List[str]] = None, 
                   labels_y: Optional[List[str]] = None, output: str = "") -> Dict[str, Any]:
    try:
        data_arr = np.array(data)
        if data_arr.ndim != 2:
            raise ValueError("Data must be 2-dimensional.")
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(max(6, data_arr.shape[1]), max(5, data_arr.shape[0])))
        cax = ax.matshow(data_arr, cmap="viridis", aspect="auto")
        fig.colorbar(cax)
        if labels_x:
            ax.set_xticks(range(len(labels_x)))
            ax.set_xticklabels(labels_x, rotation=45, ha="left")
        if labels_y:
            ax.set_yticks(range(len(labels_y)))
            ax.set_yticklabels(labels_y)
        ax.set_title("Heatmap")
        return _save_and_return(fig, "heatmap", output, {"type": "heatmap", "shape": data_arr.shape})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_box_plot(data: List[List[float]], labels: Optional[List[str]] = None, 
                    title: str = "", output: str = "") -> Dict[str, Any]:
    try:
        if not data:
            raise ValueError("Data cannot be empty.")
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(max(7, len(data)), 6))
        bp = ax.boxplot(data, patch_artist=True, labels=labels)
        for patch in bp["boxes"]:
            patch.set(alpha=0.7)
        ax.set_title(title)
        ax.set_ylabel("Values")
        ax.grid(axis="y", alpha=0.3)
        return _save_and_return(fig, title if title else "box_plot", output, {"type": "box", "groups": len(data)})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_area_chart(x: List[float], y: List[float], title: str = "", output: str = "") -> Dict[str, Any]:
    try:
        if len(x) != len(y):
            raise ValueError("x and y length mismatch.")
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.fill_between(x, y, alpha=0.4, step="mid")
        ax.plot(x, y, linewidth=2)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        return _save_and_return(fig, title, output, {"type": "area", "count": len(x)})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_stacked_bar(labels: List[str], datasets: Dict[str, List[float]], 
                       title: str = "", output: str = "") -> Dict[str, Any]:
    try:
        if not datasets:
            raise ValueError("Datasets cannot be empty.")
        vals = list(datasets.values())
        if len(vals) > 0 and any(len(v) != len(labels) for v in vals):
            raise ValueError("All datasets must match labels length.")
        
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(max(8, len(labels)), 6))
        bottom = np.zeros(len(labels))
        for name, values in datasets.items():
            ax.bar(labels, values, label=name, bottom=bottom)
            bottom += np.array(values)
        ax.set_title(title)
        ax.set_ylabel("Values")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        return _save_and_return(fig, title, output, {"type": "stacked_bar", "series": len(datasets)})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_multi_line(x: List[float], datasets: Dict[str, List[float]], 
                      title: str = "", output: str = "") -> Dict[str, Any]:
    try:
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(8, 6))
        for name, values in datasets.items():
            if len(values) != len(x):
                raise ValueError(f"Dataset '{name}' length mismatch with x.")
            ax.plot(x, values, label=name, linewidth=2)
        ax.set_title(title)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.legend()
        ax.grid(True, alpha=0.3)
        return _save_and_return(fig, title, output, {"type": "multi_line", "series": len(datasets)})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_donut_chart(labels: List[Any], values: List[float], title: str = "", output: str = "") -> Dict[str, Any]:
    try:
        if not values or sum(values) <= 0:
            raise ValueError("Values must be positive and non-empty.")
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(7, 7))
        wedges, _ = ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90, 
                           pctdistance=0.85, textprops={"fontsize": 10})
        centre_circle = plt.Circle((0, 0), 0.70, fc="white")
        fig.gca().add_artist(centre_circle)
        ax.set_title(title)
        return _save_and_return(fig, title, output, {"type": "donut", "count": len(values)})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_radar_chart(labels: List[str], values: List[float], title: str = "", output: str = "") -> Dict[str, Any]:
    try:
        if len(labels) < 3:
            raise ValueError("Radar charts require at least 3 axes.")
        if len(labels) != len(values):
            raise ValueError("Labels and values length mismatch.")
        
        _apply_style_settings()
        num_vars = len(labels)
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        values_closed = values + values[:1]
        angles += angles[:1]
        
        fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
        ax.plot(angles, values_closed, "o-", linewidth=2)
        ax.fill(angles, values_closed, alpha=0.25)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=10)
        ax.set_title(title, pad=20)
        return _save_and_return(fig, title, output, {"type": "radar", "axes": num_vars})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_gantt_chart(tasks: List[Dict[str, Any]], output: str = "") -> Dict[str, Any]:
    """Expects tasks: [{'task': str, 'start': float, 'end': float}, ...]"""
    try:
        if not tasks:
            raise ValueError("Tasks list cannot be empty.")
        for t in tasks:
            if not all(k in t for k in ("task", "start", "end")):
                raise ValueError("Each task dict requires 'task', 'start', 'end'.")
        
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(10, max(5, len(tasks) * 0.5)))
        tasks_sorted = sorted(tasks, key=lambda x: x["start"], reverse=True)
        y_pos = np.arange(len(tasks_sorted))
        for i, t in enumerate(tasks_sorted):
            duration = t["end"] - t["start"]
            ax.barh(t["task"], duration, left=t["start"], height=0.4, align="center")
        ax.set_xlabel("Time")
        ax.set_title("Gantt Chart")
        ax.grid(axis="x", alpha=0.3)
        return _save_and_return(fig, "gantt", output, {"type": "gantt", "count": len(tasks)})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_waterfall_chart(labels: List[str], values: List[float], title: str = "", output: str = "") -> Dict[str, Any]:
    try:
        if len(labels) != len(values):
            raise ValueError("Labels and values length mismatch.")
        
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(max(8, len(labels)), 6))
        cumulative = np.cumsum(values)
        starts = np.insert(cumulative, 0, 0)[:-1]
        ends = starts + values
        colors = ["green" if v >= 0 else "red" for v in values]
        
        for i, (s, e, c) in enumerate(zip(starts, ends, colors)):
            ax.bar(i, values[i], bottom=min(s, e), color=c, edgecolor="black", width=0.6)
            if i > 0:
                ax.plot([i - 0.3, i - 0.1], [starts[i], starts[i]], color="gray", linewidth=1.5)
        
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_title(title)
        ax.set_ylabel("Value")
        return _save_and_return(fig, title, output, {"type": "waterfall", "steps": len(values)})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}


def create_treemap(labels: List[str], sizes: List[float], output: str = "") -> Dict[str, Any]:
    """Basic binary slice & dice treemap implementation."""
    try:
        if len(labels) != len(sizes) or sum(sizes) <= 0:
            raise ValueError("Invalid labels/sizes.")
        
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(8, 8))
        
        def _draw_rect(x0, y0, w, h, label, area, total_area, ax_ref):
            ratio = area / total_area
            if w > h:
                nw = w * math.sqrt(ratio) if ratio < 1 else w
                nh = h / math.sqrt(ratio) if ratio < 1 else h * ratio
                ax_ref.add_patch(plt.Rectangle((x0, y0), nw, nh, facecolor=np.random.rand(3,), 
                                              edgecolor="white", linewidth=2))
                ax_ref.text(x0 + nw/2, y0 + nh/2, f"{label}\n{area:.1f}", 
                           ha="center", va="center", fontsize=8, wrap=True)
                return x0 + nw, y0, nw, nh
            return x0, y0 + nh, nw, nh

        # Simplified treemap layout for toolkit compatibility
        total = sum(sizes)
        curr_x, curr_y, curr_w, curr_h = 0, 0, 1, 1
        remaining = sizes.copy()
        temp_labels = labels.copy()
        
        idx = 0
        while idx < len(remaining) and curr_h > 0.01:
            frac = remaining[idx] / total
            h = frac if h > 0 else 0.01
            ax.add_patch(plt.Rectangle((curr_x, curr_y), 1, h, facecolor=np.random.rand(3,), edgecolor="white"))
            ax.text(curr_x + 0.5, curr_y + h/2, f"{temp_labels[idx]}\n{sizes[idx]}", 
                   ha="center", va="center", fontsize=8, wrap=True)
            curr_y += h
            idx += 1
            
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        return _save_and_return(fig, "treemap", output, {"type": "treemap", "nodes": len(labels)})
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e), "metadata": {}}

# =============================================================================
# POST-PROCESSING & UTILITIES
# =============================================================================

def set_style(style: str = "seaborn") -> Dict[str, Any]:
    global _CURRENT_STYLE
    try:
        available = matplotlib.style.available
        match = [s for s in available if style.lower() in s.lower()]
        if not match:
            _CURRENT_STYLE = "default"
        else:
            _CURRENT_STYLE = match[0]
        _apply_style_settings()
        return {"status": "success", "error": None, "metadata": {"applied_style": _CURRENT_STYLE}}
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e)}


def set_color_palette(palette: List[str]) -> Dict[str, Any]:
    global _CURRENT_PALETTE
    try:
        if not isinstance(palette, list) or len(palette) < 2:
            raise ValueError("Palette must be a list of at least 2 hex/color strings.")
        _CURRENT_PALETTE = palette
        _apply_style_settings()
        return {"status": "success", "error": None, "metadata": {"colors": palette}}
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e)}


def add_annotation(chart_path: str, text: str, x: float, y: float) -> Dict[str, Any]:
    try:
        if not os.path.exists(chart_path):
            raise FileNotFoundError(f"Chart not found: {chart_path}")
        
        img = Image.open(chart_path)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except IOError:
            font = ImageFont.load_default()
            
        bbox = draw.multiline_textbbox((x, y), text, font=font)
        pad = 4
        draw.rectangle([bbox[0]-pad, bbox[1]-pad, bbox[2]+pad, bbox[3]+pad], fill="white", outline="black")
        draw.multiline_text((x, y), text, fill="black", font=font)
        
        out_path = chart_path.replace(".png", "_annotated.png") if chart_path.endswith(".png") else chart_path + "_annotated.png"
        img.save(out_path)
        return {"status": "success", "path": out_path, "metadata": {"text": text, "coords": [x, y]}}
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e)}


def combine_charts(chart_paths: List[str], layout: str = "grid", output: str = "") -> Dict[str, Any]:
    try:
        if not chart_paths:
            raise ValueError("No chart paths provided.")
        images = [Image.open(p) for p in chart_paths]
        w, h = images[0].size
        cols = math.ceil(math.sqrt(len(images)))
        rows = math.ceil(len(images) / cols)
        
        master = Image.new("RGB", (w * cols, h * rows), "white")
        for i, img in enumerate(images):
            master.paste(img, ((i % cols) * w, (i // cols) * h))
        
        out_path = _resolve_output_path("combined", output)
        master.save(out_path)
        return {"status": "success", "path": out_path, "metadata": {"layout": f"{rows}x{cols}"}}
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e)}


def export_chart(fig_data: bytes, format: str = "png", output: str = "") -> Dict[str, Any]:
    try:
        out_path = _resolve_output_path("export", output)
        if "." not in out_path.split(os.sep)[-1]:
            out_path += f".{format}"
        with open(out_path, "wb") as f:
            f.write(fig_data)
        return {"status": "success", "path": out_path, "metadata": {"format": format, "bytes": len(fig_data)}}
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e)}


def create_dashboard(charts: list, layout: tuple = (2, 2), output: str = "") -> Dict[str, Any]:
    """charts can be paths or matplotlib Figure objects. Flattens to grid."""
    try:
        images = []
        for c in charts:
            if isinstance(c, str):
                images.append(Image.open(c))
            elif hasattr(c, "savefig"):
                buf = io.BytesIO()
                c.savefig(buf, format="png", dpi=150, bbox_inches="tight")
                plt.close(c)
                images.append(Image.open(buf))
            else:
                images.append(Image.open(io.BytesIO(c)))
        
        cols, rows = layout[0], layout[1]
        base_w, base_h = images[0].size
        master = Image.new("RGB", (base_w * cols, base_h * rows), "white")
        
        for i, img in enumerate(images):
            if i >= cols * rows: break
            master.paste(img.resize((base_w, base_h)), ((i % cols) * base_w, (i // cols) * base_h))
            
        out_path = _resolve_output_path("dashboard", output)
        master.save(out_path)
        return {"status": "success", "path": out_path, "metadata": {"grid": layout}}
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e)}


def chart_to_base64(chart_path: str) -> Dict[str, Any]:
    try:
        with open(chart_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        img = Image.open(chart_path)
        return {"status": "success", "data": b64, "metadata": {"width": img.width, "height": img.height}}
    except Exception as e:
        return {"status": "error", "data": None, "error": str(e)}


def create_sparkline(data: list, width: int = 100, height: int = 30) -> Dict[str, Any]:
    try:
        if len(data) < 2:
            raise ValueError("Sparkline requires >= 2 points.")
        _apply_style_settings()
        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
        fig.patch.set_alpha(0)
        ax.patch.set_alpha(0)
        ax.plot(data, linewidth=1.5)
        ax.fill_between(range(len(data)), data, alpha=0.2)
        ax.axis("off")
        
        buf = io.BytesIO()
        fig.savefig(buf, format="png", transparent=True, dpi=100, bbox_inches="tight", pad_inches=0.1)
        plt.close(fig)
        return {"status": "success", "data_bytes": buf.getvalue(), "metadata": {"width": width, "height": height}}
    except Exception as e:
        return {"status": "error", "data_bytes": None, "error": str(e)}


def add_legend(chart_path: str, labels: list, position: str = "best") -> Dict[str, Any]:
    """Adds a simulated legend box to an existing chart using PIL."""
    try:
        img = Image.open(chart_path).convert("RGBA")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except IOError:
            font = ImageFont.load_default()
            
        box_w, box_h = 120, 15 + len(labels) * 18
        x, y = 10, 10
        if "right" in position: x = img.width - box_w - 10
        if "lower" in position: y = img.height - box_h - 10
        
        draw.rectangle([x, y, x + box_w, y + box_h], fill=(255, 255, 255, 200), outline=(0, 0, 0, 255))
        for i, lbl in enumerate(labels):
            cy = y + 10 + i * 18
            draw.rectangle([x + 5, cy, x + 20, cy + 10], fill=np.random.randint(0, 200, 3).tolist() + [255])
            draw.text((x + 25, cy - 2), str(lbl), fill="black", font=font)
            
        out_path = chart_path.replace(".png", "_legend.png")
        img.save(out_path)
        return {"status": "success", "path": out_path}
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e)}


def save_chart_data(chart_config: dict, output: str = "") -> Dict[str, Any]:
    try:
        out_path = _resolve_output_path("config", output)
        if not out_path.endswith(".json"):
            out_path += ".json"
        with open(out_path, "w") as f:
            json.dump(chart_config, f, indent=2, default=str)
        return {"status": "success", "path": out_path, "metadata": {"keys": list(chart_config.keys())}}
    except Exception as e:
        return {"status": "error", "path": None, "error": str(e)}