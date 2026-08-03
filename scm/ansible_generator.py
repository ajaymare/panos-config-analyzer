"""Generate Ansible playbook ZIP from parsed PAN-OS SD-WAN configurations.

Produces a self-contained Ansible project with:
  - OAuth2 authentication role for SCM
  - Per-feature roles with configure and delete tasks
  - Variable files populated from parsed config data
  - Master configure_all.yml and delete_all.yml playbooks
"""
from __future__ import annotations

import io
import os
import zipfile
from typing import Any

import yaml

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parsers.base import FeatureResult
from scm.mapper import map_results
from scm.migration_report import generate_migration_report


# ---------------------------------------------------------------------------
# YAML helpers — produce clean, readable YAML
# ---------------------------------------------------------------------------

class _LiteralStr(str):
    """Tag a string for literal block scalar (|) in YAML output."""
    pass


def _literal_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')


def _str_representer(dumper, data):
    """Use quoted style for strings that look like booleans or contain special chars."""
    if data.lower() in ('yes', 'no', 'true', 'false', 'on', 'off', 'null', ''):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style="'")
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


def _dump_yaml(data: Any) -> str:
    """Dump data to clean YAML string."""
    dumper = yaml.SafeDumper
    dumper.add_representer(_LiteralStr, _literal_representer)
    # Don't override str representer globally — use default
    return yaml.dump(data, Dumper=dumper, default_flow_style=False,
                     sort_keys=False, allow_unicode=True, width=120)


# ---------------------------------------------------------------------------
# Playbook content generators
# ---------------------------------------------------------------------------

_ROLE_DISPLAY_NAMES = {
    'sdwan_interface_profiles': 'SD-WAN Interface Profiles',
    'sdwan_path_quality_profiles': 'Path Quality Profiles',
    'sdwan_traffic_distribution_profiles': 'Traffic Distribution Profiles',
    'sdwan_policies': 'SD-WAN Policies (App-ID Steering)',
    'security_rules': 'Security Rules',
    'nat_rules': 'NAT Rules',
    'ike_gateways': 'IKE Gateways',
    'ipsec_tunnels': 'IPSec Tunnels',
    'bgp_routing_profiles': 'BGP Routing Profiles',
    'interfaces': 'Interfaces',
    'zones': 'Zones',
    'custom_applications': 'Custom Applications',
    'sdwan_vpn_clusters': 'SD-WAN VPN Clusters',
    'sdwan_devices': 'SD-WAN Devices',
    'sdwan_bgp_policies': 'SD-WAN BGP Policies',
}


def _make_inventory() -> str:
    return _dump_yaml({
        'all': {
            'hosts': {
                'localhost': {
                    'ansible_connection': 'local',
                    'ansible_python_interpreter': '{{ ansible_playbook_python }}',
                }
            }
        }
    })


def _make_credentials(credentials: dict[str, str] | None = None) -> str:
    creds = credentials or {}
    return _dump_yaml({
        'scm_client_id': creds.get('client_id') or 'YOUR_CLIENT_ID_HERE',
        'scm_client_secret': creds.get('client_secret') or 'YOUR_CLIENT_SECRET_HERE',
        'scm_tsg_id': creds.get('tsg_id') or 'YOUR_TSG_ID_HERE',
        'scm_auth_url': 'https://auth.apps.paloaltonetworks.com/am/oauth2/access_token',
        'scm_base_url': 'https://api.sase.paloaltonetworks.com',
    })


def _make_settings(mapped: dict[str, dict]) -> str:
    """Generate settings with per-resource endpoint and folder."""
    settings: dict[str, Any] = {}
    for resource_name, info in mapped.items():
        settings[f'{resource_name}_endpoint'] = info['endpoint']
        settings[f'{resource_name}_folder'] = info['folder']
    return _dump_yaml(settings)


def _make_auth_tasks() -> str:
    tasks = [
        {
            'name': 'Authenticate to Strata Cloud Manager (OAuth2)',
            'ansible.builtin.uri': {
                'url': '{{ scm_auth_url }}',
                'method': 'POST',
                'body_format': 'form-urlencoded',
                'body': {
                    'grant_type': 'client_credentials',
                    'scope': 'tsg_id:{{ scm_tsg_id }}',
                    'client_id': '{{ scm_client_id }}',
                    'client_secret': '{{ scm_client_secret }}',
                },
                'status_code': [200],
            },
            'register': 'auth_response',
            'no_log': True,
        },
        {
            'name': 'Set SCM access token fact',
            'ansible.builtin.set_fact': {
                'scm_access_token': '{{ auth_response.json.access_token }}',
            },
            'no_log': True,
        },
    ]
    return _dump_yaml(tasks)


def _make_configure_tasks(resource_name: str, info: dict) -> str:
    display = _ROLE_DISPLAY_NAMES.get(resource_name, resource_name)
    endpoint_var = f'{resource_name}_endpoint'
    folder_var = f'{resource_name}_folder'

    tasks = [
        {
            'name': f'Configure {display} — {{{{ item.name | default("unnamed") }}}}',
            'ansible.builtin.uri': {
                'url': '{{ scm_base_url }}{{ ' + endpoint_var + ' }}?folder={{ ' + folder_var + ' }}',
                'method': 'POST',
                'headers': {
                    'Authorization': 'Bearer {{ scm_access_token }}',
                    'Content-Type': 'application/json',
                },
                'body_format': 'json',
                'body': '{{ item }}',
                'status_code': [200, 201],
            },
            'loop': '{{ ' + resource_name + ' | default([]) }}',
            'loop_control': {
                'label': '{{ item.name | default("unnamed") }}',
            },
            'register': f'{resource_name}_result',
        },
    ]
    return _dump_yaml(tasks)


def _make_delete_tasks(resource_name: str, info: dict) -> str:
    display = _ROLE_DISPLAY_NAMES.get(resource_name, resource_name)
    endpoint_var = f'{resource_name}_endpoint'
    folder_var = f'{resource_name}_folder'
    id_field = info.get('id_field', 'name')

    tasks = [
        {
            'name': f'Get existing {display}',
            'ansible.builtin.uri': {
                'url': '{{ scm_base_url }}{{ ' + endpoint_var + ' }}?folder={{ ' + folder_var + ' }}&name={{ item.name | default("") }}',
                'method': 'GET',
                'headers': {
                    'Authorization': 'Bearer {{ scm_access_token }}',
                    'Content-Type': 'application/json',
                },
                'status_code': [200, 404],
            },
            'loop': '{{ ' + resource_name + ' | default([]) }}',
            'loop_control': {
                'label': '{{ item.name | default("unnamed") }}',
            },
            'register': f'{resource_name}_lookup',
            'ignore_errors': True,
        },
        {
            'name': f'Delete {display} — {{{{ item.item.name | default("unnamed") }}}}',
            'ansible.builtin.uri': {
                'url': '{{ scm_base_url }}{{ ' + endpoint_var + ' }}/{{ item.json.id }}?folder={{ ' + folder_var + ' }}',
                'method': 'DELETE',
                'headers': {
                    'Authorization': 'Bearer {{ scm_access_token }}',
                    'Content-Type': 'application/json',
                },
                'status_code': [200, 204, 404],
            },
            'loop': '{{ ' + resource_name + '_lookup.results | default([]) }}',
            'loop_control': {
                'label': '{{ item.item.name | default("unnamed") }}',
            },
            'when': 'item.status == 200 and item.json.id is defined',
        },
    ]
    return _dump_yaml(tasks)


def _make_vars(resource_name: str, payloads: list[dict]) -> str:
    return _dump_yaml({resource_name: payloads})


_ROLES_ORDER = [
    'sdwan_vpn_clusters',
    'sdwan_devices',
    'sdwan_interface_profiles',
    'sdwan_path_quality_profiles',
    'sdwan_traffic_distribution_profiles',
    'sdwan_policies',
    'security_rules',
    'nat_rules',
    'ike_gateways',
    'ipsec_tunnels',
    'bgp_routing_profiles',
    'sdwan_bgp_policies',
    'interfaces',
    'zones',
    'custom_applications',
]


def _make_master_playbook(mapped: dict[str, dict], action: str) -> str:
    """Generate configure_all.yml or delete_all.yml."""
    task_includes = []

    task_includes.append({
        'name': 'Authenticate to SCM',
        'ansible.builtin.include_role': {
            'name': 'scm_auth',
        },
    })

    for resource_name in _ROLES_ORDER:
        if resource_name not in mapped:
            continue
        display = _ROLE_DISPLAY_NAMES.get(resource_name, resource_name)
        task_includes.append({
            'name': f'{action.title()} {display}',
            'ansible.builtin.include_role': {
                'name': resource_name,
                'tasks_from': f'{action}.yml',
            },
        })

    play = [
        {
            'name': f'{action.title()} PAN-OS SD-WAN Configuration on SCM',
            'hosts': 'localhost',
            'gather_facts': False,
            'tasks': task_includes,
        }
    ]
    return _dump_yaml(play)


def _make_single_playbook(resource_name: str, action: str) -> str:
    """Generate a standalone playbook for a single feature (configure or delete)."""
    display = _ROLE_DISPLAY_NAMES.get(resource_name, resource_name)
    play = [
        {
            'name': f'{action.title()} {display} on SCM',
            'hosts': 'localhost',
            'gather_facts': False,
            'tasks': [
                {
                    'name': 'Authenticate to SCM',
                    'ansible.builtin.include_role': {
                        'name': 'scm_auth',
                    },
                },
                {
                    'name': f'{action.title()} {display}',
                    'ansible.builtin.include_role': {
                        'name': resource_name,
                        'tasks_from': f'{action}.yml',
                    },
                },
            ],
        }
    ]
    return _dump_yaml(play)


def _make_readme(mapped: dict[str, dict]) -> str:
    features = []
    for rn in mapped:
        display = _ROLE_DISPLAY_NAMES.get(rn, rn)
        count = len(mapped[rn]['payloads'])
        folder = mapped[rn]['folder']
        features.append(f'  - {display}: {count} item(s) -> folder: {folder}')

    features_text = '\n'.join(features) if features else '  (none detected)'

    return f"""# SCM Ansible Playbooks — PAN-OS SD-WAN Migration

Auto-generated Ansible playbooks to deploy PAN-OS SD-WAN configuration
to Palo Alto Networks Strata Cloud Manager (SCM).

## Prerequisites

- Ansible >= 2.14
- Python >= 3.9
- SCM service account with API access (client_id, client_secret, tsg_id)

## Quick Start

1. Edit credentials:
   ```
   vi group_vars/all/scm_credentials.yml
   ```
   Replace placeholder values with your SCM OAuth2 credentials.

2. Review generated configuration data:
   ```
   ls roles/*/vars/main.yml
   ```
   Each role's vars/main.yml contains the extracted configuration.

3. Deploy (configure) ALL features:
   ```
   ansible-playbook -i inventory/hosts.yml configure_all.yml
   ```

4. Remove (delete) ALL features:
   ```
   ansible-playbook -i inventory/hosts.yml delete_all.yml
   ```

5. Deploy a SINGLE feature (modular playbooks):
   ```
   ansible-playbook -i inventory/hosts.yml configure_sdwan_interface_profiles.yml
   ansible-playbook -i inventory/hosts.yml configure_sdwan_policies.yml
   ansible-playbook -i inventory/hosts.yml configure_security_rules.yml
   ```

6. Delete a SINGLE feature:
   ```
   ansible-playbook -i inventory/hosts.yml delete_sdwan_interface_profiles.yml
   ansible-playbook -i inventory/hosts.yml delete_security_rules.yml
   ```

## Extracted Features

{features_text}

## Folder Mapping

SCM folders are auto-detected from PAN-OS source containers:
- PAN-OS `shared` -> SCM `Shared`
- PAN-OS `device-group` / `template` / `NGFW` -> SCM `Remote Networks`

Override per-feature folders in `group_vars/all/scm_settings.yml`.

## Structure

```
inventory/hosts.yml                         - Localhost inventory
group_vars/all/
  scm_credentials.yml                       - OAuth2 credentials (EDIT THIS)
  scm_settings.yml                          - Endpoints and folder mappings
roles/
  scm_auth/                                 - OAuth2 token acquisition
  <feature>/
    tasks/configure.yml                     - Create/update resources
    tasks/delete.yml                        - Remove resources
    vars/main.yml                           - Extracted configuration data
configure_all.yml                           - Deploy ALL features
delete_all.yml                              - Remove ALL features
configure_<feature>.yml                     - Deploy a single feature
delete_<feature>.yml                        - Remove a single feature
```

## Notes

- Playbooks use the `ansible.builtin.uri` module (no external collections needed)
- SCM API authentication uses OAuth2 client_credentials grant
- Configure tasks use POST; if a resource already exists, SCM may return 409 —
  update the playbook to use PUT with the resource ID for idempotent updates
- Delete tasks first look up the resource ID by name, then issue DELETE
- Sensitive credentials in scm_credentials.yml — use Ansible Vault in production:
  ```
  ansible-vault encrypt group_vars/all/scm_credentials.yml
  ```

---
Generated by PAN-OS SD-WAN Configuration Analyzer
"""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_ansible_zip(
    results: list[FeatureResult],
    output_dir: str,
    filename: str = 'scm-ansible-playbooks.zip',
    selected_features: list[str] | None = None,
    credentials: dict[str, str] | None = None,
) -> str:
    """Generate an Ansible playbook ZIP from parsed FeatureResults.

    Args:
        results: List of FeatureResult objects from the parser pipeline.
        output_dir: Directory to write the ZIP file into.
        filename: Name of the ZIP file.
        selected_features: Optional list of scm_resource_names to include
            (e.g. ['sdwan_interface_profiles', 'security_rules']).
            If None, all features are included.
        credentials: Optional SCM credentials dict with keys
            'client_id', 'client_secret', 'tsg_id'.

    Returns:
        Full path to the generated ZIP file.
    """
    mapped = map_results(results)

    # Filter to only selected features if specified
    if selected_features is not None:
        mapped = {k: v for k, v in mapped.items() if k in selected_features}

    if not mapped:
        # Nothing to generate — create a minimal ZIP with just the README
        mapped = {}

    buf = io.BytesIO()
    prefix = 'scm-ansible-playbooks'

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Inventory
        zf.writestr(f'{prefix}/inventory/hosts.yml', _make_inventory())

        # Group vars
        zf.writestr(f'{prefix}/group_vars/all/scm_credentials.yml', _make_credentials(credentials))
        zf.writestr(f'{prefix}/group_vars/all/scm_settings.yml', _make_settings(mapped))

        # Auth role
        zf.writestr(f'{prefix}/roles/scm_auth/tasks/main.yml', _make_auth_tasks())

        # Feature roles
        for resource_name, info in mapped.items():
            role_base = f'{prefix}/roles/{resource_name}'
            zf.writestr(f'{role_base}/tasks/configure.yml',
                        _make_configure_tasks(resource_name, info))
            zf.writestr(f'{role_base}/tasks/delete.yml',
                        _make_delete_tasks(resource_name, info))
            zf.writestr(f'{role_base}/vars/main.yml',
                        _make_vars(resource_name, info['payloads']))

        # Master playbooks (all features)
        zf.writestr(f'{prefix}/configure_all.yml',
                    _make_master_playbook(mapped, 'configure'))
        zf.writestr(f'{prefix}/delete_all.yml',
                    _make_master_playbook(mapped, 'delete'))

        # Per-feature standalone playbooks
        for resource_name in mapped:
            zf.writestr(f'{prefix}/configure_{resource_name}.yml',
                        _make_single_playbook(resource_name, 'configure'))
            zf.writestr(f'{prefix}/delete_{resource_name}.yml',
                        _make_single_playbook(resource_name, 'delete'))

        # Migration report (Excel)
        report_bytes = generate_migration_report(
            results, selected_features=selected_features, mapped=mapped,
        )
        zf.writestr(f'{prefix}/SCM_Migration_Report.xlsx', report_bytes)

        # README
        zf.writestr(f'{prefix}/README.md', _make_readme(mapped))

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)
    with open(out_path, 'wb') as f:
        f.write(buf.getvalue())

    return out_path
