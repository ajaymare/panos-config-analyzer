"""Mask sensitive information in parsed results before report generation."""
import re
import copy

# IPv4 address pattern (with optional CIDR)
_IP_RE = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(/\d{1,2})?\b')

# FQDN pattern — at least two labels with dots
_FQDN_RE = re.compile(r'\b([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.){2,}[a-zA-Z]{2,}\b')

# Columns that contain IP addresses
_IP_COLUMNS = {
    'IP Address', 'Router ID', 'BGP Router ID', 'Nexthop', 'Monitor',
    'Gateway', 'SD-WAN Gateway', 'Loopback Address', 'Peer',
    'Target', 'VPN Address Pool', 'Proxy ID',
}

# Columns that contain device names / serials
_DEVICE_COLUMNS = {
    'Serial / Device', 'Router Name', 'Site', 'Hubs', 'Hub Priorities',
    'Branches', 'Cluster Name',
}

# Columns that contain network addresses (subnets, AS numbers, etc.)
_NETWORK_COLUMNS = {
    'Source Address', 'Dest Address', 'BGP AS', 'BGP IPv4 Enabled',
    'Prefix Redistribute', 'Interfaces', 'Interface',
    'Tunnel Interface', 'Name',
}

# Columns that contain certificate info
_CERT_COLUMNS = {
    'CA Certificates',
}

# Columns that contain key/password info
_KEY_COLUMNS = {
    'VPN Auth',
}

# Feature names where "Name" column contains certificate-related data
_CERT_FEATURES = {'Certificate Profiles'}

# Feature names where "Name" column contains network interface names (not sensitive device names)
_NETWORK_NAME_FEATURES = {
    'Zones and Interfaces', 'Link Management', 'VPN/IPSec Tunnels',
    'SD-WAN Interface Profiles',
}


def _mask_ip(value):
    """Replace all IP addresses in a string with x.x.x.x."""
    if not isinstance(value, str):
        return value
    return _IP_RE.sub(lambda m: 'x.x.x.x' + (m.group(2) or ''), value)


def _mask_fqdn(value):
    """Replace all FQDNs in a string with ***.***."""
    if not isinstance(value, str):
        return value
    return _FQDN_RE.sub('***.***', value)


def _make_device_masker():
    """Create a consistent device name masker that maps each unique value to DEVICE-NNN."""
    mapping = {}
    counter = [0]

    def mask(value):
        if not isinstance(value, str) or not value.strip():
            return value
        # Handle comma-separated lists (e.g., hub lists)
        parts = [p.strip() for p in value.split(',')]
        masked_parts = []
        for part in parts:
            if not part:
                masked_parts.append(part)
                continue
            # Strip priority info like "(pri=1)" for mapping, re-add after
            pri_match = re.match(r'^(.+?)(\(pri=\d+\))$', part)
            if pri_match:
                base = pri_match.group(1)
                suffix = pri_match.group(2)
            else:
                base = part
                suffix = ''
            if base not in mapping:
                counter[0] += 1
                mapping[base] = f'DEVICE-{counter[0]:03d}'
            masked_parts.append(mapping[base] + suffix)
        return ', '.join(masked_parts)

    return mask


def mask_results(results, categories):
    """Apply masking to a list of FeatureResult objects based on selected categories.

    Args:
        results: list of FeatureResult objects
        categories: list of category strings to mask

    Returns:
        New list of FeatureResult with masked data (originals not modified)
    """
    if not categories:
        return results

    cats = set(categories)
    device_masker = _make_device_masker()

    masked = []
    for r in results:
        # Deep copy to avoid modifying originals
        mr = copy.deepcopy(r)

        if not mr.columns or not mr.rows:
            masked.append(mr)
            continue

        # Build column index for this result
        col_indices = {col: i for i, col in enumerate(mr.columns)}

        for row_idx, row in enumerate(mr.rows):
            for col_idx, val in enumerate(row):
                if not isinstance(val, str) or not val:
                    continue

                col_name = mr.columns[col_idx] if col_idx < len(mr.columns) else ''

                # IP Addresses
                if 'ip_addresses' in cats:
                    if col_name in _IP_COLUMNS or _IP_RE.search(val):
                        row[col_idx] = _mask_ip(row[col_idx])
                        val = row[col_idx]

                # Hostnames & FQDNs
                if 'hostnames' in cats:
                    if _FQDN_RE.search(val):
                        row[col_idx] = _mask_fqdn(row[col_idx])
                        val = row[col_idx]

                # Device Names & Serials
                if 'devices' in cats:
                    if col_name in _DEVICE_COLUMNS:
                        row[col_idx] = device_masker(val)
                        val = row[col_idx]

                # Passwords & Keys
                if 'passwords' in cats:
                    if col_name in _KEY_COLUMNS:
                        if val and val not in ('', 'Pre-Shared Key', 'Certificate'):
                            row[col_idx] = '********'
                            val = row[col_idx]
                    # Also mask any value that looks like a key/secret
                    lower = val.lower()
                    if any(kw in lower for kw in ('password', 'secret', 'key=', 'psk')):
                        row[col_idx] = '********'
                        val = row[col_idx]

                # Certificates
                if 'certificates' in cats:
                    if col_name in _CERT_COLUMNS:
                        row[col_idx] = '****'
                        val = row[col_idx]
                    if col_name == 'Name' and mr.feature_name in _CERT_FEATURES:
                        row[col_idx] = '****'
                        val = row[col_idx]

                # Network Addresses (subnets, AS, interfaces)
                if 'network' in cats:
                    if col_name in _NETWORK_COLUMNS:
                        # For interface names like ethernet1/1, mask them
                        if col_name in ('Interfaces', 'Interface', 'Tunnel Interface'):
                            row[col_idx] = re.sub(
                                r'(ethernet|ae|tunnel|loopback|vlan)\d+[/.\d]*',
                                lambda m: m.group(0)[:len(m.group(0).rstrip('0123456789/.'))] + 'x/x',
                                val, flags=re.IGNORECASE
                            )
                        elif col_name == 'Name' and mr.feature_name in _NETWORK_NAME_FEATURES:
                            row[col_idx] = re.sub(
                                r'(ethernet|ae|tunnel|loopback|vlan)\d+[/.\d]*',
                                lambda m: m.group(0)[:len(m.group(0).rstrip('0123456789/.'))] + 'x/x',
                                val, flags=re.IGNORECASE
                            )
                        else:
                            row[col_idx] = _mask_ip(val)
                        val = row[col_idx]

        # Also mask the summary field
        if 'ip_addresses' in cats and mr.summary:
            mr.summary = _mask_ip(mr.summary)
        if 'hostnames' in cats and mr.summary:
            mr.summary = _mask_fqdn(mr.summary)

        masked.append(mr)

    return masked
