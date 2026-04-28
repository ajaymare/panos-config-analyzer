"""IKE/IPSec VPN Tunnels parser."""
from .base import BaseParser, FeatureResult

# These are under network/ in templates and NGFW
IPSEC_XPATH = './/network/tunnel/ipsec/entry'
IKE_GW_XPATH = './/network/ike/gateway/entry'
IKE_CRYPTO_XPATH = './/network/ike/crypto-profiles/ike-crypto-profiles/entry'
IPSEC_CRYPTO_XPATH = './/network/ike/crypto-profiles/ipsec-crypto-profiles/entry'


class VPNTunnelsParser(BaseParser):
    FEATURE_NAME = 'VPN/IPSec Tunnels'
    SHEET_NAME = 'VPN Tunnels'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue
            ipsec = self._find_all(c.xml_node, IPSEC_XPATH)
            ike_gw = self._find_all(c.xml_node, IKE_GW_XPATH)

            columns = ['Name', 'Type', 'IKE Gateway', 'Tunnel Interface',
                        'IPSec Crypto Profile', 'Proxy ID', 'Tunnel Monitor', 'Disabled']

            rows = []
            for entry in ipsec:
                ike_gw_entry = entry.find('auto-key/ike-gateway/entry')
                # Tunnel monitor
                tm = entry.find('tunnel-monitor')
                tunnel_mon = ''
                if tm is not None:
                    tm_enabled = self._find_text(tm, 'enable', 'no')
                    tm_dest = self._find_text(tm, 'destination-ip')
                    tunnel_mon = f"{tm_enabled}" + (f" ({tm_dest})" if tm_dest else '')
                rows.append([
                    self._get_name(entry),
                    'IPSec Tunnel',
                    self._get_name(ike_gw_entry) if ike_gw_entry is not None else '',
                    self._find_text(entry, 'tunnel-interface'),
                    self._find_text(entry, 'auto-key/ipsec-crypto-profile'),
                    self._find_text(entry, 'auto-key/proxy-id/entry'),
                    tunnel_mon,
                    self._find_text(entry, 'disabled', 'no'),
                ])

            for entry in ike_gw:
                rows.append([
                    self._get_name(entry),
                    'IKE Gateway',
                    '',
                    '',
                    '',
                    self._find_text(entry, 'peer-address/ip'),
                    self._find_text(entry, 'disabled', 'no'),
                ])

            results.append(FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=len(rows) > 0,
                summary=f"{len(ipsec)} tunnels, {len(ike_gw)} IKE gateways" if rows else "Not configured",
                columns=columns,
                rows=rows,
                source=c.name,
            ))
        return results
