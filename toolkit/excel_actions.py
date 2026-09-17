"""
excel_actions.py
----------------

A utility toolkit for working with Excel files (xlsx) from Python.  The module
provides a wide range of actions that can be used by a screen‑agent or any
automation framework.

All functions return a ``dict`` with at least the keys:

* ``success`` – ``bool`` indicating if the operation succeeded.
* ``message`` – Human‑readable description of the outcome.
* ``data``    – Optional payload (e.g. read data, sheet names, etc.).

The implementation relies on:
* ``openpyxl`` – low‑level workbook manipulation
* ``pandas``   – convenient data‑frame handling
* ``xlsxwriter`` – chart creation (via ``openpyxl`` wrapper)
* ``csv``      – CSV import / export
* ``pathlib``  – path handling
* ``os``       – file system checks
* ``json``     – optional JSON serialisation of results
* ``re``       – simple pattern checks for validation
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union, Optional

import pandas as pd
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment, NamedStyle
from openpyxl.utils import get_column_letter, range_boundaries
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule, CellIsRule, ColorScaleRule
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.chart import (
    BarChart,
    LineChart,
    PieChart,
    ScatterChart,
    Reference,
    Series,
)

# --------------------------------------------------------------------------- #
# Helper utilities
# --------------------------------------------------------------------------- #


def _ensure_path(filepath: Union[str, Path]) -> Path:
    """Make sure ``filepath`` is a ``Path`` object and its parent directory exists."""
    p = Path(filepath).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _json_result(result: Dict[str, Any]) -> str:
    """Serialise a result dictionary to JSON (pretty‑printed)."""
    return json.dumps(result, indent=2, default=str)


# --------------------------------------------------------------------------- #
# Core API
# --------------------------------------------------------------------------- #


def read_excel(
    filepath: Union[str, Path],
    sheet: Union[str, int] = 0,
    cell_range: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Read data from an Excel file.

    Parameters
    ----------
    filepath: path to the workbook.
    sheet: sheet name or zero‑based index (default first sheet).
    cell_range: Excel A1 range (e.g. ``"A1:C10"``). If ``None`` returns the whole sheet.

    Returns
    -------
    dict with keys ``success``, ``message`` and ``data`` (list of lists).
    """
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path, data_only=True, read_only=True)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]

        if cell_range:
            data = [[cell.value for cell in row] for row in ws[cell_range]]
        else:
            data = [[cell.value for cell in row] for row in ws.iter_rows(values_only=True)]

        return {"success": True, "message": "Read successful", "data": data}
    except Exception as e:
        return {"success": False, "message": f"Read failed: {e}", "data": None}


def write_excel(
    filepath: Union[str, Path],
    data: List[List[Any]],
    sheet: Union[str, int] = "Sheet1",
) -> Dict[str, Any]:
    """
    Write a 2‑D list to an Excel sheet (creates workbook if missing).

    Parameters
    ----------
    filepath: destination workbook.
    data: list of rows (each row is a list of cell values).
    sheet: target sheet name (or index for existing workbook).

    Returns
    -------
    dict with ``success`` and ``message``.
    """
    try:
        path = _ensure_path(filepath)
        if path.exists():
            wb = load_workbook(path)
        else:
            wb = Workbook()
            # remove the default sheet created by ``Workbook()``
            default_sheet = wb.active
            wb.remove(default_sheet)

        if isinstance(sheet, int):
            # Ensure the sheet index exists
            if sheet < len(wb.sheetnames):
                ws = wb[wb.sheetnames[sheet]]
            else:
                ws = wb.create_sheet(title=f"Sheet{sheet + 1}")
        else:
            if sheet in wb.sheetnames:
                ws = wb[sheet]
            else:
                ws = wb.create_sheet(title=sheet)

        for r_idx, row in enumerate(data, start=1):
            for c_idx, value in enumerate(row, start=1):
                ws.cell(row=r_idx, column=c_idx, value=value)

        wb.save(path)
        return {"success": True, "message": "Write successful", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Write failed: {e}", "data": None}


def create_workbook(
    filepath: Union[str, Path], sheets: List[str]
) -> Dict[str, Any]:
    """
    Create a new workbook with the supplied sheet names.

    Parameters
    ----------
    filepath: path where workbook will be saved.
    sheets: list of sheet names to create.

    Returns
    -------
    dict with ``success`` and ``message``.
    """
    try:
        path = _ensure_path(filepath)
        wb = Workbook()
        # Remove initial sheet created by Workbook()
        wb.remove(wb.active)

        for name in sheets:
            wb.create_sheet(title=name)

        wb.save(path)
        return {"success": True, "message": f"Workbook created with sheets {sheets}", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Creation failed: {e}", "data": None}


def get_sheet_names(filepath: Union[str, Path]) -> Dict[str, Any]:
    """Return a list of all sheet names in the workbook."""
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path, read_only=True)
        return {"success": True, "message": "Sheet names retrieved", "data": wb.sheetnames}
    except Exception as e:
        return {"success": False, "message": f"Failed to get sheet names: {e}", "data": None}


def add_sheet(
    filepath: Union[str, Path], name: str, data: Optional[List[List[Any]]] = None
) -> Dict[str, Any]:
    """
    Add a new sheet (optionally pre‑populated with data).

    Parameters
    ----------
    filepath: workbook path.
    name: new sheet name.
    data: optional 2‑D list to fill the sheet.

    Returns
    -------
    dict indicating success.
    """
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path)
        if name in wb.sheetnames:
            raise ValueError(f"Sheet '{name}' already exists.")

        ws = wb.create_sheet(title=name)
        if data:
            for r_idx, row in enumerate(data, start=1):
                for c_idx, value in enumerate(row, start=1):
                    ws.cell(row=r_idx, column=c_idx, value=value)

        wb.save(path)
        return {"success": True, "message": f"Sheet '{name}' added", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Add sheet failed: {e}", "data": None}


def delete_sheet(
    filepath: Union[str, Path], name: str
) -> Dict[str, Any]:
    """Remove a sheet from the workbook."""
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path)
        if name not in wb.sheetnames:
            raise ValueError(f"Sheet '{name}' does not exist.")
        ws = wb[name]
        wb.remove(ws)
        wb.save(path)
        return {"success": True, "message": f"Sheet '{name}' deleted", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Delete sheet failed: {e}", "data": None}


def read_cell(
    filepath: Union[str, Path], sheet: Union[str, int], cell: str
) -> Dict[str, Any]:
    """Read a single cell."""
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path, data_only=True, read_only=True)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]
        value = ws[cell].value
        return {"success": True, "message": "Cell read", "data": value}
    except Exception as e:
        return {"success": False, "message": f"Read cell failed: {e}", "data": None}


def write_cell(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    cell: str,
    value: Any,
) -> Dict[str, Any]:
    """Write a single cell."""
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]
        ws[cell].value = value
        wb.save(path)
        return {"success": True, "message": "Cell written", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Write cell failed: {e}", "data": None}


def read_range(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    start: str,
    end: str,
) -> Dict[str, Any]:
    """Read a rectangular range defined by two corner cells."""
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path, data_only=True, read_only=True)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]
        cell_range = f"{start}:{end}"
        data = [[cell.value for cell in row] for row in ws[cell_range]]
        return {"success": True, "message": "Range read", "data": data}
    except Exception as e:
        return {"success": False, "message": f"Read range failed: {e}", "data": None}


def write_range(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    start: str,
    data: List[List[Any]],
) -> Dict[str, Any]:
    """Write a 2‑D list starting at the top‑left cell ``start``."""
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]
        start_col, start_row = openpyxl.utils.coordinate_from_string(start)
        start_col_idx = openpyxl.utils.column_index_from_string(start_col)

        for r_offset, row in enumerate(data):
            for c_offset, value in enumerate(row):
                ws.cell(row=start_row + r_offset, column=start_col_idx + c_offset, value=value)

        wb.save(path)
        return {"success": True, "message": "Range written", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Write range failed: {e}", "data": None}


def apply_formula(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    cell: str,
    formula: str,
) -> Dict[str, Any]:
    """Insert a formula into a cell."""
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]
        ws[cell].value = f"={formula}"
        wb.save(path)
        return {"success": True, "message": "Formula applied", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Formula failed: {e}", "data": None}


def format_cells(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    cell_range: str,
    style: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Apply styling to a range of cells.

    ``style`` can contain keys: ``font``, ``fill``, ``border``, ``alignment``.
    Each key expects a dict compatible with the corresponding openpyxl class.
    """
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]

        # Build a NamedStyle (or re‑use if exists)
        ns_name = f"_auto_style_{hash(json.dumps(style, sort_keys=True))}"
        if ns_name in wb.named_styles:
            named_style = wb.named_styles[ns_name]
        else:
            named_style = NamedStyle(name=ns_name)

            if "font" in style:
                font_cfg = style["font"]
                named_style.font = Font(**font_cfg)

            if "fill" in style:
                fill_cfg = style["fill"]
                # Only PatternFill is supported here
                named_style.fill = PatternFill(**fill_cfg)

            if "border" in style:
                border_cfg = style["border"]
                sides = {k: Side(**v) for k, v in border_cfg.items()}
                named_style.border = Border(**sides)

            if "alignment" in style:
                align_cfg = style["alignment"]
                named_style.alignment = Alignment(**align_cfg)

            wb.add_named_style(named_style)

        for row in ws[cell_range]:
            for cell in row:
                cell.style = ns_name

        wb.save(path)
        return {"success": True, "message": "Cells formatted", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Formatting failed: {e}", "data": None}


def merge_cells(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    cell_range: str,
) -> Dict[str, Any]:
    """Merge a rectangular range of cells."""
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]
        ws.merge_cells(cell_range)
        wb.save(path)
        return {"success": True, "message": f"Cells merged ({cell_range})", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Merge failed: {e}", "data": None}


def auto_fit_columns(
    filepath: Union[str, Path],
    sheet: Union[str, int],
) -> Dict[str, Any]:
    """
    Auto‑size columns based on the longest entry in each column.
    """
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]

        for column_cells in ws.columns:
            max_length = 0
            column = column_cells[0].column_letter
            for cell in column_cells:
                if cell.value:
                    length = len(str(cell.value))
                    if length > max_length:
                        max_length = length
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column].width = adjusted_width

        wb.save(path)
        return {"success": True, "message": "Columns auto‑fitted", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Auto‑fit failed: {e}", "data": None}


def add_chart(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    chart_type: str,
    data_range: str,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Insert a chart into a sheet.

    Parameters
    ----------
    chart_type: ``"bar"``, ``"line"``, ``"pie"``, ``"scatter"``.
    data_range: e.g. ``"A1:B5"`` (must include categories and values).
    title: optional chart title.
    """
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]

        min_col, min_row, max_col, max_row = range_boundaries(data_range)
        data = Reference(ws, min_col=min_col + 1, min_row=min_row, max_row=max_row)
        cats = Reference(ws, min_col=min_col, min_row=min_row + 1, max_row=max_row)

        chart: Union[BarChart, LineChart, PieChart, ScatterChart]
        chart_type = chart_type.lower()
        if chart_type == "bar":
            chart = BarChart()
        elif chart_type == "line":
            chart = LineChart()
        elif chart_type == "pie":
            chart = PieChart()
        elif chart_type == "scatter":
            chart = ScatterChart()
        else:
            raise ValueError(f"Unsupported chart_type '{chart_type}'")

        chart.add_data(data, titles_from_data=False)
        if chart_type != "pie":
            chart.set_categories(cats)

        if title:
            chart.title = title

        # Place chart at a default location (top‑left corner after data)
        ws.add_chart(chart, "E2")
        wb.save(path)
        return {"success": True, "message": f"{chart_type.title()} chart added", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Add chart failed: {e}", "data": None}


def filter_data(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    column: str,
    criteria: str,
) -> Dict[str, Any]:
    """
    Apply an auto‑filter on a column based on a criteria expression
    compatible with pandas query syntax.
    Returns the filtered rows as a list of dicts.
    """
    try:
        path = _ensure_path(filepath)
        df = pd.read_excel(path, sheet_name=sheet if isinstance(sheet, str) else sheet)
        filtered = df.query(f"`{column}` {criteria}")
        result = filtered.to_dict(orient="records")
        return {"success": True, "message": "Data filtered", "data": result}
    except Exception as e:
        return {"success": False, "message": f"Filter failed: {e}", "data": None}


def sort_data(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    column: str,
    ascending: bool = True,
) -> Dict[str, Any]:
    """
    Sort a sheet by a column and write the sorted data back.
    Returns the sorted data for verification.
    """
    try:
        path = _ensure_path(filepath)
        df = pd.read_excel(path, sheet_name=sheet if isinstance(sheet, str) else sheet)
        df_sorted = df.sort_values(by=column, ascending=ascending)
        # Write back
        with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df_sorted.to_excel(writer, sheet_name=sheet if isinstance(sheet, str) else sheet, index=False)

        return {"success": True, "message": "Data sorted", "data": df_sorted.to_dict(orient="records")}
    except Exception as e:
        return {"success": False, "message": f"Sort failed: {e}", "data": None}


def pivot_table(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    rows: List[str],
    cols: List[str],
    values: List[str],
    aggfunc: str = "sum",
) -> Dict[str, Any]:
    """
    Generate a pivot table using pandas and write it to a new sheet
    named ``"<original>_pivot"``.
    """
    try:
        path = _ensure_path(filepath)
        df = pd.read_excel(path, sheet_name=sheet if isinstance(sheet, str) else sheet)

        pivot = pd.pivot_table(
            df,
            index=rows,
            columns=cols,
            values=values,
            aggfunc=aggfunc,
            fill_value=0,
        )
        pivot_sheet = f"{ws.title}_pivot" if isinstance(sheet, int) else f"{sheet}_pivot"

        with pd.ExcelWriter(path, engine="openpyxl", mode="a") as writer:
            pivot.to_excel(writer, sheet_name=pivot_sheet)

        return {"success": True, "message": "Pivot table created", "data": pivot.to_dict()}
    except Exception as e:
        return {"success": False, "message": f"Pivot failed: {e}", "data": None}


def vlookup(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    lookup_val: Any,
    col: str,
) -> Dict[str, Any]:
    """
    Emulate Excel VLOOKUP using pandas: search ``lookup_val`` in the first column
    and return the value from column ``col`` (column name, not index).
    """
    try:
        path = _ensure_path(filepath)
        df = pd.read_excel(path, sheet_name=sheet if isinstance(sheet, str) else sheet)

        # Find first occurrence
        match = df[df.iloc[:, 0] == lookup_val]
        if match.empty:
            raise ValueError("Lookup value not found")

        value = match.iloc[0][col]
        return {"success": True, "message": "VLOOKUP successful", "data": value}
    except Exception as e:
        return {"success": False, "message": f"VLOOKUP failed: {e}", "data": None}


def conditional_format(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    cell_range: str,
    rules: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Apply conditional formatting rules to a range.
    Each rule dict must contain ``type`` (e.g. ``"cellIs"``, ``"colorScale"``)
    and the relevant parameters for the rule class.
    """
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]

        for rule in rules:
            r_type = rule.get("type")
            if r_type == "cellIs":
                cf_rule = CellIsRule(
                    operator=rule["operator"],
                    formula=[rule["formula"]],
                    stopIfTrue=rule.get("stopIfTrue", False),
                    fill=PatternFill(**rule["fill"]),
                    font=Font(**rule.get("font", {})),
                )
                ws.conditional_formatting.add(cell_range, cf_rule)
            elif r_type == "colorScale":
                cf_rule = ColorScaleRule(
                    start_type=rule["start_type"],
                    start_color=rule["start_color"],
                    end_type=rule["end_type"],
                    end_color=rule["end_color"],
                )
                ws.conditional_formatting.add(cell_range, cf_rule)
            elif r_type == "formula":
                cf_rule = FormulaRule(
                    formula=[rule["formula"]],
                    stopIfTrue=rule.get("stopIfTrue", False),
                    fill=PatternFill(**rule["fill"]),
                )
                ws.conditional_formatting.add(cell_range, cf_rule)
            else:
                raise ValueError(f"Unsupported conditional format type '{r_type}'")

        wb.save(path)
        return {"success": True, "message": "Conditional formatting applied", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Conditional format failed: {e}", "data": None}


def export_to_csv(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    output: Union[str, Path],
) -> Dict[str, Any]:
    """Export the contents of a sheet to a CSV file."""
    try:
        path = _ensure_path(filepath)
        out_path = _ensure_path(output)

        df = pd.read_excel(path, sheet_name=sheet if isinstance(sheet, str) else sheet)
        df.to_csv(out_path, index=False, quoting=csv.QUOTE_ALL)
        return {"success": True, "message": f"Exported to {out_path}", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Export CSV failed: {e}", "data": None}


def import_from_csv(
    csv_path: Union[str, Path],
    output_xlsx: Union[str, Path],
) -> Dict[str, Any]:
    """
    Read a CSV file and write its contents to a new workbook (single sheet named ``Sheet1``).
    """
    try:
        csv_p = _ensure_path(csv_path)
        out_p = _ensure_path(output_xlsx)

        df = pd.read_csv(csv_p)
        with pd.ExcelWriter(out_p, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Sheet1", index=False)

        return {"success": True, "message": f"CSV imported to {out_p}", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Import CSV failed: {e}", "data": None}


def protect_sheet(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    password: str,
) -> Dict[str, Any]:
    """Enable worksheet protection with a password."""
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]
        ws.protection.password = password
        ws.protection.enable()
        wb.save(path)
        return {"success": True, "message": "Sheet protected", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Protect sheet failed: {e}", "data": None}


def add_data_validation(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    cell_range: str,
    rules: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Add a data‑validation rule to ``cell_range``.
    ``rules`` maps directly to ``openpyxl.worksheet.datavalidation.DataValidation`` args.
    """
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]

        dv = DataValidation(**rules)
        ws.add_data_validation(dv)
        dv.add(cell_range)

        wb.save(path)
        return {"success": True, "message": "Data validation added", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Data validation failed: {e}", "data": None}


def batch_update_cells(
    filepath: Union[str, Path],
    sheet: Union[str, int],
    updates: List[Tuple[str, Any]],
) -> Dict[str, Any]:
    """
    Apply many cell updates in a single pass.

    ``updates`` – list of ``(cell_address, value)`` tuples.
    """
    try:
        path = _ensure_path(filepath)
        wb = load_workbook(path)
        ws = wb[wb.sheetnames[sheet]] if isinstance(sheet, int) else wb[sheet]

        for cell, value in updates:
            ws[cell].value = value

        wb.save(path)
        return {"success": True, "message": f"{len(updates)} cells updated", "data": None}
    except Exception as e:
        return {"success": False, "message": f"Batch update failed: {e}", "data": None}