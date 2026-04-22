"""SD-WAN Interface Profiles parser."""
from .base import BaseParser, FeatureResult

# XPaths for SD-WAN interface profiles
NGFW_XPATH = './/devices/entry/plugins/sd_wan/sd-wan-interface-profile/entry'
TMPL_XPATH = './/template/entry/config/devices/entry/plugins/sd_wan/sd-wan-interface-profile/entry'
STACK_XPATH = './/template-stack/entry/config/devices/entry/plugins/sd_wan/sd-wan-interface-profile/entry'


class SDWANInterfaceProfilesParser(BaseParser):
    FEATURE_NAME = 'SD-WAN Interface Profiles'
    SHEET_NAME = 'Interface Profiles'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue
            xpaths = {
                'ngfw': [NGFW_XPATH],
                'template': [TMPL_XPATH, NGFW_XPATH],
                'template-stack': [STACK_XPATH, NGFW_XPATH],
                'shared': [],
            }
            entries = []
            for xp in xpaths.get(c.config_type, [NGFW_XPATH]):
                entries = self._find_all(c.xml_node, xp)
                if entries:
                    break

            columns = ['Name', 'Link Type', 'Link Tag', 'Max Upload (Mbps)',
                        'Max Download (Mbps)', 'Path Monitor IP', 'Monitor Interval', 'Probe Frequency']

            def build_row(entry):
                return [
                    self._get_name(entry),
                    self._find_text(entry, 'link-type'),
                    self._find_text(entry, 'link-tag'),
                    self._find_text(entry, 'vpn-data-tunnel-bw/upload'),
                    self._find_text(entry, 'vpn-data-tunnel-bw/download'),
                    self._find_text(entry, 'path-monitor/ip-address'),
                    self._find_text(entry, 'path-monitor/monitor-interval'),
                    self._find_text(entry, 'path-monitor/probe-frequency'),
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
