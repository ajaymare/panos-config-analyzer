"""PAN-OS XML element builders for SD-WAN POC configuration.

Each function returns a dict with 'xpath' and 'element' keys suitable for
paloaltonetworks.panos.panos_config_element Ansible module.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET


def _to_xml_str(elem: ET.Element) -> str:
    """Serialize an ElementTree element to a compact XML string."""
    return ET.tostring(elem, encoding='unicode', short_empty_elements=True)


# ---------------------------------------------------------------------------
# SD-WAN Interface Profiles (template-level)
# ---------------------------------------------------------------------------

def sdwan_interface_profile(
    name: str,
    link_type: str = 'public',
    link_tag: str = '',
    bandwidth_up: int = 100,
    bandwidth_down: int = 100,
    probe_frequency: int = 5,
    probe_idle_time: int = 60,
    failback_hold_time: int = 120,
    path_monitoring: str = 'aggressive',
    template_name: str = 'POC-Template',
) -> dict:
    xpath = (
        f"/config/devices/entry[@name='localhost.localdomain']"
        f"/template/entry[@name='{template_name}']"
        f"/config/devices/entry[@name='localhost.localdomain']"
        f"/vsys/entry[@name='vsys1']"
        f"/sdwan-interface-profile"
    )

    entry = ET.Element('entry', name=name)
    ET.SubElement(entry, 'link-type').text = link_type
    if link_tag:
        ET.SubElement(entry, 'link-tag').text = link_tag
    ET.SubElement(entry, 'path-monitoring').text = path_monitoring
    ET.SubElement(entry, 'probe-frequency').text = str(probe_frequency)
    ET.SubElement(entry, 'probe-idle-time').text = str(probe_idle_time)
    ET.SubElement(entry, 'failback-hold-time').text = str(failback_hold_time)
    ET.SubElement(entry, 'maximum-upload').text = str(bandwidth_up)
    ET.SubElement(entry, 'maximum-download').text = str(bandwidth_down)

    return {'xpath': xpath, 'element': _to_xml_str(entry)}


# ---------------------------------------------------------------------------
# Path Quality Profiles (device-group level)
# ---------------------------------------------------------------------------

def path_quality_profile(
    name: str,
    latency_threshold: int = 100,
    latency_sensitivity: str = 'medium',
    jitter_threshold: int = 50,
    jitter_sensitivity: str = 'medium',
    pkt_loss_threshold: float = 5.0,
    pkt_loss_sensitivity: str = 'medium',
    device_group: str = 'POC-DeviceGroup',
) -> dict:
    xpath = (
        f"/config/devices/entry[@name='localhost.localdomain']"
        f"/device-group/entry[@name='{device_group}']"
        f"/profiles/sdwan-path-quality"
    )

    entry = ET.Element('entry', name=name)
    metric = ET.SubElement(entry, 'metric')

    latency = ET.SubElement(metric, 'latency')
    ET.SubElement(latency, 'threshold').text = str(latency_threshold)
    ET.SubElement(latency, 'sensitivity').text = latency_sensitivity

    jitter = ET.SubElement(metric, 'jitter')
    ET.SubElement(jitter, 'threshold').text = str(jitter_threshold)
    ET.SubElement(jitter, 'sensitivity').text = jitter_sensitivity

    pkt_loss = ET.SubElement(metric, 'pkt-loss')
    ET.SubElement(pkt_loss, 'threshold').text = str(int(pkt_loss_threshold))
    ET.SubElement(pkt_loss, 'sensitivity').text = pkt_loss_sensitivity

    return {'xpath': xpath, 'element': _to_xml_str(entry)}


# ---------------------------------------------------------------------------
# Traffic Distribution Profiles (device-group level)
# ---------------------------------------------------------------------------

def traffic_distribution_profile(
    name: str,
    method: str = 'best-available-path',
    link_tags: list[str] | None = None,
    fec_enabled: bool = False,
    device_group: str = 'POC-DeviceGroup',
) -> dict:
    xpath = (
        f"/config/devices/entry[@name='localhost.localdomain']"
        f"/device-group/entry[@name='{device_group}']"
        f"/profiles/sdwan-traffic-distribution"
    )

    entry = ET.Element('entry', name=name)
    ET.SubElement(entry, 'traffic-distribution').text = method

    if link_tags:
        tags_elem = ET.SubElement(entry, 'link-tags')
        for tag in link_tags:
            ET.SubElement(tags_elem, 'entry', name=tag)

    if fec_enabled:
        ec = ET.SubElement(entry, 'error-correction')
        ET.SubElement(ec, 'enable').text = 'yes'

    return {'xpath': xpath, 'element': _to_xml_str(entry)}


# ---------------------------------------------------------------------------
# VPN Cluster (Panorama plugins level)
# ---------------------------------------------------------------------------

def vpn_address_pool(members: list[str]) -> dict:
    """Build VPN address pool config."""
    xpath = "/config/plugins/sd_wan/vpn-address-pool"

    pool = ET.Element('vpn-address-pool')
    for m in members:
        ET.SubElement(pool, 'member').text = m

    return {'xpath': xpath, 'element': _to_xml_str(pool)}


def vpn_cluster(
    name: str,
    cluster_type: str = 'hub-spoke',
    hubs: list[dict] | None = None,
    branches: list[dict] | None = None,
) -> dict:
    """Build VPN cluster config.

    hubs/branches: list of dicts with keys 'name' and optional 'priority'.
    """
    xpath = "/config/plugins/sd_wan/vpn-cluster"

    entry = ET.Element('entry', name=name)
    ET.SubElement(entry, 'type').text = cluster_type
    ET.SubElement(entry, 'authentication_type').text = 'pre-shared-key'

    if hubs:
        hubs_elem = ET.SubElement(entry, 'hubs')
        for hub in hubs:
            h = ET.SubElement(hubs_elem, 'entry', name=hub['name'])
            ET.SubElement(h, 'priority').text = str(hub.get('priority', 1))
            ET.SubElement(h, 'allow-dia-vpn-failover').text = 'yes'

    if branches:
        branches_elem = ET.SubElement(entry, 'branches')
        for branch in branches:
            ET.SubElement(branches_elem, 'entry', name=branch['name'])

    return {'xpath': xpath, 'element': _to_xml_str(entry)}


# ---------------------------------------------------------------------------
# SD-WAN Device (Panorama plugins level)
# ---------------------------------------------------------------------------

def sdwan_device(
    serial: str,
    device_type: str = 'branch',
    router_name: str = '',
    site: str = '',
    bgp_router_id: str = '',
    bgp_as_number: str = '65000',
    bgp_enabled: bool = True,
    loopback_address: str = '',
) -> dict:
    xpath = "/config/plugins/sd_wan/devices"

    entry = ET.Element('entry', name=serial)
    ET.SubElement(entry, 'type').text = device_type
    if router_name:
        ET.SubElement(entry, 'router-name').text = router_name
    if site:
        ET.SubElement(entry, 'site').text = site

    bgp = ET.SubElement(entry, 'bgp')
    ET.SubElement(bgp, 'ipv4-bgp-enable').text = 'yes' if bgp_enabled else 'no'
    if bgp_router_id:
        ET.SubElement(bgp, 'router-id').text = bgp_router_id
    if bgp_as_number:
        ET.SubElement(bgp, 'as-number').text = str(bgp_as_number)
    if loopback_address:
        ET.SubElement(bgp, 'loopback-address').text = loopback_address

    return {'xpath': xpath, 'element': _to_xml_str(entry)}


# ---------------------------------------------------------------------------
# SD-WAN Policy Rules (device-group level)
# ---------------------------------------------------------------------------

def sdwan_policy_rule(
    name: str,
    applications: list[str] | None = None,
    src_zones: list[str] | None = None,
    dst_zones: list[str] | None = None,
    path_quality_profile: str = '',
    traffic_distribution_profile: str = '',
    device_group: str = 'POC-DeviceGroup',
) -> dict:
    xpath = (
        f"/config/devices/entry[@name='localhost.localdomain']"
        f"/device-group/entry[@name='{device_group}']"
        f"/pre-rulebase/sdwan/rules"
    )

    entry = ET.Element('entry', name=name)

    # Source zones
    from_elem = ET.SubElement(entry, 'from')
    for z in (src_zones or ['trust']):
        ET.SubElement(from_elem, 'member').text = z

    # Destination zones
    to_elem = ET.SubElement(entry, 'to')
    for z in (dst_zones or ['untrust']):
        ET.SubElement(to_elem, 'member').text = z

    # Applications
    app_elem = ET.SubElement(entry, 'application')
    for app in (applications or ['any']):
        ET.SubElement(app_elem, 'member').text = app

    # Service
    svc_elem = ET.SubElement(entry, 'service')
    ET.SubElement(svc_elem, 'member').text = 'any'

    if path_quality_profile:
        ET.SubElement(entry, 'path-quality-profile').text = path_quality_profile
    if traffic_distribution_profile:
        action = ET.SubElement(entry, 'action')
        ET.SubElement(action, 'traffic-distribution-profile').text = traffic_distribution_profile

    ET.SubElement(entry, 'disabled').text = 'no'

    return {'xpath': xpath, 'element': _to_xml_str(entry)}


# ---------------------------------------------------------------------------
# Security Zones (template-level, vsys)
# ---------------------------------------------------------------------------

def security_zone(
    name: str,
    zone_type: str = 'layer3',
    template_name: str = 'POC-Template',
) -> dict:
    """Build a security zone config element."""
    xpath = (
        f"/config/devices/entry[@name='localhost.localdomain']"
        f"/template/entry[@name='{template_name}']"
        f"/config/devices/entry[@name='localhost.localdomain']"
        f"/vsys/entry[@name='vsys1']"
        f"/zone"
    )

    entry = ET.Element('entry', name=name)
    network = ET.SubElement(entry, 'network')
    ET.SubElement(network, zone_type)

    return {'xpath': xpath, 'element': _to_xml_str(entry)}


# ---------------------------------------------------------------------------
# BGP Routing on Virtual Router (template level)
# ---------------------------------------------------------------------------

def bgp_routing(
    vr_name: str = 'default',
    router_id: str = '10.0.0.1',
    local_as: str = '65000',
    enabled: bool = True,
    template_name: str = 'POC-Template',
) -> dict:
    xpath = (
        f"/config/devices/entry[@name='localhost.localdomain']"
        f"/template/entry[@name='{template_name}']"
        f"/config/devices/entry[@name='localhost.localdomain']"
        f"/network/virtual-router/entry[@name='{vr_name}']"
        f"/protocol"
    )

    bgp = ET.Element('bgp')
    ET.SubElement(bgp, 'enable').text = 'yes' if enabled else 'no'
    ET.SubElement(bgp, 'router-id').text = router_id
    ET.SubElement(bgp, 'local-as').text = str(local_as)

    gr = ET.SubElement(bgp, 'graceful-restart')
    ET.SubElement(gr, 'enable').text = 'yes'
    ET.SubElement(gr, 'stale-route-time').text = '120'

    return {'xpath': xpath, 'element': _to_xml_str(bgp)}
