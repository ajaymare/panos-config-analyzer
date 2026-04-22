"""Path Quality Profiles parser."""
from .base import BaseParser, FeatureResult

# In device-groups: profiles/sdwan-path-quality/entry
# In shared: profiles/sdwan-path-quality/entry
DG_XPATH = 'profiles/sdwan-path-quality/entry'
SHARED_XPATH = 'profiles/sdwan-path-quality/entry'
# In NGFW (standalone): devices/entry/vsys/entry — unlikely but check
NGFW_XPATH = './/vsys/entry/profiles/sdwan-path-quality/entry'


class PathQualityProfilesParser(BaseParser):
    FEATURE_NAME = 'Path Quality Profiles'
    SHEET_NAME = 'Path Quality'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type in ('template', 'template-stack'):
                continue  # These profiles live in device-groups and shared, not templates
            entries = []
            if c.config_type == 'device-group':
                entries = self._find_all(c.xml_node, DG_XPATH)
            elif c.config_type == 'shared':
                entries = self._find_all(c.xml_node, SHARED_XPATH)
            else:
                entries = self._find_all(c.xml_node, NGFW_XPATH)

            columns = ['Name', 'Latency Threshold (ms)', 'Latency Sensitivity',
                        'Jitter Threshold (ms)', 'Jitter Sensitivity',
                        'Packet Loss Threshold (%)', 'Packet Loss Sensitivity']

            def build_row(entry):
                return [
                    self._get_name(entry),
                    self._find_text(entry, 'metric/latency/threshold'),
                    self._find_text(entry, 'metric/latency/sensitivity'),
                    self._find_text(entry, 'metric/jitter/threshold'),
                    self._find_text(entry, 'metric/jitter/sensitivity'),
                    self._find_text(entry, 'metric/pkt-loss/threshold'),
                    self._find_text(entry, 'metric/pkt-loss/sensitivity'),
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
