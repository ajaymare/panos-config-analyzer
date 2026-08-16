"""Sizing algorithm for PA Firewall SD-WAN deployments.

Takes site requirements as input and recommends the best-fit PA model
for both Hub and Branch roles.

Tunnel calculation logic:
- Private ISP links: 1-to-1 tunnels (each branch private link -> matching hub private link)
- Public ISP links: 1-to-many tunnels (each branch public link -> ALL hub public links on ALL hubs)
"""

from .models import PA_MODELS, VM_MODELS, LICENSE_RECOMMENDATIONS, SECURITY_FEATURES


def _format_number(n):
    """Format large numbers with K/M suffixes."""
    if n >= 1_000_000:
        return f'{n / 1_000_000:.1f}M'
    if n >= 1_000:
        return f'{n / 1_000:.0f}K'
    return str(n)


def _get_throughput_key(security_features):
    """Determine which throughput metric to use based on enabled security features.

    Priority (worst-case throughput wins):
    1. SSL Decryption enabled -> ssl_decrypt_throughput (lowest)
    2. Threat Prevention enabled -> threat_throughput
    3. Neither -> ipsec_vpn_throughput (best case)
    """
    if security_features.get('ssl_decryption'):
        return 'ssl_decrypt_throughput'
    if security_features.get('threat_prevention'):
        return 'threat_throughput'
    return 'ipsec_vpn_throughput'


def _throughput_label(security_features):
    """Human-readable label for the throughput metric being used."""
    if security_features.get('ssl_decryption'):
        return 'SSL Decryption'
    if security_features.get('threat_prevention'):
        return 'Threat Prevention'
    return 'IPSec VPN'


def calculate_tunnels(num_hubs, hub_public_isps, hub_private_isps,
                      num_branches, branch_public_isps, branch_private_isps,
                      topology='hub-spoke'):
    """Calculate IPSec tunnel counts based on ISP types and topology.

    Hub-Spoke topology:
        Private links: 1-to-1 mapping -- each branch private link builds
            one tunnel to each hub's private link (per hub).
        Public links: 1-to-many -- each branch public link builds a tunnel
            to every public link on every hub.

    Full Mesh topology:
        Same as hub-spoke PLUS branch-to-branch tunnels -- each branch
        builds tunnels to every other branch via public links.

    Returns dict with per-branch, per-hub, and total tunnel counts + breakdown.
    """
    # Per branch: tunnels to ALL hubs
    branch_private_tunnels = branch_private_isps * hub_private_isps * num_hubs
    branch_public_tunnels = branch_public_isps * hub_public_isps * num_hubs
    tunnels_per_branch = branch_private_tunnels + branch_public_tunnels

    # Per hub: tunnels from ALL branches
    hub_private_tunnels = hub_private_isps * branch_private_isps * num_branches
    hub_public_tunnels = hub_public_isps * branch_public_isps * num_branches
    tunnels_per_hub = hub_private_tunnels + hub_public_tunnels

    # Full mesh: branch-to-branch tunnels via public links
    branch_to_branch_tunnels = 0
    if topology == 'full-mesh' and num_branches > 1:
        # Each branch builds public tunnels to every OTHER branch
        branch_to_branch_tunnels = branch_public_isps * branch_public_isps * (num_branches - 1)
        tunnels_per_branch += branch_to_branch_tunnels

    total_tunnels = (tunnels_per_hub * num_hubs) + (tunnels_per_branch * num_branches)

    breakdown = {
        'hub': {
            'private': f'{hub_private_isps} hub private x {branch_private_isps} branch private x {num_branches} branches = {hub_private_tunnels}',
            'public': f'{hub_public_isps} hub public x {branch_public_isps} branch public x {num_branches} branches = {hub_public_tunnels}',
        },
        'branch': {
            'private': f'{branch_private_isps} branch private x {hub_private_isps} hub private x {num_hubs} hubs = {branch_private_tunnels}',
            'public': f'{branch_public_isps} branch public x {hub_public_isps} hub public x {num_hubs} hubs = {branch_public_tunnels}',
        },
    }

    if topology == 'full-mesh' and num_branches > 1:
        breakdown['branch']['mesh'] = (
            f'{branch_public_isps} local public x {branch_public_isps} remote public x '
            f'{num_branches - 1} other branches = {branch_to_branch_tunnels}'
        )

    return {
        'tunnels_per_branch': tunnels_per_branch,
        'branch_private_tunnels': branch_private_tunnels,
        'branch_public_tunnels': branch_public_tunnels,
        'branch_to_branch_tunnels': branch_to_branch_tunnels,
        'tunnels_per_hub': tunnels_per_hub,
        'hub_private_tunnels': hub_private_tunnels,
        'hub_public_tunnels': hub_public_tunnels,
        'total_tunnels': total_tunnels,
        'topology': topology,
        'breakdown': breakdown,
    }


def _find_best_model(required_throughput, concurrent_sessions, num_tunnels,
                     role, security_features, platform='hardware', headroom_pct=30):
    """Find the smallest PA model that meets all requirements with headroom.

    A minimum headroom (default 30%) is applied to all requirements to ensure
    the recommended model has sufficient capacity for growth and burst traffic.

    Returns (model_name, specs, rationale, alternative).
    """
    headroom_factor = 1 + (headroom_pct / 100)  # 1.3 for 30%
    throughput_key = _get_throughput_key(security_features)
    tp_label = _throughput_label(security_features)
    rationale = []

    # Select model catalog
    models = VM_MODELS if platform == 'virtual' else PA_MODELS

    # Sized-up requirements (with headroom baked in)
    sized_throughput = int(required_throughput * headroom_factor)
    sized_sessions = int(concurrent_sessions * headroom_factor)
    sized_tunnels = int(num_tunnels * headroom_factor)

    rationale.append(
        f'Required throughput: {_format_number(required_throughput)} Mbps '
        f'(using {tp_label} throughput)'
    )
    rationale.append(f'Required concurrent sessions: {_format_number(concurrent_sessions)}')
    rationale.append(f'Required IPSec tunnels: {_format_number(num_tunnels)}')
    rationale.append(f'Minimum headroom: {headroom_pct}% '
                     f'(sizing for {_format_number(sized_throughput)} Mbps / '
                     f'{_format_number(sized_sessions)} sessions / '
                     f'{_format_number(sized_tunnels)} tunnels)')

    # Security features summary
    enabled = [SECURITY_FEATURES[k]['label'] for k in SECURITY_FEATURES
               if security_features.get(k)]
    if enabled:
        rationale.append(f'Security features: {", ".join(enabled)}')
    else:
        rationale.append('Security features: None (IPSec VPN only)')

    rationale.append(f'Platform: {platform.title()}')
    rationale.append(f'Site role: {role.title()}')

    candidates = []
    for model_name, specs in models.items():
        if specs[throughput_key] < sized_throughput:
            continue
        if specs['max_sessions'] < sized_sessions:
            continue
        if specs['max_ipsec_tunnels'] < sized_tunnels:
            continue
        candidates.append((model_name, specs))

    if not candidates:
        largest = list(models.items())[-1]
        rationale.append(
            f'No model fully meets all requirements. '
            f'Recommending the largest available: {largest[0]}'
        )
        return largest[0], largest[1], rationale, None

    # Prefer models matching the role
    role_preferred = []
    for model_name, specs in candidates:
        rec_role = specs['recommended_role']
        if rec_role == 'both' or rec_role == role:
            role_preferred.append((model_name, specs))

    if role_preferred:
        pick = role_preferred[0]
        rationale.append(
            f'Selected {pick[0]} -- smallest model meeting all requirements '
            f'and recommended for {role} deployments'
        )
    else:
        pick = candidates[0]
        rationale.append(
            f'Selected {pick[0]} -- smallest model meeting all requirements '
            f'(no {role}-specific model available at this tier)'
        )

    # Find alternative (next model up)
    all_models = list(models.keys())
    pick_idx = all_models.index(pick[0])
    alternative = None
    if pick_idx + 1 < len(all_models):
        alt_name = all_models[pick_idx + 1]
        alternative = {'model': alt_name, 'specs': models[alt_name]}

    # Add headroom info
    specs = pick[1]
    tp_headroom = ((specs[throughput_key] - required_throughput) / required_throughput * 100)
    sess_headroom = ((specs['max_sessions'] - concurrent_sessions) / concurrent_sessions * 100)
    tun_headroom = ((specs['max_ipsec_tunnels'] - num_tunnels) / num_tunnels * 100) if num_tunnels > 0 else 100
    rationale.append(
        f'Headroom -- Throughput: {tp_headroom:.0f}%, '
        f'Sessions: {sess_headroom:.0f}%, '
        f'Tunnels: {tun_headroom:.0f}%'
    )

    return pick[0], pick[1], rationale, alternative


def calculate_sizing(inputs):
    """Run the sizing calculator.

    Args:
        inputs: dict with keys:
            num_hubs: int
            num_branches: int
            hub_public_isps: int
            hub_private_isps: int
            branch_public_isps: int
            branch_private_isps: int
            hub_bandwidth_mbps: int
            branch_bandwidth_mbps: int
            hub_sessions: int
            branch_sessions: int
            threat_prevention: bool
            ssl_decryption: bool
            url_filtering: bool
            wildfire: bool
            dns_security: bool
            hub_ha: bool
            branch_ha_count: int
            vm_series: bool (include VM-Series hub recommendation)

    Returns:
        dict with hub, branch, (optional hub_virtual), tunnel_calc,
        licensing, summary.
    """
    num_hubs = inputs.get('num_hubs', 1)
    num_branches = inputs.get('num_branches', 1)
    hub_public_isps = inputs.get('hub_public_isps', 1)
    hub_private_isps = inputs.get('hub_private_isps', 1)
    branch_public_isps = inputs.get('branch_public_isps', 1)
    branch_private_isps = inputs.get('branch_private_isps', 0)
    hub_bandwidth = inputs.get('hub_bandwidth_mbps', 1000)
    branch_bandwidth = inputs.get('branch_bandwidth_mbps', 100)
    topology = inputs.get('topology', 'hub-spoke')
    hub_ha = inputs.get('hub_ha', False)
    branch_ha_count = inputs.get('branch_ha_count', 0)
    vm_series = inputs.get('vm_series', False)

    # Auto-derive concurrent sessions from throughput
    # Rule of thumb: ~500 sessions per Mbps of throughput
    hub_sessions = inputs.get('hub_sessions', hub_bandwidth * 500)
    branch_sessions = inputs.get('branch_sessions', branch_bandwidth * 500)

    # Security features dict
    security_features = {
        'threat_prevention': inputs.get('threat_prevention', False),
        'ssl_decryption': inputs.get('ssl_decryption', False),
        'url_filtering': inputs.get('url_filtering', False),
        'wildfire': inputs.get('wildfire', False),
        'dns_security': inputs.get('dns_security', False),
    }

    # --- Calculate tunnels from ISP links ---
    tunnel_calc = calculate_tunnels(
        num_hubs=num_hubs,
        hub_public_isps=hub_public_isps,
        hub_private_isps=hub_private_isps,
        num_branches=num_branches,
        branch_public_isps=branch_public_isps,
        branch_private_isps=branch_private_isps,
        topology=topology,
    )

    hub_tunnels = tunnel_calc['tunnels_per_hub']
    branch_tunnels = tunnel_calc['tunnels_per_branch']

    # --- Hub sizing (Hardware) ---
    hub_model, hub_specs, hub_rationale, hub_alt = _find_best_model(
        required_throughput=hub_bandwidth,
        concurrent_sessions=hub_sessions,
        num_tunnels=hub_tunnels,
        role='hub',
        security_features=security_features,
        platform='hardware',
    )

    # --- Hub sizing (VM-Series) — only when VM-Series enabled ---
    hub_vm_result = None
    if vm_series:
        vm_model, vm_specs, vm_rationale, vm_alt = _find_best_model(
            required_throughput=hub_bandwidth,
            concurrent_sessions=hub_sessions,
            num_tunnels=hub_tunnels,
            role='hub',
            security_features=security_features,
            platform='virtual',
        )
        hub_vm_result = {
            'model': vm_model,
            'specs': vm_specs,
            'rationale': vm_rationale,
            'alternative': vm_alt,
            'platform': 'virtual',
            'inputs': {
                'bandwidth_mbps': hub_bandwidth,
                'tunnels': hub_tunnels,
                'sessions': hub_sessions,
            },
            'isps': {
                'public': hub_public_isps,
                'private': hub_private_isps,
                'total': hub_public_isps + hub_private_isps,
            },
        }

    # --- Branch sizing (always Hardware) ---
    branch_model, branch_specs, branch_rationale, branch_alt = _find_best_model(
        required_throughput=branch_bandwidth,
        concurrent_sessions=branch_sessions,
        num_tunnels=branch_tunnels,
        role='branch',
        security_features=security_features,
        platform='hardware',
    )

    # --- Licensing ---
    licenses = []
    licenses.append({
        **LICENSE_RECOMMENDATIONS['sdwan'],
        'applies_to': 'All devices',
    })

    # Count enabled security features
    sec_count = sum(1 for v in security_features.values() if v)

    if sec_count >= 3:
        # Recommend BPLA bundle when 3+ features enabled
        licenses.append({
            **LICENSE_RECOMMENDATIONS['bpla'],
            'applies_to': 'All devices',
            'note': 'Recommended bundle — includes Threat Prevention, WildFire, URL Filtering, DNS Security, and SD-WAN',
        })
    else:
        if security_features['threat_prevention']:
            licenses.append({
                **LICENSE_RECOMMENDATIONS['threat_prevention'],
                'applies_to': 'All devices',
            })
        if security_features['url_filtering']:
            licenses.append({
                **LICENSE_RECOMMENDATIONS['url_filtering'],
                'applies_to': 'All devices',
            })
        if security_features['wildfire']:
            licenses.append({
                **LICENSE_RECOMMENDATIONS['wildfire'],
                'applies_to': 'All devices',
            })
        if security_features['dns_security']:
            licenses.append({
                **LICENSE_RECOMMENDATIONS['dns_security'],
                'applies_to': 'All devices',
            })
        if not security_features['threat_prevention']:
            licenses.append({
                **LICENSE_RECOMMENDATIONS['threat_prevention'],
                'applies_to': 'Optional',
                'note': 'Consider enabling for branch security',
            })

    if security_features['ssl_decryption']:
        licenses.append({
            **LICENSE_RECOMMENDATIONS['ssl_decryption'],
            'applies_to': 'All devices',
            'note': 'No additional license required — included in PAN-OS. Ensure sufficient throughput headroom.',
        })

    licenses.append({
        **LICENSE_RECOMMENDATIONS['adem'],
        'applies_to': 'Optional',
        'note': 'Recommended for SD-WAN visibility and monitoring',
    })

    # --- Device counts ---
    hub_devices = num_hubs * (2 if hub_ha else 1)
    branch_ha_count = min(branch_ha_count, num_branches)
    branch_non_ha = num_branches - branch_ha_count
    branch_devices = (branch_ha_count * 2) + branch_non_ha
    total_devices = hub_devices + branch_devices

    result = {
        'hub': {
            'model': hub_model,
            'specs': hub_specs,
            'rationale': hub_rationale,
            'alternative': hub_alt,
            'device_count': hub_devices,
            'platform': 'hardware',
            'inputs': {
                'bandwidth_mbps': hub_bandwidth,
                'tunnels': hub_tunnels,
                'sessions': hub_sessions,
            },
            'isps': {
                'public': hub_public_isps,
                'private': hub_private_isps,
                'total': hub_public_isps + hub_private_isps,
            },
        },
        'branch': {
            'model': branch_model,
            'specs': branch_specs,
            'rationale': branch_rationale,
            'alternative': branch_alt,
            'device_count': branch_devices,
            'platform': 'hardware',
            'inputs': {
                'bandwidth_mbps': branch_bandwidth,
                'tunnels': branch_tunnels,
                'sessions': branch_sessions,
            },
            'isps': {
                'public': branch_public_isps,
                'private': branch_private_isps,
                'total': branch_public_isps + branch_private_isps,
            },
        },
        'tunnel_calc': tunnel_calc,
        'licensing': licenses,
        'security_features': security_features,
        'vm_series': vm_series,
        'summary': {
            'num_hubs': num_hubs,
            'num_branches': num_branches,
            'topology': topology,
            'hub_ha': hub_ha,
            'branch_ha_count': branch_ha_count,
            'threat_prevention': security_features['threat_prevention'],
            'ssl_decryption': security_features['ssl_decryption'],
            'url_filtering': security_features['url_filtering'],
            'wildfire': security_features['wildfire'],
            'dns_security': security_features['dns_security'],
            'total_devices': total_devices,
            'hub_devices': hub_devices,
            'branch_devices': branch_devices,
            'vm_series': vm_series,
        },
        'inputs': inputs,
    }

    if hub_vm_result:
        hub_vm_result['device_count'] = hub_devices
        result['hub_virtual'] = hub_vm_result

    return result
