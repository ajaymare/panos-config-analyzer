"""Generate inline HTML dashboard for SCM migration analysis."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .excel_generator import FEATURE_CATEGORIES, CAT_COLORS

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scm.mapper import get_mappers, get_mapper_for_feature, map_results
from scm.migration_report import (
    _classify_feature, _ROLE_DISPLAY_NAMES,
    _PARTIAL_FEATURES, _NOT_SUPPORTED_REASONS,
)


def _esc(text):
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _migration_score(results, selected_features=None, mapped=None):
    """Compute migration analysis scores from parsed results.

    Returns dict with counts, per-feature statuses, and category breakdowns.
    """
    if mapped is None:
        mapped = map_results(results)

    # Build enabled lookup
    enabled_features: dict[str, bool] = {}
    for r in results:
        if r.feature_name not in enabled_features:
            enabled_features[r.feature_name] = r.enabled
        elif r.enabled:
            enabled_features[r.feature_name] = True

    counts = {
        'Fully Converted': 0,
        'Partially Converted': 0,
        'Not Supported by SCM': 0,
        'Ignored (User Skipped)': 0,
        'Not Configured': 0,
    }

    feature_statuses = []  # list of dicts per feature
    category_data = {}  # per-category migration stats

    for category, features in FEATURE_CATEGORIES.items():
        cat_converted = 0
        cat_partial = 0
        cat_not_supported = 0
        cat_total = len(features)

        for feat in features:
            enabled = enabled_features.get(feat, False)
            status, scm_ref, notes = _classify_feature(feat, enabled, selected_features)
            counts[status] += 1

            feature_statuses.append({
                'category': category,
                'feature': feat,
                'enabled': enabled,
                'status': status,
                'scm_ref': scm_ref,
                'notes': notes,
            })

            if status == 'Fully Converted':
                cat_converted += 1
            elif status == 'Partially Converted':
                cat_partial += 1
            elif status == 'Not Supported by SCM':
                cat_not_supported += 1

        category_data[category] = {
            'converted': cat_converted,
            'partial': cat_partial,
            'not_supported': cat_not_supported,
            'total': cat_total,
        }

    # Resources converted summary
    resource_summary = []
    for resource_name, info in sorted(mapped.items()):
        display = _ROLE_DISPLAY_NAMES.get(resource_name, resource_name)
        resource_summary.append({
            'resource': resource_name,
            'display': display,
            'endpoint': info['endpoint'],
            'folder': info['folder'],
            'count': len(info['payloads']),
        })

    total_features = sum(counts.values())
    converted_total = counts['Fully Converted'] + counts['Partially Converted']

    return {
        'counts': counts,
        'feature_statuses': feature_statuses,
        'category_data': category_data,
        'resource_summary': resource_summary,
        'total_features': total_features,
        'converted_total': converted_total,
        'mapped': mapped,
    }


def _migration_scorecard_html(score_data):
    """Render migration summary scorecard."""
    counts = score_data['counts']
    total = score_data['total_features']
    converted = counts['Fully Converted']
    partial = counts['Partially Converted']
    not_supported = counts['Not Supported by SCM']
    not_configured = counts['Not Configured']
    ignored = counts['Ignored (User Skipped)']

    # Migration readiness percentage (fully + partially converted out of configured features)
    configured = total - not_configured
    if configured > 0:
        readiness_pct = round((converted + partial) / configured * 100)
    else:
        readiness_pct = 0

    # Determine readiness level
    if readiness_pct >= 80:
        level = 'High'
        level_color = '#1E8449'
    elif readiness_pct >= 50:
        level = 'Medium'
        level_color = '#B9770E'
    else:
        level = 'Low'
        level_color = '#C0392B'

    return f'''
    <div class="score-cards">
      <div class="score-card">
        <div class="card-header-bar" style="background:{level_color}">
          <span class="level-badge">Migration Readiness: {level}</span>
        </div>
        <h3 class="config-name">SCM Migration Analysis</h3>
        <div class="config-type">Automated Conversion Status</div>
        <div class="score-circle" style="--pct:{readiness_pct};--color:{level_color}">
          <svg viewBox="0 0 36 36">
            <path class="bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
            <path class="fg" stroke="{level_color}" stroke-dasharray="{readiness_pct}, 100"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
          </svg>
          <div class="score-text">{readiness_pct}%</div>
        </div>
        <div class="score-details">
          <div class="score-stat enabled">{converted} Converted</div>
          <div class="score-stat panorama-managed">{partial} Partial</div>
          <div class="score-stat disabled">{not_supported} Manual</div>
        </div>
      </div>

      <div class="score-card">
        <div class="card-header-bar" style="background:#1a1a2e">
          <span class="level-badge">Conversion Summary</span>
        </div>
        <div style="padding:16px; text-align:left;">
          <div class="migration-stat-row">
            <span class="migration-stat-dot" style="background:#1E8449"></span>
            <span class="migration-stat-label">Fully Converted</span>
            <span class="migration-stat-val" style="color:#1E8449">{converted}</span>
          </div>
          <div class="migration-stat-row">
            <span class="migration-stat-dot" style="background:#B9770E"></span>
            <span class="migration-stat-label">Partially Converted</span>
            <span class="migration-stat-val" style="color:#B9770E">{partial}</span>
          </div>
          <div class="migration-stat-row">
            <span class="migration-stat-dot" style="background:#C0392B"></span>
            <span class="migration-stat-label">Not Supported (Manual)</span>
            <span class="migration-stat-val" style="color:#C0392B">{not_supported}</span>
          </div>
          <div class="migration-stat-row">
            <span class="migration-stat-dot" style="background:#6C3483"></span>
            <span class="migration-stat-label">Ignored (User Skipped)</span>
            <span class="migration-stat-val" style="color:#6C3483">{ignored}</span>
          </div>
          <div class="migration-stat-row">
            <span class="migration-stat-dot" style="background:#95A5A6"></span>
            <span class="migration-stat-label">Not Configured</span>
            <span class="migration-stat-val" style="color:#95A5A6">{not_configured}</span>
          </div>
        </div>
      </div>

      <div class="score-card">
        <div class="card-header-bar" style="background:#2E86C1">
          <span class="level-badge">Ansible Playbooks</span>
        </div>
        <div style="padding:16px; text-align:left;">
          <div style="font-size:28px; font-weight:700; color:#1a1a2e; text-align:center; margin:8px 0;">
            {len(score_data['resource_summary'])}
          </div>
          <div style="font-size:11px; color:#6b7a8d; text-align:center; margin-bottom:12px;">
            SCM Resources Generated
          </div>
          {''.join(
              f'<div style="font-size:11px; padding:3px 0; color:#4a5568; border-bottom:1px solid #f0f4f8;">'
              f'{_esc(r["display"])} ({r["count"]})</div>'
              for r in score_data['resource_summary']
          )}
        </div>
      </div>
    </div>'''


def _migration_table_html(score_data):
    """Render per-feature migration status table."""
    rows = ''
    for category, features in FEATURE_CATEGORIES.items():
        color = f'#{CAT_COLORS.get(category, "2E86C1")}'
        rows += f'<tr class="cat-row" style="background:{color}"><td colspan="4">{_esc(category)}</td></tr>\n'

        for feat_data in score_data['feature_statuses']:
            if feat_data['category'] != category:
                continue
            status = feat_data['status']
            notes = feat_data['notes']

            if status == 'Fully Converted':
                status_class = 'enabled'
                status_icon = '&#10003;'
            elif status == 'Partially Converted':
                status_class = 'panorama-managed'
                status_icon = '&#9670;'
            elif status == 'Not Supported by SCM':
                status_class = 'disabled'
                status_icon = '&#10007;'
            elif status == 'Ignored (User Skipped)':
                status_class = 'ignored'
                status_icon = '&#9632;'
            else:
                status_class = 'not-configured'
                status_icon = '&mdash;'

            rows += (
                f'<tr>'
                f'<td class="feat-name">{_esc(feat_data["feature"])}</td>'
                f'<td class="status-cell {status_class}" title="{_esc(notes)}">{status_icon}</td>'
                f'<td class="migration-status-label {status_class}">{_esc(status)}</td>'
                f'<td class="migration-notes">{_esc(notes)}</td>'
                f'</tr>\n'
            )

    return f'''
    <table class="comparison-table">
      <thead><tr>
        <th>Feature</th>
        <th>Status</th>
        <th>Migration Status</th>
        <th>Notes / SCM Reference</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>'''


def _migration_category_bars_html(score_data):
    """Render per-category migration coverage bars."""
    bars = ''
    for cat_name, cat_data in score_data['category_data'].items():
        color = f'#{CAT_COLORS.get(cat_name, "2E86C1")}'
        total = cat_data['total']
        converted = cat_data['converted'] + cat_data['partial']
        pct = round(converted / total * 100) if total > 0 else 0

        bars += f'''
        <div class="cat-bar-row">
          <div class="cat-bar-label">{_esc(cat_name)}</div>
          <div class="cat-bar-track">
            <div class="cat-bar-fill" style="width:{pct}%;background:{color}"></div>
          </div>
          <div class="cat-bar-val">{converted}/{total}</div>
        </div>'''

    return f'''
    <div class="cat-chart-card">
      <h4>Migration Coverage by Category</h4>
      {bars}
    </div>'''


def _migration_resources_html(score_data):
    """Render converted resources detail cards."""
    if not score_data['resource_summary']:
        return '<p style="color:#6b7a8d; font-size:13px;">No features were converted to SCM resources.</p>'

    items = ''
    for r in score_data['resource_summary']:
        items += f'''
        <div class="migration-resource-item">
          <div class="migration-resource-name">{_esc(r['display'])}</div>
          <div class="migration-resource-meta">
            <span>Endpoint: <code>{_esc(r['endpoint'])}</code></span>
            <span>Folder: <strong>{_esc(r['folder'])}</strong></span>
            <span>Items: <strong>{r['count']}</strong></span>
          </div>
        </div>'''

    return f'<div class="migration-resources">{items}</div>'


def _migration_action_items_html(score_data):
    """Render action items for features that need manual configuration."""
    manual_items = [f for f in score_data['feature_statuses']
                    if f['status'] == 'Not Supported by SCM' and f['enabled']]

    if not manual_items:
        return '''
        <div class="gap-card full">
          <h4>All Configured Features Covered</h4>
          <p class="congrats">All enabled features can be migrated via Ansible playbooks.</p>
        </div>'''

    items_html = ''
    for f in manual_items:
        items_html += f'<li><strong>{_esc(f["feature"])}</strong> — {_esc(f["notes"])}</li>'

    return f'''
    <div class="gap-card">
      <h4>{len(manual_items)} Features Require Manual SCM Configuration</h4>
      <ul>{items_html}</ul>
    </div>'''


def generate_migration_dashboard_fragment(
    results,
    selected_features=None,
    mapped=None,
    configs_data=None,
):
    """Generate migration analysis dashboard HTML fragment.

    Args:
        results: list of FeatureResult objects (all configs combined).
        selected_features: list of scm_resource_names user selected.
        mapped: Output from map_results() (optional, computed if None).
        configs_data: Original configs_data for device info display.

    Returns:
        HTML string fragment (no wrapper).
    """
    score_data = _migration_score(results, selected_features, mapped)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Device info subtitle
    subtitle_parts = []
    if configs_data:
        for cfg in configs_data:
            subtitle_parts.append(f'{_esc(cfg["filename"])} ({cfg["config_type"].upper()})')
    subtitle = ' + '.join(subtitle_parts) if subtitle_parts else 'Configuration'

    scorecard = _migration_scorecard_html(score_data)
    table = _migration_table_html(score_data)
    category_bars = _migration_category_bars_html(score_data)
    resources = _migration_resources_html(score_data)
    action_items = _migration_action_items_html(score_data)

    return f'''
    <div class="dash-header-inline">
      <h2>SCM Migration Analysis</h2>
      <p>{subtitle} &mdash; Generated {timestamp}</p>
    </div>

    <div class="section">
      <div class="section-title">Migration Readiness Scorecard</div>
      {scorecard}
    </div>

    <div class="section">
      <div class="section-title">Feature Migration Status</div>
      {table}
    </div>

    <div class="section">
      <div class="section-title">Migration Coverage by Category</div>
      <div class="cat-charts">{category_bars}</div>
    </div>

    <div class="section">
      <div class="section-title">Converted SCM Resources</div>
      {resources}
    </div>

    <div class="section">
      <div class="section-title">Manual Configuration Required</div>
      <div class="gap-cards">{action_items}</div>
    </div>

    <div class="dash-footer-inline">
      PAN-OS SD-WAN to SCM Migration Analyzer &mdash; {timestamp}
    </div>'''
