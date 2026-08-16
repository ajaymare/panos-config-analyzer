"""SD-WAN Advisor recommendation engine.

Scores PAN-OS SD-WAN vs Prisma SD-WAN across 6 weighted categories
based on customer requirements and returns a structured recommendation.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Scoring tables — each maps an input value to (panos_score, prisma_score)
# Scores are 0-10 scale.
# ---------------------------------------------------------------------------

INVESTMENT_SCORES = {
    'yes_panorama': (10, 3),
    'yes_scm':      (6, 8),
    'no':           (5, 7),
}

SECURITY_SCORES = {
    'full_ngfw':        (10, 4),
    'cloud_delivered':  (4, 10),
    'basic':            (6, 7),
}

MANAGEMENT_SCORES = {
    'on_prem':       (10, 2),
    'cloud':         (4, 10),
    'no_preference': (6, 7),
}

SCALE_SCORES = {
    '1-10':    (8, 5),
    '11-50':   (7, 7),
    '51-200':  (6, 8),
    '201-500': (5, 9),
    '500+':    (4, 10),
}

COMPETITOR_SCORES = {
    'fortinet':      (9, 5),
    'cisco_viptela': (6, 7),
    'cisco_meraki':  (4, 9),
    'velocloud':     (4, 9),
    'silver_peak':   (6, 7),
    'none':          (6, 7),
}

# Priority weights — (panos_delta, prisma_delta) per priority
PRIORITY_WEIGHTS = {
    'cost':               (0, 2),
    'sase':               (0, 3),
    'rapid_deploy':       (0, 2),
    'leverage_investment': (3, 0),
    'advanced_threat':    (3, 0),
    'iot_security':       (0, 2),
    'multi_cloud':        (0, 2),
}

# Category definitions — (key, label, weight)
CATEGORIES = [
    ('investment',  'Existing Investment',  3),
    ('security',    'Security Model',       2),
    ('management',  'Management Preference', 2),
    ('scale',       'Deployment Scale',     1),
    ('competitor',  'Competitive Fit',      2),
    ('priorities',  'Priority Alignment',   2),
]

# ---------------------------------------------------------------------------
# Competitive displacement data
# ---------------------------------------------------------------------------

COMPETITOR_LABELS = {
    'fortinet':      'Fortinet SD-WAN',
    'cisco_viptela': 'Cisco SD-WAN (Viptela)',
    'cisco_meraki':  'Cisco Meraki SD-WAN',
    'velocloud':     'VMware VeloCloud',
    'silver_peak':   'HPE Aruba (Silver Peak)',
    'none':          'Greenfield',
}

DISPLACEMENT_DATA = {
    'fortinet': {
        'messages': [
            'Fortinet customers are familiar with firewall-based SD-WAN — PAN-OS SD-WAN offers a natural transition with superior threat prevention',
            'Palo Alto NGFW consistently ranks higher in independent security efficacy tests (NSS Labs, MITRE ATT&CK)',
            'Single-pass architecture provides better performance than Fortinet\'s UTM approach under full security inspection',
            'Panorama provides centralized management comparable to FortiManager with stronger SD-WAN analytics',
        ],
        'objections': [
            ('Fortinet is cheaper', 'Fortinet pricing often excludes advanced threat prevention. When comparing with equivalent security stack (IPS + SSL + WildFire equivalent), PAN-OS TCO is competitive. Additionally, superior threat prevention reduces breach risk and associated costs.'),
            ('We already know FortiOS', 'PAN-OS is consistently rated easiest to manage among enterprise firewalls. Migration tools and professional services ensure a smooth transition.'),
        ],
    },
    'cisco_viptela': {
        'messages': [
            'Cisco Viptela requires separate security appliances — PAN-OS SD-WAN integrates world-class NGFW security natively',
            'Palo Alto offers simpler licensing without Cisco\'s complex DNA/DNAC/vManage stack',
            'PAN-OS SD-WAN + Prisma Access provides a complete SASE solution Cisco still struggles to match',
            'No dependency on Cisco\'s evolving product consolidation strategy (Viptela vs Meraki vs SD-WAN fabric)',
        ],
        'objections': [
            ('We\'re a Cisco shop', 'Many Cisco shops deploy Palo Alto for security while keeping Cisco for routing. SD-WAN is the natural next step to consolidate security + networking.'),
            ('Viptela has more SD-WAN features', 'PAN-OS SD-WAN covers all essential SD-WAN capabilities while adding best-in-class security that Viptela cannot match without bolt-on solutions.'),
        ],
    },
    'cisco_meraki': {
        'messages': [
            'Meraki customers value cloud simplicity — Prisma SD-WAN delivers the same cloud-managed experience with enterprise-grade security',
            'Prisma SD-WAN offers true zero-touch provisioning matching Meraki\'s ease of deployment',
            'Unlike Meraki, Prisma SD-WAN integrates with Prisma Access for complete SASE without additional appliances',
            'Prisma SD-WAN provides granular application-aware routing Meraki SD-WAN cannot match',
        ],
        'objections': [
            ('Meraki is simpler to manage', 'Strata Cloud Manager provides the same cloud-first simplicity as Meraki dashboard while offering enterprise features Meraki lacks.'),
        ],
    },
    'velocloud': {
        'messages': [
            'VMware uncertainty post-Broadcom acquisition makes VeloCloud a risky long-term bet',
            'Prisma SD-WAN offers equivalent cloud-native SD-WAN with Palo Alto\'s proven security ecosystem',
            'Native integration with Prisma Access provides SASE capabilities VeloCloud requires third-party solutions for',
            'Palo Alto\'s continued R&D investment in SASE vs Broadcom\'s cost-cutting approach',
        ],
        'objections': [
            ('VeloCloud has a larger installed base', 'Installed base is shifting as customers evaluate post-acquisition risks. Palo Alto is gaining SD-WAN market share while providing a clear SASE roadmap.'),
        ],
    },
    'silver_peak': {
        'messages': [
            'HPE Aruba SD-WAN (Silver Peak) lacks integrated next-gen security — requires separate security stack',
            'Prisma SD-WAN + Prisma Access delivers WAN optimization AND security in a unified SASE platform',
            'PAN-OS SD-WAN provides stronger branch security than Silver Peak\'s basic zone firewall',
            'Palo Alto offers a clearer cloud/SASE strategy than HPE\'s fragmented networking portfolio',
        ],
        'objections': [
            ('Silver Peak has better WAN optimization', 'SD-WAN has evolved beyond WAN optimization. Modern requirements demand integrated security, which Palo Alto excels at across both PAN-OS and Prisma SD-WAN.'),
        ],
    },
}

# ---------------------------------------------------------------------------
# Feature comparison matrix
# ---------------------------------------------------------------------------

FEATURE_COMPARISON = [
    {
        'feature': 'Architecture',
        'panos': 'SD-WAN built into PA-Series NGFW appliances',
        'prisma': 'Cloud-native SD-WAN on ION appliances',
    },
    {
        'feature': 'Branch Security',
        'panos': 'Full NGFW with IPS, AV, Anti-Spyware, WildFire at every branch',
        'prisma': 'Zone-based firewall + cloud-delivered security via Prisma Access',
    },
    {
        'feature': 'Management',
        'panos': 'On-premises Panorama with SD-WAN plugin',
        'prisma': 'Cloud-managed via Strata Cloud Manager',
    },
    {
        'feature': 'Zero-Touch Provisioning',
        'panos': 'ZTP via Panorama with SD-WAN plugin',
        'prisma': 'Native auto-provisioning — plug in and go',
    },
    {
        'feature': 'SASE Integration',
        'panos': 'Prisma Access integration available (hub model)',
        'prisma': 'Native convergence with Prisma Access and SSE',
    },
    {
        'feature': 'IoT Security',
        'panos': 'Via Enterprise IoT subscription on NGFW',
        'prisma': 'Built-in IoT discovery and security',
    },
    {
        'feature': 'Deployment Speed',
        'panos': 'Template-based deployment via Panorama',
        'prisma': 'Fastest — zero-touch cloud provisioning',
    },
    {
        'feature': 'Scalability',
        'panos': 'Proven at scale with Panorama managing 10,000+ devices',
        'prisma': 'Cloud-native — scales elastically with no controller limits',
    },
    {
        'feature': 'Licensing',
        'panos': 'Per-device SD-WAN license + security subscriptions (or BPLA bundle)',
        'prisma': 'Bandwidth-tiered subscription per ION appliance',
    },
    {
        'feature': 'Typical CPE',
        'panos': 'PA-400/800/1400 (branch), PA-3400/5400 (hub), VM-Series',
        'prisma': 'ION 1200 (branch), ION 2000/3000 (hub), ION 9000 (DC)',
    },
]

# ---------------------------------------------------------------------------
# Next steps templates
# ---------------------------------------------------------------------------

PANOS_NEXT_STEPS = [
    'Use the Sizing Calculator in this toolkit to determine the right PA firewall model for each site',
    'Generate a POC configuration using the POC Config Generator for rapid proof-of-concept deployment',
    'Schedule a PAN-OS SD-WAN demo with the customer focusing on integrated NGFW + SD-WAN capabilities',
    'Review existing PA firewall inventory to identify devices eligible for SD-WAN license activation',
    'Prepare a Bill of Materials with PA hardware, SD-WAN licenses, and security subscriptions',
]

PRISMA_NEXT_STEPS = [
    'Schedule a Prisma SD-WAN demo highlighting cloud management and zero-touch provisioning',
    'Conduct a bandwidth assessment to determine ION appliance sizing per site',
    'Present the Prisma SASE story — SD-WAN + Prisma Access + SSE as a unified platform',
    'Prepare a proposal with bandwidth-tiered licensing for the customer\'s branch footprint',
    'Engage Palo Alto SE team for Prisma SD-WAN POC planning and ION appliance provisioning',
]


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def _score_priorities(priorities: list[str]) -> tuple[int, int]:
    """Score priority alignment. Returns (panos_raw, prisma_raw) on 0-10 scale."""
    if not priorities:
        return (5, 5)

    panos_raw = 0
    prisma_raw = 0
    for p in priorities:
        deltas = PRIORITY_WEIGHTS.get(p, (0, 0))
        panos_raw += deltas[0]
        prisma_raw += deltas[1]

    # Normalize to 0-10 based on max possible score
    max_possible = max(
        sum(d[0] for d in PRIORITY_WEIGHTS.values()),
        sum(d[1] for d in PRIORITY_WEIGHTS.values()),
    )
    if max_possible == 0:
        return (5, 5)

    panos_score = round(panos_raw / max_possible * 10, 1)
    prisma_score = round(prisma_raw / max_possible * 10, 1)

    # Ensure minimum of 1 if any priorities selected
    panos_score = max(panos_score, 1)
    prisma_score = max(prisma_score, 1)

    return (panos_score, prisma_score)


def generate_recommendation(inputs: dict) -> dict:
    """Run the SD-WAN Advisor scoring engine.

    Args:
        inputs: dict with keys:
            existing_pa: str — 'yes_panorama', 'yes_standalone', or 'no'
            competitor: str — 'fortinet', 'cisco_viptela', etc.
            branch_count: str — '1-10', '11-50', etc.
            hub_count: str — '1', '2', '3+'
            security: str — 'full_ngfw', 'cloud_delivered', 'basic'
            management: str — 'on_prem', 'cloud', 'no_preference'
            priorities: list[str] — selected priority keys

    Returns:
        dict with recommendation, scores, analysis, and next steps.
    """
    existing_pa = inputs.get('existing_pa', 'no')
    competitor = inputs.get('competitor', 'none')
    branch_count = inputs.get('branch_count', '11-50')
    security = inputs.get('security', 'full_ngfw')
    management = inputs.get('management', 'no_preference')
    priorities = inputs.get('priorities', [])

    # --- Score each category ---
    category_scores = {}

    inv = INVESTMENT_SCORES.get(existing_pa, (5, 7))
    category_scores['investment'] = {
        'panos': inv[0], 'prisma': inv[1],
        'rationale': _investment_rationale(existing_pa),
    }

    sec = SECURITY_SCORES.get(security, (6, 7))
    category_scores['security'] = {
        'panos': sec[0], 'prisma': sec[1],
        'rationale': _security_rationale(security),
    }

    mgmt = MANAGEMENT_SCORES.get(management, (6, 7))
    category_scores['management'] = {
        'panos': mgmt[0], 'prisma': mgmt[1],
        'rationale': _management_rationale(management),
    }

    scale = SCALE_SCORES.get(branch_count, (7, 7))
    category_scores['scale'] = {
        'panos': scale[0], 'prisma': scale[1],
        'rationale': _scale_rationale(branch_count),
    }

    comp = COMPETITOR_SCORES.get(competitor, (6, 7))
    category_scores['competitor'] = {
        'panos': comp[0], 'prisma': comp[1],
        'rationale': _competitor_rationale(competitor),
    }

    pri = _score_priorities(priorities)
    category_scores['priorities'] = {
        'panos': pri[0], 'prisma': pri[1],
        'rationale': _priorities_rationale(priorities),
    }

    # --- Weighted totals ---
    panos_weighted = 0.0
    prisma_weighted = 0.0
    total_weight = 0

    for key, label, weight in CATEGORIES:
        cs = category_scores[key]
        panos_weighted += cs['panos'] * weight
        prisma_weighted += cs['prisma'] * weight
        total_weight += weight

    # Normalize to 0-100
    panos_score = round(panos_weighted / total_weight * 10, 1)
    prisma_score = round(prisma_weighted / total_weight * 10, 1)

    # --- Recommendation ---
    if panos_score > prisma_score:
        recommendation = 'panos'
        rec_label = 'PAN-OS SD-WAN'
        rec_summary = _panos_summary(inputs)
    elif prisma_score > panos_score:
        recommendation = 'prisma'
        rec_label = 'Prisma SD-WAN'
        rec_summary = _prisma_summary(inputs)
    else:
        recommendation = 'prisma'
        rec_label = 'Prisma SD-WAN'
        rec_summary = 'Both solutions are strong fits for this customer profile. Prisma SD-WAN is recommended as the cloud-first industry trend, but PAN-OS SD-WAN is equally viable.'

    # --- Confidence ---
    score_diff = abs(panos_score - prisma_score)
    max_score = max(panos_score, prisma_score, 1)
    confidence = min(0.5 + (score_diff / max_score) * 0.5, 0.95)
    confidence = round(confidence, 2)

    # --- Competitive displacement ---
    competitive_displacement = None
    if competitor != 'none':
        competitive_displacement = {
            'competitor_label': COMPETITOR_LABELS.get(competitor, competitor),
            **DISPLACEMENT_DATA.get(competitor, {'messages': [], 'objections': []}),
        }

    # --- Feature comparison with dynamic advantage ---
    feature_comparison = []
    for feat in FEATURE_COMPARISON:
        advantage = _determine_advantage(feat['feature'], inputs)
        feature_comparison.append({**feat, 'advantage': advantage})

    # --- Next steps ---
    next_steps = PANOS_NEXT_STEPS[:] if recommendation == 'panos' else PRISMA_NEXT_STEPS[:]

    return {
        'recommendation': recommendation,
        'rec_label': rec_label,
        'rec_summary': rec_summary,
        'confidence': confidence,
        'panos_score': panos_score,
        'prisma_score': prisma_score,
        'category_scores': category_scores,
        'categories': CATEGORIES,
        'feature_comparison': feature_comparison,
        'competitive_displacement': competitive_displacement,
        'next_steps': next_steps,
        'inputs': inputs,
    }


# ---------------------------------------------------------------------------
# Rationale helpers
# ---------------------------------------------------------------------------

def _investment_rationale(existing_pa: str) -> str:
    if existing_pa == 'yes_panorama':
        return 'Customer has PA firewalls managed by Panorama — SD-WAN is a license activation, maximizing existing investment'
    if existing_pa == 'yes_scm':
        return 'Customer already uses Strata Cloud Manager — cloud-managed PA firewalls align well with Prisma SD-WAN\'s cloud-native approach'
    return 'No existing Palo Alto investment — both solutions start on equal footing; Prisma offers simpler cloud onboarding'


def _security_rationale(security: str) -> str:
    if security == 'full_ngfw':
        return 'Full NGFW at every branch is PAN-OS SD-WAN\'s core value — integrated IPS, AV, WildFire without additional appliances'
    if security == 'cloud_delivered':
        return 'Cloud-delivered security aligns with Prisma SD-WAN + Prisma Access for a unified SASE approach'
    return 'Basic firewall needs can be met by either solution; Prisma offers cost advantage with simpler branch CPE'


def _management_rationale(management: str) -> str:
    if management == 'on_prem':
        return 'On-premises management preference strongly favors PAN-OS SD-WAN with Panorama'
    if management == 'cloud':
        return 'Cloud management preference aligns with Prisma SD-WAN\'s Strata Cloud Manager'
    return 'No management preference — both options available; cloud management trend slightly favors Prisma'


def _scale_rationale(branch_count: str) -> str:
    if branch_count in ('1-10', '11-50'):
        return 'Smaller deployments are well-served by PAN-OS SD-WAN with manageable Panorama overhead'
    if branch_count in ('51-200',):
        return 'Mid-size deployments work well with either solution'
    return 'Large-scale deployments benefit from Prisma SD-WAN\'s cloud-native auto-provisioning and simplified operations'


def _competitor_rationale(competitor: str) -> str:
    labels = COMPETITOR_LABELS
    if competitor == 'fortinet':
        return f'Replacing {labels[competitor]} — customer is accustomed to firewall-based SD-WAN, making PAN-OS a natural fit'
    if competitor in ('cisco_meraki', 'velocloud'):
        return f'Replacing {labels[competitor]} — customer expects cloud-managed simplicity, aligning with Prisma SD-WAN'
    if competitor == 'cisco_viptela':
        return f'Replacing {labels[competitor]} — controller-based model; both solutions are viable alternatives'
    if competitor == 'silver_peak':
        return f'Replacing {labels[competitor]} — Prisma offers similar cloud approach with stronger security integration'
    return 'Greenfield deployment — no competitive displacement considerations'


def _priorities_rationale(priorities: list[str]) -> str:
    if not priorities:
        return 'No specific priorities selected — neutral impact on recommendation'
    labels = {
        'cost': 'Cost Optimization',
        'sase': 'SASE / Zero Trust',
        'rapid_deploy': 'Rapid Deployment',
        'leverage_investment': 'Leverage Existing Investment',
        'advanced_threat': 'Advanced Threat Prevention',
        'iot_security': 'IoT Security',
        'multi_cloud': 'Multi-Cloud Connectivity',
    }
    selected = [labels.get(p, p) for p in priorities]
    panos_favored = [p for p in priorities if PRIORITY_WEIGHTS.get(p, (0, 0))[0] > 0]
    prisma_favored = [p for p in priorities if PRIORITY_WEIGHTS.get(p, (0, 0))[1] > 0]

    if len(panos_favored) > len(prisma_favored):
        return f'Selected priorities ({", ".join(selected)}) lean toward PAN-OS SD-WAN strengths'
    if len(prisma_favored) > len(panos_favored):
        return f'Selected priorities ({", ".join(selected)}) align with Prisma SD-WAN capabilities'
    return f'Selected priorities ({", ".join(selected)}) are balanced across both solutions'


def _determine_advantage(feature: str, inputs: dict) -> str:
    """Determine which product has the advantage for a given feature based on inputs."""
    security = inputs.get('security', 'full_ngfw')
    management = inputs.get('management', 'no_preference')
    priorities = inputs.get('priorities', [])

    if feature == 'Branch Security':
        return 'panos' if security == 'full_ngfw' else 'prisma'
    if feature == 'Management':
        return 'panos' if management == 'on_prem' else ('prisma' if management == 'cloud' else 'neutral')
    if feature == 'SASE Integration':
        return 'prisma' if 'sase' in priorities else 'neutral'
    if feature == 'IoT Security':
        return 'prisma' if 'iot_security' in priorities else 'neutral'
    if feature == 'Deployment Speed':
        return 'prisma' if 'rapid_deploy' in priorities else 'neutral'
    if feature == 'Zero-Touch Provisioning':
        return 'prisma'
    if feature == 'Licensing':
        return 'prisma' if 'cost' in priorities else 'neutral'
    return 'neutral'


def _panos_summary(inputs: dict) -> str:
    """Generate a summary paragraph for PAN-OS SD-WAN recommendation."""
    parts = ['PAN-OS SD-WAN is the recommended solution for this customer.']
    if inputs.get('existing_pa') == 'yes_panorama':
        parts.append('The existing Palo Alto firewall investment can be extended with SD-WAN license activation, minimizing new hardware costs.')
    if inputs.get('security') == 'full_ngfw':
        parts.append('The requirement for full NGFW security at every branch is PAN-OS SD-WAN\'s core strength.')
    if inputs.get('management') == 'on_prem':
        parts.append('On-premises Panorama management aligns with the customer\'s operational model.')
    return ' '.join(parts)


def _prisma_summary(inputs: dict) -> str:
    """Generate a summary paragraph for Prisma SD-WAN recommendation."""
    parts = ['Prisma SD-WAN is the recommended solution for this customer.']
    if inputs.get('management') == 'cloud':
        parts.append('Cloud-managed operations via Strata Cloud Manager matches the customer\'s preference for cloud-first infrastructure.')
    if inputs.get('security') == 'cloud_delivered':
        parts.append('Cloud-delivered security through Prisma Access integration provides comprehensive protection without branch NGFW complexity.')
    if 'sase' in inputs.get('priorities', []):
        parts.append('The SASE/Zero Trust priority aligns perfectly with Prisma SD-WAN\'s native Prisma Access convergence.')
    branch = inputs.get('branch_count', '')
    if branch in ('201-500', '500+'):
        parts.append('Zero-touch auto-provisioning will simplify deployment across the large branch footprint.')
    return ' '.join(parts)
