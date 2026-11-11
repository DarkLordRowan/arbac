"""Publication-correct name for legacy levin_sidi_m.

E.J. Weniger (1989), Eqs. (9.2-5), (9.2-6), (9.4-1).
This is NOT an additional mathematical algorithm. Legacy registration preserved.
"""
from arbacc.core.registry import register
from arbacc.accelerators.additional_transforms import LevinSidiM


@register('accelerators', 'weniger_m')
class WenigerM(LevinSidiM):

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Weniger, Nonlinear Sequence Transformations (1989 dissertation; 2003 arXiv version)', 'url': 'https://arxiv.org/abs/math/0306302', 'locator': 'sections 9.2 and 9.4', 'relation': 'alias', 'implementation_note': 'Published-name alias for legacy levin_sidi_m; not an independent algorithm.'}
    name = display_name = 'weniger_m'
