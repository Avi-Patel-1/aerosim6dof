# Examples Gallery

The examples gallery exposes curated cards for checked-in files under
`examples/scenarios`. It is deliberately independent of `outputs/`: gallery
generation reads scenario JSON only, so a fresh clone can render the gallery
before any runs, reports, or plots exist.

Route and Workbench wiring live outside this production pass. The backend helper
and frontend component are safe to use from an API route, a local page, or tests.

## Backend Helper

Use `aerosim6dof.analysis.examples_gallery.build_examples_gallery()` to scan the
repo examples directory:

```python
from aerosim6dof.analysis.examples_gallery import build_examples_gallery

cards = build_examples_gallery()
```

Each card is a plain dictionary with stable, scenario-file-derived IDs:

- `id`
- `title`
- `category`
- `description`
- `scenario_path`
- `tags`
- `difficulty`
- `expected_outputs`
- `primary_metrics`
- `suggested_next_edit`
- `clone_payload`
- `edit_payload`
- `run_payload`
- `can_run`
- `notes`

Curated metadata is provided for the public examples checked into
`examples/scenarios`, including baseline, environment, guidance, engagement,
sensors/navigation, aerodynamics, atmosphere, control-authority, and failure
injection cases. Unknown scenario files still get fallback metadata inferred
from the filename and JSON fields.

Malformed JSON, missing directories, unsafe symlink targets, or scenario JSON
with an unexpected shape do not raise from gallery generation. Invalid or weird
files either become non-runnable cards with notes or are skipped when the path
would escape `examples/scenarios`.

## Payloads

Cards include one-click handoff payloads without requiring live run outputs:

```json
{
  "clone_payload": {
    "action": "clone_example",
    "source_scenario_id": "nominal_ascent",
    "scenario_path": "examples/scenarios/nominal_ascent.json",
    "suggested_name": "nominal_ascent_copy",
    "scenario_patch": { "name": "nominal_ascent_copy" }
  },
  "edit_payload": {
    "action": "edit_example",
    "scenario_id": "nominal_ascent",
    "scenario_path": "examples/scenarios/nominal_ascent.json",
    "focus": "Clone it, then change one pitch-program breakpoint..."
  },
  "run_payload": {
    "action": "run",
    "params": { "scenario_id": "nominal_ascent" }
  }
}
```

Keep `scenario_path` repo-relative. Use `id` for current scenario APIs and the
payloads for future clone/edit/run route wiring.

## Frontend Integration

`web/src/examplesGallery.ts` defines the shared card type and helpers:

- `filterExamplesGallery(cards, filters)`
- `groupExamplesByCategory(cards)`
- `groupExamplesByDifficulty(cards)`
- `groupExamplesByTag(cards)`
- `examplesGalleryCategories(cards)`
- `examplesGalleryDifficulties(cards)`
- `examplesGalleryTags(cards)`
- `sortExamplesGalleryCards(cards)`

`web/src/components/ExamplesGallery.tsx` renders built-in search, category,
difficulty, tag, and runnable-status filters. Existing card callbacks still work:

```tsx
<ExamplesGallery
  cards={cards}
  selectedId={selectedScenarioId}
  onOpen={(card) => openScenario(card.id)}
  onClone={(card) => cloneScenario(card.scenario_path)}
  onRun={(card) => runScenario(card.id)}
/>
```

New route integrations can use payload callbacks instead:

```tsx
<ExamplesGallery
  cards={cards}
  onEditPayload={(payload) => editExample(payload)}
  onClonePayload={(payload) => cloneExample(payload)}
  onRunPayload={(payload) => runTool(payload.action, payload.params ?? {})}
/>
```

The component does not fetch data or own route state.
