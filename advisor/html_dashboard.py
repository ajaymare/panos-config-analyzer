"""Generate HTML dashboard fragment for SD-WAN Advisor results."""
from __future__ import annotations

from html import escape

from .engine import CATEGORIES, COMPETITOR_LABELS


def generate_advisor_dashboard(result: dict) -> str:
    """Generate the SD-WAN Advisor results dashboard HTML fragment."""
    rec = result['recommendation']
    rec_label = result['rec_label']
    rec_summary = result['rec_summary']
    confidence = result['confidence']
    panos_score = result['panos_score']
    prisma_score = result['prisma_score']
    category_scores = result['category_scores']
    feature_comparison = result['feature_comparison']
    competitive = result.get('competitive_displacement')
    next_steps = result['next_steps']
    inputs = result['inputs']

    html = '<div class="sizing-dashboard">'

    # --- Input Summary Banner ---
    existing_labels = {
        'yes_panorama': 'Yes — Panorama',
        'yes_scm': 'Yes — SCM',
        'no': 'No',
    }
    security_labels = {
        'full_ngfw': 'Full NGFW',
        'cloud_delivered': 'Cloud Security',
        'basic': 'Basic Firewall',
    }
    mgmt_labels = {
        'on_prem': 'On-Premises',
        'cloud': 'Cloud-Managed',
        'no_preference': 'No Preference',
    }
    competitor_label = COMPETITOR_LABELS.get(inputs.get('competitor', 'none'), 'N/A')
    priorities = inputs.get('priorities', [])

    html += f'''
    <div class="sizing-summary-banner">
        <div class="sizing-summary-item">
            <div class="sizing-summary-value">{escape(existing_labels.get(inputs.get("existing_pa", "no"), "N/A"))}</div>
            <div class="sizing-summary-label">Existing PA</div>
        </div>
        <div class="sizing-summary-item">
            <div class="sizing-summary-value">{escape(competitor_label)}</div>
            <div class="sizing-summary-label">Competitor</div>
        </div>
        <div class="sizing-summary-item">
            <div class="sizing-summary-value">{escape(inputs.get("branch_count", "N/A"))}</div>
            <div class="sizing-summary-label">Branch Sites</div>
        </div>
        <div class="sizing-summary-item">
            <div class="sizing-summary-value">{escape(security_labels.get(inputs.get("security", ""), "N/A"))}</div>
            <div class="sizing-summary-label">Security Model</div>
        </div>
        <div class="sizing-summary-item">
            <div class="sizing-summary-value">{escape(mgmt_labels.get(inputs.get("management", ""), "N/A"))}</div>
            <div class="sizing-summary-label">Management</div>
        </div>
        <div class="sizing-summary-item">
            <div class="sizing-summary-value">{len(priorities)}</div>
            <div class="sizing-summary-label">Priorities</div>
        </div>
    </div>
    '''

    # --- Recommendation Banner ---
    if rec == 'panos':
        banner_bg = 'linear-gradient(135deg, #fa582d 0%, #e8451c 100%)'
        banner_icon = '&#128737;'
    else:
        banner_bg = 'linear-gradient(135deg, #00c0a3 0%, #008f7a 100%)'
        banner_icon = '&#9729;'

    confidence_pct = int(confidence * 100)

    html += f'''
    <div class="advisor-rec-banner" style="background: {banner_bg};">
        <div class="advisor-rec-header">
            <span class="advisor-rec-icon">{banner_icon}</span>
            <div>
                <div class="advisor-rec-title">Recommended: {escape(rec_label)}</div>
                <div class="advisor-rec-confidence">Confidence: {confidence_pct}%</div>
            </div>
        </div>
        <div class="advisor-rec-summary">{escape(rec_summary)}</div>
        <div class="advisor-score-overview">
            <div class="advisor-score-pill advisor-score-panos">
                PAN-OS SD-WAN: <strong>{panos_score:.0f}</strong>/100
            </div>
            <div class="advisor-score-pill advisor-score-prisma">
                Prisma SD-WAN: <strong>{prisma_score:.0f}</strong>/100
            </div>
        </div>
    </div>
    '''

    # --- Scoring Breakdown ---
    html += '''
    <div class="sizing-card" style="margin-top: 16px;">
        <div class="sizing-card-header" style="background: #1a3a5c;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 18px;">&#128200;</span>
                <span>Scoring Breakdown</span>
            </div>
        </div>
        <div class="sizing-card-body" style="padding: 16px;">
    '''

    for key, label, weight in CATEGORIES:
        cs = category_scores[key]
        panos_val = cs['panos']
        prisma_val = cs['prisma']
        rationale = cs.get('rationale', '')

        panos_width = int(panos_val * 10)
        prisma_width = int(prisma_val * 10)

        html += f'''
            <div class="advisor-score-row">
                <div class="advisor-score-label">
                    <strong>{escape(label)}</strong>
                    <span class="advisor-weight-badge">x{weight}</span>
                </div>
                <div class="advisor-score-bars">
                    <div class="advisor-bar-row">
                        <span class="advisor-bar-label">PAN-OS</span>
                        <div class="advisor-bar-track">
                            <div class="advisor-bar-fill advisor-bar-panos" style="width: {panos_width}%;"></div>
                        </div>
                        <span class="advisor-bar-value">{panos_val:.0f}</span>
                    </div>
                    <div class="advisor-bar-row">
                        <span class="advisor-bar-label">Prisma</span>
                        <div class="advisor-bar-track">
                            <div class="advisor-bar-fill advisor-bar-prisma" style="width: {prisma_width}%;"></div>
                        </div>
                        <span class="advisor-bar-value">{prisma_val:.0f}</span>
                    </div>
                </div>
                <div class="advisor-score-rationale">{escape(rationale)}</div>
            </div>
        '''

    html += '''
        </div>
    </div>
    '''

    # --- Feature Comparison Table ---
    html += '''
    <div class="sizing-card" style="margin-top: 16px;">
        <div class="sizing-card-header" style="background: #1a3a5c;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 18px;">&#128203;</span>
                <span>Feature Comparison</span>
            </div>
        </div>
        <div class="sizing-card-body" style="padding: 0;">
            <table class="sizing-table" style="margin: 0;">
                <thead>
                    <tr>
                        <th>Feature</th>
                        <th>PAN-OS SD-WAN</th>
                        <th>Prisma SD-WAN</th>
                    </tr>
                </thead>
                <tbody>
    '''

    for feat in feature_comparison:
        advantage = feat.get('advantage', 'neutral')
        if advantage == 'panos':
            panos_style = 'background: #fff3e6; font-weight: 600;'
            prisma_style = ''
        elif advantage == 'prisma':
            panos_style = ''
            prisma_style = 'background: #e6f9f5; font-weight: 600;'
        else:
            panos_style = ''
            prisma_style = ''

        html += f'''
                    <tr>
                        <td><strong>{escape(feat["feature"])}</strong></td>
                        <td style="{panos_style}">{escape(feat["panos"])}</td>
                        <td style="{prisma_style}">{escape(feat["prisma"])}</td>
                    </tr>
        '''

    html += '''
                </tbody>
            </table>
        </div>
    </div>
    '''

    # --- Competitive Displacement (conditional) ---
    if competitive and competitive.get('messages'):
        comp_label = competitive.get('competitor_label', 'Competitor')
        html += f'''
    <div class="sizing-card" style="margin-top: 16px;">
        <div class="sizing-card-header" style="background: #7d3c98;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 18px;">&#9876;</span>
                <span>Competitive Displacement: {escape(comp_label)}</span>
            </div>
        </div>
        <div class="sizing-card-body">
            <div style="margin-bottom: 16px;">
                <div style="font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px;">Key Messages</div>
                <ul style="font-size: 13px; line-height: 1.8; color: var(--text-secondary); margin: 0; padding-left: 20px;">
        '''
        for msg in competitive['messages']:
            html += f'<li>{escape(msg)}</li>\n'

        html += '</ul></div>'

        if competitive.get('objections'):
            html += '''
            <div>
                <div style="font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px;">Objection Handling</div>
            '''
            for objection, response in competitive['objections']:
                html += f'''
                <div style="margin-bottom: 12px; padding: 10px; background: #f8f9fa; border-radius: 6px; border-left: 3px solid #7d3c98;">
                    <div style="font-size: 12px; font-weight: 600; color: #7d3c98; margin-bottom: 4px;">"{escape(objection)}"</div>
                    <div style="font-size: 13px; color: var(--text-secondary); line-height: 1.6;">{escape(response)}</div>
                </div>
                '''
            html += '</div>'

        html += '''
        </div>
    </div>
        '''

    # --- Next Steps ---
    html += '''
    <div class="sizing-card" style="margin-top: 16px;">
        <div class="sizing-card-header" style="background: #2e86c1;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 18px;">&#9889;</span>
                <span>Recommended Next Steps</span>
            </div>
        </div>
        <div class="sizing-card-body">
            <div style="font-size: 13px; line-height: 1.8;">
    '''
    for i, step in enumerate(next_steps, 1):
        html += f'<strong>{i}.</strong> {escape(step)}<br>\n'

    html += '''
            </div>
        </div>
    </div>
    '''

    html += '</div>'  # sizing-dashboard
    return html
