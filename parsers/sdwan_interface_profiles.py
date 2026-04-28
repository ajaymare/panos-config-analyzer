"""SD-WAN Interface Profiles parser."""
from .base import BaseParser, FeatureResult

# In Panorama templates: config/devices/entry/vsys/entry/sdwan-interface-profile/entry
# In NGFW: devices/entry/vsys/entry/sdwan-interface-profile/entry
VSYS_XPATH = './/vsys/entry/sdwan-interface-profile/entry'


class SDWANInterfaceProfilesParser(BaseParser):
    FEATURE_NAME = 'Bandwidth Monitoring'
    SHEET_NAME = 'Interface Profiles'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue
            entries = self._find_all(c.xml_node, VSYS_XPATH)

            columns = ['Name', 'Link Type', 'Link Tag', 'Path Monitoring',
                        'Probe Frequency', 'Probe Idle Time',
                        'Failback Hold Time (s)',
                        'Max Upload (Mbps)', 'Max Download (Mbps)']

            def build_row(entry):
                return [
                    self._get_name(entry),
                    self._find_text(entry, 'link-type'),
                    self._find_text(entry, 'link-tag'),
                    self._find_text(entry, 'path-monitoring'),
                    self._find_text(entry, 'probe-frequency'),
                    self._find_text(entry, 'probe-idle-time'),
                    self._find_text(entry, 'failback-hold-time'),
                    self._find_text(entry, 'maximum-upload'),
                    self._find_text(entry, 'maximum-download'),
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))

            # Sub-feature: Probe Idle Time
            has_probe_idle = any(self._find_text(e, 'probe-idle-time') for e in entries)
            results.append(FeatureResult(
                feature_name='Probe Idle Time',
                enabled=has_probe_idle,
                summary='Configured' if has_probe_idle else 'Not configured',
                source=c.name,
            ))

            # Sub-feature: Failback Hold Time
            has_failback = any(self._find_text(e, 'failback-hold-time') for e in entries)
            results.append(FeatureResult(
                feature_name='Failback Hold Time',
                enabled=has_failback,
                summary='Configured' if has_failback else 'Not configured',
                source=c.name,
            ))
        return results
