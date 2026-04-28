"""Template/Stack to Device Mapping parser."""
from .base import BaseParser, FeatureResult

STACK_XPATH = './/template-stack/entry'
DG_XPATH = './/device-group/entry'


class TemplateStackParser(BaseParser):
    FEATURE_NAME = 'Template/Stack Mapping'
    SHEET_NAME = 'Template Stacks'

    def extract(self, xml_root, containers):
        # Template stacks
        stacks = self._find_all(xml_root, STACK_XPATH)

        if not stacks:
            return [FeatureResult(
                feature_name=self.FEATURE_NAME,
                enabled=False,
                summary='Not configured',
                source='Panorama',
            )]

        columns = ['Stack Name', 'Templates', 'Devices']
        rows = []
        for stack in stacks:
            templates = self._find_all(stack, 'templates/member')
            devices = self._find_all(stack, 'devices/entry')
            rows.append([
                self._get_name(stack),
                ', '.join(m.text for m in templates if m.text),
                ', '.join(self._get_name(d) for d in devices),
            ])

        return [FeatureResult(
            feature_name=self.FEATURE_NAME,
            enabled=True,
            summary=f'{len(stacks)} stacks, {sum(len(self._find_all(s, "devices/entry")) for s in stacks)} devices',
            columns=columns, rows=rows,
            source='Panorama',
        )]
