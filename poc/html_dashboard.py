"""Generate HTML dashboard fragment for POC Config Generator results."""
from __future__ import annotations

from html import escape


def generate_poc_dashboard(inputs: dict, summary: dict) -> str:
    """Generate the POC results dashboard HTML fragment."""
    topology = summary.get('topology', 'hub-spoke')
    num_hubs = summary.get('num_hubs', 0)
    num_branches = summary.get('num_branches', 0)
    total_elements = summary.get('total_elements', 0)
    template_name = summary.get('template_name', 'POC-Template')
    device_group = summary.get('device_group', 'POC-DeviceGroup')
    active_roles = summary.get('active_roles', [])
    role_items = summary.get('role_items', {})
    target = summary.get('target', 'panorama')
    is_scm = target == 'scm'

    html = '<div class="sizing-dashboard">'

    # --- Summary Banner ---
    target_label = 'SCM (Terraform)' if is_scm else 'Panorama (Ansible)'
    html += f'''
    <div class="sizing-summary-banner">
        <div class="sizing-summary-item">
            <div class="sizing-summary-value">{escape(target_label)}</div>
            <div class="sizing-summary-label">Target</div>
        </div>
        <div class="sizing-summary-item">
            <div class="sizing-summary-value">{escape(topology.replace("-", " ").title())}</div>
            <div class="sizing-summary-label">Topology</div>
        </div>
        <div class="sizing-summary-item">
            <div class="sizing-summary-value">{num_hubs}</div>
            <div class="sizing-summary-label">Hub Sites</div>
        </div>
        <div class="sizing-summary-item">
            <div class="sizing-summary-value">{num_branches}</div>
            <div class="sizing-summary-label">Branch Sites</div>
        </div>
        <div class="sizing-summary-item">
            <div class="sizing-summary-value">{len(active_roles)}</div>
            <div class="sizing-summary-label">Features</div>
        </div>
        <div class="sizing-summary-item">
            <div class="sizing-summary-value">{total_elements}</div>
            <div class="sizing-summary-label">Config Elements</div>
        </div>
    </div>
    '''

    # --- Target Details ---
    if is_scm:
        scm_folder = summary.get('scm_folder', inputs.get('scm_folder', 'Remote Networks'))
        html += f'''
        <div class="sizing-card" style="margin-bottom: 16px;">
            <div class="sizing-card-header" style="background: #1a3a5c;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 20px;">&#9881;</span>
                    <span>Strata Cloud Manager Target</span>
                </div>
            </div>
            <div class="sizing-card-body">
                <div class="sizing-specs-grid">
                    <div class="sizing-spec-row">
                        <span class="sizing-spec-label">Platform</span>
                        <span class="sizing-spec-value">SCM (Terraform)</span>
                    </div>
                    <div class="sizing-spec-row">
                        <span class="sizing-spec-label">Provider</span>
                        <span class="sizing-spec-value">paloaltonetworks/scm</span>
                    </div>
                    <div class="sizing-spec-row">
                        <span class="sizing-spec-label">Folder</span>
                        <span class="sizing-spec-value">{escape(scm_folder)}</span>
                    </div>
                </div>
            </div>
        </div>
        '''
    else:
        html += f'''
        <div class="sizing-card" style="margin-bottom: 16px;">
            <div class="sizing-card-header" style="background: #1a3a5c;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 20px;">&#9881;</span>
                    <span>Panorama Configuration Target</span>
                </div>
            </div>
            <div class="sizing-card-body">
                <div class="sizing-specs-grid">
                    <div class="sizing-spec-row">
                        <span class="sizing-spec-label">Template</span>
                        <span class="sizing-spec-value">{escape(template_name)}</span>
                    </div>
                    <div class="sizing-spec-row">
                        <span class="sizing-spec-label">Device Group</span>
                        <span class="sizing-spec-value">{escape(device_group)}</span>
                    </div>
                    <div class="sizing-spec-row">
                        <span class="sizing-spec-label">Panorama IP</span>
                        <span class="sizing-spec-value">{escape(inputs.get('panorama_ip', 'Set in credentials'))}</span>
                    </div>
                </div>
            </div>
        </div>
        '''

    # --- Feature Cards ---
    html += '<div class="sizing-cards-grid">'

    role_icons = {
        'zones': '&#128737;',
        'interface_profiles': '&#128268;',
        'path_quality': '&#128200;',
        'traffic_distribution': '&#128736;',
        'vpn_topology': '&#128274;',
        'sdwan_devices': '&#128421;',
        'sdwan_policies': '&#128220;',
    }

    role_descriptions = {
        'zones': _describe_zones(inputs),
        'interface_profiles': _describe_interface_profiles(inputs),
        'path_quality': _describe_path_quality(inputs),
        'traffic_distribution': _describe_traffic_distribution(inputs),
        'vpn_topology': _describe_vpn_topology(inputs),
        'sdwan_devices': _describe_sdwan_devices(inputs),
        'sdwan_policies': _describe_policies(inputs),
    }

    for role_key, display_name in active_roles:
        count = role_items.get(role_key, 0)
        icon = role_icons.get(role_key, '&#9881;')
        desc = role_descriptions.get(role_key, '')

        html += f'''
        <div class="sizing-card">
            <div class="sizing-card-header" style="background: #fa582d;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 18px;">{icon}</span>
                    <span>{escape(display_name)}</span>
                </div>
                <div class="sizing-device-count">{count} items</div>
            </div>
            <div class="sizing-card-body">
                <div style="font-size: 13px; color: var(--text-secondary); line-height: 1.6;">
                    {desc}
                </div>
            </div>
        </div>
        '''

    html += '</div>'  # sizing-cards-grid

    # --- File Summary Table ---
    if is_scm:
        html += '''
    <div class="sizing-card" style="margin-top: 16px;">
        <div class="sizing-card-header" style="background: #1a3a5c;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 18px;">&#128230;</span>
                <span>Generated Terraform Files</span>
            </div>
        </div>
        <div class="sizing-card-body" style="padding: 0;">
            <table class="sizing-table" style="margin: 0;">
                <thead>
                    <tr><th>File</th><th>Contents</th><th>Resources</th></tr>
                </thead>
                <tbody>
        '''
        tf_file_map = {
            'zones': ('zones.tf', 'Security Zones'),
            'path_quality': ('path_quality.tf', 'Path Quality Profiles'),
            'traffic_distribution': ('traffic_distribution.tf', 'Traffic Distribution Profiles'),
            'sdwan_policies': ('sdwan_rules.tf', 'SD-WAN Policy Rules'),
        }
        for role_key, display_name in active_roles:
            count = role_items.get(role_key, 0)
            tf_info = tf_file_map.get(role_key, (f'{role_key}.tf', display_name))
            html += f'''
                    <tr>
                        <td><code>{escape(tf_info[0])}</code></td>
                        <td>{escape(tf_info[1])}</td>
                        <td>{count}</td>
                    </tr>
            '''
        html += f'''
                    <tr style="background: #f0f4f8;">
                        <td><code>provider.tf</code></td>
                        <td>SCM Provider Configuration</td>
                        <td>-</td>
                    </tr>
                    <tr style="background: #f0f4f8;">
                        <td><code>variables.tf</code></td>
                        <td>Input Variables</td>
                        <td>-</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
        '''
    else:
        html += '''
    <div class="sizing-card" style="margin-top: 16px;">
        <div class="sizing-card-header" style="background: #1a3a5c;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 18px;">&#128230;</span>
                <span>Generated Playbooks</span>
            </div>
        </div>
        <div class="sizing-card-body" style="padding: 0;">
            <table class="sizing-table" style="margin: 0;">
                <thead>
                    <tr><th>Playbook</th><th>Feature</th><th>Elements</th></tr>
                </thead>
                <tbody>
        '''
        html += f'''
                    <tr style="background: #f0f4f8; font-weight: 600;">
                        <td>configure_all.yml</td>
                        <td>All Features + Commit</td>
                        <td>{total_elements}</td>
                    </tr>
        '''
        for role_key, display_name in active_roles:
            count = role_items.get(role_key, 0)
            html += f'''
                    <tr>
                        <td><code>configure_{escape(role_key)}.yml</code></td>
                        <td>{escape(display_name)}</td>
                        <td>{count}</td>
                    </tr>
            '''
        html += '''
                </tbody>
            </table>
        </div>
    </div>
        '''

    # --- Quick Start Guide ---
    if is_scm:
        html += '''
    <div class="sizing-card" style="margin-top: 16px;">
        <div class="sizing-card-header" style="background: #2e86c1;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 18px;">&#9889;</span>
                <span>Quick Start</span>
            </div>
        </div>
        <div class="sizing-card-body">
            <div style="font-size: 13px; line-height: 1.8;">
                <strong>1.</strong> Download and extract the Terraform ZIP<br>
                <strong>2.</strong> Edit credentials:
                <code style="background: #f0f4f8; padding: 2px 6px; border-radius: 3px;">
                    vi terraform.tfvars
                </code><br>
                <strong>3.</strong> Initialize Terraform:
                <code style="background: #f0f4f8; padding: 2px 6px; border-radius: 3px;">
                    terraform init
                </code><br>
                <strong>4.</strong> Review the plan:
                <code style="background: #f0f4f8; padding: 2px 6px; border-radius: 3px;">
                    terraform plan
                </code><br>
                <strong>5.</strong> Apply the configuration:
                <code style="background: #f0f4f8; padding: 2px 6px; border-radius: 3px;">
                    terraform apply
                </code>
            </div>
        </div>
    </div>
        '''
    else:
        html += '''
    <div class="sizing-card" style="margin-top: 16px;">
        <div class="sizing-card-header" style="background: #2e86c1;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 18px;">&#9889;</span>
                <span>Quick Start</span>
            </div>
        </div>
        <div class="sizing-card-body">
            <div style="font-size: 13px; line-height: 1.8;">
                <strong>1.</strong> Download and extract the playbook ZIP<br>
                <strong>2.</strong> Install the PAN-OS collection:
                <code style="background: #f0f4f8; padding: 2px 6px; border-radius: 3px;">
                    ansible-galaxy collection install -r collections/requirements.yml
                </code><br>
                <strong>3.</strong> Edit credentials:
                <code style="background: #f0f4f8; padding: 2px 6px; border-radius: 3px;">
                    vi group_vars/all/panorama_credentials.yml
                </code><br>
                <strong>4.</strong> Run the master playbook:
                <code style="background: #f0f4f8; padding: 2px 6px; border-radius: 3px;">
                    ansible-playbook -i inventory/hosts.yml configure_all.yml -v
                </code>
            </div>
        </div>
    </div>
        '''

    html += '</div>'  # sizing-dashboard
    return html


# ---------------------------------------------------------------------------
# Feature description helpers
# ---------------------------------------------------------------------------

def _describe_zones(inputs: dict) -> str:
    zones = inputs.get('zones', [])
    if not zones:
        return 'No zones defined'
    parts = []
    for z in zones:
        name = z.get('name', '?')
        ztype = z.get('type', 'layer3')
        parts.append(f"{name} ({ztype})")
    return '<br>'.join(parts)


def _describe_interface_profiles(inputs: dict) -> str:
    hub_links = inputs.get('hub_links', [])
    branch_links = inputs.get('branch_links', [])
    parts = []
    if hub_links:
        types = [l.get('type', 'public') for l in hub_links]
        parts.append(f"Hub: {len(hub_links)} links ({', '.join(types)})")
    if branch_links:
        types = [l.get('type', 'public') for l in branch_links]
        parts.append(f"Branch: {len(branch_links)} links ({', '.join(types)})")
    probe = inputs.get('probe_frequency', 5)
    parts.append(f"Probe frequency: {probe}s")
    return '<br>'.join(parts)


def _describe_path_quality(inputs: dict) -> str:
    return (
        f"Latency: {inputs.get('latency_threshold', 100)}ms "
        f"({inputs.get('latency_sensitivity', 'medium')})<br>"
        f"Jitter: {inputs.get('jitter_threshold', 50)}ms "
        f"({inputs.get('jitter_sensitivity', 'medium')})<br>"
        f"Packet Loss: {inputs.get('pkt_loss_threshold', 5)}% "
        f"({inputs.get('pkt_loss_sensitivity', 'medium')})"
    )


def _describe_traffic_distribution(inputs: dict) -> str:
    method = inputs.get('td_method', 'best-available-path')
    fec = 'Enabled' if inputs.get('fec_enabled', False) else 'Disabled'
    return f"Method: {method}<br>FEC: {fec}"


def _describe_vpn_topology(inputs: dict) -> str:
    topology = inputs.get('topology_type', 'hub-spoke')
    cluster = inputs.get('cluster_name') or 'VPN-Cluster'
    pool = inputs.get('vpn_address_pool', '')
    parts = [f"Type: {topology}", f"Cluster: {cluster}", "Auth: Pre-Shared Key"]
    if pool:
        parts.append(f"Address Pool: {pool}")
    return '<br>'.join(parts)


def _describe_sdwan_devices(inputs: dict) -> str:
    hubs = inputs.get('hub_devices', [])
    branches = inputs.get('branch_devices', [])
    parts = []
    for d in hubs[:4]:
        name = d.get('name', d.get('serial', '?'))
        details = [name]
        if d.get('bgp_as'):
            details.append(f"AS {d['bgp_as']}")
        if d.get('router_id'):
            details.append(f"RID {d['router_id']}")
        parts.append(f"Hub: {' / '.join(details)}")
    if len(hubs) > 4:
        parts.append(f'...+{len(hubs)-4} more hubs')
    for d in branches[:4]:
        name = d.get('name', d.get('serial', '?'))
        details = [name]
        if d.get('bgp_as'):
            details.append(f"AS {d['bgp_as']}")
        parts.append(f"Branch: {' / '.join(details)}")
    if len(branches) > 4:
        parts.append(f'...+{len(branches)-4} more branches')
    return '<br>'.join(parts)


def _describe_policies(inputs: dict) -> str:
    tpl = inputs.get('policy_template', 'default')
    labels = {'default': 'Default All Traffic', 'voice-video': 'Priority Voice/Video', 'custom': 'Custom Rules'}
    return f"Template: {labels.get(tpl, tpl)}"


