"""QoS Profiles parser."""
from .base import BaseParser, FeatureResult

# QoS is under network/ in templates and NGFW
QOS_PROF_XPATH = './/network/qos/profile/entry'
QOS_INTF_XPATH = './/network/qos/interface/entry'


class QoSProfilesParser(BaseParser):
    FEATURE_NAME = 'QoS Profiles'
    SHEET_NAME = 'QoS'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue
            profiles = self._find_all(c.xml_node, QOS_PROF_XPATH)
            interfaces = self._find_all(c.xml_node, QOS_INTF_XPATH)

            columns = ['Name', 'Type', 'Max Bandwidth', 'Guaranteed', 'Priority', 'Classes']

            rows = []
            for p in profiles:
                classes = self._find_all(p, 'class/entry')
                class_names = ', '.join(self._get_name(cl) for cl in classes)
                rows.append([
                    self._get_name(p),
                    'Profile',
                    self._find_text(p, 'aggregate-bandwidth/egress-max'),
                    self._find_text(p, 'aggregate-bandwidth/egress-guaranteed'),
                    '',
                    class_names,
                ])

            for intf in interfaces:
                rows.append([
                    self._get_name(intf),
                    'Interface Binding',
                    self._find_text(intf, 'interface-bandwidth/egress-max'),
                    self._find_text(intf, 'interface-bandwidth/egress-guaranteed'),
                    '',
                    self._find_text(intf, 'qos-profile'),
                ])

            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=len(rows) > 0,
                summary=f"{len(profiles)} profiles, {len(interfaces)} bindings" if rows else "Not configured",
                columns=columns, rows=rows, source=c.name,
            ))
        return results
