import { test } from "node:test";
import assert from "node:assert/strict";
import { createApp } from "../server/app.js";
import { overview, searchPeople } from "../server/demo.js";
async function withServer(
  config: Parameters<typeof createApp>[0],
  fn: (url: string) => Promise<void>,
) {
  const s = createApp(config).listen(0, "127.0.0.1");
  await new Promise<void>((r) => s.once("listening", r));
  try {
    const addr = s.address() as { port: number };
    await fn(`http://127.0.0.1:${addr.port}`);
  } finally {
    await new Promise<void>((r) => s.close(() => r()));
  }
}
test("production refuses sample mode", () =>
  assert.throws(
    () => createApp({ demo: true, production: true }),
    /forbidden/,
  ));
test("unconfigured staging fails closed", () =>
  withServer({ demo: false }, async (url) => {
    for (const path of [
      "/api/offerings",
      "/api/people/search?q=test",
      "/api/saved",
    ])
      assert.equal((await fetch(url + path)).status, 503);
  }));
test("configured staging denies anonymous data access before contacting upstream", () =>
  withServer(
    { demo: false, url: "https://example.supabase.co", key: "publishable" },
    async (url) => {
      for (const path of [
        "/api/overview",
        "/api/offerings",
        "/api/people/search?q=test",
        "/api/saved",
      ])
        assert.equal((await fetch(url + path)).status, 401);
    },
  ));
test("sample search is person-specific, evidence-bearing and supports phrase/name queries", () => {
  assert.equal(searchPeople("University of Michigan", "").length, 2);
  assert.equal(
    searchPeople("University of Michigan", "Beneficial owner").length,
    1,
  );
  assert.equal(searchPeople("Harvard Business School", "Director").length, 0);
  assert.equal(searchPeople("Morgan Vale", "")[0].offeringId, "northline");
  for (const m of searchPeople("Goldman Sachs", "")) {
    assert.ok(m.evidence.excerpt.includes("Goldman Sachs"));
    assert.ok(m.person.source.excerpt);
    assert.equal(m.evidence.url, null);
  }
});
test("sample API is paginated, filters saved IDs before paging and rejects invalid input", () =>
  withServer({ demo: true }, async (url) => {
    const p = await (
      await fetch(url + "/api/offerings?saved=1&ids=northline")
    ).json();
    assert.equal(p.total, 1);
    assert.equal(p.items[0].id, "northline");
    assert.equal(p.items[0].people, undefined);
    assert.equal((await fetch(url + "/api/offerings?min=-1")).status, 400);
    assert.equal((await fetch(url + "/api/people/search?q=x")).status, 400);
    assert.equal((await fetch(url + "/api/offerings/missing")).status, 404);
    const r = await fetch(url + "/api/overview");
    assert.equal(r.headers.get("cache-control"), "no-store");
  }));
test("overview is derived from the same fixture corpus", () => {
  const o = overview();
  assert.equal(o.tracked, o.filed + o.priced);
  assert.equal(
    o.months.reduce((n, m) => n + m.filed, 0),
    o.tracked,
  );
  assert.equal(
    o.months.reduce((n, m) => n + m.priced, 0),
    o.priced,
  );
});
