"""Generate Ansible playbook ZIP for PAN-OS SD-WAN POC deployment.

Produces a self-contained Ansible project that configures SD-WAN features
on Panorama using paloaltonetworks.panos.panos_config_element.
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
    }
    return zip_path, summary
