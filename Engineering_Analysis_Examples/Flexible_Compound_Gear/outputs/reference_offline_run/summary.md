# Flexible Compound Gear – Co-Simulation Summary

## Data provenance

- Source: Offline surrogate packaged with the repository

## Reference scenario KPIs

- Peak surface temperature: 353.4 °C
- Peak ring bulk temperature: 108.9 °C
- Duty >260/315/370 °C: 50.21% / 24.07% / 0.00%
- Final wear depth: 0.0 µm
- Mean wear rate: 0.102 µm/hr
- Time to 50% damping: 1074.00 h
- Verdict: VALID

## Sweep verdict distribution

- INVALID: 12
- NEEDS_REVIEW: 6
- VALID: 30

## Recommended levers

- Increase oil-side convection (larger jet, higher flow, lower oil inlet temperature).
- Reduce friction coefficient via coatings or surface finishing to limit flash temperature.
- Revisit torsional compliance to reduce slip energy while maintaining torque capacity.

## Parameter sweeps

| μ_lub | h_oil [kW/m²-K] | N scale | Peak T_surface [°C] | Duty >315 °C | Wear @ end [µm] | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| 0.06 | 1.0 | 0.50 | 214.5 | 0.00% | 0.0 | INVALID |
| 0.06 | 1.0 | 1.00 | 319.7 | 2.07% | 0.0 | VALID |
| 0.06 | 1.0 | 1.50 | 362.1 | 32.37% | 0.0 | VALID |
| 0.06 | 2.5 | 0.50 | 214.3 | 0.00% | 0.0 | INVALID |
| 0.06 | 2.5 | 1.00 | 319.6 | 2.07% | 0.0 | VALID |
| 0.06 | 2.5 | 1.50 | 358.7 | 23.65% | 0.0 | VALID |
| 0.06 | 5.0 | 0.50 | 214.1 | 0.00% | 0.0 | INVALID |
| 0.06 | 5.0 | 1.00 | 319.3 | 1.66% | 0.0 | NEEDS_REVIEW |
| 0.06 | 5.0 | 1.50 | 356.9 | 21.99% | 0.0 | VALID |
| 0.06 | 10.0 | 0.50 | 213.6 | 0.00% | 0.0 | INVALID |
| 0.06 | 10.0 | 1.00 | 318.8 | 0.83% | 0.0 | NEEDS_REVIEW |
| 0.06 | 10.0 | 1.50 | 356.0 | 21.16% | 0.0 | VALID |
| 0.12 | 1.0 | 0.50 | 233.1 | 0.00% | 0.0 | INVALID |
| 0.12 | 1.0 | 1.00 | 354.4 | 25.31% | 0.0 | VALID |
| 0.12 | 1.0 | 1.50 | 362.5 | 45.64% | 0.0 | VALID |
| 0.12 | 2.5 | 0.50 | 232.9 | 0.00% | 0.0 | INVALID |
| 0.12 | 2.5 | 1.00 | 353.9 | 25.31% | 0.0 | VALID |
| 0.12 | 2.5 | 1.50 | 359.0 | 43.98% | 0.0 | VALID |
| 0.12 | 5.0 | 0.50 | 232.7 | 0.00% | 0.0 | INVALID |
| 0.12 | 5.0 | 1.00 | 353.4 | 24.07% | 0.0 | VALID |
| 0.12 | 5.0 | 1.50 | 358.4 | 42.74% | 0.0 | VALID |
| 0.12 | 10.0 | 0.50 | 232.1 | 0.00% | 0.0 | INVALID |
| 0.12 | 10.0 | 1.00 | 352.0 | 23.65% | 0.0 | VALID |
| 0.12 | 10.0 | 1.50 | 357.5 | 40.25% | 0.0 | VALID |
| 0.20 | 1.0 | 0.50 | 257.8 | 0.00% | 0.0 | INVALID |
| 0.20 | 1.0 | 1.00 | 361.9 | 24.48% | 0.0 | VALID |
| 0.20 | 1.0 | 1.50 | 362.9 | 55.19% | 0.0 | VALID |
| 0.20 | 2.5 | 0.50 | 257.7 | 0.00% | 0.0 | INVALID |
| 0.20 | 2.5 | 1.00 | 358.6 | 24.07% | 0.0 | VALID |
| 0.20 | 2.5 | 1.50 | 359.3 | 54.77% | 0.0 | VALID |
| 0.20 | 5.0 | 0.50 | 257.4 | 0.00% | 0.0 | INVALID |
| 0.20 | 5.0 | 1.00 | 356.8 | 23.24% | 0.0 | VALID |
| 0.20 | 5.0 | 1.50 | 358.4 | 54.77% | 0.0 | VALID |
| 0.20 | 10.0 | 0.50 | 256.9 | 0.00% | 0.0 | INVALID |
| 0.20 | 10.0 | 1.00 | 356.0 | 22.41% | 0.0 | VALID |
| 0.20 | 10.0 | 1.50 | 357.5 | 53.94% | 0.0 | VALID |
| 0.35 | 1.0 | 0.50 | 304.2 | 0.00% | 0.0 | NEEDS_REVIEW |
| 0.35 | 1.0 | 1.00 | 362.6 | 47.72% | 0.0 | VALID |
| 0.35 | 1.0 | 1.50 | 362.5 | 49.79% | 0.0 | VALID |
| 0.35 | 2.5 | 0.50 | 304.1 | 0.00% | 0.0 | NEEDS_REVIEW |
| 0.35 | 2.5 | 1.00 | 359.1 | 46.47% | 0.0 | VALID |
| 0.35 | 2.5 | 1.50 | 359.0 | 49.79% | 0.0 | VALID |
| 0.35 | 5.0 | 0.50 | 303.8 | 0.00% | 0.0 | NEEDS_REVIEW |
| 0.35 | 5.0 | 1.00 | 358.4 | 44.81% | 0.0 | VALID |
| 0.35 | 5.0 | 1.50 | 358.3 | 49.79% | 0.0 | VALID |
| 0.35 | 10.0 | 0.50 | 303.3 | 0.00% | 0.0 | NEEDS_REVIEW |
| 0.35 | 10.0 | 1.00 | 357.5 | 43.57% | 0.0 | VALID |
| 0.35 | 10.0 | 1.50 | 357.5 | 49.79% | 0.0 | VALID |
