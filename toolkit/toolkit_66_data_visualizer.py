"""
toolkit_66_data_visualizer.py
Create charts and graphs as image files: bar, line, pie, scatter,
histogram, heatmap. Uses matplotlib (soft-import) with text fallback.
"""
from __future__ import annotations
import os
from typing import Any, Dict, List

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

def check_matplotlib() -> Dict[str, Any]:
    return {"success": True, "data": {"matplotlib": HAS_MPL}, "error": None}

def bar_chart(labels: list, values: list, output_path: str, title: str = "", xlabel: str = "", ylabel: str = "", color: str = "steelblue") -> Dict[str, Any]:
    try:
        if not HAS_MPL:
            return {"success": False, "data": None, "error": "matplotlib not installed (pip install matplotlib)"}
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(labels, values, color=color)
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def horizontal_bar_chart(labels: list, values: list, output_path: str, title: str = "", color: str = "steelblue") -> Dict[str, Any]:
    try:
        if not HAS_MPL:
            return {"success": False, "data": None, "error": "matplotlib not installed"}
        fig, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.4)))
        ax.barh(labels, values, color=color)
        ax.set_title(title)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def line_chart(x_values: list, y_values: list, output_path: str, title: str = "", xlabel: str = "", ylabel: str = "", color: str = "steelblue") -> Dict[str, Any]:
    try:
        if not HAS_MPL:
            return {"success": False, "data": None, "error": "matplotlib not installed"}
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(x_values, y_values, color=color, marker="o", markersize=4)
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def multi_line_chart(x_values: list, series: dict, output_path: str, title: str = "") -> Dict[str, Any]:
    """series: {name: [y_values]}"""
    try:
        if not HAS_MPL:
            return {"success": False, "data": None, "error": "matplotlib not installed"}
        fig, ax = plt.subplots(figsize=(10, 6))
        for name, values in series.items():
            ax.plot(x_values, values, label=name, marker="o", markersize=3)
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def pie_chart(labels: list, values: list, output_path: str, title: str = "") -> Dict[str, Any]:
    try:
        if not HAS_MPL:
            return {"success": False, "data": None, "error": "matplotlib not installed"}
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        ax.set_title(title)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def scatter_plot(x_values: list, y_values: list, output_path: str, title: str = "", xlabel: str = "", ylabel: str = "", color: str = "steelblue") -> Dict[str, Any]:
    try:
        if not HAS_MPL:
            return {"success": False, "data": None, "error": "matplotlib not installed"}
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(x_values, y_values, alpha=0.7, color=color)
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def histogram(values: list, output_path: str, title: str = "", bins: int = 20, color: str = "steelblue") -> Dict[str, Any]:
    try:
        if not HAS_MPL:
            return {"success": False, "data": None, "error": "matplotlib not installed"}
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.hist(values, bins=bins, color=color, edgecolor="black", alpha=0.7)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def stacked_bar_chart(labels: list, series: dict, output_path: str, title: str = "") -> Dict[str, Any]:
    """series: {group_name: [values per label]}"""
    try:
        if not HAS_MPL:
            return {"success": False, "data": None, "error": "matplotlib not installed"}
        import numpy as np
        fig, ax = plt.subplots(figsize=(10, 6))
        bottoms = [0.0] * len(labels)
        for name, values in series.items():
            ax.bar(labels, values, bottom=bottoms, label=name)
            bottoms = [b + v for b, v in zip(bottoms, values)]
        ax.set_title(title)
        ax.legend()
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def table_to_image(headers: list, rows: list, output_path: str, title: str = "") -> Dict[str, Any]:
    try:
        if not HAS_MPL:
            return {"success": False, "data": None, "error": "matplotlib not installed"}
        fig, ax = plt.subplots(figsize=(max(8, len(headers) * 1.5), max(3, len(rows) * 0.4 + 1)))
        ax.axis("off")
        if title:
            ax.set_title(title)
        table = ax.table(cellText=rows, colLabels=headers, cellLoc="center", loc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.5)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def ascii_bar_chart(labels: list, values: list, width: int = 40) -> Dict[str, Any]:
    """Generate a text-based bar chart (no matplotlib needed)."""
    try:
        max_val = max(values) if values else 1
        lines = []
        for label, val in zip(labels, values):
        	bar_len = int((val / max_val) * width)
        	bar = "#" * bar_len
        	lines.append(f"{str(label)[:15]:>15} | {bar:<{width}} {val}")
        return {"success": True, "data": "\n".join(lines), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
