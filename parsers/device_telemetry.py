"""Device Telemetry and System Settings parser."""
from .base import BaseParser, FeatureResult

SYSTEM_XPATH = './/deviceconfig/system'
SETTING_XPATH = './/deviceconfig/setting'


class DeviceTelemetryParser(BaseParser):
    FEATURE_NAME = 'Device Telemetry'
    SHEET_NAME = 'Device Telemetry'

    def extract(self, xml_root, containers):
        results = []

        for c in containers:
            if c.config_type in ('device-group', 'shared'):
                continue

            system = c.xml_node.find(SYSTEM_XPATH)
            setting = c.xml_node.find(SETTING_XPATH)

            if system is None and setting is None:
                results.append(FeatureResult(
                    feature_name=self.FEATURE_NAME,
                    enabled=False,
                    summary='Not configured',
                    source=c.name,
                ))
                continue

            columns = ['Setting', 'Value']
            rows = []

            if system is not None:
                telemetry = system.find('device-telemetry')
                if telemetry is not None:
                    rows.append(['Health Performance', self._find_text(telemetry, 'device-health-performance', 'no')])
                    rows.append(['Product Usage', self._find_text(telemetry, 'product-usage', 'no')])
                    rows.append(['Threat Prevention', self._find_text(telemetry, 'threat-prevention', 'no')])
                    rows.append(['Region', self._find_text(telemetry, 'region')])

                dns = system.find('dns-setting/servers')
                if dns is not None:
                    primary = self._find_text(dns, 'primary')
                    if primary:
                        rows.append(['DNS Primary', primary])

                ntp = system.find('ntp-servers/primary-ntp-server')
                if ntp is not None:
                    rows.append(['NTP Server', self._find_text(ntp, 'ntp-server-address')])

            if setting is not None:
                advance_routing = self._find_text(setting, 'advance-routing', 'no')
                rows.append(['Advance Routing', advance_routing])

            enabled = len(rows) > 0
            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=enabled,
                summary=f'{len(rows)} settings' if enabled else 'Not configured',
                columns=columns, rows=rows,
                source=c.name,
            ))

            # Sub-feature: Advance Routing
            if setting is not None:
                adv_rt = self._find_text(setting, 'advance-routing', 'no') == 'yes'
            else:
                adv_rt = False
            results.append(FeatureResult(
                feature_name='Advance Routing',
                enabled=adv_rt,
                summary='Enabled' if adv_rt else 'Not configured',
                source=c.name,
            ))

        # Also check root-level system for Panorama
        system = xml_root.find('.//devices/entry/deviceconfig/system')
        setting = xml_root.find('.//devices/entry/deviceconfig/setting')
        if system is not None and not any(r.source == 'Panorama' for r in results):
            columns = ['Setting', 'Value']
            rows = []
            telemetry = system.find('device-telemetry')
            if telemetry is not None:
                rows.append(['Health Performance', self._find_text(telemetry, 'device-health-performance', 'no')])
                rows.append(['Product Usage', self._find_text(telemetry, 'product-usage', 'no')])
                rows.append(['Threat Prevention', self._find_text(telemetry, 'threat-prevention', 'no')])
                rows.append(['Region', self._find_text(telemetry, 'region')])
            if setting is not None:
                rows.append(['Advance Routing', self._find_text(setting, 'advance-routing', 'no')])

            if rows:
                results.append(FeatureResult(
                    feature_name=self.FEATURE_NAME,
                    enabled=True,
                    summary=f'{len(rows)} settings',
                    columns=columns, rows=rows,
                    source='Panorama',
                ))
                adv_rt = self._find_text(setting, 'advance-routing', 'no') == 'yes' if setting else False
                results.append(FeatureResult(
                    feature_name='Advance Routing',
                    enabled=adv_rt,
                    summary='Enabled' if adv_rt else 'Not configured',
                    source='Panorama',
                ))

        if not results:
            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME, enabled=False,
                summary='Not configured', source='Config',
            ))
            results.append(FeatureResult(
                feature_name='Advance Routing', enabled=False,
                summary='Not configured', source='Config',
            ))

        return results
