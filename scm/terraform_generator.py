"""Generate Terraform HCL files from parsed PAN-OS SD-WAN configurations.

Produces a self-contained Terraform project targeting the paloaltonetworks/scm
provider to deploy SD-WAN configuration to Strata Cloud Manager (SCM).
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from typing import Any

from parsers.base import FeatureResult
from scm.mapper import map_results


# ---------------------------------------------------------------------------
# HCL helpers
# ---------------------------------------------------------------------------

def _sanitize_tf_name(name: str) -> str:
    """Convert a resource name to a valid Terraform identifier."""
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9_]', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    if s and s[0].isdigit():
        s = 'r_' + s
    return s or 'unnamed'


def _hcl_value(value: Any, indent: int = 2) -> str:
    """Render a Python value as HCL."""
    pad = '  ' * indent
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        if not value:
            return '[]'
        if all(isinstance(v, str) for v in value):
            items = ', '.join(f'"{v}"' for v in value)
            return f'[{items}]'
        # List of objects
        lines = ['[']
        for item in value:
            lines.append(f'{pad}  {{')
            if isinstance(item, dict):
                for k, v in item.items():
                    lines.append(f'{pad}    {k} = {_hcl_value(v, indent + 2)}')
            lines.append(f'{pad}  }},')
        lines.append(f'{pad}]')
        return '\n'.join(lines)
    if isinstance(value, dict):
        if not value:
            return '{}'
        lines = ['{']
        for k, v in value.items():
            lines.append(f'{pad}  {k} = {_hcl_value(v, indent + 1)}')
        lines.append(f'{pad}}}')
        return '\n'.join(lines)
    return f'"{value}"'


def _hcl_block(block_type: str, labels: list[str], attrs: dict[str, Any],
               nested_blocks: dict[str, dict | list] | None = None) -> str:
    """Render a complete HCL block."""
    label_str = ' '.join(f'"{l}"' for l in labels)
    lines = [f'{block_type} {label_str} {{']

    for key, val in attrs.items():
        lines.append(f'  {key} = {_hcl_value(val, 1)}')

    if nested_blocks:
        for bname, bval in nested_blocks.items():
            if isinstance(bval, dict):
                lines.append('')
                lines.append(f'  {bname} {{')
                for k, v in bval.items():
                    if isinstance(v, dict):
                        lines.append(f'    {k} {{')
                        for kk, vv in v.items():
                            lines.append(f'      {kk} = {_hcl_value(vv, 3)}')
                        lines.append('    }')
                    else:
                        lines.append(f'    {k} = {_hcl_value(v, 2)}')
                lines.append('  }')

    lines.append('}')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Resource mapping: mapper scm_resource_name → Terraform resource type
# ---------------------------------------------------------------------------

_RESOURCE_MAP = {
    'sdwan_path_quality_profiles': 'scm_sdwan_path_quality_profile',
    'sdwan_traffic_distribution_profiles': 'scm_sdwan_traffic_distribution_profile',
    'sdwan_policies': 'scm_sdwan_rule',
    'security_rules': 'scm_security_rule',
    'nat_rules': 'scm_nat_rule',
    'ike_gateways': 'scm_ike_gateway',
    'ipsec_tunnels': 'scm_ipsec_tunnel',
    'bgp_routing_profiles': 'scm_bgp_routing',
    'zones': 'scm_zone',
    'custom_applications': 'scm_application',
    'sdwan_vpn_clusters': 'scm_auto_vpn_cluster',
    'sdwan_devices': 'scm_auto_vpn_cluster',
    'interfaces': 'scm_ethernet_interface',
    'sdwan_interface_profiles': 'scm_sdwan_path_quality_profile',  # placeholder
    'sdwan_bgp_policies': 'scm_bgp_routing',
}

_TF_FILE_MAP = {
    'sdwan_path_quality_profiles': 'path_quality.tf',
    'sdwan_traffic_distribution_profiles': 'traffic_distribution.tf',
    'sdwan_policies': 'sdwan_rules.tf',
    'security_rules': 'security_rules.tf',
    'nat_rules': 'nat_rules.tf',
    'ike_gateways': 'vpn.tf',
    'ipsec_tunnels': 'vpn.tf',
    'bgp_routing_profiles': 'routing.tf',
    'zones': 'zones.tf',
    'custom_applications': 'applications.tf',
    'sdwan_vpn_clusters': 'auto_vpn.tf',
    'sdwan_devices': 'auto_vpn.tf',
    'interfaces': 'interfaces.tf',
    'sdwan_interface_profiles': 'interface_profiles.tf',
    'sdwan_bgp_policies': 'routing.tf',
}

# Display names for comments
_DISPLAY_NAMES = {
    'sdwan_path_quality_profiles': 'SD-WAN Path Quality Profiles',
    'sdwan_traffic_distribution_profiles': 'SD-WAN Traffic Distribution Profiles',
    'sdwan_policies': 'SD-WAN Policy Rules (App-ID Steering)',
    'security_rules': 'Security Rules',
    'nat_rules': 'NAT Rules',
    'ike_gateways': 'IKE Gateways',
    'ipsec_tunnels': 'IPSec Tunnels',
    'bgp_routing_profiles': 'BGP Routing Profiles',
    'zones': 'Security Zones',
    'custom_applications': 'Custom Applications',
    'sdwan_vpn_clusters': 'SD-WAN VPN Clusters (Auto-VPN)',
    'sdwan_devices': 'SD-WAN Devices',
    'interfaces': 'Network Interfaces',
    'sdwan_interface_profiles': 'SD-WAN Interface Profiles',
    'sdwan_bgp_policies': 'SD-WAN BGP Policies',
}


# ---------------------------------------------------------------------------
# Per-resource HCL converters
# ---------------------------------------------------------------------------

def _convert_path_quality(payload: dict, folder: str) -> str:
    """Convert path quality payload to scm_sdwan_path_quality_profile HCL."""
    name = payload.get('name', 'unnamed')
    tf_name = _sanitize_tf_name(name)

    metric = payload.get('metric', {})
    nested = {}
    if metric:
        metric_block = {}
        for key in ('latency', 'jitter', 'pkt_loss'):
            if key in metric:
                metric_block[key] = metric[key]
        if metric_block:
            nested['metric'] = metric_block

    return _hcl_block('resource', ['scm_sdwan_path_quality_profile', tf_name], {
        'name': name,
        'folder': folder,
    }, nested)


def _convert_traffic_distribution(payload: dict, folder: str) -> str:
    """Convert traffic distribution payload to scm_sdwan_traffic_distribution_profile HCL."""
    name = payload.get('name', 'unnamed')
    tf_name = _sanitize_tf_name(name)

    attrs: dict[str, Any] = {
        'name': name,
        'folder': folder,
    }
    if payload.get('traffic_distribution'):
        attrs['traffic_distribution'] = payload['traffic_distribution']

    # Link tags as nested blocks
    link_tags = payload.get('link_tags', [])
    weights_str = payload.get('weights', '')
    nested = {}
    if link_tags:
        tag_list = []
        weights = [w.strip() for w in weights_str.split(',')] if weights_str else []
        for i, tag in enumerate(link_tags):
            tag_entry: dict[str, Any] = {'name': tag}
            if i < len(weights):
                try:
                    tag_entry['weight'] = int(weights[i])
                except ValueError:
                    pass
            tag_list.append(tag_entry)
        # Render link_tags as repeated blocks
        lines = []
        for t in tag_list:
            block = ['  link_tags {']
            block.append(f'    name = "{t["name"]}"')
            if 'weight' in t:
                block.append(f'    weight = {t["weight"]}')
            block.append('  }')
            lines.append('\n'.join(block))
        # Return custom rendering
        attr_lines = [f'resource "scm_sdwan_traffic_distribution_profile" "{tf_name}" {{']
        for k, v in attrs.items():
            attr_lines.append(f'  {k} = {_hcl_value(v, 1)}')
        attr_lines.append('')
        attr_lines.extend(lines)
        attr_lines.append('}')
        return '\n'.join(attr_lines)

    return _hcl_block('resource', ['scm_sdwan_traffic_distribution_profile', tf_name], attrs)


def _convert_sdwan_rule(payload: dict, folder: str) -> str:
    """Convert SD-WAN policy payload to scm_sdwan_rule HCL."""
    name = payload.get('name', 'unnamed')
    tf_name = _sanitize_tf_name(name)

    attrs: dict[str, Any] = {
        'name': name,
        'folder': folder,
        'position': 'pre',
    }

    if payload.get('from'):
        attrs['from'] = payload['from']
    if payload.get('to'):
        attrs['to'] = payload['to']
    if payload.get('application'):
        attrs['application'] = payload['application']
    if payload.get('service'):
        attrs['service'] = payload['service']

    # source/destination/source_user defaults
    attrs['source'] = ['any']
    attrs['destination'] = ['any']
    attrs['source_user'] = ['any']

    if payload.get('path_quality_profile'):
        attrs['path_quality_profile'] = payload['path_quality_profile']
    if payload.get('saas_quality_profile'):
        attrs['saas_quality_profile'] = payload['saas_quality_profile']
    if payload.get('disabled'):
        attrs['disabled'] = True

    nested = {}
    td = payload.get('traffic_distribution_profile')
    if td:
        nested['action'] = {'traffic_distribution_profile': td}

    return _hcl_block('resource', ['scm_sdwan_rule', tf_name], attrs, nested)


def _convert_security_rule(payload: dict, folder: str) -> str:
    """Convert security rule payload to scm_security_rule HCL."""
    name = payload.get('name', 'unnamed')
    tf_name = _sanitize_tf_name(name)

    attrs: dict[str, Any] = {
        'name': name,
        'folder': folder,
        'position': 'pre',
    }

    for field in ('from', 'to', 'source', 'destination', 'application', 'service'):
        if payload.get(field):
            attrs[field] = payload[field]

    attrs.setdefault('source_user', ['any'])

    action = payload.get('action', 'allow')
    attrs['action'] = action

    if payload.get('log_end'):
        attrs['log_end'] = payload['log_end']
    if payload.get('disabled'):
        attrs['disabled'] = True

    return _hcl_block('resource', ['scm_security_rule', tf_name], attrs)


def _convert_nat_rule(payload: dict, folder: str) -> str:
    """Convert NAT rule payload to scm_nat_rule HCL."""
    name = payload.get('name', 'unnamed')
    tf_name = _sanitize_tf_name(name)

    attrs: dict[str, Any] = {
        'name': name,
        'folder': folder,
        'position': 'pre',
    }

    for field in ('from', 'to', 'source', 'destination', 'service'):
        if payload.get(field):
            attrs[field] = payload[field]

    if payload.get('disabled'):
        attrs['disabled'] = True

    # Source/dest translation as comments (complex nested structures)
    lines = [_hcl_block('resource', ['scm_nat_rule', tf_name], attrs)]
    if payload.get('source_translation'):
        lines.insert(-1, f'  # source_translation: {payload["source_translation"]}')
    if payload.get('destination_translation'):
        lines.insert(-1, f'  # destination_translation: {payload["destination_translation"]}')
    return '\n'.join(lines)


def _convert_ike_gateway(payload: dict, folder: str) -> str:
    """Convert IKE gateway payload to scm_ike_gateway HCL."""
    name = payload.get('name', 'unnamed')
    tf_name = _sanitize_tf_name(name)

    attrs: dict[str, Any] = {
        'name': name,
        'folder': folder,
    }

    nested = {}
    peer = payload.get('peer_address', {})
    if peer:
        nested['peer_address'] = peer

    nested['authentication'] = {
        'pre_shared_key': {'key': 'CHANGE_ME'},
    }
    nested['protocol'] = {
        'version': 'ikev2-preferred',
    }

    return _hcl_block('resource', ['scm_ike_gateway', tf_name], attrs, nested)


def _convert_ipsec_tunnel(payload: dict, folder: str) -> str:
    """Convert IPSec tunnel payload to scm_ipsec_tunnel HCL."""
    name = payload.get('name', 'unnamed')
    tf_name = _sanitize_tf_name(name)

    attrs: dict[str, Any] = {
        'name': name,
        'folder': folder,
    }

    if payload.get('tunnel_interface'):
        attrs['tunnel_interface'] = payload['tunnel_interface']

    nested = {}
    auto_key = payload.get('auto_key', {})
    if auto_key:
        nested['auto_key'] = auto_key

    if payload.get('tunnel_monitor', {}).get('enable'):
        nested['tunnel_monitor'] = {'enable': True}

    return _hcl_block('resource', ['scm_ipsec_tunnel', tf_name], attrs, nested)


def _convert_bgp_routing(payload: dict, folder: str) -> str:
    """Convert BGP routing payload to scm_bgp_routing HCL."""
    name = payload.get('name', 'unnamed')
    tf_name = _sanitize_tf_name(name)

    attrs: dict[str, Any] = {
        'folder': folder,
    }

    # BGP routing is a singleton in SCM — add relevant fields as comments
    lines = [f'# BGP Routing Profile: {name}']
    if payload.get('router_id'):
        lines.append(f'# Router ID: {payload["router_id"]}')
    if payload.get('local_as'):
        lines.append(f'# Local AS: {payload["local_as"]}')

    lines.append(f'resource "scm_bgp_routing" "{tf_name}" {{')
    lines.append(f'  folder = "{folder}"')
    lines.append('')
    lines.append('  backbone_routing = {')
    if payload.get('local_as'):
        lines.append(f'    asn = "{payload["local_as"]}"')
    lines.append('    accept_route = {')
    lines.append('      default_route = true')
    lines.append('    }')
    lines.append('  }')
    lines.append('}')

    return '\n'.join(lines)


def _convert_zone(payload: dict, folder: str) -> str:
    """Convert zone payload to scm_zone HCL."""
    name = payload.get('name', 'unnamed')
    tf_name = _sanitize_tf_name(name)

    attrs: dict[str, Any] = {
        'name': name,
        'folder': folder,
    }

    nested = {}
    network = payload.get('network', {})
    if network:
        nested['network'] = network

    return _hcl_block('resource', ['scm_zone', tf_name], attrs, nested)


def _convert_interface(payload: dict, folder: str) -> str:
    """Convert interface payload to scm_ethernet_interface HCL."""
    name = payload.get('name', 'unnamed')
    tf_name = _sanitize_tf_name(name)

    attrs: dict[str, Any] = {
        'name': name,
        'folder': folder,
    }

    if payload.get('comment'):
        attrs['comment'] = payload['comment']

    # SD-WAN link settings
    sdwan = payload.get('sdwan_link_settings')
    lines = [_hcl_block('resource', ['scm_ethernet_interface', tf_name], attrs)]
    if sdwan:
        lines.insert(-1, f'  # sdwan_interface_profile: {sdwan.get("sdwan_interface_profile", "")}')
    return '\n'.join(lines)


def _convert_application(payload: dict, folder: str) -> str:
    """Convert custom application payload to scm_application HCL."""
    name = payload.get('name', 'unnamed')
    tf_name = _sanitize_tf_name(name)

    attrs: dict[str, Any] = {
        'name': name,
        'folder': folder,
    }

    if payload.get('category'):
        attrs['category'] = payload['category']
    if payload.get('subcategory'):
        attrs['subcategory'] = payload['subcategory']
    if payload.get('technology'):
        attrs['technology'] = payload['technology']
    if payload.get('risk') is not None:
        attrs['risk'] = payload['risk']

    return _hcl_block('resource', ['scm_application', tf_name], attrs)


def _convert_vpn_cluster(payload: dict, folder: str) -> str:
    """Convert VPN cluster payload to scm_auto_vpn_cluster HCL."""
    name = payload.get('name', 'unnamed')
    tf_name = _sanitize_tf_name(name)

    attrs: dict[str, Any] = {
        'name': name,
    }

    cluster_type = payload.get('type', 'hub-spoke')
    attrs['type'] = cluster_type
    attrs['enable_sdwan'] = True

    # Hubs
    hubs = payload.get('hubs', [])
    branches = payload.get('branches', [])

    lines = [f'resource "scm_auto_vpn_cluster" "{tf_name}" {{']
    for k, v in attrs.items():
        lines.append(f'  {k} = {_hcl_value(v, 1)}')

    if hubs:
        lines.append('')
        for hub in hubs:
            hub_name = hub if isinstance(hub, str) else hub.get('name', hub)
            lines.append('  gateways {')
            lines.append(f'    name = "{hub_name}"')
            lines.append('  }')

    if branches:
        lines.append('')
        for branch in branches:
            branch_name = branch if isinstance(branch, str) else branch.get('name', branch)
            lines.append('  branches {')
            lines.append(f'    name = "{branch_name}"')
            lines.append('  }')

    lines.append('}')
    return '\n'.join(lines)


def _convert_sdwan_device(payload: dict, folder: str) -> str:
    """Convert SD-WAN device payload to a comment block (devices are part of auto_vpn_cluster)."""
    name = payload.get('name', 'unnamed')
    dev_type = payload.get('type', 'branch')
    bgp = payload.get('bgp', {})

    lines = [f'# SD-WAN Device: {name} (type: {dev_type})']
    if payload.get('router_name'):
        lines.append(f'#   Router Name: {payload["router_name"]}')
    if payload.get('site'):
        lines.append(f'#   Site: {payload["site"]}')
    if bgp.get('router_id'):
        lines.append(f'#   BGP Router ID: {bgp["router_id"]}')
    if bgp.get('as_number'):
        lines.append(f'#   BGP AS: {bgp["as_number"]}')
    if bgp.get('loopback_address'):
        lines.append(f'#   Loopback: {bgp["loopback_address"]}')
    lines.append(f'# Note: Add this device to the appropriate scm_auto_vpn_cluster resource above')
    return '\n'.join(lines)


def _convert_bgp_policy(payload: dict, folder: str) -> str:
    """Convert BGP policy payload to a comment block."""
    name = payload.get('name', 'unnamed')
    rules = payload.get('rules', [])
    lines = [f'# BGP Policy: {name}']
    if rules:
        lines.append(f'#   Security Rules: {", ".join(rules)}')
    return '\n'.join(lines)


def _convert_interface_profile(payload: dict, folder: str) -> str:
    """Convert SD-WAN interface profile to a comment + variable block.

    Interface profiles don't have a direct Terraform resource in the SCM provider.
    They are configured as part of Auto-VPN cluster link settings.
    """
    name = payload.get('name', 'unnamed')
    tf_name = _sanitize_tf_name(name)

    lines = [f'# SD-WAN Interface Profile: {name}']
    lines.append(f'# Note: Interface profiles are applied via scm_auto_vpn_cluster sdwan_link_settings')

    props = []
    for key in ('link_type', 'link_tag', 'path_monitoring', 'probe_frequency',
                'probe_idle_time', 'failback_hold_time', 'maximum_upload', 'maximum_download'):
        if payload.get(key) is not None:
            props.append(f'#   {key}: {payload[key]}')
    if props:
        lines.extend(props)

    # Generate a local value for reference
    lines.append(f'')
    lines.append(f'locals {{')
    lines.append(f'  interface_profile_{tf_name} = {{')
    for key in ('link_type', 'link_tag', 'path_monitoring', 'probe_frequency',
                'probe_idle_time', 'failback_hold_time', 'maximum_upload', 'maximum_download'):
        if payload.get(key) is not None:
            lines.append(f'    {key} = {_hcl_value(payload[key], 2)}')
    lines.append(f'  }}')
    lines.append(f'}}')

    return '\n'.join(lines)


# Converter dispatch
_CONVERTERS = {
    'sdwan_path_quality_profiles': _convert_path_quality,
    'sdwan_traffic_distribution_profiles': _convert_traffic_distribution,
    'sdwan_policies': _convert_sdwan_rule,
    'security_rules': _convert_security_rule,
    'nat_rules': _convert_nat_rule,
    'ike_gateways': _convert_ike_gateway,
    'ipsec_tunnels': _convert_ipsec_tunnel,
    'bgp_routing_profiles': _convert_bgp_routing,
    'zones': _convert_zone,
    'custom_applications': _convert_application,
    'sdwan_vpn_clusters': _convert_vpn_cluster,
    'sdwan_devices': _convert_sdwan_device,
    'interfaces': _convert_interface,
    'sdwan_interface_profiles': _convert_interface_profile,
    'sdwan_bgp_policies': _convert_bgp_policy,
}


# ---------------------------------------------------------------------------
# Static file generators
# ---------------------------------------------------------------------------

def _make_provider_tf() -> str:
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


def _make_variables_tf(folder: str) -> str:
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


def _make_tfvars(credentials: dict[str, str] | None = None) -> str:
    creds = credentials or {}
    cid = creds.get('client_id', 'YOUR_CLIENT_ID_HERE')
    csec = creds.get('client_secret', 'YOUR_CLIENT_SECRET_HERE')
    tsg = creds.get('tsg_id', 'YOUR_TSG_ID_HERE')

    return f'''# SCM Credentials — update with your values
# For production, use environment variables or a .tfvars file NOT checked into git
#   export TF_VAR_scm_client_id="..."
#   export TF_VAR_scm_client_secret="..."
#   export TF_VAR_scm_tsg_id="..."

scm_client_id     = "{cid}"
scm_client_secret = "{csec}"
scm_tsg_id        = "{tsg}"
'''


def _make_outputs_tf(mapped: dict[str, dict]) -> str:
    lines = ['# Outputs — resource IDs for reference', '']
    for resource_name, info in mapped.items():
        tf_type = _RESOURCE_MAP.get(resource_name)
        if not tf_type or resource_name in ('sdwan_devices', 'sdwan_bgp_policies',
                                             'sdwan_interface_profiles'):
            continue
        display = _DISPLAY_NAMES.get(resource_name, resource_name)
        safe_name = _sanitize_tf_name(resource_name)
        lines.append(f'# output "{safe_name}_ids" {{')
        lines.append(f'#   description = "IDs of created {display}"')
        lines.append(f'#   value       = [for r in {tf_type}.* : r.id]')
        lines.append(f'# }}')
        lines.append('')
    return '\n'.join(lines)


def _make_readme(mapped: dict[str, dict]) -> str:
    features = []
    for rn in mapped:
        display = _DISPLAY_NAMES.get(rn, rn)
        count = len(mapped[rn]['payloads'])
        folder = mapped[rn]['folder']
        tf_type = _RESOURCE_MAP.get(rn, 'N/A')
        features.append(f'| {display} | {count} | `{tf_type}` | {folder} |')

    features_table = '\n'.join(features) if features else '| (none detected) | | | |'

    return f"""# SCM Terraform Configuration — PAN-OS SD-WAN

Auto-generated Terraform configuration to deploy PAN-OS SD-WAN settings
to Palo Alto Networks Strata Cloud Manager (SCM).

## Prerequisites

- Terraform >= 1.5
- SCM service account with API access (client_id, client_secret, tsg_id)
- `paloaltonetworks/scm` Terraform provider

## Quick Start

1. Update credentials in `terraform.tfvars` (or use environment variables):
   ```bash
   export TF_VAR_scm_client_id="your-client-id"
   export TF_VAR_scm_client_secret="your-client-secret"
   export TF_VAR_scm_tsg_id="your-tsg-id"
   ```

2. Initialize Terraform:
   ```bash
   terraform init
   ```

3. Preview changes:
   ```bash
   terraform plan
   ```

4. Apply configuration:
   ```bash
   terraform apply
   ```

5. To destroy all managed resources:
   ```bash
   terraform destroy
   ```

## Extracted Features

| Feature | Count | Terraform Resource | SCM Folder |
|---------|-------|--------------------|------------|
{features_table}

## Folder Mapping

SCM folders are auto-detected from PAN-OS source containers:
- PAN-OS `shared` -> SCM `Shared`
- PAN-OS `device-group` / `template` / `NGFW` -> SCM `Remote Networks`

Override the default folder via the `scm_folder` variable.

## File Structure

```
provider.tf              - Provider configuration
variables.tf             - Variable declarations
terraform.tfvars         - Credential values (DO NOT commit to git)
path_quality.tf          - SD-WAN Path Quality Profiles
traffic_distribution.tf  - SD-WAN Traffic Distribution Profiles
sdwan_rules.tf           - SD-WAN Policy Rules
security_rules.tf        - Security Rules
nat_rules.tf             - NAT Rules
vpn.tf                   - IKE Gateways & IPSec Tunnels
routing.tf               - BGP Routing
zones.tf                 - Security Zones
interfaces.tf            - Network Interfaces
applications.tf          - Custom Applications
auto_vpn.tf              - Auto-VPN Clusters
interface_profiles.tf    - SD-WAN Interface Profiles (as locals)
outputs.tf               - Output values
```

## Notes

- Terraform state tracks all managed resources — use `terraform plan` to preview changes
- The SCM provider handles OAuth2 authentication automatically
- Interface profiles are stored as `locals` since there is no dedicated Terraform resource;
  they are applied via `scm_auto_vpn_cluster` sdwan_link_settings
- Review all generated resources before applying to production

---
Generated by PAN-OS SD-WAN Configuration Analyzer
"""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_terraform_zip(
    results: list[FeatureResult],
    output_dir: str,
    filename: str = 'scm-terraform.zip',
    selected_features: list[str] | None = None,
    credentials: dict[str, str] | None = None,
) -> str:
    """Generate a Terraform project ZIP from parsed FeatureResults.

    Args:
        results: List of FeatureResult objects from the parser pipeline.
        output_dir: Directory to write the ZIP file into.
        filename: Name of the ZIP file.
        selected_features: Optional list of scm_resource_names to include.
            If None, all features are included.
        credentials: Optional SCM credentials dict with keys
            'client_id', 'client_secret', 'tsg_id'.

    Returns:
        Full path to the generated ZIP file.
    """
    mapped = map_results(results)

    if selected_features is not None:
        mapped = {k: v for k, v in mapped.items() if k in selected_features}

    # Determine default folder from mapped data
    default_folder = 'Shared'
    for info in mapped.values():
        default_folder = info.get('folder', 'Shared')
        break

    # Group HCL blocks by output file
    file_blocks: dict[str, list[str]] = {}

    for resource_name, info in mapped.items():
        converter = _CONVERTERS.get(resource_name)
        if not converter:
            continue

        tf_file = _TF_FILE_MAP.get(resource_name, f'{resource_name}.tf')
        display = _DISPLAY_NAMES.get(resource_name, resource_name)
        folder = info.get('folder', default_folder)

        blocks = file_blocks.setdefault(tf_file, [])
        if not blocks:
            blocks.append(f'# {display}')
            blocks.append(f'# Auto-generated from PAN-OS configuration')
            blocks.append('')
        else:
            blocks.append('')
            blocks.append(f'# --- {display} ---')
            blocks.append('')

        for payload in info['payloads']:
            hcl = converter(payload, folder)
            blocks.append(hcl)
            blocks.append('')

    # Assemble ZIP
    buf = io.BytesIO()
    prefix = 'scm-terraform'

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f'{prefix}/provider.tf', _make_provider_tf())
        zf.writestr(f'{prefix}/variables.tf', _make_variables_tf(default_folder))
        zf.writestr(f'{prefix}/terraform.tfvars', _make_tfvars(credentials))

        for tf_file, blocks in file_blocks.items():
            content = '\n'.join(blocks)
            zf.writestr(f'{prefix}/{tf_file}', content)

        zf.writestr(f'{prefix}/outputs.tf', _make_outputs_tf(mapped))
        zf.writestr(f'{prefix}/README.md', _make_readme(mapped))

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)
    with open(out_path, 'wb') as f:
        f.write(buf.getvalue())

    return out_path
