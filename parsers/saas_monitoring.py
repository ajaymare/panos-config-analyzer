"""SaaS Quality Monitoring parser."""
from .base import BaseParser, FeatureResult

# In device-groups: profiles/sdwan-saas-quality/entry
DG_XPATH = 'profiles/sdwan-saas-quality/entry'
SHARED_XPATH = 'profiles/sdwan-saas-quality/entry'
NGFW_XPATH = './/vsys/entry/profiles/sdwan-saas-quality/entry'


class SaaSMonitoringParser(BaseParser):
    FEATURE_NAME = 'SaaS Quality Monitoring'
    SHEET_NAME = 'SaaS Monitoring'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type in ('template', 'template-stack'):
                continue
            entries = []
            if c.config_type == 'device-group':
                entries = self._find_all(c.xml_node, DG_XPATH)
            elif c.config_type == 'shared':
                entries = self._find_all(c.xml_node, SHARED_XPATH)
            else:
                entries = self._find_all(c.xml_node, NGFW_XPATH)

            columns = ['Name', 'Monitor Mode', 'Static IPs', 'Probe Interval',
                        'Disable Override']

            def build_row(entry):
                # Determine monitor mode
                mode = ''
                static_ips = ''
                probe_interval = ''
                monitor = entry.find('monitor-mode')
                if monitor is not None:
                    if monitor.find('adaptive') is not None:
                        mode = 'Adaptive'
                    elif monitor.find('static-ip') is not None:
                        mode = 'Static IP'
                        ip_entries = self._find_all(monitor, 'static-ip/ip-address/entry')
                        ips = []
                        for ip_entry in ip_entries:
                            ips.append(self._get_name(ip_entry))
                            pi = self._find_text(ip_entry, 'probe-interval')
                            if pi:
                                probe_interval = pi
                        static_ips = ', '.join(ips)

                return [
                    self._get_name(entry),
                    mode,
                    static_ips,
                    probe_interval,
                    self._find_text(entry, 'disable-override', 'no'),
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
