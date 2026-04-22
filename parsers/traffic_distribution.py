"""Traffic Distribution Profiles parser."""
from .base import BaseParser, FeatureResult

NGFW_XPATH = './/devices/entry/plugins/sd_wan/traffic-distribution-profile/entry'
TMPL_XPATH = './/template/entry/config/devices/entry/plugins/sd_wan/traffic-distribution-profile/entry'


class TrafficDistributionParser(BaseParser):
    FEATURE_NAME = 'Traffic Distribution Profiles'
    SHEET_NAME = 'Traffic Distribution'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            if c.config_type == 'device-group':
                continue
            entries = self._find_all(c.xml_node, TMPL_XPATH) or self._find_all(c.xml_node, NGFW_XPATH)

            columns = ['Name', 'Algorithm', 'Link Tags', 'Weights']

            def build_row(entry):
                algo = ''
                weights = ''
                for method in ('best-available-path', 'top-down-priority', 'weighted-session-distribution'):
                    if entry.find(method) is not None:
                        algo = method
                        # Try to get weights for weighted distribution
                        if method == 'weighted-session-distribution':
                            weight_entries = self._find_all(entry, f'{method}/member/entry')
                            weights = ', '.join(
                                f"{self._get_name(w)}={self._find_text(w, 'weight')}"
                                for w in weight_entries
                            )
                        break
                # Link tags
                tags = self._find_all(entry, 'link-tag/member')
                tag_list = ', '.join(t.text for t in tags if t.text) if tags else ''
                return [self._get_name(entry), algo, tag_list, weights]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
