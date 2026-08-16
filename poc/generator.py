"""Generate POC deployment packages for PAN-OS SD-WAN.

Produces either:
- Ansible playbooks targeting Panorama (paloaltonetworks.panos.panos_config_element)
- Terraform HCL targeting SCM (paloaltonetworks/scm provider)
"""
from __future__ import annotations

import io
import os
import zipfile
from typing import Any

import yaml

from poc.templates import (
    sdwan_interface_profile,
    path_quality_profile,
    traffic_distribution_profile,
    vpn_address_pool,
    vpn_cluster,
    sdwan_device,
    sdwan_policy_rule,
    security_zone,
)


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

class _LiteralStr(str):
    pass


def _literal_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')


def _str_representer(dumper, data):
    if data.lower() in ('yes', 'no', 'true', 'false', 'on', 'off', 'null', ''):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style="'")
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


def _dump_yaml(data: Any) -> str:
    dumper = yaml.SafeDumper
    dumper.add_representer(_LiteralStr, _literal_representer)
    return yaml.dump(data, Dumper=dumper, default_flow_style=False,
                     sort_keys=False, allow_unicode=True, width=120)


# ---------------------------------------------------------------------------
# Config builders — convert form inputs to xpath/element pairs
# ---------------------------------------------------------------------------

def _build_interface_profiles(inputs: dict) -> list[dict]:
    """Build interface profile configs from link definitions."""
    items = []
    template = inputs.get('template_name', 'POC-Template')
    for link in inputs.get('hub_links', []):
        item = sdwan_interface_profile(
            name=link['name'],
            link_type=link.get('type', 'public'),
            link_tag=link.get('tag', f"tag-{link.get('type', 'public')}"),
            bandwidth_up=int(link.get('bandwidth', 100)),
            bandwidth_down=int(link.get('bandwidth', 100)),
            probe_frequency=int(inputs.get('probe_frequency', 5)),
            probe_idle_time=int(inputs.get('probe_idle_time', 60)),
            failback_hold_time=int(inputs.get('failback_hold_time', 120)),
            template_name=template,
        )
        item['name'] = link['name']
        items.append(item)

    for link in inputs.get('branch_links', []):
        item = sdwan_interface_profile(
            name=link['name'],
            link_type=link.get('type', 'public'),
            link_tag=link.get('tag', f"tag-{link.get('type', 'public')}"),
            bandwidth_up=int(link.get('bandwidth', 100)),
            bandwidth_down=int(link.get('bandwidth', 100)),
            probe_frequency=int(inputs.get('probe_frequency', 5)),
            probe_idle_time=int(inputs.get('probe_idle_time', 60)),
            failback_hold_time=int(inputs.get('failback_hold_time', 120)),
            template_name=template,
        )
        item['name'] = link['name']
        items.append(item)
    return items


def _build_path_quality(inputs: dict) -> list[dict]:
    dg = inputs.get('device_group', 'POC-DeviceGroup')
    profiles = inputs.get('pq_profiles', [])
    if profiles:
        items = []
        for p in profiles:
            item = path_quality_profile(
                name=p['name'],
                latency_threshold=int(p.get('latency_threshold', 100)),
                latency_sensitivity=p.get('latency_sensitivity', 'medium'),
                jitter_threshold=int(p.get('jitter_threshold', 50)),
                jitter_sensitivity=p.get('jitter_sensitivity', 'medium'),
                pkt_loss_threshold=float(p.get('pkt_loss_threshold', 5)),
                pkt_loss_sensitivity=p.get('pkt_loss_sensitivity', 'medium'),
                device_group=dg,
            )
            item['name'] = p['name']
            items.append(item)
        return items
    # Legacy single-profile fallback
    item = path_quality_profile(
        name=inputs.get('pq_name', 'POC-PathQuality-Default'),
        latency_threshold=int(inputs.get('latency_threshold', 100)),
        latency_sensitivity=inputs.get('latency_sensitivity', 'medium'),
        jitter_threshold=int(inputs.get('jitter_threshold', 50)),
        jitter_sensitivity=inputs.get('jitter_sensitivity', 'medium'),
        pkt_loss_threshold=float(inputs.get('pkt_loss_threshold', 5)),
        pkt_loss_sensitivity=inputs.get('pkt_loss_sensitivity', 'medium'),
        device_group=dg,
    )
    item['name'] = inputs.get('pq_name', 'POC-PathQuality-Default')
    return [item]


def _build_traffic_distribution(inputs: dict) -> list[dict]:
    dg = inputs.get('device_group', 'POC-DeviceGroup')
    profiles = inputs.get('td_profiles', [])
    if profiles:
        items = []
        for p in profiles:
            item = traffic_distribution_profile(
                name=p['name'],
                method=p.get('method', 'best-available-path'),
                fec_enabled=p.get('fec_enabled', False),
                device_group=dg,
            )
            item['name'] = p['name']
            items.append(item)
        return items
    # Legacy single-profile fallback
    method = inputs.get('td_method', 'best-available-path')
    fec = inputs.get('fec_enabled', False)
    item = traffic_distribution_profile(
        name=inputs.get('td_name', f'POC-TrafficDist-{method.title().replace("-", "")}'),
        method=method,
        fec_enabled=fec,
        device_group=dg,
    )
    item['name'] = inputs.get('td_name', f'POC-TrafficDist-{method.title().replace("-", "")}')
    return [item]


def _build_vpn_topology(inputs: dict) -> list[dict]:
    topology = inputs.get('topology_type', 'hub-spoke')
    cluster_name = inputs.get('cluster_name') or 'VPN-Cluster'
    pool_subnet = inputs.get('vpn_address_pool', '').strip()

    items = []

    # VPN Address Pool (if provided)
    if pool_subnet:
        pool_item = vpn_address_pool([pool_subnet])
        pool_item['name'] = 'VPN-Address-Pool'
        items.append(pool_item)

    hubs = []
    for i, dev in enumerate(inputs.get('hub_devices', [])):
        hubs.append({'name': dev.get('serial', f'hub-{i+1}'), 'priority': i + 1})

    branches = []
    for i, dev in enumerate(inputs.get('branch_devices', [])):
        branches.append({'name': dev.get('serial', f'branch-{i+1}')})

    cluster_item = vpn_cluster(
        name=cluster_name,
        cluster_type=topology,
        hubs=hubs,
        branches=branches,
    )
    cluster_item['name'] = cluster_name
    items.append(cluster_item)
    return items


def _build_sdwan_devices(inputs: dict) -> list[dict]:
    items = []
    fallback_hub_as = inputs.get('hub_bgp_as', '')
    fallback_branch_as = inputs.get('branch_bgp_as', '')

    for i, dev in enumerate(inputs.get('hub_devices', [])):
        serial = dev.get('serial', f'hub-{i+1}')
        item = sdwan_device(
            serial=serial,
            device_type='hub',
            router_name=dev.get('name', ''),
            site=dev.get('site', ''),
            bgp_router_id=dev.get('router_id', ''),
            bgp_as_number=dev.get('bgp_as', '') or fallback_hub_as,
            bgp_enabled=inputs.get('bgp_enabled', True),
            loopback_address=dev.get('loopback', ''),
        )
        item['name'] = serial
        items.append(item)

    for i, dev in enumerate(inputs.get('branch_devices', [])):
        serial = dev.get('serial', f'branch-{i+1}')
        item = sdwan_device(
            serial=serial,
            device_type='branch',
            router_name=dev.get('name', ''),
            site=dev.get('site', ''),
            bgp_router_id=dev.get('router_id', ''),
            bgp_as_number=dev.get('bgp_as', '') or fallback_branch_as,
            bgp_enabled=inputs.get('bgp_enabled', True),
            loopback_address=dev.get('loopback', ''),
        )
        item['name'] = serial
        items.append(item)
    return items


def _build_policies(inputs: dict) -> list[dict]:
    if not inputs.get('policy_enabled', False):
        return []
    dg = inputs.get('device_group', 'POC-DeviceGroup')

    # Multi-rule support (wizard mode)
    policy_rules = inputs.get('policy_rules', [])
    if policy_rules:
        items = []
        for rule in policy_rules:
            items.append(_make_policy_item(
                rule['name'],
                rule.get('apps', ['any']),
                rule.get('pq_profile', ''),
                rule.get('td_profile', ''),
                dg,
            ))
        return items

    # Legacy single-profile fallback
    pq_name = inputs.get('pq_name', 'POC-PathQuality-Default')
    td_method = inputs.get('td_method', 'best-available-path')
    td_name = inputs.get('td_name', f'POC-TrafficDist-{td_method.title().replace("-", "")}')

    policy_template = inputs.get('policy_template', 'default')
    items = []

    if policy_template == 'voice-video':
        items.append(_make_policy_item(
            'POC-Policy-VoiceVideo', ['ms-teams', 'zoom', 'webex'],
            pq_name, td_name, dg,
        ))
        items.append(_make_policy_item(
            'POC-Policy-Default', ['any'],
            pq_name, td_name, dg,
        ))
    elif policy_template == 'custom':
        for rule in inputs.get('custom_rules', []):
            apps = [a.strip() for a in rule.get('apps', 'any').split(',')]
            items.append(_make_policy_item(
                rule.get('name', 'POC-Policy-Custom'),
                apps, pq_name, td_name, dg,
            ))
    else:
        items.append(_make_policy_item(
            'POC-Policy-AllTraffic', ['any'],
            pq_name, td_name, dg,
        ))
    return items


def _make_policy_item(name, apps, pq_name, td_name, dg):
    item = sdwan_policy_rule(
        name=name,
        applications=apps,
        path_quality_profile=pq_name,
        traffic_distribution_profile=td_name,
        device_group=dg,
    )
    item['name'] = name
    return item


def _build_zones(inputs: dict) -> list[dict]:
    """Build security zone configs."""
    template = inputs.get('template_name', 'POC-Template')
    items = []
    for zone in inputs.get('zones', []):
        name = zone.get('name', '').strip()
        if not name:
            continue
        zone_type = zone.get('type', 'layer3')
        item = security_zone(
            name=name,
            zone_type=zone_type,
            template_name=template,
        )
        item['name'] = name
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------

_ROLES = [
    ('zones', 'Security Zones', _build_zones),
    ('interface_profiles', 'SD-WAN Interface Profiles', _build_interface_profiles),
    ('path_quality', 'Path Quality Profiles', _build_path_quality),
    ('traffic_distribution', 'Traffic Distribution Profiles', _build_traffic_distribution),
    ('vpn_topology', 'VPN Topology', _build_vpn_topology),
    ('sdwan_devices', 'SD-WAN Devices', _build_sdwan_devices),
    ('sdwan_policies', 'SD-WAN Policies', _build_policies),
]


# ---------------------------------------------------------------------------
# ZIP assembly
# ---------------------------------------------------------------------------

def _make_inventory(panorama_ip: str) -> str:
    return _dump_yaml({
        'all': {
            'hosts': {
                'panorama': {
                    'ansible_host': panorama_ip or '{{ panorama_ip }}',
                    'ansible_connection': 'local',
                },
            },
        },
    })


def _make_credentials() -> str:
    return _dump_yaml({
        'panorama_ip': '<PANORAMA_IP_OR_HOSTNAME>',
        'panorama_user': '<USERNAME>',
        'panorama_password': '<PASSWORD>',
    })


def _make_collections_requirements() -> str:
    return _dump_yaml({
        'collections': [
            {'name': 'paloaltonetworks.panos', 'version': '>=2.21.0'},
        ],
    })


def _make_role_tasks(role_key: str, display_name: str) -> str:
    tasks = [{
        'name': f'Configure {display_name} — {{{{ item.name }}}}',
        'paloaltonetworks.panos.panos_config_element': {
            'provider': {
                'ip_address': '{{ panorama_ip }}',
                'username': '{{ panorama_user }}',
                'password': '{{ panorama_password }}',
            },
            'xpath': '{{ item.xpath }}',
            'element': _LiteralStr('{{ item.element }}'),
        },
        'loop': f'{{{{ {role_key}_items }}}}',
        'loop_control': {'label': '{{ item.name }}'},
    }]
    return _dump_yaml(tasks)


def _make_role_vars(role_key: str, items: list[dict]) -> str:
    return _dump_yaml({f'{role_key}_items': items})


def _make_master_playbook(active_roles: list[tuple[str, str]]) -> str:
    tasks = []
    for role_key, display_name in active_roles:
        tasks.append({
            'name': f'Configure {display_name}',
            'ansible.builtin.include_role': {
                'name': role_key,
            },
        })

    # Commit to Panorama
    tasks.append({
        'name': 'Commit configuration to Panorama',
        'paloaltonetworks.panos.panos_commit_panorama': {
            'provider': {
                'ip_address': '{{ panorama_ip }}',
                'username': '{{ panorama_user }}',
                'password': '{{ panorama_password }}',
            },
        },
    })

    playbook = [{
        'name': 'Configure PAN-OS SD-WAN POC on Panorama',
        'hosts': 'localhost',
        'gather_facts': False,
        'vars_files': ['group_vars/all/panorama_credentials.yml'],
        'tasks': tasks,
    }]
    return _dump_yaml(playbook)


def _make_standalone_playbook(role_key: str, display_name: str) -> str:
    playbook = [{
        'name': f'Configure {display_name}',
        'hosts': 'localhost',
        'gather_facts': False,
        'vars_files': ['group_vars/all/panorama_credentials.yml'],
        'tasks': [{
            'name': f'Configure {display_name}',
            'ansible.builtin.include_role': {
                'name': role_key,
            },
        }],
    }]
    return _dump_yaml(playbook)


def _make_readme(inputs: dict, active_roles: list[tuple[str, str]]) -> str:
    topology = inputs.get('topology_type', 'hub-spoke')
    num_hubs = len(inputs.get('hub_devices', []))
    num_branches = len(inputs.get('branch_devices', []))
    roles_list = '\n'.join(f'  - {name}' for _, name in active_roles)

    return f"""# PAN-OS SD-WAN POC Ansible Playbooks

Auto-generated playbooks for deploying an SD-WAN proof-of-concept on Panorama.

## Deployment Summary

- **Topology**: {topology}
- **Hubs**: {num_hubs}
- **Branches**: {num_branches}
- **Template**: {inputs.get('template_name', 'POC-Template')}
- **Device Group**: {inputs.get('device_group', 'POC-DeviceGroup')}

## Features Configured

{roles_list}

## Quick Start

1. Install the PAN-OS Ansible collection:

   ```bash
   ansible-galaxy collection install -r collections/requirements.yml
   ```

2. Edit credentials:

   ```bash
   vi group_vars/all/panorama_credentials.yml
   ```

3. Run the master playbook:

   ```bash
   ansible-playbook -i inventory/hosts.yml configure_all.yml -v
   ```

4. Or run individual feature playbooks:

   ```bash
   ansible-playbook -i inventory/hosts.yml configure_interface_profiles.yml -v
   ```

## Notes

- All config elements use `panos_config_element` to push XML directly to Panorama
- The master playbook commits to Panorama after all features are configured
- Review and adjust the generated config values before deploying to production
"""


def build_inputs_from_wizard(answers: dict) -> dict:
    """Expand 5 wizard answers into the full inputs dict for generate_poc_zip().

    answers keys:
        panorama_ip: str
        hub_count: int (1 or 2)
        branch_count: int (1-5)
        wan_type: str ('internet', 'dual-internet', 'mpls-internet')
        bandwidth: int (Mbps)
    """
    hub_count = int(answers.get('hub_count', 1))
    branch_count = int(answers.get('branch_count', 2))
    wan_type = answers.get('wan_type', 'internet')
    bandwidth = int(answers.get('bandwidth', 100))

    # --- Devices ---
    hub_devices = []
    for i in range(hub_count):
        idx = i + 1
        hub_devices.append({
            'serial': f'hub-{idx:03d}',
            'name': f'HUB-{idx}',
            'site': f'Hub-Site-{idx}',
            'bgp_as': '65000',
            'router_id': f'10.255.0.{idx}',
            'loopback': f'10.254.0.{idx}/32',
        })

    branch_devices = []
    for i in range(branch_count):
        idx = i + 1
        branch_devices.append({
            'serial': f'branch-{idx:03d}',
            'name': f'BRANCH-{idx}',
            'site': f'Branch-Site-{idx}',
            'bgp_as': str(65000 + idx),
            'router_id': f'10.255.1.{idx}',
            'loopback': f'10.254.1.{idx}/32',
        })

    # --- WAN links ---
    hub_links = []
    branch_links = []
    if wan_type == 'internet':
        hub_links = [{'name': 'WAN-Internet-1', 'type': 'public', 'bandwidth': bandwidth, 'tag': 'tag-internet'}]
        branch_links = [{'name': 'WAN-Internet-1', 'type': 'public', 'bandwidth': bandwidth, 'tag': 'tag-internet'}]
    elif wan_type == 'dual-internet':
        hub_links = [
            {'name': 'WAN-Internet-1', 'type': 'public', 'bandwidth': bandwidth, 'tag': 'tag-internet-1'},
            {'name': 'WAN-Internet-2', 'type': 'public', 'bandwidth': bandwidth, 'tag': 'tag-internet-2'},
        ]
        branch_links = [
            {'name': 'WAN-Internet-1', 'type': 'public', 'bandwidth': bandwidth, 'tag': 'tag-internet-1'},
            {'name': 'WAN-Internet-2', 'type': 'public', 'bandwidth': bandwidth, 'tag': 'tag-internet-2'},
        ]
    elif wan_type == 'mpls-internet':
        hub_links = [
            {'name': 'WAN-MPLS-1', 'type': 'private', 'bandwidth': bandwidth, 'tag': 'tag-mpls'},
            {'name': 'WAN-Internet-1', 'type': 'public', 'bandwidth': bandwidth, 'tag': 'tag-internet'},
        ]
        branch_links = [
            {'name': 'WAN-MPLS-1', 'type': 'private', 'bandwidth': bandwidth, 'tag': 'tag-mpls'},
            {'name': 'WAN-Internet-1', 'type': 'public', 'bandwidth': bandwidth, 'tag': 'tag-internet'},
        ]

    # --- Path Quality Profiles (3 profiles for full coverage) ---
    pq_profiles = [
        {
            'name': 'POC-PQ-RealTime',
            'latency_threshold': 50, 'latency_sensitivity': 'high',
            'jitter_threshold': 20, 'jitter_sensitivity': 'high',
            'pkt_loss_threshold': 1, 'pkt_loss_sensitivity': 'high',
        },
        {
            'name': 'POC-PQ-Business',
            'latency_threshold': 100, 'latency_sensitivity': 'medium',
            'jitter_threshold': 50, 'jitter_sensitivity': 'medium',
            'pkt_loss_threshold': 5, 'pkt_loss_sensitivity': 'medium',
        },
        {
            'name': 'POC-PQ-Default',
            'latency_threshold': 200, 'latency_sensitivity': 'low',
            'jitter_threshold': 100, 'jitter_sensitivity': 'low',
            'pkt_loss_threshold': 10, 'pkt_loss_sensitivity': 'low',
        },
    ]

    # --- Traffic Distribution Profiles (3 profiles) ---
    td_profiles = [
        {'name': 'POC-TD-TopDown', 'method': 'top-down', 'fec_enabled': False},
        {'name': 'POC-TD-BestPath', 'method': 'best-available-path', 'fec_enabled': False},
        {'name': 'POC-TD-BestPathFEC', 'method': 'best-available-path', 'fec_enabled': True},
    ]

    # --- SD-WAN Policy Rules (3 rules with different PQ/TD combos) ---
    policy_rules = [
        {
            'name': 'POC-Rule-VoiceVideo',
            'apps': ['ms-teams', 'zoom', 'webex'],
            'pq_profile': 'POC-PQ-RealTime',
            'td_profile': 'POC-TD-BestPathFEC',
        },
        {
            'name': 'POC-Rule-BusinessApps',
            'apps': ['ms-office365', 'salesforce', 'sap'],
            'pq_profile': 'POC-PQ-Business',
            'td_profile': 'POC-TD-BestPath',
        },
        {
            'name': 'POC-Rule-Default',
            'apps': ['any'],
            'pq_profile': 'POC-PQ-Default',
            'td_profile': 'POC-TD-TopDown',
        },
    ]

    return {
        'panorama_ip': answers.get('panorama_ip', ''),
        'template_name': 'POC-Template',
        'device_group': 'POC-DeviceGroup',
        'topology_type': 'hub-spoke',
        'cluster_name': 'POC-VPN-Cluster',
        'vpn_address_pool': '169.254.0.0/16',
        'hub_devices': hub_devices,
        'branch_devices': branch_devices,
        'hub_links': hub_links,
        'branch_links': branch_links,
        'hub_bgp_as': '65000',
        'branch_bgp_as': '65001',
        'bgp_enabled': True,
        'zones': [
            {'name': 'trust', 'type': 'layer3'},
            {'name': 'untrust', 'type': 'layer3'},
            {'name': 'vpn', 'type': 'layer3'},
        ],
        'probe_frequency': 5,
        'probe_idle_time': 60,
        'failback_hold_time': 120,
        'pq_profiles': pq_profiles,
        'td_profiles': td_profiles,
        'policy_enabled': True,
        'policy_rules': policy_rules,
    }


def generate_poc_zip(inputs: dict, output_dir: str) -> tuple[str, dict]:
    """Generate the POC Ansible playbook ZIP file.

    Returns (zip_path, summary_dict).
    """
    prefix = 'poc-ansible-playbooks'

    # Build config items for each role
    active_roles = []
    role_items = {}
    for role_key, display_name, builder in _ROLES:
        items = builder(inputs)
        if items:
            active_roles.append((role_key, display_name))
            role_items[role_key] = items

    # Assemble ZIP
    zip_filename = 'poc-ansible-playbooks.zip'
    zip_path = os.path.join(output_dir, zip_filename)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f'{prefix}/inventory/hosts.yml',
                    _make_inventory(inputs.get('panorama_ip', '')))
        zf.writestr(f'{prefix}/group_vars/all/panorama_credentials.yml',
                    _make_credentials())
        zf.writestr(f'{prefix}/collections/requirements.yml',
                    _make_collections_requirements())

        for role_key, display_name in active_roles:
            zf.writestr(f'{prefix}/roles/{role_key}/tasks/main.yml',
                        _make_role_tasks(role_key, display_name))
            zf.writestr(f'{prefix}/roles/{role_key}/vars/main.yml',
                        _make_role_vars(role_key, role_items[role_key]))

        zf.writestr(f'{prefix}/configure_all.yml',
                    _make_master_playbook(active_roles))

        for role_key, display_name in active_roles:
            zf.writestr(f'{prefix}/configure_{role_key}.yml',
                        _make_standalone_playbook(role_key, display_name))

        zf.writestr(f'{prefix}/README.md',
                    _make_readme(inputs, active_roles))

    summary = {
        'active_roles': [(k, n) for k, n in active_roles],
        'role_items': {k: len(v) for k, v in role_items.items()},
        'total_elements': sum(len(v) for v in role_items.values()),
        'topology': inputs.get('topology_type', 'hub-spoke'),
        'num_hubs': len(inputs.get('hub_devices', [])),
        'num_branches': len(inputs.get('branch_devices', [])),
        'template_name': inputs.get('template_name', 'POC-Template'),
        'device_group': inputs.get('device_group', 'POC-DeviceGroup'),
        'target': 'panorama',
    }
    return zip_path, summary


# ---------------------------------------------------------------------------
# SCM Terraform HCL generation
# ---------------------------------------------------------------------------

import re


def _san(name: str) -> str:
    """Sanitize a name for use as a Terraform identifier."""
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9_]', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    if s and s[0].isdigit():
        s = 'r_' + s
    return s or 'unnamed'


def _hcl_val(value, indent=2):
    """Render a Python value as HCL."""
    pad = '  ' * indent
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        if not value:
            return '[]'
        if all(isinstance(v, str) for v in value):
            items = ', '.join(f'"{v}"' for v in value)
            return f'[{items}]'
        return '[]'
    if isinstance(value, dict):
        if not value:
            return '{}'
        lines = ['{']
        for k, v in value.items():
            lines.append(f'{pad}  {k} = {_hcl_val(v, indent + 1)}')
        lines.append(f'{pad}}}')
        return '\n'.join(lines)
    return f'"{value}"'


def _tf_zones(inputs: dict, folder: str) -> str:
    """Generate scm_zone resources."""
    lines = ['# Security Zones', '']
    for zone in inputs.get('zones', []):
        name = zone.get('name', '').strip()
        if not name:
            continue
        tf_name = _san(name)
        lines.append(f'resource "scm_zone" "{tf_name}" {{')
        lines.append(f'  name   = "{name}"')
        lines.append(f'  folder = var.scm_folder')
        lines.append('')
        lines.append(f'  network {{')
        lines.append(f'    {zone.get("type", "layer3")} {{}}')
        lines.append(f'  }}')
        lines.append('}')
        lines.append('')
    return '\n'.join(lines)


def _tf_path_quality(inputs: dict, folder: str) -> str:
    """Generate scm_sdwan_path_quality_profile resources."""
    lines = ['# SD-WAN Path Quality Profiles', '']
    for p in inputs.get('pq_profiles', []):
        name = p['name']
        tf_name = _san(name)
        lines.append(f'resource "scm_sdwan_path_quality_profile" "{tf_name}" {{')
        lines.append(f'  name   = "{name}"')
        lines.append(f'  folder = var.scm_folder')
        lines.append('')
        lines.append(f'  metric {{')
        lines.append(f'    latency {{')
        lines.append(f'      threshold   = {p.get("latency_threshold", 100)}')
        lines.append(f'      sensitivity = "{p.get("latency_sensitivity", "medium")}"')
        lines.append(f'    }}')
        lines.append(f'    jitter {{')
        lines.append(f'      threshold   = {p.get("jitter_threshold", 50)}')
        lines.append(f'      sensitivity = "{p.get("jitter_sensitivity", "medium")}"')
        lines.append(f'    }}')
        lines.append(f'    pkt_loss {{')
        lines.append(f'      threshold   = {p.get("pkt_loss_threshold", 5)}')
        lines.append(f'      sensitivity = "{p.get("pkt_loss_sensitivity", "medium")}"')
        lines.append(f'    }}')
        lines.append(f'  }}')
        lines.append('}')
        lines.append('')
    return '\n'.join(lines)


def _tf_traffic_distribution(inputs: dict, folder: str) -> str:
    """Generate scm_sdwan_traffic_distribution_profile resources."""
    lines = ['# SD-WAN Traffic Distribution Profiles', '']
    for p in inputs.get('td_profiles', []):
        name = p['name']
        tf_name = _san(name)
        method = p.get('method', 'best-available-path')
        fec = p.get('fec_enabled', False)
        lines.append(f'resource "scm_sdwan_traffic_distribution_profile" "{tf_name}" {{')
        lines.append(f'  name   = "{name}"')
        lines.append(f'  folder = var.scm_folder')
        lines.append(f'  traffic_distribution = "{method}"')
        if fec:
            lines.append('')
            lines.append(f'  error_correction {{')
            lines.append(f'    enabled = true')
            lines.append(f'  }}')
        lines.append('}')
        lines.append('')
    return '\n'.join(lines)


def _tf_sdwan_rules(inputs: dict, folder: str) -> str:
    """Generate scm_sdwan_rule resources."""
    lines = ['# SD-WAN Policy Rules', '']
    for i, rule in enumerate(inputs.get('policy_rules', [])):
        name = rule['name']
        tf_name = _san(name)
        apps = rule.get('apps', ['any'])
        pq = rule.get('pq_profile', '')
        td = rule.get('td_profile', '')
        app_list = ', '.join(f'"{a}"' for a in apps)

        lines.append(f'resource "scm_sdwan_rule" "{tf_name}" {{')
        lines.append(f'  name     = "{name}"')
        lines.append(f'  folder   = var.scm_folder')
        lines.append(f'  position = "pre"')
        lines.append(f'  from     = ["trust"]')
        lines.append(f'  to       = ["untrust"]')
        lines.append(f'  source   = ["any"]')
        lines.append(f'  destination = ["any"]')
        lines.append(f'  application = [{app_list}]')
        lines.append(f'  service  = ["any"]')
        if pq:
            lines.append(f'  path_quality_profile = "{pq}"')
        if td:
            lines.append(f'  action {{')
            lines.append(f'    traffic_distribution_profile = "{td}"')
            lines.append(f'  }}')
        lines.append('}')
        lines.append('')
    return '\n'.join(lines)


def _tf_provider() -> str:
    return '''terraform {
  required_providers {
    scm = {
      source  = "paloaltonetworks/scm"
      version = ">= 0.9.0"
    }
  }
}

provider "scm" {
  client_id     = var.scm_client_id
  client_secret = var.scm_client_secret
  scope         = var.scm_tsg_id
  logging       = "quiet"
}
'''


def _tf_variables(folder: str) -> str:
    return f'''variable "scm_client_id" {{
  description = "SCM OAuth2 Client ID"
  type        = string
}}

variable "scm_client_secret" {{
  description = "SCM OAuth2 Client Secret"
  type        = string
  sensitive   = true
}}

variable "scm_tsg_id" {{
  description = "SCM Tenant Service Group ID"
  type        = string
}}

variable "scm_folder" {{
  description = "SCM folder for resource placement"
  type        = string
  default     = "{folder}"
}}
'''


def _tf_tfvars() -> str:
    return '''# SCM Credentials — update with your values
# For production, use environment variables:
#   export TF_VAR_scm_client_id="..."
#   export TF_VAR_scm_client_secret="..."
#   export TF_VAR_scm_tsg_id="..."

scm_client_id     = "YOUR_CLIENT_ID_HERE"
scm_client_secret = "YOUR_CLIENT_SECRET_HERE"
scm_tsg_id        = "YOUR_TSG_ID_HERE"
'''


def _tf_outputs(inputs: dict) -> str:
    lines = ['# Outputs — resource IDs for reference', '']
    if inputs.get('zones'):
        lines.append('output "zone_ids" {')
        lines.append('  description = "IDs of created security zones"')
        lines.append('  value       = [for r in scm_zone.* : r.id]')
        lines.append('}')
        lines.append('')
    if inputs.get('pq_profiles'):
        lines.append('output "path_quality_profile_ids" {')
        lines.append('  description = "IDs of created path quality profiles"')
        lines.append('  value       = [for r in scm_sdwan_path_quality_profile.* : r.id]')
        lines.append('}')
        lines.append('')
    if inputs.get('td_profiles'):
        lines.append('output "traffic_distribution_profile_ids" {')
        lines.append('  description = "IDs of created traffic distribution profiles"')
        lines.append('  value       = [for r in scm_sdwan_traffic_distribution_profile.* : r.id]')
        lines.append('}')
        lines.append('')
    if inputs.get('policy_rules'):
        lines.append('output "sdwan_rule_ids" {')
        lines.append('  description = "IDs of created SD-WAN rules"')
        lines.append('  value       = [for r in scm_sdwan_rule.* : r.id]')
        lines.append('}')
        lines.append('')
    return '\n'.join(lines)


def _tf_readme(inputs: dict) -> str:
    num_hubs = len(inputs.get('hub_devices', []))
    num_branches = len(inputs.get('branch_devices', []))
    folder = inputs.get('scm_folder', 'Remote Networks')

    return f"""# PAN-OS SD-WAN POC — SCM Terraform Configuration

Auto-generated Terraform HCL for deploying an SD-WAN proof-of-concept to Strata Cloud Manager.

## Deployment Summary

- **Target**: Strata Cloud Manager (SCM)
- **Folder**: {folder}
- **Topology**: {num_hubs} Hub(s), {num_branches} Branch(es)

## Generated Resources

- Security Zones (trust, untrust, vpn)
- 3 Path Quality Profiles (RealTime, Business, Default)
- 3 Traffic Distribution Profiles (TopDown, BestPath, BestPath+FEC)
- 3 SD-WAN Policy Rules (VoiceVideo, BusinessApps, Default)

## Quick Start

1. Edit credentials:

   ```bash
   vi terraform.tfvars
   ```

2. Initialize Terraform:

   ```bash
   terraform init
   ```

3. Review the plan:

   ```bash
   terraform plan
   ```

4. Apply the configuration:

   ```bash
   terraform apply
   ```

## Notes

- All resources are placed in the SCM folder: `{folder}`
- SD-WAN interface profiles, VPN clusters, and device onboarding are managed via the SCM UI
- Review and adjust the generated values before deploying to production
"""


def generate_poc_terraform_zip(inputs: dict, output_dir: str) -> tuple[str, dict]:
    """Generate the POC Terraform HCL ZIP file for SCM deployment.

    Returns (zip_path, summary_dict).
    """
    prefix = 'poc-scm-terraform'
    folder = inputs.get('scm_folder', 'Remote Networks')

    # Build HCL content for each feature
    tf_files = {}
    role_items = {}

    zones_hcl = _tf_zones(inputs, folder)
    if zones_hcl.strip():
        tf_files['zones.tf'] = zones_hcl
        role_items['zones'] = len(inputs.get('zones', []))

    pq_hcl = _tf_path_quality(inputs, folder)
    if pq_hcl.strip():
        tf_files['path_quality.tf'] = pq_hcl
        role_items['path_quality'] = len(inputs.get('pq_profiles', []))

    td_hcl = _tf_traffic_distribution(inputs, folder)
    if td_hcl.strip():
        tf_files['traffic_distribution.tf'] = td_hcl
        role_items['traffic_distribution'] = len(inputs.get('td_profiles', []))

    rules_hcl = _tf_sdwan_rules(inputs, folder)
    if rules_hcl.strip():
        tf_files['sdwan_rules.tf'] = rules_hcl
        role_items['sdwan_policies'] = len(inputs.get('policy_rules', []))

    # Assemble ZIP
    zip_filename = 'poc-scm-terraform.zip'
    zip_path = os.path.join(output_dir, zip_filename)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f'{prefix}/provider.tf', _tf_provider())
        zf.writestr(f'{prefix}/variables.tf', _tf_variables(folder))
        zf.writestr(f'{prefix}/terraform.tfvars', _tf_tfvars())

        for filename, content in tf_files.items():
            zf.writestr(f'{prefix}/{filename}', content)

        zf.writestr(f'{prefix}/outputs.tf', _tf_outputs(inputs))
        zf.writestr(f'{prefix}/README.md', _tf_readme(inputs))

    active_roles = []
    display_names = {
        'zones': 'Security Zones',
        'path_quality': 'Path Quality Profiles',
        'traffic_distribution': 'Traffic Distribution Profiles',
        'sdwan_policies': 'SD-WAN Policy Rules',
    }
    for key in ('zones', 'path_quality', 'traffic_distribution', 'sdwan_policies'):
        if key in role_items:
            active_roles.append((key, display_names[key]))

    summary = {
        'active_roles': active_roles,
        'role_items': role_items,
        'total_elements': sum(role_items.values()),
        'topology': inputs.get('topology_type', 'hub-spoke'),
        'num_hubs': len(inputs.get('hub_devices', [])),
        'num_branches': len(inputs.get('branch_devices', [])),
        'template_name': '',
        'device_group': '',
        'scm_folder': folder,
        'target': 'scm',
    }
    return zip_path, summary
