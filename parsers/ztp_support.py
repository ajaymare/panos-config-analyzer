"""Zero Touch Provisioning (ZTP) parser."""
from .base import BaseParser, FeatureResult

ZTP_XPATH = './/plugins/ztp'


class ZTPSupportParser(BaseParser):
    FEATURE_NAME = 'ZTP Support'
    SHEET_NAME = 'ZTP Support'

    def extract(self, xml_root, containers):
        ztp = xml_root.find(ZTP_XPATH)

        if ztp is None:
            return [FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=False,
                summary='Not configured',
                source='Config',
            )]

        columns = ['Setting', 'Value']
        rows = []

        ztp_version = ztp.get('version', '')
        if ztp_version:
            rows.append(['ZTP Version', ztp_version])

        service_ztp = self._find_text(ztp, 'service-type-ztp', '')
        rows.append(['Service Type ZTP', service_ztp])

        panorama_server = self._find_text(ztp, 'panorama/panorama-server', '')
        if panorama_server:
            rows.append(['Panorama Server', panorama_server])

        ddns = self._find_text(ztp, 'service-type-ddns', '')
        rows.append(['DDNS Enabled', ddns])

        return [FeatureResult(
            feature_name=self.FEATURE_NAME,
            enabled=True,
            summary=f"ZTP v{ztp_version}" if ztp_version else 'ZTP configured',
            columns=columns,
            rows=rows,
            source='Panorama Plugins',
        )]
