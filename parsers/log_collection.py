"""Log Collection Configuration parser."""
from .base import BaseParser, FeatureResult

LOG_COLLECTOR_XPATH = './/log-collector/entry'
LOG_FWD_XPATH = 'log-settings/profiles/entry'


class LogCollectionParser(BaseParser):
    FEATURE_NAME = 'Log Collection'
    SHEET_NAME = 'Log Collection'

    def extract(self, xml_root, containers):
        results = []

        # Check Panorama log collectors
        collectors = self._find_all(xml_root, LOG_COLLECTOR_XPATH)
        if collectors:
            columns = ['Collector', 'Log Collection', 'Syslog Forwarding',
                        'Telemetry Forwarding', 'SNMP']
            rows = []
            for entry in collectors:
                rows.append([
                    self._get_name(entry),
                    'Disabled' if self._find_text(entry, 'disable-device-log-collection', 'no') == 'yes' else 'Enabled',
                    'Disabled' if self._find_text(entry, 'disable-syslog-forwarding', 'no') == 'yes' else 'Enabled',
                    'Disabled' if self._find_text(entry, 'disable-device-telemetry-forwarding', 'no') == 'yes' else 'Enabled',
                    'Disabled' if self._find_text(entry, 'disable-snmp', 'no') == 'yes' else 'Enabled',
                ])
            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=True,
                summary=f'{len(collectors)} log collectors',
                columns=columns, rows=rows,
                source='Panorama',
            ))

        # Check device-group log forwarding profiles
        for c in containers:
            if c.config_type in ('template', 'template-stack'):
                continue
            entries = self._find_all(c.xml_node, LOG_FWD_XPATH)
            if entries:
                columns = ['Profile Name', 'Match List Entries']
                rows = []
                for entry in entries:
                    match_list = self._find_all(entry, 'match-list/entry')
                    rows.append([
                        self._get_name(entry),
                        str(len(match_list)),
                    ])
                results.append(FeatureResult(
                    feature_name=self.FEATURE_NAME,
                    enabled=True,
                    summary=f'{len(entries)} forwarding profiles',
                    columns=columns, rows=rows,
                    source=c.name,
                ))

        if not results:
            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=False,
                summary='Not configured',
                source='Config',
            ))
        return results
