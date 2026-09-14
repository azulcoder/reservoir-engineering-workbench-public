"""Independent reference values and loaders used by the test suite.

Everything in this package is *independent of the implementation under test*: closed
forms, published worked examples, values retrieved from an external reference source,
or a second algorithm that shares no code with the first. A value produced by an
earlier run of `reservoir_lab` is a regression check, not an oracle, and does not
belong here.
"""
