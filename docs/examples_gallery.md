# Examples Gallery Foundation

The examples gallery exposes curated cards for files under `examples/scenarios`.
It is a data layer and presentational component only; route and Workbench wiring can
be added by the parent integration.

## Backend Helper

Use `aerosim6dof.analysis.examples_gallery.build_examples_gallery()` to scan the
repo examples directory:

```python
from aerosim6dof.analysis.examples_gallery import build_examples_gallery

cards = build_examples_gallery()
```

Each card is a plain dictionary with:

- `id`
- `title`
- `description`
- `scenario_path`
- `tags`
- `difficulty`
- `expected_outputs`
- `primary_metrics`
- `can_run`
- `notes`

The helper has hand-authored metadata for nominal ascent, target/intercept,
terrain/contact, and fault-style scenarios. Unknown scenarios get fallback
metadata from the file name, guidance mode, and available config references.

Malformed JSON, missing directories, unsafe symlink targets, or scenario JSON
with an unexpected shape do not raise from gallery generation. Invalid or weird
files either become non-runnable cards with notes or are skipped when the path
would escape `examples/scenarios`.

## Route Integration

The intended API route can be added beside the existing scenario routes:

```python
@router.get("/examples-gallery")
def examples_gallery() -> list[dict[str, Any]]:
    return build_examples_gallery(EXAMPLES_DIR)
```

Keep `scenario_path` as a repo-relative path such as
`examples/scenarios/nominal_ascent.json`. The UI can use `id` for open/run
requests and `scenario_path` for clone/edit handoff.

## Frontend Integration

`web/src/examplesGallery.ts` defines the shared card type and helpers:

- `filterExamplesGallery(cards, filters)`
- `groupExamplesByDifficulty(cards)`
- `groupExamplesByTag(cards)`
- `examplesGalleryTags(cards)`
- `sortExamplesGalleryCards(cards)`

`web/src/components/ExamplesGallery.tsx` is presentational:

```tsx
<ExamplesGallery
  cards={cards}
  selectedId={selectedScenarioId}
  onOpen={(card) => openScenario(card.id)}
  onClone={(card) => cloneScenario(card.scenario_path)}
  onRun={(card) => runScenario(card.id)}
/>
```

The component reuses existing Workbench classes for sections, cards, badges, and
actions. It does not fetch data or own route state.
