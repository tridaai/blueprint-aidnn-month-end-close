"""Trida AI Blueprint — aidnn month-end close, deployed.

The deployment layer around Isotopes AI's aidnn for one workflow:
a multi-entity group's month-end close. Connectors pull source
extracts, a versioned definition pack says what every figure
means, a finance engine behind a port answers the pack's defined
questions, an independent verifier recomputes every figure from
source, and a controller signs — or nobody does.
"""

__version__ = "0.1.0"
