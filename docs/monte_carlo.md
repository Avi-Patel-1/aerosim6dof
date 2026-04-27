# Monte Carlo and Campaigns

Monte Carlo runs perturb a validated base scenario with repeatable seeds. Current built-in dispersions are loaded mass and steady wind.

Campaign sweeps run Cartesian products over dotted scenario fields:

```bash
python3 -m aerosim6dof sweep --scenario examples/scenarios/nominal_ascent.json --set guidance.throttle=0.82,0.86 --set guidance.pitch_command_deg=10,14 --out outputs/sweep
```

Campaign outputs include per-run artifacts, `campaign_summary.json`, `campaign_index.csv`, and `campaign_report.html`.

