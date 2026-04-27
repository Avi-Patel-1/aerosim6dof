# Stability Analysis

The package exports numerical linear models and includes NumPy-only LQR utilities:

- controllability matrix
- controllability rank
- discrete LQR Riccati iteration
- closed-loop eigenvalue summaries
- eigenvalue map reports
- damping ratio, natural frequency, period, and time constant summaries
- lightweight mode labels for short-period, phugoid, Dutch-roll, spiral, roll-subsidence, and unstable roots

These tools are intentionally lightweight and work with the matrices exported by `linearize`.

Commands:

```bash
python3 -m aerosim6dof linearize --scenario examples/scenarios/nominal_ascent.json --time 3.0 --out outputs/linearized
python3 -m aerosim6dof stability --linearization outputs/linearized/linearization.json --out outputs/stability
python3 -m aerosim6dof linear-model-report --linearization outputs/linearized/linearization.json --out outputs/linear_model_report
```

The mode labels are heuristics based on eigenvalue frequency and dominant state participation. They are intended as a first-pass stability review, not a replacement for aircraft-specific modal analysis.
