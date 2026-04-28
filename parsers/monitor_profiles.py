"""Network Monitor Profiles parser."""
from .base import BaseParser, FeatureResult

MONITOR_XPATH = './/network/profiles/monitor-profile/entry'


class MonitorProfilesParser(BaseParser):
    FEATURE_NAME = 'Monitor Profiles'
    SHEET_NAME = 'Monitor Profiles'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type in ('device-group', 'shared'):
                continue
            entries = self._find_all(c.xml_node, MONITOR_XPATH)

            columns = ['Profile Name', 'Interval (s)', 'Threshold', 'Action']

            def build_row(entry):
                return [
                    self._get_name(entry),
                    self._find_text(entry, 'interval'),
                    self._find_text(entry, 'threshold'),
                    self._find_text(entry, 'action'),
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
