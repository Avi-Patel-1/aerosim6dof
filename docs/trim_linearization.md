# Trim and Linearization

The trim command searches alpha/elevator combinations for a requested speed and altitude. The trim-sweep command repeats that calculation over a grid and writes feasibility metrics, CSV, SVG plots, and HTML.

The linearize command propagates to a requested time and exports numerical A/B matrices using finite differences. The stability and linear-model-report commands convert those matrices into eigenvalue data, matrix norms, ranks, mode labels, and HTML reports.

The `gnc.lqr` module adds NumPy-only controllability checks and discrete LQR synthesis for linear models.

Commands:

```bash
python3 -m aerosim6dof trim --vehicle examples/vehicles/baseline.json --speed 120 --altitude 1000 --out outputs/trim
python3 -m aerosim6dof trim-sweep --vehicle examples/vehicles/baseline.json --speeds 90,120,150 --altitudes 0,1000 --out outputs/trim_sweep
python3 -m aerosim6dof linearize --scenario examples/scenarios/nominal_ascent.json --time 3.0 --out outputs/linearized
python3 -m aerosim6dof stability --linearization outputs/linearized/linearization.json --out outputs/stability
python3 -m aerosim6dof linear-model-report --linearization outputs/linearized/linearization.json --out outputs/linear_model_report
```
