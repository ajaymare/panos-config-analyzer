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

            columns = ['Name', 'Distribution Method', 'Link Tags', 'Weights']

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

                return [
                    self._get_name(entry),
                    method,
                    ', '.join(tags),
                    ', '.join(weights) if weights else '',
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
