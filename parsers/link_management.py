"""Link Management (SD-WAN link settings on interfaces) parser."""
from .base import BaseParser, FeatureResult

# SD-WAN link settings are on interfaces in templates
# template/entry/config/devices/entry/network/interface/ethernet/entry/layer3/sdwan-link-settings
INTF_XPATH = './/network/interface/ethernet/entry'


class LinkManagementParser(BaseParser):
    FEATURE_NAME = 'Link Management'
    SHEET_NAME = 'Link Management'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue

            entries = self._find_all(c.xml_node, INTF_XPATH)

            columns = ['Interface', 'SD-WAN Enabled', 'SD-WAN Profile',
                        'Upstream NAT', 'IPv6 Enabled', 'SD-WAN Gateway',
                        'IP Address']

            rows = []
            for entry in entries:
                sdwan = entry.find('layer3/sdwan-link-settings')
                if sdwan is None:
                    continue
                enabled = self._find_text(sdwan, 'enable', 'no')
                profile = self._find_text(sdwan, 'sdwan-interface-profile')
                upstream_nat = self._find_text(sdwan, 'upstream-nat/enable', 'no')
                ipv6 = self._find_text(sdwan, 'ipv6-enable', 'no')

                # Get IP and gateway from layer3/ip
                ip_entry = entry.find('layer3/ip/entry')
                ip_addr = self._get_name(ip_entry) if ip_entry is not None else ''
                gateway = self._find_text(ip_entry, 'sdwan-gateway') if ip_entry is not None else ''

                rows.append([
                    self._get_name(entry),
                    enabled,
                    profile,
                    upstream_nat,
                    ipv6,
                    gateway,
                    ip_addr,
                ])

            if rows:
                intf_names = [r[0] for r in rows if r and r[0]]
                summary = f"{c.name}: {', '.join(intf_names)}"
            else:
                summary = "Not configured"
            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=len(rows) > 0,
                summary=summary,
                columns=columns,
                rows=rows,
                source=c.name,
            ))
        return results
