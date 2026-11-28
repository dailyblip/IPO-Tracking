// Fictional fixtures are server-only and never inserted into the research database.
import type {
  Detail,
  Match,
  Overview,
  Page,
  Offering,
  Person,
  Source,
} from "../shared/types.js";
const source = (excerpt: string): Source => ({
  title: "Illustrative prospectus",
  url: null,
  date: "2026-09-18",
  excerpt,
  locator: "Sample management section — not a real filing",
});
const person = (
  id: string,
  name: string,
  role: string,
  relationship: string,
  bio: string,
): Person => ({
  id,
  name,
  role,
  relationship,
  shares: relationship === "Beneficial owner" ? 1250000 : null,
  percent: relationship === "Beneficial owner" ? 4.2 : null,
  source: source(
    `${name} is the ${role.toLowerCase()} of the company${relationship === "Beneficial owner" ? " and a disclosed beneficial owner" : ""}.`,
  ),
  biography: bio,
});
const people: Person[] = [
  person(
    "morgan",
    "Morgan Vale",
    "Chief executive officer",
    "Beneficial owner",
    "Morgan earned a bachelor's degree in engineering from the University of Michigan. Morgan has worked in the automotive industry for twelve years.",
  ),
  person(
    "avery",
    "Avery Chen",
    "Independent director",
    "Director",
    "Avery received an MBA from the University of Michigan and previously worked in investment banking at Goldman Sachs.",
  ),
  person(
    "jordan",
    "Jordan Ellis",
    "Chief executive officer",
    "Beneficial owner",
    "Jordan earned an MBA from Harvard Business School and previously worked at Sequoia Capital.",
  ),
  person(
    "riley",
    "Riley Bennett",
    "Chief financial officer",
    "Executive",
    "Riley previously worked in investment banking at Goldman Sachs.",
  ),
];
const rows: [
  string,
  string,
  string,
  string,
  string,
  string | null,
  number | null,
  string | null,
  number | null,
][] = [
  [
    "northline",
    "Northline Robotics",
    "NLRB",
    "Industrial technology",
    "2026-09-18",
    null,
    180000000,
    "$18–$20",
    null,
  ],
  [
    "arcwell",
    "Arcwell Energy",
    "ARCE",
    "Energy transition",
    "2026-07-03",
    "2026-08-12",
    230000000,
    "$22–$24",
    23,
  ],
  [
    "kestrel",
    "Kestrel Systems",
    "KSTR",
    "Enterprise software",
    "2026-09-10",
    null,
    null,
    "$14–$16",
    null,
  ],
  [
    "meridian",
    "Meridian Health",
    "MDHN",
    "Healthcare",
    "2026-06-08",
    "2026-07-14",
    420000000,
    "$26–$28",
    28,
  ],
  [
    "cobalt",
    "Cobalt Networks",
    "CBNT",
    "Digital infrastructure",
    "2026-08-18",
    null,
    95000000,
    "$12–$14",
    null,
  ],
  [
    "forma",
    "Forma Materials",
    "FRMA",
    "Advanced materials",
    "2026-07-19",
    "2026-08-27",
    160000000,
    "$16–$18",
    16,
  ],
  [
    "atlas",
    "Atlas Water",
    "ATLW",
    "Infrastructure",
    "2026-06-21",
    "2026-07-28",
    310000000,
    "$19–$21",
    20,
  ],
  [
    "solace",
    "Solace Analytics",
    "SLCA",
    "Data & analytics",
    "2026-09-02",
    null,
    120000000,
    "$10–$12",
    null,
  ],
  [
    "lumen",
    "Lumen Aero",
    "LMAR",
    "Aerospace",
    "2026-08-07",
    null,
    650000000,
    "$30–$34",
    null,
  ],
  [
    "everfield",
    "Everfield Foods",
    "EVFD",
    "Consumer",
    "2026-06-15",
    "2026-06-29",
    80000000,
    "$8–$10",
    10,
  ],
  [
    "nimbus",
    "Nimbus Compute",
    "NMBX",
    "Cloud infrastructure",
    "2026-07-23",
    "2026-09-09",
    1100000000,
    "$38–$42",
    40,
  ],
  [
    "strand",
    "Strand Bio",
    "STBD",
    "Life sciences",
    "2026-08-25",
    null,
    null,
    null,
    null,
  ],
];
export const details: Detail[] = rows.map(
  (
    [
      id,
      company,
      ticker,
      sector,
      filed,
      pricingDate,
      value,
      filingPrice,
      finalPrice,
    ],
    i,
  ) => {
    const ps =
      i === 0
        ? [people[0]]
        : i === 2
          ? [people[1]]
          : i === 1
            ? [people[2], people[3]]
            : [];
    return {
      id,
      company,
      ticker,
      sector,
      form: pricingDate ? "424B4" : "S-1/A",
      stage: pricingDate ? "Priced" : "Pre-pricing",
      filed,
      pricingDate,
      value,
      filingPrice,
      finalPrice,
      currentPrice: null,
      signals: [
        pricingDate
          ? "Final offering terms disclosed"
          : filingPrice
            ? "Preliminary range disclosed"
            : "Terms not yet disclosed",
      ],
      peopleCount: ps.length,
      people: ps,
      source: source(
        "Fictional sample for interface review. No investment or ownership claim is made.",
      ),
    };
  },
);
export function publicOffering(d: Detail): Offering {
  const { people, source, ...offering } = d;
  return offering;
}
export function pageOfferings(
  q: string,
  stage: string,
  min: number,
  page: number,
  ids?: string[],
): Page<Offering> {
  const f = details.filter(
    (d) =>
      (!ids || ids.includes(d.id)) &&
      (!stage || stage === d.stage) &&
      (!min || (d.value !== null && d.value >= min)) &&
      `${d.company} ${d.ticker}`.toLowerCase().includes(q.toLowerCase()),
  );
  return {
    items: f.slice((page - 1) * 25, page * 25).map(publicOffering),
    total: f.length,
    page,
    pageSize: 25,
  };
}
export function searchPeople(q: string, relationship: string): Match[] {
  const needle = q.toLocaleLowerCase().trim();
  if (needle.length < 2) return [];
  return details.flatMap((d) =>
    d.people
      .filter(
        (p) =>
          (!relationship || p.relationship === relationship) &&
          `${p.name} ${p.biography}`.toLocaleLowerCase().includes(needle),
      )
      .map((p) => ({
        id: d.id + ":" + p.id,
        person: p,
        company: d.company,
        offeringId: d.id,
        stage: d.stage,
        matchType: p.name.toLowerCase().includes(needle)
          ? "Name match"
          : "Biography text match",
        evidence: source(p.biography!),
      })),
  );
}
export function overview(): Overview {
  const vals = details
    .filter((d) => d.value !== null)
    .map((d) => d.value!)
    .sort((a, b) => a - b);
  const months = ["2026-06", "2026-07", "2026-08", "2026-09"].map((month) => ({
    month,
    filed: details.filter((d) => d.filed.startsWith(month)).length,
    priced: details.filter((d) => d.pricingDate?.startsWith(month)).length,
  }));
  return {
    tracked: details.length,
    filed: details.filter((d) => !d.pricingDate).length,
    priced: details.filter((d) => d.pricingDate).length,
    median: vals.length
      ? (vals[Math.floor((vals.length - 1) / 2)] +
          vals[Math.floor(vals.length / 2)]) /
        2
      : null,
    months,
    events: details
      .flatMap((d) => [
        {
          id: d.id + "-filed",
          offeringId: d.id,
          company: d.company,
          type: "Filed",
          date: d.filed,
          summary: "Initial registration filed",
        },
        ...(d.pricingDate
          ? [
              {
                id: d.id + "-priced",
                offeringId: d.id,
                company: d.company,
                type: "Priced",
                date: d.pricingDate,
                summary: `Offering priced at $${d.finalPrice}`,
              },
            ]
          : []),
      ])
      .sort((a, b) => b.date.localeCompare(a.date))
      .slice(0, 6),
    updatedAt: null,
  };
}
