export type ExamplesGalleryDifficulty = "Beginner" | "Intermediate" | "Advanced" | string;

export type ExamplesGalleryCard = {
  id: string;
  title: string;
  description: string;
  scenario_path: string;
  tags: string[];
  difficulty: ExamplesGalleryDifficulty;
  expected_outputs: string[];
  primary_metrics: string[];
  can_run: boolean;
  notes: string[];
};

export type ExamplesGalleryFilters = {
  query?: string;
  tag?: string;
  difficulty?: ExamplesGalleryDifficulty | "all";
  canRun?: boolean | "all";
};

const DIFFICULTY_ORDER: Record<string, number> = {
  Beginner: 0,
  Intermediate: 1,
  Advanced: 2
};

export function sortExamplesGalleryCards(cards: ExamplesGalleryCard[]): ExamplesGalleryCard[] {
  return [...cards].sort((a, b) => {
    const difficultyDelta = (DIFFICULTY_ORDER[a.difficulty] ?? 9) - (DIFFICULTY_ORDER[b.difficulty] ?? 9);
    if (difficultyDelta !== 0) {
      return difficultyDelta;
    }
    return a.title.localeCompare(b.title);
  });
}

export function examplesGalleryTags(cards: ExamplesGalleryCard[]): string[] {
  const tags = new Set<string>();
  cards.forEach((card) => card.tags.forEach((tag) => tags.add(tag)));
  return Array.from(tags).sort((a, b) => a.localeCompare(b));
}

export function groupExamplesByDifficulty(cards: ExamplesGalleryCard[]): Record<string, ExamplesGalleryCard[]> {
  return sortExamplesGalleryCards(cards).reduce<Record<string, ExamplesGalleryCard[]>>((groups, card) => {
    const key = card.difficulty || "Unspecified";
    groups[key] = groups[key] ?? [];
    groups[key].push(card);
    return groups;
  }, {});
}

export function groupExamplesByTag(cards: ExamplesGalleryCard[]): Record<string, ExamplesGalleryCard[]> {
  return sortExamplesGalleryCards(cards).reduce<Record<string, ExamplesGalleryCard[]>>((groups, card) => {
    const tags = card.tags.length ? card.tags : ["untagged"];
    tags.forEach((tag) => {
      groups[tag] = groups[tag] ?? [];
      groups[tag].push(card);
    });
    return groups;
  }, {});
}

export function filterExamplesGallery(cards: ExamplesGalleryCard[], filters: ExamplesGalleryFilters = {}): ExamplesGalleryCard[] {
  const query = filters.query?.trim().toLowerCase() ?? "";
  return sortExamplesGalleryCards(
    cards.filter((card) => {
      if (filters.tag && filters.tag !== "all" && !card.tags.includes(filters.tag)) {
        return false;
      }
      if (filters.difficulty && filters.difficulty !== "all" && card.difficulty !== filters.difficulty) {
        return false;
      }
      if (filters.canRun !== undefined && filters.canRun !== "all" && card.can_run !== filters.canRun) {
        return false;
      }
      if (!query) {
        return true;
      }
      const searchable = [
        card.id,
        card.title,
        card.description,
        card.scenario_path,
        card.difficulty,
        ...card.tags,
        ...card.expected_outputs,
        ...card.primary_metrics,
        ...card.notes
      ]
        .join(" ")
        .toLowerCase();
      return searchable.includes(query);
    })
  );
}
