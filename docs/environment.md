# Environment

Environment configs define terrain and wind. The atmosphere model uses ISA-like layers and gravity varies with altitude. Wind supports steady components, shear, sinusoidal gusts, discrete gusts, and Dryden-like turbulence.

The environment report samples atmosphere, gravity, and deterministic wind versus altitude and writes CSV, JSON, SVG, and HTML outputs.

CLI:

```bash
python3 -m aerosim6dof environment-report --environment examples/environments/gusted_range.json --out outputs/environment_report
```

