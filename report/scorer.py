"""Deployment maturity scoring for SD-WAN configurations."""
from .excel_generator import FEATURE_CATEGORIES

# All known features (flattened from categories)
ALL_FEATURES = []
for feats in FEATURE_CATEGORIES.values():
    ALL_FEATURES.extend(feats)

TOTAL_FEATURES = len(ALL_FEATURES)

# Maturity levels (adjusted for 23 features)
LEVELS = [
    (16, 'Full', '#1E8449'),
    (8, 'Advanced', '#B9770E'),
    (0, 'Basic', '#2E86C1'),
]

# Recommendations per missing feature
RECOMMENDATIONS = {
    'App-ID Steering': 'Create App-ID based SD-WAN policies for intelligent path selection',
    'Path Quality Metrics': 'Add SLA thresholds (latency, jitter, packet loss) for path selection',
    'Bandwidth Monitoring': 'Define interface profiles with bandwidth limits for WAN link monitoring',
    'Probe Idle Time': 'Configure probe idle time on SD-WAN interface profiles',
    'Failback Hold Time': 'Set failback hold time on SD-WAN interface profiles for link stability',
    'Link Remediation (FEC)': 'Enable Forward Error Correction in traffic distribution profiles',
    'Packet Duplication': 'Enable packet duplication in traffic distribution profiles for reliability',
    'VPN Automation': 'Define VPN clusters with hub/branch topology for SD-WAN overlay',
    'Topologies Supported': 'Configure VPN cluster topologies (full-mesh, hub-spoke)',
    'Hub Capacity': 'Add hub and branch devices to VPN clusters',
    'Prisma Access Hub': 'Configure Panorama connectivity for Prisma Access integration',
    'Sub-Second Failover': 'Enable DIA VPN failover on hub devices for sub-second failover',
    'Tunnel Monitor': 'Enable tunnel monitoring on IPSec tunnels with destination IP probes',
    'Dynamic Routing': 'Enable dynamic routing (BGP/OSPF) and ECMP for path redundancy',
    'BGP AS Control': 'Configure BGP AS numbers on SD-WAN devices',
    'BGP Private AS': 'Enable remove-private-AS for BGP route filtering',
    'BGP Timer Profile': 'Configure BGP graceful restart timers for faster convergence',
    'BGP Security Rule': 'Add BGP security policies per device-group',
    'IPv6 Support': 'Enable OSPFv3 for IPv6 routing support',
    'Multi-VR Support': 'Enable multi-VR support on SD-WAN devices',
    'ADEM Integration': 'Deploy Autonomous DEM for end-to-end application performance visibility',
    'Sub/Agg Interfaces': 'Configure zones, sub-interfaces, and aggregate interfaces',
    'ZTP Support': 'Enable Zero Touch Provisioning for automated device onboarding',
}


def score_config(results):
    """Score a single config's SD-WAN deployment maturity.

    Args:
        results: list of FeatureResult objects for one config

    Returns:
        dict with: score, total, level, level_color, category_scores,
                   enabled_features, missing_features, panorama_managed_features,
                   recommendations
    """
    # Aggregate: feature is enabled if ANY result for that feature is enabled
    feature_status = {}  # True = enabled, False = disabled
    panorama_managed = set()  # Features marked as Panorama-Managed
    for r in results:
        if r.feature_name not in feature_status:
            feature_status[r.feature_name] = False
        if r.enabled:
            feature_status[r.feature_name] = True
        elif r.summary == 'Panorama-Managed':
            panorama_managed.add(r.feature_name)

    # Count enabled features (only those in our known list)
    enabled_features = [f for f in ALL_FEATURES if feature_status.get(f, False)]
    panorama_managed_features = [f for f in ALL_FEATURES
                                  if f in panorama_managed and not feature_status.get(f, False)]
    missing_features = [f for f in ALL_FEATURES
                        if not feature_status.get(f, False) and f not in panorama_managed]

    # Score includes both enabled and panorama-managed (they ARE configured)
    score = len(enabled_features) + len(panorama_managed_features)

    # Determine level
    level = 'Basic'
    level_color = '#2E86C1'
    for threshold, lvl, color in LEVELS:
        if score >= threshold:
            level = lvl
            level_color = color
            break

    # Per-category breakdown
    category_scores = {}
    for cat_name, feats in FEATURE_CATEGORIES.items():
        enabled = sum(1 for f in feats
                      if feature_status.get(f, False) or f in panorama_managed)
        category_scores[cat_name] = {
            'enabled': enabled,
            'total': len(feats),
            'percent': round(enabled / len(feats) * 100) if feats else 0,
            'features': {f: feature_status.get(f, False) for f in feats},
        }

    # Recommendations only for truly missing features (not Panorama-managed)
    recs = [RECOMMENDATIONS.get(f, f'Configure {f}') for f in missing_features]

    return {
        'score': score,
        'total': TOTAL_FEATURES,
        'percent': round(score / TOTAL_FEATURES * 100) if TOTAL_FEATURES else 0,
        'level': level,
        'level_color': level_color,
        'enabled_features': enabled_features,
        'panorama_managed_features': panorama_managed_features,
        'missing_features': missing_features,
        'category_scores': category_scores,
        'recommendations': recs,
    }


def score_configs(configs_data):
    """Score multiple configs and compute comparison analytics.

    Args:
        configs_data: list of dicts with keys: filename, config_type, results

    Returns:
        list of dicts, each with: filename, config_type, scoring (from score_config)
    """
    scored = []
    for cfg in configs_data:
        scoring = score_config(cfg['results'])
        scored.append({
            'filename': cfg['filename'],
            'config_type': cfg['config_type'],
            'scoring': scoring,
            'versions': cfg.get('versions'),
            'results': cfg['results'],
        })

    # Add comparison data if multiple configs
    if len(scored) > 1:
        all_enabled_sets = [
            set(s['scoring']['enabled_features']) | set(s['scoring']['panorama_managed_features'])
            for s in scored
        ]
        common = set.intersection(*all_enabled_sets)
        for i, s in enumerate(scored):
            others = [all_enabled_sets[j] for j in range(len(scored)) if j != i]
            others_union = set.union(*others) if others else set()
            s['scoring']['unique_features'] = list(
                (set(s['scoring']['enabled_features']) | set(s['scoring']['panorama_managed_features']))
                - others_union
            )
        scored[0]['common_features'] = list(common)

    return scored
