"""Digital Experience Monitoring (DEM) parser."""
from .base import BaseParser, FeatureResult

NGFW_XPATH = './/devices/entry/plugins/sd_wan/dem/entry'
TMPL_XPATH = './/template/entry/config/devices/entry/plugins/sd_wan/dem/entry'
# Also check autonomous DEM config
ADEM_XPATH = './/devices/entry/plugins/sd_wan/autonomous-dem'
TMPL_ADEM = './/template/entry/config/devices/entry/plugins/sd_wan/autonomous-dem'


class DEMMonitoringParser(BaseParser):
    FEATURE_NAME = 'Digital Experience Monitoring'
    SHEET_NAME = 'DEM'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue
            entries = self._find_all(c.xml_node, TMPL_XPATH) or self._find_all(c.xml_node, NGFW_XPATH)
            adem = c.xml_node.find(TMPL_ADEM)
            if adem is None:
                adem = c.xml_node.find(ADEM_XPATH)

            columns = ['Name', 'Target', 'Probe Type', 'Probe Interval',
                        'Threshold', 'Autonomous DEM']

            def build_row(entry):
                return [
                    self._get_name(entry),
                    self._find_text(entry, 'target'),
                    self._find_text(entry, 'probe-type'),
                    self._find_text(entry, 'probe-interval'),
                    self._find_text(entry, 'threshold'),
                    'Enabled' if adem is not None else 'Disabled',
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
