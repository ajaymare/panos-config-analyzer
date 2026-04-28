"""SD-WAN NAT Policies parser."""
from .base import BaseParser, FeatureResult

PLUGIN_NAT_XPATH = './/plugins/sd_wan/nat-policies/device-group/entry'
DG_NAT_XPATH = 'pre-rulebase/nat/rules/entry'


class NATPoliciesParser(BaseParser):
    FEATURE_NAME = 'SD-WAN NAT Policies'
    SHEET_NAME = 'NAT Policies'

    def extract(self, xml_root, containers):
        results = []

        # Check plugin-level NAT policy references
        plugin_nats = self._find_all(xml_root, PLUGIN_NAT_XPATH)
        if plugin_nats:
            columns = ['Device Group', 'NAT Rules']
            rows = []
            for dg in plugin_nats:
                rules = self._find_all(dg, 'rule/entry')
                rule_names = ', '.join(self._get_name(r) for r in rules)
                rows.append([self._get_name(dg), rule_names])
            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=True,
                summary=f'{len(plugin_nats)} device groups with NAT',
                columns=columns, rows=rows,
                source='Panorama Plugins',
            ))

        # Check device-group NAT rules
        for c in containers:
            if c.config_type in ('template', 'template-stack'):
                continue
            entries = []
            if c.config_type == 'device-group':
                entries = self._find_all(c.xml_node, DG_NAT_XPATH)
            elif c.config_type != 'shared':
                entries = self._find_all(c.xml_node, './/vsys/entry/rulebase/nat/rules/entry')

            if not entries:
                continue

            columns = ['Rule Name', 'Source Zone', 'Dest Zone', 'Service',
                        'Source Translation', 'Dest Translation', 'Disabled']
            rows = []
            for entry in entries:
                src_zones = self._find_all(entry, 'from/member')
                dst_zones = self._find_all(entry, 'to/member')
                services = self._find_all(entry, 'service/member')

                # Source translation type
                src_trans = ''
                if entry.find('source-translation/dynamic-ip-and-port') is not None:
                    src_trans = 'Dynamic IP and Port'
                elif entry.find('source-translation/dynamic-ip') is not None:
                    src_trans = 'Dynamic IP'
                elif entry.find('source-translation/static-ip') is not None:
                    src_trans = 'Static IP'

                dst_trans = ''
                if entry.find('destination-translation') is not None:
                    dst_addr = self._find_text(entry, 'destination-translation/translated-address')
                    dst_trans = dst_addr if dst_addr else 'Configured'

                rows.append([
                    self._get_name(entry),
                    ', '.join(m.text for m in src_zones if m.text),
                    ', '.join(m.text for m in dst_zones if m.text),
                    ', '.join(m.text for m in services if m.text),
                    src_trans,
                    dst_trans,
                    self._find_text(entry, 'disabled', 'no'),
                ])

            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=len(rows) > 0,
                summary=f'{len(rows)} NAT rules' if rows else 'Not configured',
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
