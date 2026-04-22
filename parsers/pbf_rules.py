"""Policy-Based Forwarding Rules parser."""
from .base import BaseParser, FeatureResult

NGFW_XPATH = './/vsys/entry/rulebase/pbf/rules/entry'
DG_PRE_XPATH = './/pre-rulebase/pbf/rules/entry'
DG_POST_XPATH = './/post-rulebase/pbf/rules/entry'


class PBFRulesParser(BaseParser):
    FEATURE_NAME = 'Policy-Based Forwarding'
    SHEET_NAME = 'PBF Rules'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            entries = []
            if c.config_type == 'device-group':
                entries = self._find_all(c.xml_node, DG_PRE_XPATH) + \
                          self._find_all(c.xml_node, DG_POST_XPATH)
            else:
                entries = self._find_all(c.xml_node, NGFW_XPATH)

            columns = ['Name', 'Source Zone', 'Source Address', 'Dest Address',
                        'Application', 'Action', 'Nexthop', 'Monitor', 'Disabled']

            def build_row(entry):
                src_zones = self._find_all(entry, 'from/zone/member')
                src_addr = self._find_all(entry, 'source/member')
                dst_addr = self._find_all(entry, 'destination/member')
                apps = self._find_all(entry, 'application/member')
                action = entry.find('action')
                action_type = ''
                nexthop = ''
                if action is not None:
                    fwd = action.find('forward')
                    if fwd is not None:
                        action_type = 'Forward'
                        nh = fwd.find('nexthop/ip-address')
                        nexthop = nh.text if nh is not None and nh.text else ''
                    elif action.find('discard') is not None:
                        action_type = 'Discard'
                    elif action.find('no-pbf') is not None:
                        action_type = 'No PBF'
                return [
                    self._get_name(entry),
                    ', '.join(z.text for z in src_zones if z.text),
                    ', '.join(a.text for a in src_addr if a.text),
                    ', '.join(a.text for a in dst_addr if a.text),
                    ', '.join(a.text for a in apps if a.text),
                    action_type,
                    nexthop,
                    self._find_text(entry, 'action/forward/monitor/ip-address'),
                    self._find_text(entry, 'disabled', 'no'),
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
