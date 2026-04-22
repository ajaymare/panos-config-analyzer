"""SD-WAN Policy Rules parser."""
from .base import BaseParser, FeatureResult

NGFW_XPATH = './/vsys/entry/rulebase/sdwan/rules/entry'
DG_PRE_XPATH = './/pre-rulebase/sdwan/rules/entry'
DG_POST_XPATH = './/post-rulebase/sdwan/rules/entry'


class SDWANPoliciesParser(BaseParser):
    FEATURE_NAME = 'SD-WAN Policy Rules'
    SHEET_NAME = 'SD-WAN Rules'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            entries = []
            if c.config_type == 'device-group':
                entries = self._find_all(c.xml_node, DG_PRE_XPATH) + \
                          self._find_all(c.xml_node, DG_POST_XPATH)
            else:
                entries = self._find_all(c.xml_node, NGFW_XPATH)

            columns = ['Name', 'Source Zone', 'Dest Zone', 'Application',
                        'Path Quality Profile', 'Traffic Distribution', 'Error Correction',
                        'Action', 'Disabled']

            def build_row(entry):
                src_zones = self._find_all(entry, 'from/member')
                dst_zones = self._find_all(entry, 'to/member')
                apps = self._find_all(entry, 'application/member')
                return [
                    self._get_name(entry),
                    ', '.join(z.text for z in src_zones if z.text),
                    ', '.join(z.text for z in dst_zones if z.text),
                    ', '.join(a.text for a in apps if a.text),
                    self._find_text(entry, 'action/sdwan-path-quality'),
                    self._find_text(entry, 'action/sdwan-traffic-distribution'),
                    self._find_text(entry, 'action/error-correction'),
                    self._find_text(entry, 'action/type', 'sdwan'),
                    self._find_text(entry, 'disabled', 'no'),
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
