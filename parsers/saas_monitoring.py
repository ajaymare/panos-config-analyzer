"""SaaS Quality Monitoring parser."""
from .base import BaseParser, FeatureResult

NGFW_XPATH = './/devices/entry/plugins/sd_wan/saas-quality/monitor/entry'
TMPL_XPATH = './/template/entry/config/devices/entry/plugins/sd_wan/saas-quality/monitor/entry'


class SaaSMonitoringParser(BaseParser):
    FEATURE_NAME = 'SaaS Quality Monitoring'
    SHEET_NAME = 'SaaS Monitoring'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue
            entries = self._find_all(c.xml_node, TMPL_XPATH) or self._find_all(c.xml_node, NGFW_XPATH)

            columns = ['Name', 'Application', 'Probe URL', 'Probe Frequency',
                        'Latency Threshold (ms)', 'Jitter Threshold (ms)',
                        'Packet Loss Threshold (%)']

            def build_row(entry):
                return [
                    self._get_name(entry),
                    self._find_text(entry, 'application'),
                    self._find_text(entry, 'probe-url'),
                    self._find_text(entry, 'probe-frequency'),
                    self._find_text(entry, 'threshold/latency'),
                    self._find_text(entry, 'threshold/jitter'),
                    self._find_text(entry, 'threshold/packet-loss'),
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
