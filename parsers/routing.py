"""Routing (BGP, OSPF, ECMP) parser."""
from .base import BaseParser, FeatureResult

VR_XPATH = './/devices/entry/network/virtual-router/entry'
TMPL_VR_XPATH = './/template/entry/config/devices/entry/network/virtual-router/entry'
LR_XPATH = './/devices/entry/network/logical-router/entry'
TMPL_LR_XPATH = './/template/entry/config/devices/entry/network/logical-router/entry'


class RoutingParser(BaseParser):
    FEATURE_NAME = 'Routing (BGP/OSPF/ECMP)'
    SHEET_NAME = 'Routing'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue
            vrs = self._find_all(c.xml_node, TMPL_VR_XPATH) or self._find_all(c.xml_node, VR_XPATH)
            lrs = self._find_all(c.xml_node, TMPL_LR_XPATH) or self._find_all(c.xml_node, LR_XPATH)

            columns = ['Router Name', 'Type', 'BGP Enabled', 'BGP Router ID', 'BGP AS',
                        'OSPF Enabled', 'ECMP Enabled', 'ECMP Max Path', 'ECMP Algorithm',
                        'Static Routes']

            rows = []
            for vr in vrs:
                bgp = vr.find('protocol/bgp')
                ospf = vr.find('protocol/ospf')
                ecmp = vr.find('ecmp')
                static_routes = self._find_all(vr, 'routing-table/ip/static-route/entry')
                rows.append([
                    self._get_name(vr),
                    'Virtual Router',
                    self._find_text(bgp, 'enable', 'no') if bgp is not None else 'no',
                    self._find_text(bgp, 'router-id') if bgp is not None else '',
                    self._find_text(bgp, 'local-as') if bgp is not None else '',
                    self._find_text(ospf, 'enable', 'no') if ospf is not None else 'no',
                    self._find_text(ecmp, 'enable', 'no') if ecmp is not None else 'no',
                    self._find_text(ecmp, 'max-path') if ecmp is not None else '',
                    self._find_text(ecmp, 'algorithm') if ecmp is not None else '',
                    str(len(static_routes)),
                ])

            for lr in lrs:
                bgp = lr.find('protocol/bgp')
                ospf = lr.find('protocol/ospf')
                vrfs = self._find_all(lr, 'vrf/entry')
                for vrf in vrfs:
                    ecmp = vrf.find('ecmp')
                    rows.append([
                        f"{self._get_name(lr)} / VRF:{self._get_name(vrf)}",
                        'Logical Router (VRF)',
                        self._find_text(bgp, 'enable', 'no') if bgp is not None else 'no',
                        self._find_text(bgp, 'router-id') if bgp is not None else '',
                        self._find_text(bgp, 'local-as') if bgp is not None else '',
                        self._find_text(ospf, 'enable', 'no') if ospf is not None else 'no',
                        self._find_text(ecmp, 'enable', 'no') if ecmp is not None else 'no',
                        self._find_text(ecmp, 'max-path') if ecmp is not None else '',
                        '', '',
                    ])

            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=len(rows) > 0,
                summary=f"{len(vrs)} VRs, {len(lrs)} LRs" if rows else "Not configured",
                columns=columns, rows=rows, source=c.name,
            ))
        return results
