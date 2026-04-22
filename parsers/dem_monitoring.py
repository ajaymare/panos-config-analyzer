"""Digital Experience Monitoring (DEM) parser."""
from .base import BaseParser, FeatureResult

# DEM config could be under plugins/sd_wan or device-group profiles
PLUGIN_DEM_XPATH = './/plugins/sd_wan/dem/entry'
DG_DEM_XPATH = 'profiles/sdwan-dem/entry'
ADEM_XPATH = './/plugins/sd_wan/autonomous-dem'


class DEMMonitoringParser(BaseParser):
    FEATURE_NAME = 'Digital Experience Monitoring'
    SHEET_NAME = 'DEM'

    def extract(self, xml_root, containers):
        # Check plugins section from xml_root
        entries = self._find_all(xml_root, PLUGIN_DEM_XPATH)
        adem = xml_root.find(ADEM_XPATH)

        # Also check device-group profiles
        for c in containers:
            if c.config_type == 'device-group':
                dg_entries = self._find_all(c.xml_node, DG_DEM_XPATH)
                entries.extend(dg_entries)

        columns = ['Name', 'Target', 'Probe Type', 'Probe Interval',
                    'Threshold', 'Autonomous DEM']

        rows = []
        for entry in entries:
            rows.append([
                self._get_name(entry),
                self._find_text(entry, 'target'),
                self._find_text(entry, 'probe-type'),
                self._find_text(entry, 'probe-interval'),
                self._find_text(entry, 'threshold'),
                'Enabled' if adem is not None else 'Disabled',
            ])

        return [FeatureResult(
            feature_name=self.FEATURE_NAME,
            enabled=len(rows) > 0,
            summary=f"{len(rows)} configured" if rows else "Not configured",
            columns=columns,
            rows=rows,
            source='Config',
        )]
