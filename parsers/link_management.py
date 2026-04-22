"""Link Management (tags, monitoring, probes) parser."""
from .base import BaseParser, FeatureResult

NGFW_XPATH = './/devices/entry/plugins/sd_wan/sd-wan-interface-profile/entry'
TMPL_XPATH = './/template/entry/config/devices/entry/plugins/sd_wan/sd-wan-interface-profile/entry'


class LinkManagementParser(BaseParser):
    FEATURE_NAME = 'Link Management'
    SHEET_NAME = 'Link Management'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue
            entries = self._find_all(c.xml_node, TMPL_XPATH) or self._find_all(c.xml_node, NGFW_XPATH)

            columns = ['Interface Profile', 'Link Type', 'Link Tag', 'ISP Name',
                        'Monitor Enabled', 'Monitor IP', 'Probe Interval (s)',
                        'Failover Threshold', 'Recovery Threshold']

            def build_row(entry):
                pm = entry.find('path-monitor')
                return [
                    self._get_name(entry),
                    self._find_text(entry, 'link-type'),
                    self._find_text(entry, 'link-tag'),
                    self._find_text(entry, 'isp'),
                    'yes' if pm is not None else 'no',
                    self._find_text(pm, 'ip-address') if pm is not None else '',
                    self._find_text(pm, 'monitor-interval') if pm is not None else '',
                    self._find_text(pm, 'failover-threshold') if pm is not None else '',
                    self._find_text(pm, 'recovery-threshold') if pm is not None else '',
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
