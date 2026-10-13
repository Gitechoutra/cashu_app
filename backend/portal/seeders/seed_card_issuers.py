"""Seeds the configurable list of credit-card issuing banks. Idempotent: inserts
missing codes only and never overwrites rows an admin has edited.

sort_order < 9 marks a bank as "Popular" (shown as the top grid in the app);
everything else appears in the alphabetical "All banks" list."""

from portal import db
from portal.models.card_issuers import CardIssuers

POPULAR_CUTOFF = 9

ISSUERS = [
    # code,       name,                                   short,          gradient,              sort
    ('SBI',       'SBI Card',                             'SBI Card',     '#1A4F9C', '#0B2A5B',  0),
    ('HDFC',      'HDFC Bank',                            'HDFC',         '#0F3D7A', '#071E3D',  1),
    ('ICICI',     'ICICI Bank',                           'ICICI',        '#A3361F', '#4F1408',  2),
    ('AXIS',      'Axis Bank',                            'Axis',         '#97144D', '#4A0726',  3),
    ('KOTAK',     'Kotak Mahindra Bank',                  'Kotak',        '#C8102E', '#5C0612',  4),
    ('AMEX',      'American Express',                     'Amex',         '#2E77BB', '#123A63',  5),
    ('IDFC',      'IDFC FIRST Bank',                      'IDFC FIRST',   '#9C1D26', '#3D0A0E',  6),
    ('INDUSIND',  'IndusInd Bank',                        'IndusInd',     '#7A2E2E', '#2E1010',  7),
    ('YES',       'YES Bank',                             'YES Bank',     '#00518F', '#00264A',  8),
    ('AU',        'AU Small Finance Bank',                'AU Bank',      '#6B2C91', '#2E1240',  20),
    ('RBL',       'RBL Bank',                             'RBL',          '#21409A', '#0E1D4A',  21),
    ('HSBC',      'HSBC India',                           'HSBC',         '#B5121B', '#3B0509',  22),
    ('SC',        'Standard Chartered',                   'StanChart',    '#0072AA', '#00334D',  23),
    ('BOB',       'BOBCARD (Bank of Baroda)',             'BOBCARD',      '#E35205', '#6B2400',  24),
    ('FEDERAL',   'Federal Bank',                         'Federal',      '#1C3F94', '#0B1A40',  25),
    # Further card-issuing banks (alphabetical list in the app)
    ('UNION',     'Union Bank of India',                  'Union Bank',   '#D71920', '#0B3B8C',  100),
    ('CANARA',    'Canara Bank',                          'Canara',       '#00A0E3', '#F7A600',  100),
    ('PNB',       'Punjab National Bank',                 'PNB',          '#A2123B', '#5C0A22',  100),
    ('BOI',       'Bank of India',                        'Bank of India','#F47920', '#0B3B8C',  100),
    ('INDIAN',    'Indian Bank',                          'Indian Bank',  '#0B3B8C', '#F7A600',  100),
    ('CENTRAL',   'Central Bank of India',                'Central Bank', '#C8102E', '#0B3B8C',  100),
    ('IOB',       'Indian Overseas Bank',                 'IOB',          '#0B3B8C', '#061E48',  100),
    ('UCO',       'UCO Bank',                             'UCO Bank',     '#0B3B8C', '#F7A600',  100),
    ('BOM',       'Bank of Maharashtra',                  'Bank of Maharashtra', '#0B5AA6', '#062E57', 100),
    ('PSB',       'Punjab & Sind Bank',                   'Punjab & Sind','#0E7A3C', '#F2C500',  100),
    ('IDBI',      'IDBI Bank',                            'IDBI',         '#00836C', '#F58220',  100),
    ('SIB',       'South Indian Bank',                    'South Indian', '#B5121B', '#5C0612',  100),
    ('KVB',       'Karur Vysya Bank',                     'KVB',          '#0E7A3C', '#E5D50B',  100),
    ('CUB',       'City Union Bank',                      'City Union',   '#B5121B', '#0B3B8C',  100),
    ('KTK',       'Karnataka Bank',                       'Karnataka Bank','#6B2C91', '#2E1240', 100),
    ('TMB',       'Tamilnad Mercantile Bank',             'TMB',          '#0B3B8C', '#061E48',  100),
    ('JKB',       'J&K Bank',                             'J&K Bank',     '#B5121B', '#0E7A3C',  100),
    ('DCB',       'DCB Bank',                             'DCB',          '#00A0E3', '#0B3B8C',  100),
    ('CSB',       'CSB Bank',                             'CSB',          '#0B3B8C', '#F47920',  100),
    ('DBS',       'DBS Bank India',                       'DBS',          '#E31837', '#5C0612',  100),
    ('SARASWAT',  'Saraswat Co-operative Bank',           'Saraswat',     '#B5121B', '#5C0612',  100),
    ('SBM',       'SBM Bank India',                       'SBM',          '#0B3B8C', '#00A0E3',  100),
    ('EQUITAS',   'Equitas Small Finance Bank',           'Equitas',      '#0B3B8C', '#D71920',  100),
    ('UTKARSH',   'Utkarsh Small Finance Bank',           'Utkarsh',      '#6B2C91', '#F47920',  100),
    ('SURYODAY',  'Suryoday Small Finance Bank',          'Suryoday',     '#F47920', '#0B3B8C',  100),
    ('BANDHAN',   'Bandhan Bank',                         'Bandhan',      '#E1251B', '#7A0F0A',  100),
    ('DHANLAXMI', 'Dhanlaxmi Bank',                       'Dhanlaxmi',    '#6B1F5E', '#2E0C28',  100),
    ('OTHER',     'Other bank',                           'Other',        '#334155', '#0F172A',  999),
]


def seed_card_issuers():
    existing = {c for (c,) in db.session.query(CardIssuers.code).all()}
    added = 0
    for code, name, short, g1, g2, order in ISSUERS:
        if code in existing:
            continue
        db.session.add(CardIssuers(code=code, name=name, short_name=short, gradient_from=g1,
                                   gradient_to=g2, sort_order=order))
        added += 1
    db.session.commit()
    return added
