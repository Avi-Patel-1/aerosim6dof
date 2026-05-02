# Mission Campaign Designer

The browser-side mission campaign designer is split into a pure helper module and a React component:

- `web/src/campaignDesigner.ts` owns draft state types, defaults, UI-level validation, plan summaries, and API payload construction.
- `web/src/components/CampaignDesigner.tsx` renders the designer with existing workbench classes and emits a ready-to-run payload through `onRunPlan`.

No backend API changes are required. The helper returns the same `{ action, params }` shape consumed by `runAction(action, params)` and `startJob(action, params)`.

## Supported Plans

| Plan | Action | Params |
| --- | --- | --- |
| Batch | `batch` | `{}` |
| Monte Carlo | `monte_carlo` | `scenario_id`, `samples`, `seed`, `mass_sigma_kg`, `wind_sigma_mps` |
| Parameter sweep | `sweep` | `scenario_id`, `parameter`, `values`, `max_runs` |
| Fault campaign | `fault_campaign` | `scenario_id`, `faults`, `max_runs` |

`values` is emitted as a typed array where numeric entries are numbers and other entries remain strings. `faults` is emitted as a string array; an empty array intentionally lets the API run every built-in fault.

## Validation

The browser validation catches obvious setup issues before work is queued:

- Missing or unknown scenario IDs when a scenario-backed plan is selected.
- Monte Carlo samples outside the API-supported `1..50` range.
- Non-integer seeds and negative dispersions.
- Empty or malformed sweep parameter paths.
- Empty sweep values, sweep expansions above `max_runs`, and `max_runs` outside `1..100`.
- Unknown fault names and fault expansions above `max_runs`.

Validation is deliberately limited to UI-level checks. Scenario physics, config resolution, and deeper model validity still belong to the existing simulator validation and job execution paths.

## Integration

The component is designed to be mounted by the workbench campaigns tab without changing `web/src/api.ts`:

```tsx
<CampaignDesigner
  scenarios={scenarios}
  capabilities={capabilities}
  busyAction={busyAction}
  onRunPlan={({ action, params }) => runTool(action, params, "reports")}
/>
```

The component also exposes `onDraftChange` for previews, tests, or future persistence:

```tsx
onDraftChange={(draft, payload, validation) => {
  console.log(draft.kind, payload.action, validation.valid);
}}
```

## Helper API

```ts
import {
  buildCampaignActionPayload,
  createDefaultCampaignDraft,
  summarizeCampaignPlan,
  validateCampaignDraft
} from "./campaignDesigner";

const draft = createDefaultCampaignDraft("nominal_ascent");
const validation = validateCampaignDraft(draft, { scenarios, faultOptions });
const payload = buildCampaignActionPayload(draft);
const summary = summarizeCampaignPlan(draft, scenarios, faultOptions);
```

`summary.rows` is intended for readable plan review in the UI. `payload` is the object to pass to the existing action/job API.
