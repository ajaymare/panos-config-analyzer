"""Generate Excel report from parser results."""
import os
import uuid
from datetime import datetime

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from . import styles
from ..config import REPORT_DIR


def generate(results: list, config_type: str = 'unknown') -> str:
    """Generate Excel workbook with summary and detail sheets.

    Args:
        results: List of FeatureResult objects from all parsers
        config_type: 'panorama', 'ngfw', or 'unknown'

    Returns:
        Path to generated Excel file
    """
    wb = Workbook()

    # ── Summary Sheet ──
    ws = wb.active
    ws.title = 'Summary'

    # Title row
    ws.merge_cells('A1:D1')
    title_cell = ws['A1']
    title_cell.value = 'PAN-OS SD-WAN Feature Report'
    title_cell.font = styles.title_font

    # Metadata
    ws['A2'] = f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    ws['A2'].font = styles.subtitle_font
    ws['A3'] = f'Config Type: {config_type.upper()}'
    ws['A3'].font = styles.subtitle_font

    # Header row
    header_row = 5
    headers = ['Feature', 'Status', 'Summary', 'Source']
    for col, h in enumerate(headers, 1):
        ws.cell(row=header_row, column=col, value=h)
    styles.style_header_row(ws, header_row, len(headers))

    # Data rows
    row = header_row + 1
    for result in results:
        ws.cell(row=row, column=1, value=result.feature_name)
        styles.style_data_cell(ws.cell(row=row, column=1), row - header_row - 1)

        status_cell = ws.cell(row=row, column=2)
        styles.style_status_cell(status_cell, result.enabled)

        ws.cell(row=row, column=3, value=result.summary)
        styles.style_data_cell(ws.cell(row=row, column=3), row - header_row - 1)

        ws.cell(row=row, column=4, value=result.source)
        styles.style_data_cell(ws.cell(row=row, column=4), row - header_row - 1)

        row += 1

    # Auto-filter
    ws.auto_filter.ref = f'A{header_row}:D{row - 1}'
    styles.auto_width(ws)

    # Freeze panes below header
    ws.freeze_panes = f'A{header_row + 1}'

    # ── Detail Sheets ──
    seen_sheets = set()
    for result in results:
        if not result.rows or not result.columns:
            continue

        # Ensure unique sheet name (max 31 chars)
        sheet_name = result.feature_name[:31]
        if sheet_name in seen_sheets:
            sheet_name = sheet_name[:28] + f'_{len(seen_sheets)}'
        seen_sheets.add(sheet_name)

        ds = wb.create_sheet(title=sheet_name)

        # Source label
        ds['A1'] = f'Source: {result.source}'
        ds['A1'].font = styles.subtitle_font

        # Headers
        h_row = 3
        for col, h in enumerate(result.columns, 1):
            ds.cell(row=h_row, column=col, value=h)
        styles.style_header_row(ds, h_row, len(result.columns))

        # Data
        for r_idx, data_row in enumerate(result.rows):
            for c_idx, val in enumerate(data_row):
                cell = ds.cell(row=h_row + 1 + r_idx, column=c_idx + 1, value=val)
                styles.style_data_cell(cell, r_idx)

        # Auto-filter and width
        if result.rows:
            last_col = get_column_letter(len(result.columns))
            ds.auto_filter.ref = f'A{h_row}:{last_col}{h_row + len(result.rows)}'
        styles.auto_width(ds)
        ds.freeze_panes = f'A{h_row + 1}'

    # Save
    filename = f'sdwan_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{uuid.uuid4().hex[:6]}.xlsx'
    filepath = os.path.join(REPORT_DIR, filename)
    wb.save(filepath)
    return filepath
