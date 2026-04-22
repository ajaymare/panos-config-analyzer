"""Path Quality Profiles parser."""
from .base import BaseParser, FeatureResult

NGFW_XPATH = './/devices/entry/plugins/sd_wan/path-quality-profile/entry'
TMPL_XPATH = './/template/entry/config/devices/entry/plugins/sd_wan/path-quality-profile/entry'


class PathQualityProfilesParser(BaseParser):
    FEATURE_NAME = 'Path Quality Profiles'
    SHEET_NAME = 'Path Quality'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue
            entries = self._find_all(c.xml_node, TMPL_XPATH) or self._find_all(c.xml_node, NGFW_XPATH)

            columns = ['Name', 'Latency (ms)', 'Jitter (ms)', 'Packet Loss (%)',
                        'Traffic Class', 'Sensitivity']

            def build_row(entry):
                # Path quality profiles have per-class thresholds
                sla = entry.find('metric/sla')
                latency = jitter = loss = ''
                if sla is not None:
                    latency = self._find_text(sla, 'latency')
                    jitter = self._find_text(sla, 'jitter')
                    loss = self._find_text(sla, 'packet-loss')
                return [
                    self._get_name(entry),
                    latency,
                    jitter,
                    loss,
                    self._find_text(entry, 'traffic-class'),
                    self._find_text(entry, 'sensitivity'),
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
