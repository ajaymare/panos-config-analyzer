"""Zones and Interfaces parser (SD-WAN relevant)."""
from .base import BaseParser, FeatureResult

ZONE_XPATH = './/vsys/entry/zone/entry'
TMPL_ZONE = './/template/entry/config/devices/entry/vsys/entry/zone/entry'
ETH_XPATH = './/devices/entry/network/interface/ethernet/entry'
TMPL_ETH = './/template/entry/config/devices/entry/network/interface/ethernet/entry'
TUNNEL_XPATH = './/devices/entry/network/interface/tunnel/units/entry'
TMPL_TUNNEL = './/template/entry/config/devices/entry/network/interface/tunnel/units/entry'


class ZonesInterfacesParser(BaseParser):
    FEATURE_NAME = 'Zones & Interfaces'
    SHEET_NAME = 'Zones Interfaces'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue

            zones = self._find_all(c.xml_node, TMPL_ZONE) or self._find_all(c.xml_node, ZONE_XPATH)
            eth_intfs = self._find_all(c.xml_node, TMPL_ETH) or self._find_all(c.xml_node, ETH_XPATH)
            tunnels = self._find_all(c.xml_node, TMPL_TUNNEL) or self._find_all(c.xml_node, TUNNEL_XPATH)

            columns = ['Name', 'Type', 'Zone', 'IP Address', 'Virtual Router', 'Comment']

            rows = []
            # Zone summary
            for z in zones:
                members = []
                for net_type in ('layer3', 'tap', 'virtual-wire', 'tunnel'):
                    mems = self._find_all(z, f'network/{net_type}/member')
                    members.extend(m.text for m in mems if m.text)
                rows.append([
                    self._get_name(z),
                    'Zone',
                    '',
                    '',
                    '',
                    f"Members: {', '.join(members)}" if members else '',
                ])

            for eth in eth_intfs:
                ip_el = eth.find('.//ip/entry')
                ip_addr = self._get_name(ip_el) if ip_el is not None else ''
                rows.append([
                    self._get_name(eth),
                    'Ethernet',
                    '',
                    ip_addr,
                    self._find_text(eth, './/virtual-router'),
                    self._find_text(eth, 'comment'),
                ])

            for tun in tunnels:
                ip_el = tun.find('ip/entry')
                ip_addr = self._get_name(ip_el) if ip_el is not None else ''
                rows.append([
                    self._get_name(tun),
                    'Tunnel',
                    '',
                    ip_addr,
                    self._find_text(tun, 'virtual-router'),
                    self._find_text(tun, 'comment'),
                ])

            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=len(rows) > 0,
                summary=f"{len(zones)} zones, {len(eth_intfs)} ethernet, {len(tunnels)} tunnels" if rows else "Not configured",
                columns=columns, rows=rows, source=c.name,
            ))
        return results
