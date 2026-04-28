"""SD-WAN Ad-Hoc Reports parser."""
from .base import BaseParser, FeatureResult

REPORT_XPATH = './/plugins/sd_wan/ad-hoc-report/entry'


class SDWANReportsParser(BaseParser):
    FEATURE_NAME = 'SD-WAN Reporting'
    SHEET_NAME = 'SD-WAN Reports'

    def extract(self, xml_root, containers):
        entries = self._find_all(xml_root, REPORT_XPATH)

        if not entries:
            return [FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=False,
                summary='Not configured',
                source='Panorama Plugins',
            )]

        columns = ['Report Name', 'Report Type', 'Cluster', 'Site',
                    'Application', 'Link Tag', 'Top N', 'Time Period']
        rows = []
        for entry in entries:
            rows.append([
                self._get_name(entry),
                self._find_text(entry, 'report-type'),
                self._find_text(entry, 'cluster'),
                self._find_text(entry, 'site'),
                self._find_text(entry, 'application'),
                self._find_text(entry, 'link-tag'),
                self._find_text(entry, 'topn'),
                self._find_text(entry, 'time-period'),
            ])

        return [FeatureResult(
            feature_name=self.FEATURE_NAME,
            enabled=True,
            summary=f'{len(rows)} reports configured',
            columns=columns, rows=rows,
            source='Panorama Plugins',
        )]
