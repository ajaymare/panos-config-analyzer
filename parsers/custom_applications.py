"""Custom Application Definitions parser."""
from .base import BaseParser, FeatureResult

SHARED_XPATH = 'content-preview/application/entry'
DG_XPATH = 'application/entry'


class CustomApplicationsParser(BaseParser):
    FEATURE_NAME = 'Custom Applications'
    SHEET_NAME = 'Custom Apps'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            entries = []
            if c.config_type == 'shared':
                entries = self._find_all(c.xml_node, SHARED_XPATH)
            elif c.config_type == 'device-group':
                entries = self._find_all(c.xml_node, DG_XPATH)
            elif c.config_type in ('template', 'template-stack'):
                continue
            else:
                entries = self._find_all(c.xml_node, './/vsys/entry/application/entry')

            columns = ['Application Name', 'Category', 'Subcategory', 'Technology', 'Risk']

            def build_row(entry):
                return [
                    self._get_name(entry),
                    self._find_text(entry, 'category'),
                    self._find_text(entry, 'subcategory'),
                    self._find_text(entry, 'technology'),
                    self._find_text(entry, 'risk'),
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
