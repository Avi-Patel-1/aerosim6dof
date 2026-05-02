import { Copy, FileJson, FolderOpen, Gauge, Play, Search, SlidersHorizontal, Tags, Wrench } from "lucide-react";
import { useMemo, useState } from "react";
import {
  examplesGalleryCategories,
  examplesGalleryDifficulties,
  examplesGalleryTags,
  filterExamplesGallery,
  groupExamplesByCategory,
  type ExamplesGalleryActionPayload,
  type ExamplesGalleryCard
} from "../examplesGallery";

export type ExamplesGalleryPayloadCallback = (payload: ExamplesGalleryActionPayload, card: ExamplesGalleryCard) => void | Promise<void>;

export type ExamplesGalleryProps = {
  cards: ExamplesGalleryCard[];
  selectedId?: string | null;
  onOpen?: (card: ExamplesGalleryCard) => void;
  onClone?: (card: ExamplesGalleryCard) => void;
  onRun?: (card: ExamplesGalleryCard) => void;
  onEditPayload?: ExamplesGalleryPayloadCallback;
  onClonePayload?: ExamplesGalleryPayloadCallback;
  onRunPayload?: ExamplesGalleryPayloadCallback;
};

export function ExamplesGallery({
  cards,
  selectedId,
  onOpen,
  onClone,
  onRun,
  onEditPayload,
  onClonePayload,
  onRunPayload
}: ExamplesGalleryProps) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [difficulty, setDifficulty] = useState("all");
  const [tag, setTag] = useState("all");
  const [canRun, setCanRun] = useState<"all" | "true" | "false">("all");

  const categories = useMemo(() => examplesGalleryCategories(cards), [cards]);
  const difficulties = useMemo(() => examplesGalleryDifficulties(cards), [cards]);
  const tags = useMemo(() => examplesGalleryTags(cards), [cards]);
  const filteredCards = useMemo(
    () =>
      filterExamplesGallery(cards, {
        query,
        category,
        difficulty,
        tag,
        canRun: canRun === "all" ? "all" : canRun === "true"
      }),
    [cards, canRun, category, difficulty, query, tag]
  );
  const groups = useMemo(() => groupExamplesByCategory(filteredCards), [filteredCards]);
  const groupEntries = Object.entries(groups);

  return (
    <section className="scenario-builder-v2" aria-label="Examples gallery">
      <section className="builder-section" aria-label="Examples gallery filters">
        <div className="section-row">
          <div>
            <p className="eyebrow">Public examples</p>
            <h3>{filteredCards.length} scenario{filteredCards.length === 1 ? "" : "s"}</h3>
          </div>
          <span className="validation-state ok">
            <SlidersHorizontal size={14} />
            Curated
          </span>
        </div>
        <div className="guided-grid scenario-builder-v2-grid">
          <label className="field">
            <span>
              <Search size={14} />
              Search
            </span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="target, gps, stall" />
          </label>
          <label className="field">
            <span>Category</span>
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="all">All categories</option>
              {categories.map((value) => (
                <option value={value} key={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Difficulty</span>
            <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
              <option value="all">All difficulties</option>
              {difficulties.map((value) => (
                <option value={value} key={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Tag</span>
            <select value={tag} onChange={(event) => setTag(event.target.value)}>
              <option value="all">All tags</option>
              {tags.map((value) => (
                <option value={value} key={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Status</span>
            <select value={canRun} onChange={(event) => setCanRun(event.target.value as "all" | "true" | "false")}>
              <option value="all">All statuses</option>
              <option value="true">Runnable</option>
              <option value="false">Review needed</option>
            </select>
          </label>
        </div>
      </section>

      {groupEntries.length === 0 ? (
        <div className="empty-state">No example scenarios match the current filters.</div>
      ) : (
        groupEntries.map(([groupCategory, groupCards]) => (
          <section className="builder-section" key={groupCategory} aria-label={`${groupCategory} examples`}>
            <div className="section-row">
              <div>
                <p className="eyebrow">{groupCategory}</p>
                <h3>{groupCards.length} example{groupCards.length === 1 ? "" : "s"}</h3>
              </div>
            </div>
            <div className="builder-card-grid scenario-builder-v2-card-grid">
              {groupCards.map((card) => (
                <ExampleCard
                  card={card}
                  isSelected={card.id === selectedId}
                  key={card.id}
                  onOpen={onOpen}
                  onClone={onClone}
                  onRun={onRun}
                  onEditPayload={onEditPayload}
                  onClonePayload={onClonePayload}
                  onRunPayload={onRunPayload}
                />
              ))}
            </div>
          </section>
        ))
      )}
    </section>
  );
}

function ExampleCard({
  card,
  isSelected,
  onOpen,
  onClone,
  onRun,
  onEditPayload,
  onClonePayload,
  onRunPayload
}: {
  card: ExamplesGalleryCard;
  isSelected: boolean;
  onOpen?: (card: ExamplesGalleryCard) => void;
  onClone?: (card: ExamplesGalleryCard) => void;
  onRun?: (card: ExamplesGalleryCard) => void;
  onEditPayload?: ExamplesGalleryPayloadCallback;
  onClonePayload?: ExamplesGalleryPayloadCallback;
  onRunPayload?: ExamplesGalleryPayloadCallback;
}) {
  const editEnabled = Boolean(onEditPayload || onOpen);
  const cloneEnabled = Boolean(onClonePayload || onClone);
  const runEnabled = card.can_run && Boolean(onRunPayload || onRun);

  const handleEdit = () => {
    if (onEditPayload) {
      void onEditPayload(card.edit_payload, card);
      return;
    }
    onOpen?.(card);
  };

  const handleClone = () => {
    if (onClonePayload) {
      void onClonePayload(card.clone_payload, card);
      return;
    }
    onClone?.(card);
  };

  const handleRun = () => {
    if (onRunPayload) {
      void onRunPayload(card.run_payload, card);
      return;
    }
    onRun?.(card);
  };

  return (
    <article className="builder-card scenario-builder-v2-card" aria-current={isSelected ? "true" : undefined}>
      <div className="section-row">
        <div>
          <p className="eyebrow">
            {card.id} / {card.difficulty}
          </p>
          <h3>{card.title}</h3>
        </div>
        <span className={`validation-state ${card.can_run ? "ok" : "bad"}`}>{card.can_run ? "Runnable" : "Review"}</span>
      </div>

      <p className="scenario-builder-v2-hint">{card.description}</p>

      <div className="scenario-builder-v2-warning-panel">
        <p>
          <FileJson size={15} />
          <span>{card.scenario_path}</span>
        </p>
        <p>
          <Tags size={15} />
          <span>{card.tags.join(", ") || "untagged"}</span>
        </p>
        <p>
          <Gauge size={15} />
          <span>{card.primary_metrics.join(", ")}</span>
        </p>
        <p>
          <Wrench size={15} />
          <span>{card.suggested_next_edit}</span>
        </p>
      </div>

      <div className="metric-grid" aria-label={`${card.title} expected outputs`}>
        {card.expected_outputs.slice(0, 4).map((output) => (
          <div key={output}>
            <span>Output</span>
            <strong>{output}</strong>
          </div>
        ))}
      </div>

      {card.notes.length > 0 && (
        <div className="scenario-explain">
          <strong>Notes</strong>
          {card.notes.map((note) => (
            <p key={note}>{note}</p>
          ))}
        </div>
      )}

      <div className="editor-actions section-row">
        <button className={isSelected ? "primary-action" : "secondary-action"} type="button" onClick={handleEdit} disabled={!editEnabled}>
          <FolderOpen size={16} />
          Edit
        </button>
        <button className="secondary-action" type="button" onClick={handleClone} disabled={!cloneEnabled}>
          <Copy size={16} />
          Clone
        </button>
        <button className="primary-action" type="button" onClick={handleRun} disabled={!runEnabled}>
          <Play size={16} />
          Run
        </button>
      </div>
    </article>
  );
}
