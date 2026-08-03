"""Map FeatureResult objects to SCM (Strata Cloud Manager) API payloads.

Each FeatureMapper subclass handles one parser's output and converts its
tabular rows/columns into JSON dicts matching the SCM REST API schema.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parsers.base import FeatureResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_list(value: str) -> list[str]:
    """Split comma-separated cell value into a list, stripping whitespace."""
    if not value or not value.strip():
        return []
    return [v.strip() for v in value.split(',') if v.strip()]


def _to_int(value: str, default: int | None = None) -> int | None:
    """Coerce string to int; return *default* for empty / non-numeric."""
    if not value or not value.strip():
        return default
    cleaned = re.sub(r'[^\d.-]', '', value.strip())
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return default


def _to_float(value: str, default: float | None = None) -> float | None:
    """Coerce string to float."""
    if not value or not value.strip():
        return default
    cleaned = re.sub(r'[^\d.-]', '', value.strip())
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return default


def _col_index(columns: list[str], name: str) -> int:
    """Return index of *name* in *columns*, case-insensitive. -1 if missing."""
    name_lower = name.lower()
    for i, c in enumerate(columns):
        if c.lower() == name_lower:
            return i
    return -1


def _get(row: list, columns: list[str], name: str, default: str = '') -> str:
    """Get a cell value by column name."""
    idx = _col_index(columns, name)
    if idx < 0 or idx >= len(row):
        return default
    val = row[idx]
    return str(val) if val is not None else default


def detect_scm_folder(source: str) -> str:
    """Auto-detect SCM folder from PAN-OS source container name.

    Mapping:
      shared / Shared           → Shared
      device-group / template   → Remote Networks
      NGFW                      → Remote Networks
      default                   → Shared
    """
    s = source.lower().strip()
    if s in ('shared',):
        return 'Shared'
    if any(kw in s for kw in ('device-group', 'template', 'ngfw')):
        return 'Remote Networks'
    return 'Shared'


# ---------------------------------------------------------------------------
# Base mapper
# ---------------------------------------------------------------------------

class FeatureMapper(ABC):
    """Converts a FeatureResult into a list of SCM API payloads."""

    feature_name: str = ''          # must match FeatureResult.feature_name
    scm_endpoint: str = ''          # SCM REST path
    scm_resource_name: str = ''     # Ansible variable name (snake_case)

    @abstractmethod
    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        """Convert a single FeatureResult into SCM JSON payloads (one per row)."""
        ...

    def get_id_field(self) -> str:
        """Field used to identify a resource for DELETE. Override if not 'name'."""
        return 'name'


# ---------------------------------------------------------------------------
# Concrete mappers
# ---------------------------------------------------------------------------

class InterfaceProfileMapper(FeatureMapper):
    feature_name = 'SD-WAN Interface Profiles'
    scm_endpoint = '/sdwan/v2.0/api/sdwaninterfaceprofiles'
    scm_resource_name = 'sdwan_interface_profiles'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        payloads = []
        for row in result.rows:
            p: dict[str, Any] = {
                'name': _get(row, result.columns, 'Name'),
            }
            link_type = _get(row, result.columns, 'Link Type')
            if link_type:
                p['link_type'] = link_type

            link_tag = _get(row, result.columns, 'Link Tag')
            if link_tag:
                p['link_tag'] = link_tag

            path_mon = _get(row, result.columns, 'Path Monitoring')
            if path_mon:
                p['path_monitoring'] = path_mon

            probe_freq = _to_int(_get(row, result.columns, 'Probe Frequency'))
            if probe_freq is not None:
                p['probe_frequency'] = probe_freq

            probe_idle = _to_int(_get(row, result.columns, 'Probe Idle Time'))
            if probe_idle is not None:
                p['probe_idle_time'] = probe_idle

            failback = _to_int(_get(row, result.columns, 'Failback Hold Time (s)'))
            if failback is not None:
                p['failback_hold_time'] = failback

            max_up = _to_int(_get(row, result.columns, 'Max Upload (Mbps)'))
            if max_up is not None:
                p['maximum_upload'] = max_up

            max_down = _to_int(_get(row, result.columns, 'Max Download (Mbps)'))
            if max_down is not None:
                p['maximum_download'] = max_down

            if p.get('name'):
                payloads.append(p)
        return payloads


class PathQualityMapper(FeatureMapper):
    feature_name = 'Path Quality Metrics'
    scm_endpoint = '/sdwan/v2.0/api/sdwanpathqualityprofiles'
    scm_resource_name = 'sdwan_path_quality_profiles'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        payloads = []
        for row in result.rows:
            p: dict[str, Any] = {
                'name': _get(row, result.columns, 'Name'),
                'metric': {},
            }
            lat_thresh = _to_int(_get(row, result.columns, 'Latency Threshold (ms)'))
            lat_sens = _get(row, result.columns, 'Latency Sensitivity')
            if lat_thresh is not None or lat_sens:
                p['metric']['latency'] = {}
                if lat_thresh is not None:
                    p['metric']['latency']['threshold'] = lat_thresh
                if lat_sens:
                    p['metric']['latency']['sensitivity'] = lat_sens

            jit_thresh = _to_int(_get(row, result.columns, 'Jitter Threshold (ms)'))
            jit_sens = _get(row, result.columns, 'Jitter Sensitivity')
            if jit_thresh is not None or jit_sens:
                p['metric']['jitter'] = {}
                if jit_thresh is not None:
                    p['metric']['jitter']['threshold'] = jit_thresh
                if jit_sens:
                    p['metric']['jitter']['sensitivity'] = jit_sens

            pkt_thresh = _to_float(_get(row, result.columns, 'Packet Loss Threshold (%)'))
            pkt_sens = _get(row, result.columns, 'Packet Loss Sensitivity')
            if pkt_thresh is not None or pkt_sens:
                p['metric']['pkt_loss'] = {}
                if pkt_thresh is not None:
                    p['metric']['pkt_loss']['threshold'] = pkt_thresh
                if pkt_sens:
                    p['metric']['pkt_loss']['sensitivity'] = pkt_sens

            if not p['metric']:
                del p['metric']

            if p.get('name'):
                payloads.append(p)
        return payloads


class TrafficDistributionMapper(FeatureMapper):
    feature_name = 'Traffic Distribution Profiles'
    scm_endpoint = '/sdwan/v2.0/api/sdwantrafficdistributionprofiles'
    scm_resource_name = 'sdwan_traffic_distribution_profiles'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        payloads = []
        for row in result.rows:
            p: dict[str, Any] = {
                'name': _get(row, result.columns, 'Name'),
            }
            method = _get(row, result.columns, 'Distribution Method')
            if method:
                p['traffic_distribution'] = method

            link_tags = _get(row, result.columns, 'Link Tags')
            if link_tags:
                p['link_tags'] = _split_list(link_tags)

            weights = _get(row, result.columns, 'Weights')
            if weights:
                p['weights'] = weights

            fec = _get(row, result.columns, 'Error Correction (FEC)')
            if fec:
                p['error_correction'] = fec.lower() == 'yes'

            pkt_dup = _get(row, result.columns, 'Packet Duplication')
            if pkt_dup:
                p['packet_duplication'] = pkt_dup.lower() == 'yes'

            if p.get('name'):
                payloads.append(p)
        return payloads


class SDWANPolicyMapper(FeatureMapper):
    feature_name = 'App-ID Steering'
    scm_endpoint = '/sdwan/v2.0/api/sdwanpolicyrules'
    scm_resource_name = 'sdwan_policies'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        payloads = []
        for row in result.rows:
            p: dict[str, Any] = {
                'name': _get(row, result.columns, 'Name'),
            }
            src_zone = _get(row, result.columns, 'Source Zone')
            if src_zone:
                p['from'] = _split_list(src_zone)

            dst_zone = _get(row, result.columns, 'Dest Zone')
            if dst_zone:
                p['to'] = _split_list(dst_zone)

            app = _get(row, result.columns, 'Application')
            if app:
                p['application'] = _split_list(app)

            svc = _get(row, result.columns, 'Service')
            if svc:
                p['service'] = _split_list(svc)

            pq = _get(row, result.columns, 'Path Quality Profile')
            if pq:
                p['path_quality_profile'] = pq

            td = _get(row, result.columns, 'Traffic Distribution Profile')
            if td:
                p['traffic_distribution_profile'] = td

            saas = _get(row, result.columns, 'SaaS Quality Profile')
            if saas:
                p['saas_quality_profile'] = saas

            disabled = _get(row, result.columns, 'Disabled')
            if disabled and disabled.lower() == 'yes':
                p['disabled'] = True

            if p.get('name'):
                payloads.append(p)
        return payloads


class SecurityRuleMapper(FeatureMapper):
    feature_name = 'SD-WAN Security Rules'
    scm_endpoint = '/sse/config/v1/security-rules'
    scm_resource_name = 'security_rules'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        payloads = []
        for row in result.rows:
            p: dict[str, Any] = {
                'name': _get(row, result.columns, 'Rule Name'),
            }
            # SCM uses 'from'/'to' for zones, 'source'/'destination' for addresses
            src_zone = _get(row, result.columns, 'Source Zone')
            p['from'] = _split_list(src_zone) if src_zone else ['any']

            dst_zone = _get(row, result.columns, 'Dest Zone')
            p['to'] = _split_list(dst_zone) if dst_zone else ['any']

            # source and destination are required by SCM API
            src_addr = _get(row, result.columns, 'Source Address')
            p['source'] = _split_list(src_addr) if src_addr else ['any']

            dst_addr = _get(row, result.columns, 'Dest Address')
            p['destination'] = _split_list(dst_addr) if dst_addr else ['any']

            app = _get(row, result.columns, 'Application')
            if app:
                p['application'] = _split_list(app)
            else:
                p['application'] = ['any']

            svc = _get(row, result.columns, 'Service')
            if svc:
                p['service'] = _split_list(svc)
            else:
                p['service'] = ['any']

            action = _get(row, result.columns, 'Action')
            if action:
                p['action'] = action
            else:
                p['action'] = 'allow'

            log_end = _get(row, result.columns, 'Log End')
            if log_end:
                p['log_end'] = log_end.lower() == 'yes'

            disabled = _get(row, result.columns, 'Disabled')
            if disabled and disabled.lower() == 'yes':
                p['disabled'] = True

            if p.get('name'):
                payloads.append(p)
        return payloads


class NATRuleMapper(FeatureMapper):
    feature_name = 'SD-WAN NAT Policies'
    scm_endpoint = '/sse/config/v1/nat-rules'
    scm_resource_name = 'nat_rules'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        payloads = []
        # Skip plugin-level results that have 'Device Group' + 'NAT Rules' columns
        if result.columns and result.columns[0] == 'Device Group':
            return payloads
        for row in result.rows:
            p: dict[str, Any] = {
                'name': _get(row, result.columns, 'Rule Name'),
            }
            # SCM uses 'from'/'to' for zones, 'source'/'destination' for addresses
            src_zone = _get(row, result.columns, 'Source Zone')
            p['from'] = _split_list(src_zone) if src_zone else ['any']

            dst_zone = _get(row, result.columns, 'Dest Zone')
            p['to'] = _split_list(dst_zone) if dst_zone else ['any']

            # source and destination are required by SCM API
            src_addr = _get(row, result.columns, 'Source Address')
            p['source'] = _split_list(src_addr) if src_addr else ['any']

            dst_addr = _get(row, result.columns, 'Dest Address')
            p['destination'] = _split_list(dst_addr) if dst_addr else ['any']

            svc = _get(row, result.columns, 'Service')
            if svc:
                p['service'] = _split_list(svc)
            else:
                p['service'] = ['any']

            src_trans = _get(row, result.columns, 'Source Translation')
            if src_trans:
                p['source_translation'] = src_trans

            dst_trans = _get(row, result.columns, 'Dest Translation')
            if dst_trans:
                p['destination_translation'] = dst_trans

            disabled = _get(row, result.columns, 'Disabled')
            if disabled and disabled.lower() == 'yes':
                p['disabled'] = True

            if p.get('name'):
                payloads.append(p)
        return payloads


class IKEGatewayMapper(FeatureMapper):
    """Maps VPN Tunnel results (Type='IKE Gateway') to SCM IKE gateway objects."""
    feature_name = 'VPN/IPSec Tunnels'
    scm_endpoint = '/sse/config/v1/ike-gateways'
    scm_resource_name = 'ike_gateways'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        payloads = []
        for row in result.rows:
            row_type = _get(row, result.columns, 'Type')
            if row_type != 'IKE Gateway':
                continue
            p: dict[str, Any] = {
                'name': _get(row, result.columns, 'Name'),
            }
            peer_addr = _get(row, result.columns, 'Proxy ID')
            if peer_addr:
                p['peer_address'] = {'ip': peer_addr}

            disabled = _get(row, result.columns, 'Disabled')
            if disabled and disabled.lower() == 'yes':
                p['disabled'] = True

            if p.get('name'):
                payloads.append(p)
        return payloads


class IPSecTunnelMapper(FeatureMapper):
    """Maps VPN Tunnel results (Type='IPSec Tunnel') to SCM IPSec tunnel objects."""
    feature_name = 'VPN/IPSec Tunnels'
    scm_endpoint = '/sse/config/v1/ipsec-tunnels'
    scm_resource_name = 'ipsec_tunnels'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        payloads = []
        for row in result.rows:
            row_type = _get(row, result.columns, 'Type')
            if row_type != 'IPSec Tunnel':
                continue
            p: dict[str, Any] = {
                'name': _get(row, result.columns, 'Name'),
            }
            ike_gw = _get(row, result.columns, 'IKE Gateway')
            if ike_gw:
                p['auto_key'] = {'ike_gateway': [{'name': ike_gw}]}

            tunnel_if = _get(row, result.columns, 'Tunnel Interface')
            if tunnel_if:
                p['tunnel_interface'] = tunnel_if

            crypto = _get(row, result.columns, 'IPSec Crypto Profile')
            if crypto:
                p.setdefault('auto_key', {})['ipsec_crypto_profile'] = crypto

            tunnel_mon = _get(row, result.columns, 'Tunnel Monitor')
            if tunnel_mon and tunnel_mon.lower() not in ('', 'no', 'disabled'):
                p['tunnel_monitor'] = {'enable': True}

            disabled = _get(row, result.columns, 'Disabled')
            if disabled and disabled.lower() == 'yes':
                p['disabled'] = True

            if p.get('name'):
                payloads.append(p)
        return payloads


class BGPRoutingMapper(FeatureMapper):
    feature_name = 'Dynamic Routing'
    scm_endpoint = '/sdwan/v2.0/api/sdwanbgproutingprofiles'
    scm_resource_name = 'bgp_routing_profiles'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        payloads = []
        for row in result.rows:
            bgp_enabled = _get(row, result.columns, 'BGP Enabled')
            if bgp_enabled.lower() != 'yes':
                continue
            name = _get(row, result.columns, 'Router Name')
            p: dict[str, Any] = {
                'name': name,
            }
            router_id = _get(row, result.columns, 'BGP Router ID')
            if router_id:
                p['router_id'] = router_id

            bgp_as = _get(row, result.columns, 'BGP AS')
            if bgp_as:
                p['local_as'] = _to_int(bgp_as)

            ecmp = _get(row, result.columns, 'ECMP Enabled')
            if ecmp:
                p['ecmp_enabled'] = ecmp.lower() == 'yes'

            ecmp_max = _to_int(_get(row, result.columns, 'ECMP Max Path'))
            if ecmp_max is not None:
                p['ecmp_max_path'] = ecmp_max

            fast_failover = _get(row, result.columns, 'Fast External Failover')
            if fast_failover:
                p['fast_external_failover'] = fast_failover.lower() == 'yes'

            graceful = _get(row, result.columns, 'Graceful Restart')
            if graceful:
                p['graceful_restart'] = graceful.lower() == 'yes'

            stale = _to_int(_get(row, result.columns, 'Stale Route Time'))
            if stale is not None:
                p['stale_route_time'] = stale

            if p.get('name'):
                payloads.append(p)
        return payloads


class InterfaceMapper(FeatureMapper):
    feature_name = 'Sub/Agg Interfaces'
    scm_endpoint = '/sse/config/v1/interfaces'
    scm_resource_name = 'interfaces'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        payloads = []
        for row in result.rows:
            p: dict[str, Any] = {
                'name': _get(row, result.columns, 'Name'),
            }
            itype = _get(row, result.columns, 'Type')
            if itype:
                p['type'] = itype

            layer = _get(row, result.columns, 'Layer')
            if layer:
                p['layer'] = layer

            ip_addr = _get(row, result.columns, 'IP Address')
            if ip_addr and ip_addr.lower() != 'dhcp':
                p['ip_address'] = ip_addr
            elif ip_addr and ip_addr.lower() == 'dhcp':
                p['dhcp_client'] = True

            link_state = _get(row, result.columns, 'Link State')
            if link_state:
                p['link_state'] = link_state

            speed = _get(row, result.columns, 'Speed/Duplex')
            if speed:
                p['speed_duplex'] = speed

            agg = _get(row, result.columns, 'Aggregate Group')
            if agg:
                p['aggregate_group'] = agg

            sdwan_profile = _get(row, result.columns, 'SD-WAN Profile')
            if sdwan_profile:
                p['sdwan_link_settings'] = {
                    'sdwan_interface_profile': sdwan_profile,
                    'enable': _get(row, result.columns, 'SD-WAN Enabled', 'no'),
                }

            zone = _get(row, result.columns, 'Zone')
            if zone:
                p['zone'] = zone

            comment = _get(row, result.columns, 'Comment')
            if comment:
                p['comment'] = comment

            if p.get('name'):
                payloads.append(p)
        return payloads


class ZoneMapper(FeatureMapper):
    """Extracts unique zones from interface data and maps to SCM zone objects."""
    feature_name = 'Sub/Agg Interfaces'
    scm_endpoint = '/sse/config/v1/zones'
    scm_resource_name = 'zones'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        seen_zones: dict[str, list[str]] = {}
        for row in result.rows:
            zone = _get(row, result.columns, 'Zone')
            iface = _get(row, result.columns, 'Name')
            if zone and zone.strip():
                seen_zones.setdefault(zone, [])
                if iface:
                    seen_zones[zone].append(iface)

        payloads = []
        for zone_name, interfaces in sorted(seen_zones.items()):
            p: dict[str, Any] = {
                'name': zone_name,
            }
            if interfaces:
                p['network'] = {'layer3': interfaces}
            payloads.append(p)
        return payloads


class CustomApplicationMapper(FeatureMapper):
    feature_name = 'Custom Applications'
    scm_endpoint = '/sse/config/v1/application-filters'
    scm_resource_name = 'custom_applications'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        payloads = []
        for row in result.rows:
            p: dict[str, Any] = {
                'name': _get(row, result.columns, 'Application Name'),
            }
            cat = _get(row, result.columns, 'Category')
            if cat:
                p['category'] = cat

            subcat = _get(row, result.columns, 'Subcategory')
            if subcat:
                p['subcategory'] = subcat

            tech = _get(row, result.columns, 'Technology')
            if tech:
                p['technology'] = tech

            risk = _to_int(_get(row, result.columns, 'Risk'))
            if risk is not None:
                p['risk'] = risk

            if p.get('name'):
                payloads.append(p)
        return payloads


class VPNClusterMapper(FeatureMapper):
    """Maps VPN Automation results (cluster data) to SCM VPN cluster objects."""
    feature_name = 'VPN Automation'
    scm_endpoint = '/sdwan/v2.0/api/sdwanvpnclusters'
    scm_resource_name = 'sdwan_vpn_clusters'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        # Only process cluster results (identified by 'Cluster Name' column)
        if not result.columns or _col_index(result.columns, 'Cluster Name') < 0:
            return []
        payloads = []
        for row in result.rows:
            name = _get(row, result.columns, 'Cluster Name')
            if not name:
                continue
            p: dict[str, Any] = {'name': name}

            cluster_type = _get(row, result.columns, 'Type')
            if cluster_type:
                p['type'] = cluster_type

            hubs = _get(row, result.columns, 'Hubs')
            if hubs:
                p['hubs'] = _split_list(hubs)

            branches = _get(row, result.columns, 'Branches')
            if branches:
                p['branches'] = _split_list(branches)

            auth_type = _get(row, result.columns, 'Auth Type')
            if auth_type:
                p['authentication_type'] = auth_type

            pool = _get(row, result.columns, 'VPN Address Pool')
            if pool:
                p['vpn_address_pool'] = _split_list(pool)

            dia_failover = _get(row, result.columns, 'DIA VPN Failover')
            if dia_failover:
                p['dia_vpn_failover'] = dia_failover

            payloads.append(p)
        return payloads


class SDWANDeviceMapper(FeatureMapper):
    """Maps VPN Automation results (device data) to SCM SD-WAN device objects."""
    feature_name = 'VPN Automation'
    scm_endpoint = '/sdwan/v2.0/api/sdwandevices'
    scm_resource_name = 'sdwan_devices'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        # Only process device results (identified by 'Serial / Device' column)
        if not result.columns or _col_index(result.columns, 'Serial / Device') < 0:
            return []
        payloads = []
        for row in result.rows:
            serial = _get(row, result.columns, 'Serial / Device')
            if not serial:
                continue
            p: dict[str, Any] = {'name': serial}

            dev_type = _get(row, result.columns, 'Type')
            if dev_type:
                p['type'] = dev_type

            router_name = _get(row, result.columns, 'Router Name')
            if router_name:
                p['router_name'] = router_name

            site = _get(row, result.columns, 'Site')
            if site:
                p['site'] = site

            # BGP configuration
            bgp_config: dict[str, Any] = {}

            router_id = _get(row, result.columns, 'BGP Router ID')
            if router_id:
                bgp_config['router_id'] = router_id

            bgp_as = _get(row, result.columns, 'BGP AS')
            if bgp_as:
                bgp_config['as_number'] = _to_int(bgp_as)

            ipv4_enabled = _get(row, result.columns, 'BGP IPv4 Enabled')
            if ipv4_enabled:
                bgp_config['ipv4_bgp_enable'] = ipv4_enabled.lower() == 'yes'

            loopback = _get(row, result.columns, 'Loopback Address')
            if loopback:
                bgp_config['loopback_address'] = loopback

            prefix = _get(row, result.columns, 'Prefix Redistribute')
            if prefix:
                bgp_config['prefix_redistribute'] = _split_list(prefix)

            remove_private = _get(row, result.columns, 'Remove Private AS')
            if remove_private and remove_private.lower() == 'yes':
                bgp_config['remove_private_as'] = True

            remove_private_v6 = _get(row, result.columns, 'Remove Private AS IPv6')
            if remove_private_v6 and remove_private_v6.lower() == 'yes':
                bgp_config['remove_private_as_ipv6'] = True

            if bgp_config:
                p['bgp'] = bgp_config

            vpn_auth = _get(row, result.columns, 'VPN Auth')
            if vpn_auth:
                p['vpn_tunnel_authentication'] = vpn_auth

            multi_vr = _get(row, result.columns, 'Multi-VR Support')
            if multi_vr and multi_vr.lower() == 'yes':
                p['multi_vr_support'] = True

            payloads.append(p)
        return payloads


class BGPPolicyMapper(FeatureMapper):
    """Maps VPN Automation results (BGP policies) to SCM BGP policy objects."""
    feature_name = 'VPN Automation'
    scm_endpoint = '/sdwan/v2.0/api/sdwanbgppolicies'
    scm_resource_name = 'sdwan_bgp_policies'

    def to_scm_payloads(self, result: FeatureResult) -> list[dict]:
        # Only process BGP policy results (identified by 'Device Group' column)
        if not result.columns or _col_index(result.columns, 'Device Group') < 0:
            return []
        # Also skip NAT rule results that have 'Device Group' — check for 'BGP Security Rules'
        if _col_index(result.columns, 'BGP Security Rules') < 0:
            return []
        payloads = []
        for row in result.rows:
            dg = _get(row, result.columns, 'Device Group')
            if not dg:
                continue
            p: dict[str, Any] = {'name': dg}

            rules = _get(row, result.columns, 'BGP Security Rules')
            if rules:
                p['rules'] = _split_list(rules)

            payloads.append(p)
        return payloads


# ---------------------------------------------------------------------------
# Mapper registry
# ---------------------------------------------------------------------------

# All mapper instances, keyed by (feature_name, scm_resource_name)
# Using tuple key because VPN/IPSec Tunnels maps to two different endpoints.
_ALL_MAPPERS: list[FeatureMapper] = [
    InterfaceProfileMapper(),
    PathQualityMapper(),
    TrafficDistributionMapper(),
    SDWANPolicyMapper(),
    SecurityRuleMapper(),
    NATRuleMapper(),
    IKEGatewayMapper(),
    IPSecTunnelMapper(),
    BGPRoutingMapper(),
    InterfaceMapper(),
    ZoneMapper(),
    CustomApplicationMapper(),
    VPNClusterMapper(),
    SDWANDeviceMapper(),
    BGPPolicyMapper(),
]


def get_mappers() -> list[FeatureMapper]:
    """Return all registered feature mappers."""
    return list(_ALL_MAPPERS)


def get_mapper_for_feature(feature_name: str) -> list[FeatureMapper]:
    """Return all mappers matching a feature name (may be >1 for VPN tunnels)."""
    return [m for m in _ALL_MAPPERS if m.feature_name == feature_name]


def map_results(results: list[FeatureResult]) -> dict[str, dict]:
    """Map all FeatureResults to SCM payloads, grouped by scm_resource_name.

    Returns:
        {
            'sdwan_interface_profiles': {
                'endpoint': '/sdwan/v2.0/api/...',
                'id_field': 'name',
                'folder': 'Shared',
                'payloads': [ {name: ..., ...}, ... ],
            },
            ...
        }
    """
    output: dict[str, dict] = {}

    for result in results:
        if not result.enabled or not result.rows:
            continue
        mappers = get_mapper_for_feature(result.feature_name)
        for mapper in mappers:
            payloads = mapper.to_scm_payloads(result)
            if not payloads:
                continue
            key = mapper.scm_resource_name
            folder = detect_scm_folder(result.source)
            if key not in output:
                output[key] = {
                    'endpoint': mapper.scm_endpoint,
                    'id_field': mapper.get_id_field(),
                    'folder': folder,
                    'payloads': [],
                }
            # Deduplicate by name within same resource
            existing_names = {p.get('name') for p in output[key]['payloads']}
            for p in payloads:
                if p.get('name') not in existing_names:
                    output[key]['payloads'].append(p)
                    existing_names.add(p.get('name'))

    return output
