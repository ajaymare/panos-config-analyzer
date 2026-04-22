"""Certificate Profiles parser."""
from .base import BaseParser, FeatureResult

SHARED_XPATH = './/shared/certificate-profile/entry'
NGFW_XPATH = './/devices/entry/certificate-profile/entry'


class CertificateProfilesParser(BaseParser):
    FEATURE_NAME = 'Certificate Profiles'
    SHEET_NAME = 'Certificates'

    def extract(self, xml_root, containers):
        results = []
        for c in containers:
            entries = []
            if c.config_type == 'shared':
                entries = self._find_all(c.xml_node, 'certificate-profile/entry')
            elif c.config_type == 'device-group':
                entries = self._find_all(c.xml_node, 'certificate-profile/entry')
            else:
                entries = self._find_all(c.xml_node, SHARED_XPATH) or \
                          self._find_all(c.xml_node, NGFW_XPATH)

            columns = ['Name', 'CA Certificates', 'Use CRL', 'Use OCSP',
                        'CRL Receive Timeout', 'Block Timeout Cert']

            def build_row(entry):
                ca_certs = self._find_all(entry, 'CA/member')
                return [
                    self._get_name(entry),
                    ', '.join(c.text for c in ca_certs if c.text),
                    self._find_text(entry, 'use-crl', 'no'),
                    self._find_text(entry, 'use-ocsp', 'no'),
                    self._find_text(entry, 'crl-receive-timeout'),
                    self._find_text(entry, 'block-unknown-cert', 'no'),
                ]

            results.append(self._make_result(c.name, entries, columns, build_row))
        return results
