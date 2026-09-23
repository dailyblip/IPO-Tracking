export type Stage = "Pre-pricing" | "Priced";
export type Source = {
  title: string;
  url: string | null;
  date: string;
  excerpt: string;
  locator: string;
};
export type Person = {
  id: string;
  name: string;
  role: string;
  relationship: string;
  shares: number | null;
  percent: number | null;
  source: Source;
  biography: string | null;
};
export type Offering = {
  id: string;
  company: string;
  ticker: string;
  sector: string;
  form: string;
  stage: Stage;
  filed: string;
  pricingDate: string | null;
  value: number | null;
  filingPrice: string | null;
  finalPrice: number | null;
  currentPrice: number | null;
  signals: string[];
  peopleCount: number;
};
export type Detail = Offering & { people: Person[]; source: Source };
export type Match = {
  id: string;
  person: Person;
  company: string;
  offeringId: string;
  stage: Stage;
  matchType: string;
  evidence: Source;
};
export type Event = {
  id: string;
  offeringId: string;
  company: string;
  type: string;
  date: string;
  summary: string;
};
export type Overview = {
  tracked: number;
  filed: number;
  priced: number;
  median: number | null;
  months: { month: string; filed: number; priced: number }[];
  events: Event[];
  updatedAt: string | null;
};
export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
};
