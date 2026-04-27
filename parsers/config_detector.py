"""Detect Panorama vs NGFW config and enumerate config containers."""
import xml.etree.ElementTree as ET
from .base import ConfigContainer


# Common device entry path
_DEV = 'devices/entry'


def detect(xml_root: ET.Element) -> list:
    """Detect config type and return list of ConfigContainer objects.

    For NGFW: returns a single container pointing to the device config.
    For Panorama: returns containers for each template, template-stack, and device-group.
    """
    containers = []

    # Check if this is Panorama config (has device-group or template nodes)
    dg_base = xml_root.find(f'{_DEV}/device-group')
    tmpl_base = xml_root.find(f'{_DEV}/template')
    tmpl_stack_base = xml_root.find(f'{_DEV}/template-stack')

    is_panorama = (dg_base is not None or tmpl_base is not None or tmpl_stack_base is not None)

    if is_panorama:
        # Templates
        if tmpl_base is not None:
            for entry in tmpl_base.findall('entry'):
                name = entry.get('name', 'unnamed')
                # Template config is nested under config/devices/entry
                config_node = entry.find('config')
                if config_node is not None:
                    containers.append(ConfigContainer(
                        name=name,
                        config_type='template',
                        xml_node=config_node,
                    ))

        # Template stacks
        if tmpl_stack_base is not None:
            for entry in tmpl_stack_base.findall('entry'):
                name = entry.get('name', 'unnamed')
                config_node = entry.find('config')
                if config_node is not None:
                    containers.append(ConfigContainer(
                        name=name,
                        config_type='template-stack',
                        xml_node=config_node,
                    ))

        # Device groups
        if dg_base is not None:
            for entry in dg_base.findall('entry'):
                name = entry.get('name', 'unnamed')
                containers.append(ConfigContainer(
                    name=name,
                    config_type='device-group',
                    xml_node=entry,
                ))

        # Also check for shared config
        shared = xml_root.find('shared')
        if shared is not None:
            containers.append(ConfigContainer(
                name='Shared',
                config_type='shared',
                xml_node=shared,
            ))
    else:
        # Standalone NGFW — the root itself or devices/entry is the container
        dev_entry = xml_root.find(_DEV)
        if dev_entry is not None:
            containers.append(ConfigContainer(
                name='NGFW',
                config_type='ngfw',
                xml_node=xml_root,
            ))
        else:
            # Root might be the config node directly
            containers.append(ConfigContainer(
                name='NGFW',
                config_type='ngfw',
                xml_node=xml_root,
            ))

    return containers


def get_config_type(xml_root: ET.Element) -> str:
    """Return 'panorama' or 'ngfw'."""
    dg = xml_root.find(f'{_DEV}/device-group')
    tmpl = xml_root.find(f'{_DEV}/template')
    if dg is not None or tmpl is not None:
        return 'panorama'
    return 'ngfw'


def is_panorama_managed(xml_root: ET.Element) -> bool:
    """Check if an NGFW config is managed by Panorama."""
    panorama_server = xml_root.find(
        f'{_DEV}/deviceconfig/system/panorama/local-panorama/panorama-server'
    )
    return panorama_server is not None


def get_device_serial(xml_root: ET.Element) -> str:
    """Extract the device serial number from an NGFW config.

    Checks mgt-config/devices/entry for serial-like names (numeric, 12+ digits).
    """
    mgt_devices = xml_root.findall('mgt-config/devices/entry')
    for entry in mgt_devices:
        name = entry.get('name', '')
        if name.isdigit() and len(name) >= 12:
            return name
    return ''


def get_managed_serials(xml_root: ET.Element) -> set:
    """Extract all managed device serial numbers from a Panorama config.

    Looks in plugins/sd_wan/devices/entry for SD-WAN managed devices.
    """
    serials = set()
    for path in [f'{_DEV}/plugins/sd_wan/devices/entry', 'plugins/sd_wan/devices/entry']:
        for entry in (xml_root.findall(path) or []):
            name = entry.get('name', '')
            if name.isdigit() and len(name) >= 12:
                serials.add(name)
    return serials
