# Evidence cards

Each card pairs a method with its sources, its validity window, its known failure modes and a set
of independent check values, then records an adversarial review that tried to refute it. The review
is part of the card, not a separate approval step: a card whose corrections are unread is not
evidence.

None of these cards is a substitute for the primary source. Where an item could not be verified
against a retrievable source it is listed as unverified, and the implementation either avoids it or
marks it in the code.

| Card | Review verdict | Corrections | Unverified | Size |
|---|---|---|---|---|
| [Gas deviation factor correlations](evidence/zfactor.md) | `SOUND_WITH_CORRECTIONS` | 10 | 12 | 75 kB |
| [Gas viscosity and compressibility](evidence/viscosity.md) | `SOUND_WITH_CORRECTIONS` | 11 | 10 | 84 kB |
| [Gas material balance](evidence/matbal.md) | `SOUND_WITH_CORRECTIONS` | 9 | 9 | 93 kB |
| [Aquifer influx models](evidence/aquifer.md) | `SOUND_WITH_CORRECTIONS` | 8 | 8 | 96 kB |
| [Real-gas pseudopressure](evidence/pseudopressure.md) | `SOUND_WITH_CORRECTIONS` | 12 | 10 | 98 kB |
| [Pressure derivative diagnostics](evidence/derivative.md) | `SOUND_WITH_CORRECTIONS` | 12 | 11 | 92 kB |
| [Regression and uncertainty for p/Z](evidence/statistics.md) | `SOUND_WITH_CORRECTIONS` | 11 | 14 | 96 kB |
| [Tooling pins and repository facts](evidence/provenance.md) | `SOUND_WITH_CORRECTIONS` | 7 | 7 | 72 kB |
