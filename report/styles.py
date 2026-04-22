"""Excel cell styles and formatting constants."""
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, NamedStyle

# Colors
BLUE = '1A2A44'
LIGHT_BLUE = 'D6E4F0'
GREEN = '28A745'
LIGHT_GREEN = 'D4EDDA'
RED = 'DC3545'
LIGHT_RED = 'F8D7DA'
GRAY = 'F2F2F2'
WHITE = 'FFFFFF'
DARK_TEXT = '1E2A3A'
BORDER_COLOR = 'D4DBE6'

# Borders
thin_border = Border(
    left=Side(style='thin', color=BORDER_COLOR),
    right=Side(style='thin', color=BORDER_COLOR),
    top=Side(style='thin', color=BORDER_COLOR),
    bottom=Side(style='thin', color=BORDER_COLOR),
)

# Header style
header_font = Font(name='Calibri', size=11, bold=True, color=WHITE)
header_fill = PatternFill(start_color=BLUE, end_color=BLUE, fill_type='solid')
header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

# Data styles
data_font = Font(name='Calibri', size=10, color=DARK_TEXT)
data_align = Alignment(vertical='center', wrap_text=True)

# Status fills
enabled_fill = PatternFill(start_color=LIGHT_GREEN, end_color=LIGHT_GREEN, fill_type='solid')
enabled_font = Font(name='Calibri', size=10, bold=True, color=GREEN)
disabled_fill = PatternFill(start_color=LIGHT_RED, end_color=LIGHT_RED, fill_type='solid')
disabled_font = Font(name='Calibri', size=10, bold=True, color=RED)

# Alternating row fill
alt_fill = PatternFill(start_color=GRAY, end_color=GRAY, fill_type='solid')

# Title style
title_font = Font(name='Calibri', size=14, bold=True, color=BLUE)
subtitle_font = Font(name='Calibri', size=11, color='6B7A8D')


def style_header_row(ws, row_num, col_count):
    """Apply header styling to a row."""
    for col in range(1, col_count + 1):
        cell = ws.cell(row=row_num, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border


def style_data_cell(cell, row_idx=0):
    """Apply data styling to a cell."""
    cell.font = data_font
    cell.alignment = data_align
    cell.border = thin_border
    if row_idx % 2 == 1:
        cell.fill = alt_fill


def style_status_cell(cell, enabled):
    """Apply enabled/disabled styling."""
    cell.border = thin_border
    if enabled:
        cell.fill = enabled_fill
        cell.font = enabled_font
        cell.value = 'Enabled'
    else:
        cell.fill = disabled_fill
        cell.font = disabled_font
        cell.value = 'Disabled'
    cell.alignment = Alignment(horizontal='center', vertical='center')


def auto_width(ws, min_width=10, max_width=50):
    """Auto-adjust column widths based on content."""
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        adjusted = min(max(max_len + 2, min_width), max_width)
        ws.column_dimensions[col_letter].width = adjusted
