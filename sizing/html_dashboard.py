"""Generate HTML dashboard fragment for sizing calculator results."""

from html import escape
from .models import TAC_RECOMMENDED_PANOS, SECURITY_FEATURES


def _fmt(n):
    """Format number with commas."""
    if isinstance(n, int):
        return f'{n:,}'
    return str(n)


def _headroom_color(specs, key, required):
    """Return CSS color based on headroom percentage."""
    val = specs.get(key, 0)
    if required == 0:
        return '#28a745'
    pct = (val - required) / required * 100
    if pct >= 50:
        return '#28a745'
    if pct >= 20:
        return '#f0ad4e'
    return '#fa582d'


def _headroom_pct(specs, key, required):
    if required == 0:
        return 100
    return int((specs.get(key, 0) - required) / required * 100)


def _get_throughput_key(security_features):
    """Determine which throughput metric to use."""
    if security_features.get('ssl_decryption'):
        return 'ssl_decrypt_throughput'
    if security_features.get('threat_prevention'):
        return 'threat_throughput'
    return 'ipsec_vpn_throughput'


def _render_model_card(role, result, security_features):
    """Render a single recommendation card (Hub or Branch)."""
    model = result['model']
    specs = result['specs']
    alt = result['alternative']
    rationale = result['rationale']
    inputs = result['inputs']
    device_count = result['device_count']
    isps = result.get('isps', {})
    platform = result.get('platform', 'hardware')

    role_color = '#fa582d' if role == 'Hub' else '#2e86c1'
    if platform == 'virtual':
        role_icon = '&#9729;' if role == 'Hub' else '&#9729;'  # cloud icon
    else:
        role_icon = '&#127981;' if role == 'Hub' else '&#127970;'

    platform_badge = ''
    if platform == 'virtual':
        platform_badge = '<span class="sizing-platform-badge sizing-platform-vm">VM-Series</span>'
    else:
        platform_badge = '<span class="sizing-platform-badge sizing-platform-hw">Hardware</span>'

    html = f'''
    <div class="sizing-card">
        <div class="sizing-card-header" style="background: {role_color};">
            <span class="sizing-role-icon">{role_icon}</span>
            <div class="sizing-card-title">
                <h3>{role} Recommendation</h3>
                <div class="sizing-model-name">{escape(model)} {platform_badge}</div>
            </div>
            <div class="sizing-device-count">
                <span class="sizing-count-num">{device_count}</span>
                <span class="sizing-count-label">device{"s" if device_count > 1 else ""}</span>
            </div>
        </div>
        <div class="sizing-card-body">
            <p class="sizing-description">{escape(specs.get("description", ""))}</p>
            <div class="sizing-panos-rec">
                <strong>TAC Recommended PAN-OS:</strong> {escape(TAC_RECOMMENDED_PANOS.get(specs.get("series", ""), "Contact TAC"))}
            </div>
    '''

    # ISP Summary
    if isps:
        pub = isps.get('public', 0)
        priv = isps.get('private', 0)
        html += f'''
            <div class="sizing-isp-summary">
                <span class="sizing-isp-badge sizing-isp-public">{pub} Public ISP{"s" if pub != 1 else ""}</span>
                <span class="sizing-isp-badge sizing-isp-private">{priv} Private ISP{"s" if priv != 1 else ""}</span>
                <span class="sizing-isp-tunnels">{_fmt(inputs["tunnels"])} tunnels calculated</span>
            </div>
        '''

    # Key specs with headroom bars
    throughput_key = _get_throughput_key(security_features)
    html += '<div class="sizing-specs-grid">'

    spec_items = [
        ('Firewall Throughput', 'firewall_throughput', inputs['bandwidth_mbps'], 'Mbps'),
        ('Threat Prevention Throughput', 'threat_throughput',
         inputs['bandwidth_mbps'] if security_features.get('threat_prevention') else 0, 'Mbps'),
        ('SSL Decryption Throughput', 'ssl_decrypt_throughput',
         inputs['bandwidth_mbps'] if security_features.get('ssl_decryption') else 0, 'Mbps'),
        ('IPSec VPN Throughput', 'ipsec_vpn_throughput', inputs['bandwidth_mbps'], 'Mbps'),
        ('Max Concurrent Sessions', 'max_sessions', inputs['sessions'], ''),
        ('New Sessions/Second', 'new_sessions_per_sec', 0, '/sec'),
        ('Max IPSec Tunnels', 'max_ipsec_tunnels', inputs['tunnels'], ''),
        ('Max Security Rules', 'max_security_rules', 0, ''),
    ]

    for label, key, required, unit in spec_items:
        val = specs.get(key, 0)
        color = _headroom_color(specs, key, required) if required > 0 else '#6b7a8d'
        headroom = _headroom_pct(specs, key, required) if required > 0 else -1

        # Highlight the throughput metric being used for sizing
        sizing_indicator = ''
        if key == throughput_key:
            sizing_indicator = ' <span class="sizing-metric-used">&#9668; sizing metric</span>'

        headroom_html = ''
        if headroom >= 0:
            headroom_html = f'''
                <div class="sizing-headroom">
                    <div class="sizing-headroom-bar" style="width: {min(headroom, 100)}%; background: {color};"></div>
                    <span class="sizing-headroom-text" style="color: {color};">+{headroom}% headroom</span>
                </div>
            '''

        html += f'''
                <div class="sizing-spec-item">
                    <div class="sizing-spec-label">{label}{sizing_indicator}</div>
                    <div class="sizing-spec-value">{_fmt(val)} {unit}</div>
                    {headroom_html}
                </div>
        '''

    # Physical specs
    html += f'''
                <div class="sizing-spec-item">
                    <div class="sizing-spec-label">Form Factor</div>
                    <div class="sizing-spec-value">{escape(specs.get("form_factor", ""))}</div>
                </div>
                <div class="sizing-spec-item">
                    <div class="sizing-spec-label">Network Ports</div>
                    <div class="sizing-spec-value">{escape(specs.get("ports", ""))}</div>
                </div>
                <div class="sizing-spec-item">
                    <div class="sizing-spec-label">Power Supply</div>
                    <div class="sizing-spec-value">{escape(specs.get("power_supply", ""))}</div>
                </div>
                <div class="sizing-spec-item">
                    <div class="sizing-spec-label">HA Supported</div>
                    <div class="sizing-spec-value">{"Yes" if specs.get("ha_supported") else "No"}</div>
                </div>
            </div>
    '''

    # Rationale
    html += '''
            <div class="sizing-rationale">
                <h4>Sizing Rationale</h4>
                <ol>
    '''
    for r in rationale:
        html += f'<li>{escape(r)}</li>'
    html += '''
                </ol>
            </div>
    '''

    # Alternative model
    if alt:
        alt_model = alt['model']
        alt_specs = alt['specs']
        html += f'''
            <div class="sizing-alternative">
                <h4>Alternative (Next Size Up)</h4>
                <div class="sizing-alt-model">
                    <strong>{escape(alt_model)}</strong> &mdash; {escape(alt_specs.get("description", ""))}
                </div>
                <div class="sizing-alt-specs">
                    Throughput: {_fmt(alt_specs.get("firewall_throughput", 0))} Mbps |
                    Sessions: {_fmt(alt_specs.get("max_sessions", 0))} |
                    Tunnels: {_fmt(alt_specs.get("max_ipsec_tunnels", 0))}
                </div>
            </div>
        '''

    html += '''
        </div>
    </div>
    '''
    return html


def _render_tunnel_breakdown(tunnel_calc, summary):
    """Render the tunnel calculation breakdown section."""
    tc = tunnel_calc
    bd = tc['breakdown']

    html = '''
    <div class="sizing-tunnel-calc">
        <h3>IPSec Tunnel Calculation</h3>
        <div class="sizing-tunnel-info">
            <span class="sizing-tunnel-rule">
                <strong>Private ISP</strong> (MPLS/P2P): 1-to-1 tunnels &mdash; each private link builds one tunnel per matching hub link
            </span>
            <span class="sizing-tunnel-rule">
                <strong>Public ISP</strong> (Internet): 1-to-many tunnels &mdash; each public link builds a tunnel to every public link on every hub
            </span>
        </div>
        <table class="sizing-tunnel-table">
            <thead>
                <tr>
                    <th>Site Role</th>
                    <th>ISP Type</th>
                    <th>Calculation</th>
                    <th>Tunnels</th>
                </tr>
            </thead>
            <tbody>
    '''

    html += f'''
                <tr>
                    <td rowspan="3"><strong>Per Hub</strong></td>
                    <td><span class="sizing-isp-badge sizing-isp-private-sm">Private</span></td>
                    <td class="sizing-calc-formula">{escape(bd["hub"]["private"])}</td>
                    <td class="sizing-calc-result">{_fmt(tc["hub_private_tunnels"])}</td>
                </tr>
                <tr>
                    <td><span class="sizing-isp-badge sizing-isp-public-sm">Public</span></td>
                    <td class="sizing-calc-formula">{escape(bd["hub"]["public"])}</td>
                    <td class="sizing-calc-result">{_fmt(tc["hub_public_tunnels"])}</td>
                </tr>
                <tr class="sizing-tunnel-subtotal">
                    <td colspan="2"><strong>Total per Hub</strong></td>
                    <td class="sizing-calc-result"><strong>{_fmt(tc["tunnels_per_hub"])}</strong></td>
                </tr>
                <tr>
                    <td rowspan="3"><strong>Per Branch</strong></td>
                    <td><span class="sizing-isp-badge sizing-isp-private-sm">Private</span></td>
                    <td class="sizing-calc-formula">{escape(bd["branch"]["private"])}</td>
                    <td class="sizing-calc-result">{_fmt(tc["branch_private_tunnels"])}</td>
                </tr>
                <tr>
                    <td><span class="sizing-isp-badge sizing-isp-public-sm">Public</span></td>
                    <td class="sizing-calc-formula">{escape(bd["branch"]["public"])}</td>
                    <td class="sizing-calc-result">{_fmt(tc["branch_public_tunnels"])}</td>
                </tr>
                <tr class="sizing-tunnel-subtotal">
                    <td colspan="2"><strong>Total per Branch</strong></td>
                    <td class="sizing-calc-result"><strong>{_fmt(tc["tunnels_per_branch"])}</strong></td>
                </tr>
    '''

    html += '''
            </tbody>
        </table>
    </div>
    '''
    return html


def _render_security_features(security_features):
    """Render the enabled security features section."""
    html = '''
    <div class="sizing-security-features">
        <h3>Security Features</h3>
        <div class="sizing-features-grid">
    '''
    for key, info in SECURITY_FEATURES.items():
        enabled = security_features.get(key, False)
        status_class = 'sizing-feature-on' if enabled else 'sizing-feature-off'
        status_icon = '&#10003;' if enabled else '&#10007;'
        impact_badge = f'<span class="sizing-impact sizing-impact-{info["impact"]}">{info["impact"].title()} Impact</span>'

        html += f'''
            <div class="sizing-feature-item {status_class}">
                <span class="sizing-feature-status">{status_icon}</span>
                <div class="sizing-feature-info">
                    <strong>{escape(info["label"])}</strong>
                    <span class="sizing-feature-desc">{escape(info["description"])}</span>
                </div>
                {impact_badge}
            </div>
        '''
    html += '''
        </div>
    </div>
    '''
    return html


def generate_sizing_dashboard(result):
    """Generate the full sizing dashboard HTML fragment."""
    summary = result['summary']
    hub = result['hub']
    branch = result['branch']
    licenses = result['licensing']
    tunnel_calc = result['tunnel_calc']
    security_features = result.get('security_features', {})

    html = '<div class="sizing-dashboard">'

    # --- Per-role platform labels ---
    hub_platform = result['hub'].get('platform', 'hardware')
    branch_platform = result['branch'].get('platform', 'hardware')
    hub_platform_label = 'VM-Series' if hub_platform == 'virtual' else 'Hardware'
    branch_platform_label = 'VM-Series' if branch_platform == 'virtual' else 'Hardware'

    # --- Deployment Summary Banner ---
    ha_text = []
    if summary['hub_ha']:
        ha_text.append(f'Hub: Yes')
    else:
        ha_text.append(f'Hub: No')
    if summary['branch_ha_count'] > 0:
        ha_text.append(f'Branch: {summary["branch_ha_count"]}/{summary["num_branches"]}')
    else:
        ha_text.append(f'Branch: No')
    ha_display = ' | '.join(ha_text)

    if hub_platform == branch_platform:
        platform_display = hub_platform_label
    else:
        platform_display = f'Hub: {hub_platform_label} | Branch: {branch_platform_label}'

    # Count enabled security features
    sec_enabled = sum(1 for k in SECURITY_FEATURES if security_features.get(k))
    sec_total = len(SECURITY_FEATURES)

    html += f'''
    <div class="sizing-summary-banner">
        <div class="sizing-summary-item">
            <span class="sizing-summary-num">{summary["num_hubs"]}</span>
            <span class="sizing-summary-label">Hub Sites</span>
        </div>
        <div class="sizing-summary-item">
            <span class="sizing-summary-num">{summary["num_branches"]}</span>
            <span class="sizing-summary-label">Branch Sites</span>
        </div>
        <div class="sizing-summary-item">
            <span class="sizing-summary-num">{summary["total_devices"]}</span>
            <span class="sizing-summary-label">Total Devices</span>
        </div>
        <div class="sizing-summary-item">
            <span class="sizing-summary-num sizing-summary-num-sm">{ha_display}</span>
            <span class="sizing-summary-label">High Availability</span>
        </div>
        <div class="sizing-summary-item">
            <span class="sizing-summary-num">{sec_enabled}/{sec_total}</span>
            <span class="sizing-summary-label">Security Features</span>
        </div>
        <div class="sizing-summary-item">
            <span class="sizing-summary-num sizing-summary-num-sm">{platform_display}</span>
            <span class="sizing-summary-label">Platform</span>
        </div>
    </div>
    '''

    # --- Security Features Summary ---
    html += _render_security_features(security_features)

    # --- Hub and Branch Cards ---
    html += '<div class="sizing-cards-row">'
    html += _render_model_card('Hub', hub, security_features)
    html += _render_model_card('Branch', branch, security_features)
    html += '</div>'

    # --- Tunnel Calculation Breakdown ---
    html += _render_tunnel_breakdown(tunnel_calc, summary)

    # --- Licensing Recommendations ---
    html += '''
    <div class="sizing-licensing">
        <h3>Licensing Recommendations</h3>
        <table class="sizing-license-table">
            <thead>
                <tr>
                    <th>License</th>
                    <th>Description</th>
                    <th>Applies To</th>
                    <th>Required</th>
                </tr>
            </thead>
            <tbody>
    '''
    for lic in licenses:
        req_badge = (
            '<span class="sizing-badge sizing-badge-required">Required</span>'
            if lic.get('required')
            else '<span class="sizing-badge sizing-badge-optional">Recommended</span>'
        )
        html += f'''
                <tr>
                    <td><strong>{escape(lic["name"])}</strong></td>
                    <td>{escape(lic.get("note", lic["description"]))}</td>
                    <td>{escape(lic.get("applies_to", ""))}</td>
                    <td>{req_badge}</td>
                </tr>
        '''
    html += '''
            </tbody>
        </table>
    </div>
    '''

    # --- BOM Summary ---
    html += '''
    <div class="sizing-bom">
        <h3>Bill of Materials Summary</h3>
        <table class="sizing-bom-table">
            <thead>
                <tr>
                    <th>Role</th>
                    <th>Model</th>
                    <th>Platform</th>
                    <th>Sites</th>
                    <th>HA</th>
                    <th>Devices</th>
                    <th>Form Factor</th>
                    <th>Series</th>
                </tr>
            </thead>
            <tbody>
    '''

    hub_ha_label = 'Yes' if summary['hub_ha'] else 'No'
    branch_ha_label = f'{summary["branch_ha_count"]} sites' if summary['branch_ha_count'] > 0 else 'No'

    html += f'''
                <tr>
                    <td>Hub</td>
                    <td><strong>{escape(hub["model"])}</strong></td>
                    <td>{hub_platform_label}</td>
                    <td>{summary["num_hubs"]}</td>
                    <td>{hub_ha_label}</td>
                    <td>{hub["device_count"]}</td>
                    <td>{escape(hub["specs"].get("form_factor", ""))}</td>
                    <td>{escape(hub["specs"].get("series", ""))}</td>
                </tr>
                <tr>
                    <td>Branch</td>
                    <td><strong>{escape(branch["model"])}</strong></td>
                    <td>{branch_platform_label}</td>
                    <td>{summary["num_branches"]}</td>
                    <td>{branch_ha_label}</td>
                    <td>{branch["device_count"]}</td>
                    <td>{escape(branch["specs"].get("form_factor", ""))}</td>
                    <td>{escape(branch["specs"].get("series", ""))}</td>
                </tr>
                <tr class="sizing-bom-total">
                    <td colspan="5"><strong>Total Devices</strong></td>
                    <td><strong>{summary["total_devices"]}</strong></td>
                    <td colspan="2"></td>
                </tr>
    '''
    html += '''
            </tbody>
        </table>
    </div>
    '''

    html += '</div>'
    return html
