"""Routing (BGP, OSPF, ECMP) parser."""
from .base import BaseParser, FeatureResult

VR_XPATH = './/network/virtual-router/entry'
LR_XPATH = './/network/logical-router/entry'


class RoutingParser(BaseParser):
    FEATURE_NAME = 'Routing (BGP/OSPF/ECMP)'
    SHEET_NAME = 'Routing'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue
            vrs = self._find_all(c.xml_node, VR_XPATH)
            lrs = self._find_all(c.xml_node, LR_XPATH)

            columns = ['Router Name', 'Type', 'BGP Enabled', 'BGP Router ID', 'BGP AS',
                        'OSPF Enabled', 'ECMP Enabled', 'ECMP Max Path',
                        'Interfaces', 'Static Routes',
                        'Fast External Failover', 'Graceful Restart',
                        'Stale Route Time', 'OSPFv3 (IPv6)']

            rows = []
            for vr in vrs:
                bgp = vr.find('protocol/bgp')
                ospf = vr.find('protocol/ospf')
                ospfv3 = vr.find('protocol/ospfv3')
                ecmp = vr.find('ecmp')
                static_routes = self._find_all(vr, 'routing-table/ip/static-route/entry')
                interfaces = self._find_all(vr, 'interface/member')

                # BGP graceful restart
                gr = bgp.find('graceful-restart') if bgp is not None else None
                gr_enabled = self._find_text(gr, 'enable', 'no') if gr is not None else 'no'
                stale_time = self._find_text(gr, 'stale-route-time') if gr is not None else ''

                rows.append([
                    self._get_name(vr),
                    'Virtual Router',
                    self._find_text(bgp, 'enable', 'no') if bgp is not None else 'no',
                    self._find_text(bgp, 'router-id') if bgp is not None else '',
                    self._find_text(bgp, 'local-as') if bgp is not None else '',
                    self._find_text(ospf, 'enable', 'no') if ospf is not None else 'no',
                    self._find_text(ecmp, 'enable', 'no') if ecmp is not None else 'no',
                    self._find_text(ecmp, 'max-path') if ecmp is not None else '',
                    ', '.join(m.text for m in interfaces if m.text),
                    str(len(static_routes)),
                    self._find_text(bgp, 'fast-external-failover', 'no') if bgp is not None else 'no',
                    gr_enabled,
                    stale_time,
                    self._find_text(ospfv3, 'enable', 'no') if ospfv3 is not None else 'no',
                ])

            for lr in lrs:
                vrfs = self._find_all(lr, 'vrf/entry')
                for vrf in vrfs:
                    bgp = vrf.find('bgp')
                    ospf = vrf.find('ospf')
                    ospfv3 = vrf.find('ospfv3')
                    ecmp = vrf.find('ecmp')
                    interfaces = self._find_all(vrf, 'interface/member')

                    gr = bgp.find('graceful-restart') if bgp is not None else None
                    gr_enabled = self._find_text(gr, 'enable', 'no') if gr is not None else 'no'
                    stale_time = self._find_text(gr, 'stale-route-time') if gr is not None else ''

                    rows.append([
                        f"{self._get_name(lr)} / VRF:{self._get_name(vrf)}",
                        'Logical Router (VRF)',
                        self._find_text(bgp, 'enable', 'no') if bgp is not None else 'no',
                        self._find_text(bgp, 'router-id') if bgp is not None else '',
                        self._find_text(bgp, 'local-as') if bgp is not None else '',
                        self._find_text(ospf, 'enable', 'no') if ospf is not None else 'no',
                        self._find_text(ecmp, 'enable', 'no') if ecmp is not None else 'no',
                        self._find_text(ecmp, 'max-path') if ecmp is not None else '',
                        ', '.join(m.text for m in interfaces if m.text),
                        '',
                        self._find_text(bgp, 'fast-external-failover', 'no') if bgp is not None else 'no',
                        gr_enabled,
                        stale_time,
                        self._find_text(ospfv3, 'enable', 'no') if ospfv3 is not None else 'no',
                    ])

            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=len(rows) > 0,
                summary=f"{len(vrs)} VRs, {len(lrs)} LRs" if rows else "Not configured",
                columns=columns, rows=rows, source=c.name,
            ))
        return results
