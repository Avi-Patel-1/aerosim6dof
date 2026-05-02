# Scenario Validation Hardening

`aerosim6dof.analysis.scenario_validation.validate_scenario_advisories` adds a
defensive advisory pass for raw scenario JSON and dictionaries. It is additive:
it does not construct a `Scenario`, does not merge config references, does not
change simulation behavior, and does not replace the existing hard validation in
`aerosim6dof.scenario`.

## Result model

Each advisory is a `ScenarioAdvisory` dataclass with these fields:

- `code`: stable advisory identifier.
- `severity`: `info`, `warning`, or `error`.
- `path`: scenario path such as `vehicle_config` or `initial.velocity_mps`.
- `message`: human-readable explanation.
- `suggestion`: optional next action.
- `resolved_reference`: optional resolved file path or unresolved candidate path.

Use `advisory.to_dict()` when an API response needs plain JSON-compatible
objects.

## Integration path

Workbench/API integration can run advisories before or after hard validation:

```python
from aerosim6dof.analysis.scenario_validation import validate_scenario_advisories

advisories = validate_scenario_advisories(raw_scenario, base_dir=scenario_file.parent)
payload = [item.to_dict() for item in advisories]
```

If `base_dir` is provided, scenario references are checked relative to the
scenario file directory first and then relative to the repository root, matching
the current scenario-loader visibility model. If `base_dir` is omitted,
references are reported as unchecked rather than treated as missing.

## Advisory codes

Reference visibility:

- `REFERENCE_RESOLVED`: referenced config file exists.
- `REFERENCE_MISSING`: referenced config file was not found.
- `REFERENCE_UNCHECKED`: reference exists in the scenario but no `base_dir` was
  provided.
- `REFERENCE_NOT_STRING`: reference field is not a path string.
- `SCENARIO_FILE_MISSING`, `SCENARIO_JSON_INVALID`,
  `SCENARIO_TOP_LEVEL_NOT_OBJECT`, `SCENARIO_INPUT_UNSUPPORTED`: defensive input
  parsing problems.

Schema and model visibility:

- `MISSING_VEHICLE_MODEL`, `MISSING_ENVIRONMENT_MODEL`: neither a config
  reference nor inline model was visible.
- `AUTOPILOT_DEFAULTS_IMPLICIT`: autopilot tuning is implicit.
- `MISSING_INITIAL_SECTION`, `INITIAL_POSITION_INVALID`,
  `INITIAL_VELOCITY_INVALID`, `INITIAL_ATTITUDE_INVALID`: initial-state shape
  issues.
- `INTEGRATOR_UNKNOWN`, `GUIDANCE_NOT_OBJECT`, `MISSING_GUIDANCE`,
  `GUIDANCE_MODE_MISSING`, `THROTTLE_OUT_OF_RANGE`,
  `VEHICLE_MASS_INCONSISTENT`, `SENSOR_FAULTS_NOT_LIST`: likely hard-validation
  or review issues.

Why-this-may-fail warnings:

- `TIMESTEP_INVALID`, `TIMESTEP_COARSE`, `DURATION_INVALID`,
  `STEP_COUNT_EXTREME`, `STEP_COUNT_LOW`: integration setup risks.
- `INITIAL_ALTITUDE_BELOW_ZERO`, `INITIAL_ALTITUDE_NEAR_GROUND`,
  `INITIAL_ALTITUDE_EXTREME`, `INITIAL_SPEED_LOW`, `INITIAL_SPEED_HIGH`,
  `INITIAL_SPEED_EXTREME`, `INITIAL_ATTITUDE_STEEP`: initial-condition risks.
- `MISSING_TERMINATION_SECTION`, `TERMINATION_LIMIT_INVALID`,
  `QBAR_LIMIT_MISSING`, `LOAD_LIMIT_MISSING`, `MISSING_OUTPUT_SECTION`: missing
  run-stop or output-review visibility.

Terrain, radar, and engagement compatibility:

- `TERRAIN_DISABLED_WITH_SETTINGS`, `GROUND_CONTACT_WITH_DISABLED_TERRAIN`,
  `RADAR_WITH_DISABLED_TERRAIN`, `TERRAIN_WITH_DISABLED_RADAR`,
  `RADAR_RANGE_INVERTED`: terrain/radar/contact contradictions or review hints.
- `TARGETS_NOT_LIST`, `INTERCEPTORS_NOT_LIST`, `TARGET_NOT_OBJECT`,
  `INTERCEPTOR_NOT_OBJECT`, `TARGET_ID_MISSING`, `TARGET_ID_DUPLICATE`,
  `INTERCEPTORS_WITHOUT_TARGETS`, `INTERCEPTOR_TARGET_MISSING`,
  `INTERCEPTOR_TARGET_UNKNOWN`, `TARGET_GUIDANCE_WITHOUT_TARGET`,
  `TARGET_THRESHOLD_MISSING`: target/interceptor linkage problems.
- `PRESET_ALTITUDE_COMPATIBILITY`, `PRESET_SPEED_COMPATIBILITY`,
  `PRESET_TERRAIN_LOW_ALTITUDE`, `PRESET_ENVIRONMENT_OVERRIDE`: preset-name
  compatibility hints for common scenario authoring mistakes.

These codes are intentionally advisory. Existing scenarios do not need to be
perfect to run, and downstream callers should not fail a simulation solely
because an advisory is present.
