"""VPN Cluster / SD-WAN Topology parser."""
from .base import BaseParser, FeatureResult

# VPN clusters and SD-WAN device config are under plugins/sd_wan at the root level
# Not inside templates or device-groups
PLUGIN_CLUSTER_XPATH = './/plugins/sd_wan/vpn-cluster/entry'
PLUGIN_DEVICES_XPATH = './/plugins/sd_wan/devices/entry'
PLUGIN_ADDRESS_POOL = './/plugins/sd_wan/vpn-address-pool/member'
PLUGIN_BGP_POLICIES = './/plugins/sd_wan/bgp-policies/device-group/entry'
PLUGIN_PANORAMA_CONN = './/plugins/sd_wan/panorama-connectivity'


class VPNTopologyParser(BaseParser):
    FEATURE_NAME = 'VPN Clusters - Topology'
    SHEET_NAME = 'VPN Topology'

    def extract(self, xml_root, containers):
        # This parser uses xml_root directly since plugins/sd_wan is at the root level
        clusters = self._find_all(xml_root, PLUGIN_CLUSTER_XPATH)
        devices = self._find_all(xml_root, PLUGIN_DEVICES_XPATH)
        address_pools = self._find_all(xml_root, PLUGIN_ADDRESS_POOL)
        bgp_policy_groups = self._find_all(xml_root, PLUGIN_BGP_POLICIES)
        panorama_conn = xml_root.find(PLUGIN_PANORAMA_CONN)

        results = []

        # VPN Cluster details
        cluster_columns = ['Cluster Name', 'Type', 'Hubs', 'Hub Priorities',
                           'Branches', 'Auth Type', 'VPN Address Pool',
                           'Hub Count', 'Branch Count', 'DIA VPN Failover']

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

            # DIA VPN Failover per hub
            dia_failover_parts = []
            for h in hub_entries:
                dia = self._find_text(h, 'allow-dia-vpn-failover', 'no')
                dia_failover_parts.append(f"{self._get_name(h)}={dia}")
            dia_failover = ', '.join(dia_failover_parts)

            cluster_rows.append([
                self._get_name(entry),
                cluster_type,
                hubs,
                hub_priorities,
                branches,
                auth_type,
                pool_text,
                str(len(hub_entries)),
                str(len(branch_entries)),
                dia_failover,
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
                           'VPN Auth', 'Multi-VR Support',
                           'Remove Private AS', 'Remove Private AS IPv6']

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
                    self._find_text(dev, 'bgp/remove-private-as', 'no'),
                    self._find_text(dev, 'bgp/remove-private-as-ipv6', 'no'),
                ])

            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=True,
                summary=f"{len(devices)} SD-WAN devices configured",
                columns=dev_columns,
                rows=dev_rows,
                source='Panorama Plugins',
            ))

        # BGP Policies
        if bgp_policy_groups:
            bgp_columns = ['Device Group', 'BGP Security Rules']
            bgp_rows = []
            for dg in bgp_policy_groups:
                rules = self._find_all(dg, 'rule/entry')
                rule_names = ', '.join(self._get_name(r) for r in rules)
                bgp_rows.append([self._get_name(dg), rule_names])

            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=True,
                summary=f"{len(bgp_policy_groups)} BGP policy groups",
                columns=bgp_columns,
                rows=bgp_rows,
                source='Panorama Plugins',
            ))

        # Panorama Connectivity (Prisma Access Hub)
        if panorama_conn is not None:
            conn_columns = ['Setting', 'Value']
            conn_rows = []
            dedicated_ipsec = self._find_text(panorama_conn, 'create-dedicated-ipsec-tunnels', 'no')
            conn_pool = self._find_text(panorama_conn, 'vpn-address-pool')
            conn_rows.append(['Dedicated IPSec Tunnels', dedicated_ipsec])
            conn_rows.append(['VPN Address Pool', conn_pool])

            primary_devices = self._find_all(panorama_conn, 'primary-termination-device/entry')
            for pd in primary_devices:
                conn_rows.append([f'Primary Termination: {self._get_name(pd)}',
                                  self._find_text(pd, 'preferred-dia')])
            secondary_devices = self._find_all(panorama_conn, 'secondary-termination-device/entry')
            for sd in secondary_devices:
                conn_rows.append([f'Secondary Termination: {self._get_name(sd)}',
                                  self._find_text(sd, 'preferred-dia')])

            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=True,
                summary='Panorama connectivity configured',
                columns=conn_columns,
                rows=conn_rows,
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
