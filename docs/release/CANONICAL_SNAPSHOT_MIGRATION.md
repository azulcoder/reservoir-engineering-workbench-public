# Canonical snapshot migration

Proposed, not applied. This records what changes if the committed A3 and A4 snapshots are
regenerated in a pinned canonical environment, and what was measured before deciding.

## Why a migration is needed

The first hosted verification of this repository, run `34852530864` on
`d2ef03316c6a3678af5fcd527e752ca86b4e4880`, failed at `synthetic case reproduction`. The
committed snapshots had been produced on macOS arm64; the runner is Linux x86_64; the gate
is `diff`, which allows no tolerance. A1 reproduced byte for byte. A3 and A4 did not.

That gate was doing its job. The mistake was in what it was asked to prove. Bitwise
equality across different operating systems, C libraries and CPU architectures is not a
property this project has, nor one it should claim: every transcendental function in libm
is permitted a fraction of a unit in the last place, and implementations disagree inside
that allowance. `cases/A1_volumetric_baseline/report.md` already said so — "Nothing here
tests reproducibility across platforms" — but the hosted gate demanded it anyway.

So the repair is not to regenerate the numbers and move on. It is to separate two claims
that had been collapsed into one:

- **Canonical bitwise reproducibility.** Exact byte identity, in one precisely defined
  environment. Still mandatory, still checked with `diff`, still zero tolerance.
- **Cross-platform numerical portability.** On other supported environments, each case's
  own scientific acceptance criteria must pass and the numerical output must stay inside a
  measured envelope. Not byte identity, and never called that.

## The two environments

| | old snapshot environment | proposed canonical environment |
| --- | --- | --- |
| basis | macOS 26.6.2, author's machine | Debian GNU/Linux 12 (bookworm), in a container |
| architecture | arm64 | x86_64 |
| C library | Apple libm | GNU libc 2.36-9+deb12u10 |
| interpreter | CPython 3.13.2 | CPython 3.13.2, GCC 12.2.0 |
| image | none; a laptop | `python:3.13.2-bookworm` |
| image digest | none | `sha256:4165118ed569aff9dbd11d5518199e5379d93bf5bf1cdda62eb13593cf66fb68` |
| how pinned | not pinned | by digest, resolved from the registry and verified twice |

The canonical environment was checked for the one property that makes it canonical: the
job runs each case twice and fails if the two runs disagree. They did not.

It was also checked for fragility. The bare `ubuntu-24.04` runner carries glibc 2.39 and
CPython 3.13.15 — two versions away on both axes — and produces **byte-identical** output
to the container. So the canonical bytes are not balanced on a single image; they are the
Linux x86_64 result.

## What the difference actually is

Not the interpreter. macOS reproduces the committed snapshots on both CPython 3.13.2 and
3.13.15; Linux fails to reproduce them on 3.11, 3.12, 3.13.2 and 3.13.15 alike. The
interpreter axis was ruled out by experiment before the platform axis was blamed.

Sweeping every libm-backed function over 742 arguments found **24 functions** differing
between the two platforms by 1 to 4 units in the last place: `acos`, `acosh`, `asin`,
`asinh`, `atan`, `atan2`, `atanh`, `cos`, `cosh`, `erf`, `erfc`, `exp`, `expm1`, `gamma`,
`lgamma`, `log10`, `log1p`, `pow`, `sin`, `sinh`, `tan`, `tanh`. `lgamma`'s apparent
3.4-million-ULP disagreement is catastrophic cancellation near its root at x=1; the
absolute difference there is 2e-17.

Bit-identical on both platforms: `math.fsum`, `log`, `sqrt`, `hypot`, `fmod`, `remainder`,
and the Mersenne Twister integer stream. That last one matters: it rules out a seeding
difference, a draw-order difference and an iteration-order difference. `random.gauss`
diverges only because it is composed of `cos`, `sin` and `log`.

No single function accounts for the result. Perturbing `lgamma` by the observed amount
moves 18 of A3's 51 divergent leaves and reaches 8e-16 against the 1.7e-08 observed;
`cos` and `sin` reach 3e-11 and 5e-13. The effect is the aggregate of two dozen
one-ULP disagreements, amplified by Monte Carlo sampling and by Newton solvers that stop
at an adjacent floating-point value. That is ordinary floating-point execution, and the
evidence above is why it is not being called a defect.

## What changes

Two case files:

- `cases/A3_uncertainty_experiments/results/summary.json`
- `cases/A4_misleading_fit_counterexample/results/summary.json`

`A1_volumetric_baseline` is unchanged: it reproduces byte for byte on every environment
tested. `A2` has no committed snapshot and is unaffected.

| | A3 | A4 |
| --- | --- | --- |
| differing numeric leaves | 51 | 249 |
| of those, zero-valued diagnostics | 0 | 13 |
| structural changes | 0 | 0 |
| maximum relative difference | 1.6574e-08 | 2.3746e-08 |
| median relative difference | 3.27e-13 | 2.595e-13 |
| acceptance criteria | 10, none changed | 17, none changed |

### The near-zero cases

Two kinds of quantity cannot be judged by relative difference, because their exact value
is zero and the denominator is the noise being measured:

- `max_solver_residual_p_over_z_psia` — a solver convergence residual, observed around
  3e-09 psia against working pressures of 1e3 to 1e4 psia. Two environments disagreeing
  there produced an apparent 21 percent relative difference that carries no information.
- `terminal_relative_error` — error against an exact analytic oracle. One environment
  produced 1.11e-16 where another produced 0.0: a relative difference of exactly 1.0.

Both are compared against declared absolute floors instead, recorded in
`docs/release/portability_envelope.json` together with the scale each should be read
against.

## Effects

**Acceptance criteria.** None changes state, on any environment. A1 reports 26 of 37 true
everywhere, including the same eleven `detected_at_A1_gate` flags that are deliberately
false — that is the study's finding, not a failure. A3 reports 10 of 10 and A4 17 of 17
on the canonical container, on macOS arm64, and on Linux with CPython 3.11, 3.12 and 3.13.

**Thresholds, configuration, inputs, equations.** Unchanged. A tree-wide diff of the
proposed migration touches the two snapshots and the artefacts generated from them, and
nothing else. No page, no README, no case report, no correlation and no threshold differs.

**Figure data.** Seven files change, re-exported through the existing audited exporter,
which reconciled all 43 of its checks against the new snapshots and accepted them. Excluding
the zero-valued residuals, the worst change in any figure datum is 2.3746e-08 relative —
about 21 times below the precision at which this site displays anything.

**Rendered figures.** Five of twelve SVGs change.

| figure | labels changed | worst coordinate shift | visible? |
| --- | --- | --- | --- |
| f03 | 0 of 122 | 1.4e-08 user units | no |
| f04 | 0 of 89 | 1.8e-10 user units | no |
| f07 | 0 of 44 | 1.5e-08 user units | no |
| f09 | 8 of 117, all sha256 digests | — | digests only |
| **f08** | **12 of 93** | 7.7e-06 user units | **yes, in the label text** |

f09's changed labels are the digests of the files that were regenerated, which is what a
provenance figure is supposed to do.

f08 is the exception and the reason this document ends where it does. Its labels print
four solver residuals to four significant figures and eight refinement values to sixteen:

```
2.232e-9 -> 2.530e-9      3.436e-9 -> 2.829e-9
3.030e-9 -> 2.887e-9      3.331e-9 -> 2.973e-9
0.1250255061080150 -> 0.1250255061080281   (and seven similar)
```

The residuals are the zero-valued convergence diagnostics described above, and both values
say the same thing — the solver converged to a few parts in a billion of a psi. The
sixteen-figure values change in their thirteenth significant figure. Neither alters a
conclusion, a ranking, a trend or the geometry of the plot.

But both are numbers a reader can see, and they change. That is a condition the owner
reserved to themselves, so this migration stops here rather than deciding it.

## Interpretation

Nothing in the science moves. What moves is the last few digits of numbers computed by
two dozen libm functions that are permitted to disagree in exactly that place, on a
platform the snapshots were never generated on. The reservoir engineering — the material
balance, the aquifer model, the regression, the acceptance criteria and every conclusion
drawn from them — is identical on every environment tested.
