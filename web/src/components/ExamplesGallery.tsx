import { Copy, FileJson, FolderOpen, Gauge, Play, Tags } from "lucide-react";
import { useMemo } from "react";
import { groupExamplesByDifficulty, type ExamplesGalleryCard } from "../examplesGallery";

export type ExamplesGalleryProps = {
  cards: ExamplesGalleryCard[];
  selectedId?: string | null;
  onOpen?: (card: ExamplesGalleryCard) => void;
  onClone?: (card: ExamplesGalleryCard) => void;
  onRun?: (card: ExamplesGalleryCard) => void;
};

export function ExamplesGallery({ cards, selectedId, onOpen, onClone, onRun }: ExamplesGalleryProps) {
  const groups = useMemo(() => groupExamplesByDifficulty(cards), [cards]);
  const groupEntries = Object.entries(groups);

  return (
    <section className="scenario-builder-v2" aria-label="Examples gallery">
      {groupEntries.length === 0 ? (
        <div className="empty-state">No example scenarios found.</div>
      ) : (
        groupEntries.map(([difficulty, groupCards]) => (
          <section className="builder-section" key={difficulty} aria-label={`${difficulty} examples`}>
            <div className="section-row">
              <div>
                <p className="eyebrow">{difficulty}</p>
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
  onRun
}: {
  card: ExamplesGalleryCard;
  isSelected: boolean;
  onOpen?: (card: ExamplesGalleryCard) => void;
  onClone?: (card: ExamplesGalleryCard) => void;
  onRun?: (card: ExamplesGalleryCard) => void;
}) {
  return (
    <article className="builder-card scenario-builder-v2-card" aria-current={isSelected ? "true" : undefined}>
      <div className="section-row">
        <div>
          <p className="eyebrow">{card.id}</p>
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
        <button className={isSelected ? "primary-action" : "secondary-action"} type="button" onClick={() => onOpen?.(card)} disabled={!onOpen}>
          <FolderOpen size={16} />
          Open
        </button>
        <button className="secondary-action" type="button" onClick={() => onClone?.(card)} disabled={!onClone}>
          <Copy size={16} />
          Clone
        </button>
        <button className="primary-action" type="button" onClick={() => onRun?.(card)} disabled={!card.can_run || !onRun}>
          <Play size={16} />
          Run
        </button>
      </div>
    </article>
  );
}
