"""IKE/IPSec VPN Tunnels parser."""
from .base import BaseParser, FeatureResult

IPSEC_XPATH = './/devices/entry/network/tunnel/ipsec/entry'
IKE_GW_XPATH = './/devices/entry/network/ike/gateway/entry'
IKE_CRYPTO_XPATH = './/devices/entry/network/ike/crypto-profiles/ike-crypto-profiles/entry'
IPSEC_CRYPTO_XPATH = './/devices/entry/network/ike/crypto-profiles/ipsec-crypto-profiles/entry'

TMPL_IPSEC = './/template/entry/config/devices/entry/network/tunnel/ipsec/entry'
TMPL_IKE_GW = './/template/entry/config/devices/entry/network/ike/gateway/entry'


class VPNTunnelsParser(BaseParser):
    FEATURE_NAME = 'VPN/IPSec Tunnels'
    SHEET_NAME = 'VPN Tunnels'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue
            ipsec = self._find_all(c.xml_node, TMPL_IPSEC) or self._find_all(c.xml_node, IPSEC_XPATH)
            ike_gw = self._find_all(c.xml_node, TMPL_IKE_GW) or self._find_all(c.xml_node, IKE_GW_XPATH)

            columns = ['Name', 'Type', 'IKE Gateway', 'Tunnel Interface',
                        'IPSec Crypto Profile', 'Proxy ID', 'Disabled']

            all_entries = []
            for entry in ipsec:
                all_entries.append(('ipsec', entry))
            for entry in ike_gw:
                all_entries.append(('ike-gw', entry))

            rows = []
            for etype, entry in all_entries:
                if etype == 'ipsec':
                    rows.append([
                        self._get_name(entry),
                        'IPSec Tunnel',
                        self._find_text(entry, 'auto-key/ike-gateway/entry'),
                        self._find_text(entry, 'tunnel-interface'),
                        self._find_text(entry, 'auto-key/ipsec-crypto-profile'),
                        self._find_text(entry, 'auto-key/proxy-id/entry'),
                        self._find_text(entry, 'disabled', 'no'),
                    ])
                else:
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
