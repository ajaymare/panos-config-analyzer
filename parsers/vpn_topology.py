"""VPN Cluster / SD-WAN Topology parser."""
from .base import BaseParser, FeatureResult

NGFW_XPATH = './/devices/entry/plugins/sd_wan/vpn-cluster/entry'
TMPL_XPATH = './/template/entry/config/devices/entry/plugins/sd_wan/vpn-cluster/entry'


class VPNTopologyParser(BaseParser):
    FEATURE_NAME = 'VPN Clusters / Topology'
    SHEET_NAME = 'VPN Topology'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue
            entries = self._find_all(c.xml_node, TMPL_XPATH) or self._find_all(c.xml_node, NGFW_XPATH)

            columns = ['Cluster Name', 'Type', 'Hubs', 'Spokes', 'Mesh Members', 'Description']

            def build_row(entry):
                cluster_type = ''
                hubs = spokes = mesh = ''
                hs = entry.find('type/hub-spoke')
                if hs is not None:
                    cluster_type = 'Hub-Spoke'
                    hub_entries = self._find_all(hs, 'hub/entry')
                    spoke_entries = self._find_all(hs, 'spoke/entry')
                    hubs = ', '.join(self._get_name(h) for h in hub_entries)
                    spokes = ', '.join(self._get_name(s) for s in spoke_entries)
                m = entry.find('type/mesh')
                if m is not None:
                    cluster_type = 'Full Mesh'
                    mesh_entries = self._find_all(m, 'member/entry')
                    mesh = ', '.join(self._get_name(mm) for mm in mesh_entries)
                return [
                    self._get_name(entry),
                    cluster_type,
                    hubs,
                    spokes,
                    mesh,
                    self._find_text(entry, 'description'),
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
