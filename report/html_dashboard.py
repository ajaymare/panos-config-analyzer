"""Generate self-contained HTML dashboard for SD-WAN config analysis."""
import os
import uuid
from datetime import datetime

from .scorer import score_config, score_configs, ALL_FEATURES
from .excel_generator import FEATURE_CATEGORIES, CAT_COLORS
import config as app_config

REPORT_DIR = app_config.REPORT_DIR


def _esc(text):
    """HTML-escape a string."""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _cat_color_css(hex_color):
    """Convert a hex color to CSS-usable format."""
    return f'#{hex_color}'


def _score_card_html(cfg_name, cfg_type, scoring, versions=None):
    """Render a single config scorecard."""
    pct = scoring['percent']
    level = scoring['level']
    level_color = scoring['level_color']
    score = scoring['score']
    total = scoring['total']
    missing_count = len(scoring['missing_features'])
    pan_managed_count = len(scoring.get('panorama_managed_features', []))

    # Version info
    version_html = ''
    if versions:
        parts = []
        if versions.get('panos_version'):
            parts.append(f'PAN-OS {_esc(versions["panos_version"])}')
        if versions.get('sdwan_version'):
            parts.append(f'SD-WAN Plugin {_esc(versions["sdwan_version"])}')
        if parts:
            version_html = f'<div class="config-version">{" | ".join(parts)}</div>'

    # CSS-only circular progress
    circle = f'''
    <div class="score-circle" style="--pct:{pct};--color:{level_color}">
      <svg viewBox="0 0 36 36">
        <path class="bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
        <path class="fg" stroke="{level_color}" stroke-dasharray="{pct}, 100"
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
      </svg>
      <div class="score-text">{score}/{total}</div>
    </div>'''

    return f'''
    <div class="score-card">
      <div class="card-header-bar" style="background:{level_color}">
        <span class="level-badge">{level}</span>
      </div>
      <h3 class="config-name">{_esc(cfg_name)}</h3>
      <div class="config-type">{_esc(cfg_type.upper())}</div>
      {version_html}
      {circle}
      <div class="score-details">
        <div class="score-stat enabled">{score} Enabled</div>
        {'<div class="score-stat panorama-managed">' + str(pan_managed_count) + ' Panorama</div>' if pan_managed_count else ''}
        <div class="score-stat disabled">{missing_count} Missing</div>
      </div>
    </div>'''


def _comparison_table_html(scored_configs):
    """Render the feature comparison table."""
    num = len(scored_configs)
    headers = ''.join(f'<th>{_esc(s["filename"][:25])}</th>' for s in scored_configs)

    rows = ''
    for cat_name, features in FEATURE_CATEGORIES.items():
        color = _cat_color_css(CAT_COLORS.get(cat_name, '2E86C1'))
        rows += f'<tr class="cat-row" style="background:{color}"><td colspan="{num + 1}">{_esc(cat_name)}</td></tr>\n'

        for feat in features:
            cells = ''
            for s in scored_configs:
                enabled = feat in s['scoring']['enabled_features']
                pan_managed = feat in s['scoring'].get('panorama_managed_features', [])
                if enabled:
                    cells += '<td class="status-cell enabled">&#10003;</td>'
                elif pan_managed:
                    cells += '<td class="status-cell panorama-managed" title="Configured via Panorama">&#9670;</td>'
                else:
                    cells += '<td class="status-cell disabled">&#10007;</td>'
            rows += f'<tr><td class="feat-name">{_esc(feat)}</td>{cells}</tr>\n'

    # Totals row
    totals = ''
    for s in scored_configs:
        sc = s['scoring']
        totals += f'<td class="total-cell"><strong>{sc["score"]}/{sc["total"]}</strong></td>'
    rows += f'<tr class="totals-row"><td><strong>Total</strong></td>{totals}</tr>'

    return f'''
    <table class="comparison-table">
      <thead><tr><th>Feature</th>{headers}</tr></thead>
      <tbody>{rows}</tbody>
    </table>'''


def _feature_details_html(configs_data):
    """Render feature breakdown showing enabled/disabled per config."""
    rows = ''
    for cat_name, features in FEATURE_CATEGORIES.items():
        color = _cat_color_css(CAT_COLORS.get(cat_name, '2E86C1'))
        rows += f'<tr class="cat-row" style="background:{color}"><td colspan="4">{_esc(cat_name)}</td></tr>\n'

        for feat in features:
            for cfg in configs_data:
                cfg_name = cfg.get('filename', 'Config')
                rlist = [r for r in cfg['results'] if r.feature_name == feat]
                enabled_count = sum(1 for r in rlist if r.enabled)

                if enabled_count:
                    rows += f'''<tr>
                      <td class="detail-device">{_esc(cfg_name)}</td>
                      <td class="feat-name">{_esc(feat)}</td>
                      <td class="status-cell enabled">&#10003;</td>
                      <td class="detail-count">{enabled_count}</td>
                    </tr>\n'''
                else:
                    rows += f'''<tr>
                      <td class="detail-device">{_esc(cfg_name)}</td>
                      <td class="feat-name">{_esc(feat)}</td>
                      <td class="status-cell disabled">&#10007;</td>
                      <td>0</td>
                    </tr>\n'''

    return f'''
    <div class="detail-card">
      <table class="detail-table">
        <thead><tr><th>Device</th><th>Feature</th><th>Status</th><th>Enabled Count</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>'''


def _gap_analysis_html(scored_configs):
    """Render the gap analysis section."""
    sections = ''

    # Common features (for multi-config)
    if len(scored_configs) > 1 and 'common_features' in scored_configs[0]:
        common = scored_configs[0]['common_features']
        if common:
            items = ''.join(f'<li>{_esc(f)}</li>' for f in common)
            sections += f'''
            <div class="gap-card common">
              <h4>Common Features ({len(common)})</h4>
              <ul>{items}</ul>
            </div>'''

    for s in scored_configs:
        missing = s['scoring']['missing_features']
        recs = s['scoring']['recommendations']
        if not missing:
            sections += f'''
            <div class="gap-card full">
              <h4>{_esc(s["filename"])} — All Features Configured</h4>
              <p class="congrats">Full SD-WAN deployment detected.</p>
            </div>'''
            continue

        items = ''
        for feat, rec in zip(missing, recs):
            items += f'<li><strong>{_esc(feat)}</strong> — {_esc(rec)}</li>'

        sections += f'''
        <div class="gap-card">
          <h4>{_esc(s["filename"])} — {len(missing)} Missing Features</h4>
          <ul>{items}</ul>
        </div>'''

    return sections


def _category_bars_html(scored_configs):
    """Render per-category horizontal bar charts."""
    bars = ''
    for s in scored_configs:
        cat_bars = ''
        for cat_name, cat_data in s['scoring']['category_scores'].items():
            color = _cat_color_css(CAT_COLORS.get(cat_name, '2E86C1'))
            pct = cat_data['percent']
            cat_bars += f'''
            <div class="cat-bar-row">
              <div class="cat-bar-label">{_esc(cat_name)}</div>
              <div class="cat-bar-track">
                <div class="cat-bar-fill" style="width:{pct}%;background:{color}"></div>
              </div>
              <div class="cat-bar-val">{cat_data["enabled"]}/{cat_data["total"]}</div>
            </div>'''

        bars += f'''
        <div class="cat-chart-card">
          <h4>{_esc(s["filename"])}</h4>
          {cat_bars}
        </div>'''

    return bars


CSS = '''
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f0f4f8; color: #1e2a3a; }
.dash-header { background: linear-gradient(135deg, #1a2a44, #243b5c);
  padding: 24px; border-bottom: 3px solid #0066cc; text-align: center; }
.dash-header h1 { color: #fff; font-size: 22px; font-weight: 600; }
.dash-header p { color: #94a3b8; font-size: 12px; margin-top: 4px; }
.container { max-width: 1100px; margin: 0 auto; padding: 24px 16px; }
.section { margin-bottom: 32px; }
.section-title { font-size: 16px; font-weight: 600; color: #1a2a44;
  border-bottom: 2px solid #0066cc; padding-bottom: 6px; margin-bottom: 16px; }

/* Score Cards */
.score-cards { display: flex; gap: 16px; flex-wrap: wrap; }
.score-card { background: #fff; border: 1px solid #d4dbe6; border-radius: 10px;
  flex: 1; min-width: 220px; text-align: center; overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.card-header-bar { padding: 6px 12px; }
.level-badge { color: #fff; font-size: 12px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 1px; }
.config-name { font-size: 14px; margin: 12px 0 2px; padding: 0 12px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.config-type { font-size: 11px; color: #6b7a8d; margin-bottom: 4px; }
.config-version { font-size: 10px; color: #0066cc; margin-bottom: 8px; font-weight: 600; }
.score-circle { width: 90px; height: 90px; margin: 0 auto; position: relative; }
.score-circle svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.score-circle .bg { fill: none; stroke: #e8ecf0; stroke-width: 3; }
.score-circle .fg { fill: none; stroke-width: 3; stroke-linecap: round;
  transition: stroke-dasharray 0.6s ease; }
.score-text { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  font-size: 18px; font-weight: 700; }
.score-details { display: flex; justify-content: center; gap: 16px;
  padding: 12px; border-top: 1px solid #e8ecf0; margin-top: 12px; }
.score-stat { font-size: 12px; font-weight: 600; }
.score-stat.enabled { color: #1E8449; }
.score-stat.panorama-managed { color: #B9770E; }
.score-stat.disabled { color: #C0392B; }

/* Comparison Table */
.comparison-table { width: 100%; border-collapse: collapse; background: #fff;
  border: 1px solid #d4dbe6; border-radius: 8px; overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.comparison-table th { background: #1a2a44; color: #fff; padding: 10px 12px;
  font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
.comparison-table td { padding: 8px 12px; border-bottom: 1px solid #e8ecf0;
  font-size: 13px; }
.cat-row td { color: #fff; font-weight: 600; font-size: 12px; letter-spacing: 0.5px; }
.feat-name { color: #1e2a3a; }
.status-cell { text-align: center; font-size: 16px; font-weight: 700; }
.status-cell.enabled { color: #1E8449; }
.status-cell.panorama-managed { color: #B9770E; }
.status-cell.disabled { color: #C0392B; }
.totals-row td { background: #f7f9fc; border-top: 2px solid #d4dbe6; }
.total-cell { text-align: center; }

/* Gap Analysis */
.gap-cards { display: flex; gap: 16px; flex-wrap: wrap; }
.gap-card { background: #fff; border: 1px solid #d4dbe6; border-radius: 8px;
  padding: 16px; flex: 1; min-width: 280px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.gap-card.common { border-left: 4px solid #1E8449; }
.gap-card.full { border-left: 4px solid #1E8449; }
.gap-card h4 { font-size: 13px; margin-bottom: 10px; color: #1a2a44; }
.gap-card ul { list-style: none; padding: 0; }
.gap-card li { font-size: 12px; padding: 4px 0; border-bottom: 1px solid #f0f4f8;
  color: #4a5568; }
.gap-card li strong { color: #C0392B; }
.congrats { color: #1E8449; font-size: 13px; font-weight: 600; }

/* Category Bars */
.cat-charts { display: flex; gap: 16px; flex-wrap: wrap; }
.cat-chart-card { background: #fff; border: 1px solid #d4dbe6; border-radius: 8px;
  padding: 16px; flex: 1; min-width: 280px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.cat-chart-card h4 { font-size: 13px; margin-bottom: 12px; color: #1a2a44; }
.cat-bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.cat-bar-label { font-size: 11px; width: 140px; color: #4a5568; flex-shrink: 0; }
.cat-bar-track { flex: 1; height: 14px; background: #e8ecf0; border-radius: 7px;
  overflow: hidden; }
.cat-bar-fill { height: 100%; border-radius: 7px; transition: width 0.6s ease; }
.cat-bar-val { font-size: 11px; font-weight: 600; width: 30px; text-align: right;
  color: #1a2a44; flex-shrink: 0; }

/* Feature Details */
.detail-card { background: #fff; border: 1px solid #d4dbe6; border-radius: 8px;
  overflow: hidden; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.detail-card h4 { font-size: 14px; padding: 12px 16px; margin: 0;
  background: #f7f9fc; border-bottom: 1px solid #e8ecf0; color: #1a2a44; }
.detail-table { width: 100%; border-collapse: collapse; }
.detail-table th { background: #1a2a44; color: #fff; padding: 8px 12px;
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; text-align: left; }
.detail-table td { padding: 6px 12px; border-bottom: 1px solid #e8ecf0; font-size: 12px; }
.detail-count { color: #1E8449; font-weight: 700; font-size: 11px; }

/* Footer */
.dash-footer { text-align: center; padding: 16px; font-size: 11px; color: #6b7a8d; }

@media print {
  body { background: #fff; }
  .score-card, .gap-card, .cat-chart-card { break-inside: avoid; }
}
'''


def generate_dashboard_fragment(configs_data):
    """Generate dashboard HTML fragment for inline display in the web UI.

    Args:
        configs_data: list of dicts with keys: filename, config_type, results

    Returns:
        HTML string (no <html>/<head>/<body> wrapper)
    """
    scored = score_configs(configs_data)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    is_comparison = len(scored) > 1

    cards = ''.join(
        _score_card_html(s['filename'], s['config_type'], s['scoring'],
                         versions=s.get('versions'))
        for s in scored
    )
    table = _comparison_table_html(scored)
    gaps = _gap_analysis_html(scored)
    bars = _category_bars_html(scored)

    title = 'SD-WAN Configuration Comparison' if is_comparison else 'SD-WAN Configuration Analysis'
    subtitle_parts = []
    for s in scored:
        subtitle_parts.append(f'{_esc(s["filename"])} ({s["config_type"].upper()})')
    subtitle = ' vs '.join(subtitle_parts)

    return f'''
    <div class="dash-header-inline">
      <h2>{title}</h2>
      <p>{subtitle} &mdash; Generated {timestamp}</p>
    </div>

    <div class="section">
      <div class="section-title">Deployment Scorecard</div>
      <div class="score-cards">{cards}</div>
    </div>

    <div class="section">
      <div class="section-title">Feature {('Comparison' if is_comparison else 'Summary')}</div>
      {table}
    </div>

    <div class="section">
      <div class="section-title">Category Breakdown</div>
      <div class="cat-charts">{bars}</div>
    </div>

    <div class="section">
      <div class="section-title">Gap Analysis &amp; Recommendations</div>
      <div class="gap-cards">{gaps}</div>
    </div>

    <div class="dash-footer-inline">
      PAN-OS SD-WAN Config Analyzer &mdash; {timestamp}
    </div>'''


def generate_dashboard(configs_data):
    """Generate a self-contained HTML dashboard file.

    Args:
        configs_data: list of dicts with keys: filename, config_type, results
            (single config = list of one)

    Returns:
        filepath of generated HTML file
    """
    scored = score_configs(configs_data)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    is_comparison = len(scored) > 1

    # Scorecards
    cards = ''.join(
        _score_card_html(s['filename'], s['config_type'], s['scoring'],
                         versions=s.get('versions'))
        for s in scored
    )

    # Comparison table
    table = _comparison_table_html(scored)

    # Gap analysis
    gaps = _gap_analysis_html(scored)

    # Category bars
    bars = _category_bars_html(scored)

    title = 'SD-WAN Configuration Comparison' if is_comparison else 'SD-WAN Configuration Analysis'
    subtitle_parts = []
    for s in scored:
        subtitle_parts.append(f'{_esc(s["filename"])} ({s["config_type"].upper()})')
    subtitle = ' vs '.join(subtitle_parts)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>

<div class="dash-header">
  <h1>PAN-OS {title}</h1>
  <p>{subtitle} &mdash; Generated {timestamp}</p>
</div>

<div class="container">

  <div class="section">
    <div class="section-title">Deployment Scorecard</div>
    <div class="score-cards">{cards}</div>
  </div>

  <div class="section">
    <div class="section-title">Feature {('Comparison' if is_comparison else 'Summary')}</div>
    {table}
  </div>

  <div class="section">
    <div class="section-title">Category Breakdown</div>
    <div class="cat-charts">{bars}</div>
  </div>

  <div class="section">
    <div class="section-title">Gap Analysis &amp; Recommendations</div>
    <div class="gap-cards">{gaps}</div>
  </div>

</div>

<div class="dash-footer">
  PAN-OS SD-WAN Config Analyzer &mdash; {timestamp}
</div>

</body>
</html>'''

    filename = f'sdwan_dashboard_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{uuid.uuid4().hex[:6]}.html'
    filepath = os.path.join(REPORT_DIR, filename)
    with open(filepath, 'w') as f:
        f.write(html)
    return filepath
