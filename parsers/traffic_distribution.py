"""Traffic Distribution Profiles parser."""
from .base import BaseParser, FeatureResult

# In device-groups: profiles/sdwan-traffic-distribution/entry
DG_XPATH = 'profiles/sdwan-traffic-distribution/entry'
SHARED_XPATH = 'profiles/sdwan-traffic-distribution/entry'
NGFW_XPATH = './/vsys/entry/profiles/sdwan-traffic-distribution/entry'


class TrafficDistributionParser(BaseParser):
    FEATURE_NAME = 'Traffic Distribution Profiles'
    SHEET_NAME = 'Traffic Distribution'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type in ('template', 'template-stack'):
                continue
            entries = []
            if c.config_type == 'device-group':
                entries = self._find_all(c.xml_node, DG_XPATH)
            elif c.config_type == 'shared':
                entries = self._find_all(c.xml_node, SHARED_XPATH)
            else:
                entries = self._find_all(c.xml_node, NGFW_XPATH)

            columns = ['Name', 'Distribution Method', 'Link Tags', 'Weights',
                        'Error Correction (FEC)', 'Packet Duplication']

            def build_row(entry):
                # Distribution method is a text element
                method = self._find_text(entry, 'traffic-distribution')

                # Link tags with optional weights
                tag_entries = self._find_all(entry, 'link-tags/entry')
                tags = []
                weights = []
                for t in tag_entries:
                    tag_name = self._get_name(t)
                    tags.append(tag_name)
                    w = self._find_text(t, 'weight')
                    if w:
                        weights.append(f"{tag_name}={w}")

                # Error correction (FEC)
                fec = self._find_text(entry, 'error-correction/enable', '')
                if not fec:
                    fec_node = entry.find('error-correction')
                    fec = 'yes' if fec_node is not None else 'no'

                # Packet duplication
                pkt_dup = self._find_text(entry, 'packet-duplication/enable', '')
                if not pkt_dup:
                    pkt_dup_node = entry.find('packet-duplication')
                    pkt_dup = 'yes' if pkt_dup_node is not None else 'no'

                return [
                    self._get_name(entry),
                    method,
                    ', '.join(tags),
                    ', '.join(weights) if weights else '',
                    fec,
                    pkt_dup,
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))

            # Sub-feature: Link Remediation (FEC)
            has_fec = any(
                entry.find('error-correction') is not None for entry in entries
            )
            results.append(FeatureResult(
                feature_name='Link Remediation (FEC)',
                enabled=has_fec,
                summary='Configured' if has_fec else 'Not configured',
                source=c.name,
            ))

            # Sub-feature: Packet Duplication
            has_pkt_dup = any(
                entry.find('packet-duplication') is not None for entry in entries
            )
            results.append(FeatureResult(
                feature_name='Packet Duplication',
                enabled=has_pkt_dup,
                summary='Configured' if has_pkt_dup else 'Not configured',
                source=c.name,
            ))
        return results
