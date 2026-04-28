"""SD-WAN Security Rules parser."""
from .base import BaseParser, FeatureResult

DG_PRE_XPATH = 'pre-rulebase/security/rules/entry'
DG_POST_XPATH = 'post-rulebase/security/rules/entry'
SHARED_PRE_XPATH = 'pre-rulebase/security/rules/entry'


class SecurityRulesParser(BaseParser):
    FEATURE_NAME = 'SD-WAN Security Rules'
    SHEET_NAME = 'Security Rules'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type in ('template', 'template-stack'):
                continue
            entries = []
            if c.config_type == 'device-group':
                entries.extend(self._find_all(c.xml_node, DG_PRE_XPATH))
                entries.extend(self._find_all(c.xml_node, DG_POST_XPATH))
            elif c.config_type == 'shared':
                entries.extend(self._find_all(c.xml_node, SHARED_PRE_XPATH))
            else:
                entries.extend(self._find_all(c.xml_node, './/vsys/entry/rulebase/security/rules/entry'))

            columns = ['Rule Name', 'Source Zone', 'Dest Zone', 'Application',
                        'Service', 'Action', 'Log End', 'Disabled']

            def build_row(entry):
                src_zones = self._find_all(entry, 'from/member')
                dst_zones = self._find_all(entry, 'to/member')
                apps = self._find_all(entry, 'application/member')
                services = self._find_all(entry, 'service/member')

                return [
                    self._get_name(entry),
                    ', '.join(m.text for m in src_zones if m.text),
                    ', '.join(m.text for m in dst_zones if m.text),
                    ', '.join(m.text for m in apps if m.text),
                    ', '.join(m.text for m in services if m.text),
                    self._find_text(entry, 'action'),
                    self._find_text(entry, 'log-end', 'no'),
                    self._find_text(entry, 'disabled', 'no'),
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
