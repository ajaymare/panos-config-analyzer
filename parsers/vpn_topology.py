"""VPN Cluster / SD-WAN Topology parser."""
from .base import BaseParser, FeatureResult

# VPN clusters and SD-WAN device config are under plugins/sd_wan at the root level
# Not inside templates or device-groups
PLUGIN_CLUSTER_XPATH = './/plugins/sd_wan/vpn-cluster/entry'
PLUGIN_DEVICES_XPATH = './/plugins/sd_wan/devices/entry'
PLUGIN_ADDRESS_POOL = './/plugins/sd_wan/vpn-address-pool/member'
PLUGIN_BGP_POLICIES = './/plugins/sd_wan/bgp-policies/device-group/entry'


class VPNTopologyParser(BaseParser):
    FEATURE_NAME = 'VPN Clusters - Topology'
    SHEET_NAME = 'VPN Topology'

    def extract(self, xml_root, containers):
        # This parser uses xml_root directly since plugins/sd_wan is at the root level
        clusters = self._find_all(xml_root, PLUGIN_CLUSTER_XPATH)
        devices = self._find_all(xml_root, PLUGIN_DEVICES_XPATH)
        address_pools = self._find_all(xml_root, PLUGIN_ADDRESS_POOL)

        results = []

        # VPN Cluster details
        cluster_columns = ['Cluster Name', 'Type', 'Hubs', 'Hub Priorities',
                           'Branches', 'Auth Type', 'VPN Address Pool']

        cluster_rows = []
        pool_text = ', '.join(m.text for m in address_pools if m.text)

        for entry in clusters:
            cluster_type = self._find_text(entry, 'type')
            hub_entries = self._find_all(entry, 'hubs/entry')
            branch_entries = self._find_all(entry, 'branches/entry')

            hubs = ', '.join(self._get_name(h) for h in hub_entries)
            hub_priorities = ', '.join(
                f"{self._get_name(h)}(pri={self._find_text(h, 'priority')})"
                for h in hub_entries
            )
            branches = ', '.join(self._get_name(b) for b in branch_entries)
            auth_type = self._find_text(entry, 'authentication_type')

            cluster_rows.append([
                self._get_name(entry),
                cluster_type,
                hubs,
                hub_priorities,
                branches,
                auth_type,
                pool_text,
            ])

        if cluster_rows:
            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=True,
                summary=f"{len(clusters)} clusters, {len(devices)} devices",
                columns=cluster_columns,
                rows=cluster_rows,
                source='Panorama Plugins',
            ))

        # SD-WAN Device details
        if devices:
            dev_columns = ['Serial / Device', 'Type', 'Router Name', 'Site',
                           'BGP Router ID', 'BGP AS', 'BGP IPv4 Enabled',
                           'Loopback Address', 'Prefix Redistribute',
                           'VPN Auth', 'Multi-VR Support']

            dev_rows = []
            for dev in devices:
                prefixes = self._find_all(dev, 'bgp/prefix-redistribute/entry')
                prefix_list = ', '.join(self._get_name(p) for p in prefixes)

                vpn_auth = ''
                vpn_tunnel = dev.find('vpn-tunnel/authentication')
                if vpn_tunnel is not None:
                    if vpn_tunnel.find('pre-shared-key') is not None:
                        vpn_auth = 'Pre-Shared Key'
                    elif vpn_tunnel.find('certificate') is not None:
                        vpn_auth = 'Certificate'

                dev_rows.append([
                    self._get_name(dev),
                    self._find_text(dev, 'type'),
                    self._find_text(dev, 'router-name'),
                    self._find_text(dev, 'site'),
                    self._find_text(dev, 'bgp/router-id'),
                    self._find_text(dev, 'bgp/as-number'),
                    self._find_text(dev, 'bgp/ipv4-bgp-enable', 'no'),
                    self._find_text(dev, 'bgp/loopback-address'),
                    prefix_list,
                    vpn_auth,
                    self._find_text(dev, 'multi-vr-support', 'no'),
                ])

            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=True,
                summary=f"{len(devices)} SD-WAN devices configured",
                columns=dev_columns,
                rows=dev_rows,
                source='Panorama Plugins',
            ))

        if not results:
            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=False,
                summary='Not configured',
                source='Panorama Plugins',
            ))

        return results
