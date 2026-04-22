"""Base parser class and result dataclass for SD-WAN feature extraction."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import xml.etree.ElementTree as ET


@dataclass
class ConfigContainer:
    """Represents a config scope (NGFW, template, device-group)."""
    name: str
    config_type: str  # 'ngfw', 'template', 'template-stack', 'device-group'
    xml_node: Any     # ElementTree element


@dataclass
class FeatureResult:
    """Result from a single parser extraction."""
    feature_name: str
    enabled: bool
    summary: str
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    source: str = 'NGFW'


class BaseParser(ABC):
    """Abstract base for all SD-WAN feature parsers."""
    FEATURE_NAME: str = ''
    SHEET_NAME: str = ''  # Max 31 chars for Excel

    @abstractmethod
    def extract(self, xml_root: ET.Element, containers: list) -> list:
        """Extract feature data from config XML.

        Args:
            xml_root: Root element of the full config XML
            containers: List of ConfigContainer objects

        Returns:
            List of FeatureResult objects (one per container that has this feature)
        """
        ...

    def _find_all(self, node, xpath):
        """Find all elements matching xpath, returns empty list if none."""
        try:
            return node.findall(xpath) or []
        except Exception:
            return []

    def _find_text(self, node, xpath, default=''):
        """Find text of first matching element."""
        try:
            el = node.find(xpath)
            return el.text if el is not None and el.text else default
        except Exception:
            return default

    def _get_name(self, entry):
        """Get the @name attribute from an entry element."""
        return entry.get('name', 'unnamed')

    def _child_texts(self, node, *tags):
        """Get text values for multiple child tags as a dict."""
        result = {}
        for tag in tags:
            el = node.find(tag)
            result[tag] = el.text if el is not None and el.text else ''
        return result

    def _has_children(self, node, xpath):
        """Check if any children exist at the given xpath."""
        els = self._find_all(node, xpath)
        return len(els) > 0

    def _make_result(self, source, entries, columns, row_builder):
        """Helper to build a FeatureResult from a list of entry elements."""
        rows = []
        for entry in entries:
            try:
                rows.append(row_builder(entry))
            except Exception:
                rows.append([self._get_name(entry), 'Parse error'])
        return FeatureResult(
            feature_name=self.FEATURE_NAME,
            enabled=len(rows) > 0,
            summary=f"{len(rows)} configured" if rows else "Not configured",
            columns=columns,
            rows=rows,
            source=source,
        )
