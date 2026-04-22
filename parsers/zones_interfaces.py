"""Zones and Interfaces parser — all interface types."""
from .base import BaseParser, FeatureResult

# Interface and zone paths (work from both template config nodes and NGFW root)
_NET = './/network/interface'

INTF_TYPES = [
    ('ethernet', 'Ethernet'),
    ('aggregate-ethernet', 'Aggregate Ethernet'),
    ('loopback/units', 'Loopback'),
    ('tunnel/units', 'Tunnel'),
    ('vlan/units', 'VLAN'),
    ('cellular', 'Cellular'),
]

ZONE_XPATH = './/vsys/entry/zone/entry'


class ZonesInterfacesParser(BaseParser):
    FEATURE_NAME = 'Zones and Interfaces'
    SHEET_NAME = 'Zones Interfaces'

    def _parse_interface(self, entry, intf_type_label, parent_name=''):
        """Parse a single interface entry into row data."""
        name = self._get_name(entry)
        if parent_name:
            name = f"{parent_name}.{name}" if not name.startswith(parent_name) else name

        # Get IP — could be under layer3/ip, ip, or various sub-paths
        ip_addr = ''
        for ip_path in ('layer3/ip/entry', 'ip/entry', './/ip/entry'):
            ip_el = entry.find(ip_path)
            if ip_el is not None:
                ip_addr = self._get_name(ip_el)
                break

        # DHCP check
        if not ip_addr:
            dhcp = entry.find('layer3/dhcp-client') or entry.find('dhcp-client')
            if dhcp is not None:
                ip_addr = 'DHCP'

        # Link state
        link_state = self._find_text(entry, 'link-state', 'auto')

        # Link speed/duplex
        link_speed = self._find_text(entry, 'link-speed', 'auto')
        link_duplex = self._find_text(entry, 'link-duplex', 'auto')

        # Layer type
        layer = ''
        for l in ('layer3', 'layer2', 'virtual-wire', 'tap', 'ha', 'decrypt-mirror', 'aggregate-group'):
            if entry.find(l) is not None:
                layer = l
                break
        if not layer and entry.find('.//layer3') is not None:
            layer = 'layer3'

        # Aggregate group (for member interfaces)
        agg_group = self._find_text(entry, 'aggregate-group')

        # SD-WAN interface profile
        sdwan_profile = self._find_text(entry, './/sdwan-link-settings/sdwan-interface-profile')

        # SD-WAN enabled
        sdwan_enabled = self._find_text(entry, './/sdwan-link-settings/enable', '')

        # Interface management profile
        mgmt_profile = self._find_text(entry, './/interface-management-profile')

        # Comment
        comment = self._find_text(entry, 'comment')

        return [name, intf_type_label, layer, ip_addr, link_state,
                f"{link_speed}/{link_duplex}", agg_group, sdwan_profile,
                sdwan_enabled, mgmt_profile, comment]

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue

            rows = []
            counts = {}

            # Zones
            zones = self._find_all(c.xml_node, ZONE_XPATH)
            zone_map = {}  # interface -> zone name
            for z in zones:
                zname = self._get_name(z)
                for net_type in ('layer3', 'tap', 'virtual-wire', 'tunnel', 'layer2'):
                    for m in self._find_all(z, f'network/{net_type}/member'):
                        if m.text:
                            zone_map[m.text] = zname

            # Scan all interface types
            for intf_path, intf_label in INTF_TYPES:
                entries = self._find_all(c.xml_node, f'{_NET}/{intf_path}/entry')

                for entry in entries:
                    row = self._parse_interface(entry, intf_label)
                    intf_name = row[0]
                    rows.append(row + [zone_map.get(intf_name, '')])

                    # Sub-interfaces
                    for sub_path in ('layer3/units/entry', 'units/entry'):
                        sub_intfs = self._find_all(entry, sub_path)
                        for sub in sub_intfs:
                            sub_row = self._parse_interface(sub, f'{intf_label} (sub)', intf_name)
                            sub_name = sub_row[0]
                            sub_row[2] = 'layer3 (sub-interface)'
                            rows.append(sub_row + [zone_map.get(sub_name, '')])

                counts[intf_label] = len(entries)

            columns = ['Name', 'Type', 'Layer', 'IP Address', 'Link State',
                       'Speed/Duplex', 'Aggregate Group', 'SD-WAN Profile',
                       'SD-WAN Enabled', 'Mgmt Profile', 'Comment', 'Zone']

            # Build summary
            parts = []
            for label, count in counts.items():
                if count > 0:
                    parts.append(f"{count} {label.lower()}")
            if zones:
                parts.append(f"{len(zones)} zones")
            summary = ', '.join(parts) if parts else 'Not configured'

            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=len(rows) > 0,
                summary=summary,
                columns=columns,
                rows=rows,
                source=c.name,
            ))
        return results
