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

    is_hub = role.startswith('Hub')
    role_color = '#fa582d' if is_hub else '#2e86c1'
    if platform == 'virtual':
        role_icon = '&#9729;'  # cloud icon
    else:
        role_icon = '&#127981;' if is_hub else '&#127970;'

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

    # SD-WAN specific specs
    html += '''
            </div>
            <div class="sizing-sdwan-section">
                <h4>SD-WAN Capabilities</h4>
                <div class="sizing-specs-grid">
    '''

    sdwan_items = [
        ('SD-WAN Policy Rules', specs.get('sdwan_rules', 'N/A')),
        ('SD-WAN Virtual Interfaces', specs.get('sdwan_virtual_interfaces', 'N/A')),
        ('Max Security Zones', specs.get('max_zones', 'N/A')),
        ('Max Virtual Routers', specs.get('max_virtual_routers', 'N/A')),
    ]

    for label, val in sdwan_items:
        html += f'''
                <div class="sizing-spec-item">
                    <div class="sizing-spec-label">{label}</div>
                    <div class="sizing-spec-value">{_fmt(val) if isinstance(val, int) else val}</div>
                </div>
        '''

    use_case = specs.get('use_case', '')
    if use_case:
        html += f'''
                <div class="sizing-spec-item" style="grid-column: 1 / -1;">
                    <div class="sizing-spec-label">Ideal Use Case</div>
                    <div class="sizing-spec-value" style="color: #2e86c1; font-weight: 600;">{escape(use_case)}</div>
                </div>
        '''

    html += '''
                </div>
            </div>
    '''

    # Physical specs
    html += f'''
            <div class="sizing-physical-section">
                <h4>Physical Specifications</h4>
                <div class="sizing-specs-grid">
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
    topology = tc.get('topology', 'hub-spoke')
    is_full_mesh = topology == 'full-mesh'
    topology_label = 'Full Mesh' if is_full_mesh else 'Hub & Spoke'

    html = f'''
    <div class="sizing-tunnel-calc">
        <h3>IPSec Tunnel Calculation &mdash; {escape(topology_label)}</h3>
        <div class="sizing-tunnel-info">
            <span class="sizing-tunnel-rule">
                <strong>Private ISP</strong> (MPLS/P2P): 1-to-1 tunnels &mdash; each private link builds one tunnel per matching hub link
            </span>
            <span class="sizing-tunnel-rule">
                <strong>Public ISP</strong> (Internet): 1-to-many tunnels &mdash; each public link builds a tunnel to every public link on every hub
            </span>
    '''
    if is_full_mesh:
        html += '''
            <span class="sizing-tunnel-rule">
                <strong>Full Mesh</strong>: Branch-to-branch tunnels &mdash; each branch builds tunnels to every other branch via public links
            </span>
        '''
    html += '''
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
    '''

    branch_rows = 3
    if is_full_mesh and tc.get('branch_to_branch_tunnels', 0) > 0:
        branch_rows = 4

    html += f'''
                <tr>
                    <td rowspan="{branch_rows}"><strong>Per Branch</strong></td>
                    <td><span class="sizing-isp-badge sizing-isp-private-sm">Private</span></td>
                    <td class="sizing-calc-formula">{escape(bd["branch"]["private"])}</td>
                    <td class="sizing-calc-result">{_fmt(tc["branch_private_tunnels"])}</td>
                </tr>
                <tr>
                    <td><span class="sizing-isp-badge sizing-isp-public-sm">Public</span></td>
                    <td class="sizing-calc-formula">{escape(bd["branch"]["public"])}</td>
                    <td class="sizing-calc-result">{_fmt(tc["branch_public_tunnels"])}</td>
                </tr>
    '''

    if is_full_mesh and tc.get('branch_to_branch_tunnels', 0) > 0:
        html += f'''
                <tr>
                    <td><span class="sizing-isp-badge" style="background:#6c3483;color:#fff;">Mesh</span></td>
                    <td class="sizing-calc-formula">{escape(bd["branch"]["mesh"])}</td>
                    <td class="sizing-calc-result">{_fmt(tc["branch_to_branch_tunnels"])}</td>
                </tr>
        '''

    html += f'''
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


def _render_doc_references(doc_refs, sizing_result=None):
    """Render the Official Documentation panel with datasheet excerpts."""
    if not doc_refs:
        return ''

    html = '''
    <div class="sizing-doc-refs">
        <h3>Official Documentation References</h3>
        <p class="sizing-doc-refs-desc">Relevant excerpts from Palo Alto Networks datasheets, auto-retrieved for recommended models.</p>
    '''

    # Build role labels with actual model names
    role_labels = {'hub': 'Hub', 'branch': 'Branch', 'hub_virtual': 'Hub (VM-Series)'}
    if sizing_result:
        for key in ('hub', 'branch', 'hub_virtual'):
            data = sizing_result.get(key)
            if data:
                model = data.get('model', '')
                series = data.get('specs', {}).get('series', '')
                base = role_labels.get(key, key.title())
                role_labels[key] = f'{base} — {model} ({series})' if series else f'{base} — {model}'
        for i, opt in enumerate(sizing_result.get('hub_options', [])):
            rk = f'hub_option_{i + 1}'
            model = opt.get('model', '')
            series = opt.get('series', opt.get('specs', {}).get('series', ''))
            role_labels[rk] = f'Hub Option {i + 1} — {model} ({series})'
        for i, opt in enumerate(sizing_result.get('branch_options', [])):
            rk = f'branch_option_{i + 1}'
            model = opt.get('model', '')
            series = opt.get('series', opt.get('specs', {}).get('series', ''))
            role_labels[rk] = f'Branch Option {i + 1} — {model} ({series})'

    for role_key, docs in doc_refs.items():
        role_label = role_labels.get(role_key, role_key.replace('_', ' ').title())
        html += f'''
        <div class="sizing-doc-role">
            <h4>{escape(role_label)} Model Documentation</h4>
        '''
        for doc in docs:
            source = doc.get('source_file', 'Unknown source')
            page = doc.get('page', '')
            source_url = doc.get('source_url', '')
            text = doc.get('text', '')
            score = doc.get('score', 0)

            page_label = f' (Page {page})' if page else ''
            link_html = ''
            if source_url:
                link_html = f' <a href="{escape(source_url)}" target="_blank" class="sizing-doc-link">View source &#8599;</a>'

            # Truncate long text
            if len(text) > 500:
                text = text[:500] + '...'

            relevance_class = 'sizing-doc-high' if score > 0.5 else 'sizing-doc-medium' if score > 0.3 else 'sizing-doc-low'

            html += f'''
            <div class="sizing-doc-snippet {relevance_class}">
                <div class="sizing-doc-source">
                    <span class="sizing-doc-file">{escape(source)}{page_label}</span>
                    {link_html}
                </div>
                <div class="sizing-doc-text">{escape(text)}</div>
            </div>
            '''
        html += '</div>'

    html += '</div>'
    return html


def _render_comparison_tool(result, security_features):
    """Render the device comparison section with add-device capability."""
    # Collect all recommended model names for the initial comparison table
    recommended = []
    hub_options = result.get('hub_options', [])
    branch_options = result.get('branch_options', [])
    if len(hub_options) >= 2:
        for opt in hub_options:
            recommended.append(opt['model'])
    else:
        recommended.append(result['hub']['model'])
    if result.get('hub_virtual'):
        recommended.append(result['hub_virtual']['model'])
    if len(branch_options) >= 2:
        for opt in branch_options:
            if opt['model'] not in recommended:
                recommended.append(opt['model'])
    else:
        if result['branch']['model'] not in recommended:
            recommended.append(result['branch']['model'])

    rec_json = ','.join(f'"{m}"' for m in recommended)

    html = f'''
    <div class="sizing-compare-section">
        <div class="sizing-compare-header">
            <h3>Device Comparison</h3>
            <div class="sizing-compare-controls">
                <select id="sizing-compare-select" class="sizing-compare-dropdown">
                    <option value="">Add a device to compare...</option>
                </select>
                <button class="btn-run" onclick="sizingAddCompare()" id="sizing-compare-add-btn">Add to Compare</button>
            </div>
        </div>
        <div class="sizing-compare-table-wrap">
            <table class="sizing-compare-table" id="sizing-compare-table">
                <thead id="sizing-compare-thead"></thead>
                <tbody id="sizing-compare-tbody"></tbody>
            </table>
        </div>
    </div>
    <script>
    var sizingAllModels = null;
    var sizingCompareModels = [{rec_json}];
    var sizingCompareSpecs = [
        ['firewall_throughput', 'Firewall Throughput', 'Mbps'],
        ['threat_throughput', 'Threat Prevention', 'Mbps'],
        ['ssl_decrypt_throughput', 'SSL Decryption', 'Mbps'],
        ['ipsec_vpn_throughput', 'IPSec VPN', 'Mbps'],
        ['max_sessions', 'Max Sessions', ''],
        ['new_sessions_per_sec', 'New Sessions/Sec', ''],
        ['max_ipsec_tunnels', 'Max IPSec Tunnels', ''],
        ['max_security_rules', 'Max Security Rules', ''],
        ['sdwan_rules', 'SD-WAN Rules', ''],
        ['sdwan_virtual_interfaces', 'SD-WAN Virtual IFs', ''],
        ['max_zones', 'Max Zones', ''],
        ['max_virtual_routers', 'Virtual Routers', ''],
        ['form_factor', 'Form Factor', ''],
        ['ports', 'Network Ports', ''],
        ['power_supply', 'Power Supply', ''],
        ['use_case', 'Ideal Use Case', ''],
    ];

    function sizingFmtNum(n) {{
        if (typeof n !== 'number') return n || '-';
        if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
        if (n >= 1000) return n.toLocaleString();
        return n.toString();
    }}

    function sizingLoadModels() {{
        if (sizingAllModels) return Promise.resolve();
        return fetch('/model-specs').then(function(r) {{ return r.json(); }}).then(function(data) {{
            sizingAllModels = data;
            var sel = document.getElementById('sizing-compare-select');
            var names = Object.keys(data).sort();
            for (var i = 0; i < names.length; i++) {{
                var o = document.createElement('option');
                o.value = names[i];
                o.textContent = names[i] + ' (' + data[names[i]].series + ')';
                sel.appendChild(o);
            }}
        }});
    }}

    function sizingRenderCompareTable() {{
        if (!sizingAllModels) return;
        var thead = document.getElementById('sizing-compare-thead');
        var tbody = document.getElementById('sizing-compare-tbody');
        // Header row
        var hdr = '<tr><th>Specification</th>';
        for (var i = 0; i < sizingCompareModels.length; i++) {{
            var m = sizingCompareModels[i];
            var isRec = i < {len(recommended)};
            var badge = isRec ? ' <span class="sizing-badge sizing-badge-required">Recommended</span>' : ' <button class="sizing-compare-remove" onclick="sizingRemoveCompare(' + i + ')">&times;</button>';
            hdr += '<th>' + m + badge + '</th>';
        }}
        hdr += '</tr>';
        thead.innerHTML = hdr;
        // Body rows
        var body = '';
        for (var s = 0; s < sizingCompareSpecs.length; s++) {{
            var key = sizingCompareSpecs[s][0];
            var label = sizingCompareSpecs[s][1];
            var unit = sizingCompareSpecs[s][2];
            body += '<tr><td class="sizing-compare-label">' + label + '</td>';
            // Find max value for this spec (for highlighting)
            var vals = [];
            for (var i = 0; i < sizingCompareModels.length; i++) {{
                var specs = sizingAllModels[sizingCompareModels[i]];
                vals.push(specs ? (specs[key] || 0) : 0);
            }}
            var maxVal = typeof vals[0] === 'number' ? Math.max.apply(null, vals) : null;
            for (var i = 0; i < sizingCompareModels.length; i++) {{
                var specs = sizingAllModels[sizingCompareModels[i]];
                var v = specs ? specs[key] : '-';
                var display = (typeof v === 'number') ? sizingFmtNum(v) + (unit ? ' ' + unit : '') : (v || '-');
                var cls = (typeof v === 'number' && maxVal && v === maxVal && sizingCompareModels.length > 1) ? ' class="sizing-compare-best"' : '';
                body += '<td' + cls + '>' + display + '</td>';
            }}
            body += '</tr>';
        }}
        tbody.innerHTML = body;
    }}

    function sizingAddCompare() {{
        var sel = document.getElementById('sizing-compare-select');
        var model = sel.value;
        if (!model) return;
        if (sizingCompareModels.indexOf(model) >= 0) {{
            sel.value = '';
            return;
        }}
        sizingCompareModels.push(model);
        sel.value = '';
        sizingRenderCompareTable();
    }}

    function sizingRemoveCompare(idx) {{
        if (idx < {len(recommended)}) return; // can't remove recommended
        sizingCompareModels.splice(idx, 1);
        sizingRenderCompareTable();
    }}

    // Initialize
    sizingLoadModels().then(function() {{ sizingRenderCompareTable(); }});
    </script>
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
    doc_refs = result.get('doc_references', {})

    hub_virtual = result.get('hub_virtual')
    vm_series = result.get('vm_series', False)

    html = '<div class="sizing-dashboard">'

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

    platform_display = 'Hardware + VM-Series' if vm_series else 'Hardware'

    # Count enabled security features
    sec_enabled = sum(1 for k in SECURITY_FEATURES if security_features.get(k))
    sec_total = len(SECURITY_FEATURES)

    topology = summary.get('topology', 'hub-spoke')
    topology_display = 'Full Mesh' if topology == 'full-mesh' else 'Hub & Spoke'

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
            <span class="sizing-summary-num sizing-summary-num-sm">{topology_display}</span>
            <span class="sizing-summary-label">Topology</span>
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

    # --- Hub Cards ---
    html += '<div class="sizing-cards-row">'
    hub_options = result.get('hub_options', [])
    if len(hub_options) >= 2:
        for i, opt in enumerate(hub_options):
            label = f'Hub Option {i + 1} ({opt["series"]})'
            html += _render_model_card(label, opt, security_features)
    else:
        html += _render_model_card('Hub', hub, security_features)
    if hub_virtual:
        html += _render_model_card('Hub (VM-Series)', hub_virtual, security_features)
    html += '</div>'

    # --- Branch Cards ---
    html += '<div class="sizing-cards-row">'
    branch_options = result.get('branch_options', [])
    if len(branch_options) >= 2:
        for i, opt in enumerate(branch_options):
            label = f'Branch Option {i + 1} ({opt["series"]})'
            html += _render_model_card(label, opt, security_features)
    else:
        html += _render_model_card('Branch', branch, security_features)
    html += '</div>'

    # --- Device Comparison Tool ---
    html += _render_comparison_tool(result, security_features)

    # --- Official Documentation References ---
    if doc_refs:
        html += _render_doc_references(doc_refs, sizing_result=result)

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

    hub_options = result.get('hub_options', [])
    if len(hub_options) >= 2:
        for i, opt in enumerate(hub_options):
            label = f'Hub Option {i + 1}'
            html += f'''
                <tr>
                    <td>{label}</td>
                    <td><strong>{escape(opt["model"])}</strong></td>
                    <td>Hardware</td>
                    <td>{summary["num_hubs"]}</td>
                    <td>{hub_ha_label}</td>
                    <td>{opt["device_count"]}</td>
                    <td>{escape(opt["specs"].get("form_factor", ""))}</td>
                    <td>{escape(opt["specs"].get("series", ""))}</td>
                </tr>
            '''
    else:
        html += f'''
                <tr>
                    <td>Hub</td>
                    <td><strong>{escape(hub["model"])}</strong></td>
                    <td>Hardware</td>
                    <td>{summary["num_hubs"]}</td>
                    <td>{hub_ha_label}</td>
                    <td>{hub["device_count"]}</td>
                    <td>{escape(hub["specs"].get("form_factor", ""))}</td>
                    <td>{escape(hub["specs"].get("series", ""))}</td>
                </tr>
        '''
    if hub_virtual:
        html += f'''
                <tr>
                    <td>Hub (Cloud)</td>
                    <td><strong>{escape(hub_virtual["model"])}</strong></td>
                    <td>VM-Series</td>
                    <td>{summary["num_hubs"]}</td>
                    <td>{hub_ha_label}</td>
                    <td>{hub_virtual["device_count"]}</td>
                    <td>{escape(hub_virtual["specs"].get("form_factor", ""))}</td>
                    <td>{escape(hub_virtual["specs"].get("series", ""))}</td>
                </tr>
        '''

    branch_options = result.get('branch_options', [])
    if len(branch_options) >= 2:
        for i, opt in enumerate(branch_options):
            label = f'Branch Option {i + 1}'
            html += f'''
                <tr>
                    <td>{label}</td>
                    <td><strong>{escape(opt["model"])}</strong></td>
                    <td>Hardware</td>
                    <td>{summary["num_branches"]}</td>
                    <td>{branch_ha_label}</td>
                    <td>{opt["device_count"]}</td>
                    <td>{escape(opt["specs"].get("form_factor", ""))}</td>
                    <td>{escape(opt["specs"].get("series", ""))}</td>
                </tr>
            '''
    else:
        html += f'''
                <tr>
                    <td>Branch</td>
                    <td><strong>{escape(branch["model"])}</strong></td>
                    <td>Hardware</td>
                    <td>{summary["num_branches"]}</td>
                    <td>{branch_ha_label}</td>
                    <td>{branch["device_count"]}</td>
                    <td>{escape(branch["specs"].get("form_factor", ""))}</td>
                    <td>{escape(branch["specs"].get("series", ""))}</td>
                </tr>
        '''

    html += f'''
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
