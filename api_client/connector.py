"""PAN-OS API connector using pan-os-python SDK."""
import xml.etree.ElementTree as ET


def fetch_config(hostname: str, api_key: str, verify_ssl: bool = False):
    """Connect to Panorama/NGFW and retrieve full running config XML.

    Args:
        hostname: Device IP or FQDN
        api_key: PAN-OS API key
        verify_ssl: Whether to verify SSL certificate

    Returns:
        Tuple of (xml_root: ET.Element, device_type: str)
        device_type is 'panorama' or 'firewall'
    """
    try:
        from panos.panorama import Panorama
        from panos.firewall import Firewall
    except ImportError:
        raise ImportError("pan-os-python is required for API access. Install with: pip install pan-os-python")

    # Try connecting as Panorama first
    device_type = 'unknown'
    device = None

    try:
        device = Panorama(hostname, api_key=api_key)
        device.refresh_system_info()
        if device.is_panorama():
            device_type = 'panorama'
        else:
            # It's a firewall, reconnect as Firewall object
            device = Firewall(hostname, api_key=api_key)
            device.refresh_system_info()
            device_type = 'firewall'
    except Exception:
        # Fall back to Firewall
        try:
            device = Firewall(hostname, api_key=api_key)
            device.refresh_system_info()
            device_type = 'firewall'
        except Exception as e:
            raise ConnectionError(f"Failed to connect to {hostname}: {e}")

    # Pull full running config
    try:
        device.xapi.show('/config')
        xml_root = device.xapi.element_result
        if xml_root is None:
            raise ValueError("Empty config returned from device")
        # The xapi returns a <result> wrapper, get the actual config
        config = xml_root.find('config')
        if config is not None:
            return config, device_type
        return xml_root, device_type
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve config from {hostname}: {e}")


def test_connection(hostname: str, api_key: str) -> dict:
    """Test connectivity to a PAN-OS device and return basic info."""
    try:
        from panos.panorama import Panorama
        from panos.firewall import Firewall
    except ImportError:
        return {'success': False, 'error': 'pan-os-python not installed'}

    try:
        device = Panorama(hostname, api_key=api_key)
        device.refresh_system_info()
        return {
            'success': True,
            'hostname': device.hostname,
            'model': getattr(device, 'model', 'unknown'),
            'serial': getattr(device, 'serial', 'unknown'),
            'sw_version': getattr(device, 'version', 'unknown'),
            'type': 'panorama' if device.is_panorama() else 'firewall',
        }
    except Exception as e:
        try:
            device = Firewall(hostname, api_key=api_key)
            device.refresh_system_info()
            return {
                'success': True,
                'hostname': device.hostname,
                'model': getattr(device, 'model', 'unknown'),
                'serial': getattr(device, 'serial', 'unknown'),
                'sw_version': getattr(device, 'version', 'unknown'),
                'type': 'firewall',
            }
        except Exception as e2:
            return {'success': False, 'error': str(e2)}
