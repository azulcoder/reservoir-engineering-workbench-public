"""Small, explicit reservoir-engineering calculations for reproducible studies.

Layout
------
``units``, ``errors``, ``validation``, ``numerics``, ``provenance``
    Foundation. Exact conversions and standard conditions, the exception hierarchy,
    shared input guards, bracketed solvers and quadrature, and write-once run records.

``gas_properties``
    Field-unit PVT correlations: pseudocriticals, deviation factor by three
    independent correlations, density, viscosity, compressibility, formation volume
    factor.

``gas``
    Unit-agnostic primitives that require only internally consistent units: formation
    volume factor from a ratio of states, volumetric p/Z regression, relative
    pseudopressure, log-time derivative, interval-rate integration, component balance.

The split is deliberate. Everything in ``gas`` is a ratio or an integral that holds in
any consistent absolute-pressure, absolute-temperature system, and it is documented and
tested that way. Everything in ``gas_properties`` is a correlation fitted in oilfield
units and is meaningless outside them, so those functions name their units in every
parameter. Mixing the two categories in one module is how a unit error becomes
invisible.
"""

__version__ = "0.2.0"

from . import errors, gas, gas_properties, numerics, provenance, units, validation

__all__ = [
    "__version__",
    "errors",
    "gas",
    "gas_properties",
    "numerics",
    "provenance",
    "units",
    "validation",
]
