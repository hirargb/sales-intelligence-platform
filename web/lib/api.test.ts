import { beforeEach, describe, expect, it, vi } from "vitest";
import { getCompanies } from "./api";

function lastCall() {
  const mock = globalThis.fetch as unknown as { mock: { calls: unknown[][] } };
  return mock.mock.calls[0];
}

describe("getCompanies query building", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn(
      async () =>
        new Response(JSON.stringify({ total: 0, items: [] }), { status: 200 })
    ) as unknown as typeof fetch;
  });

  it("encodes every filter and always sets limit and offset", async () => {
    await getCompanies({
      market: "US",
      q: "acme corp",
      minNeed: 60,
      highConfidence: true,
      sort: "need_score",
      limit: 10,
      offset: 20,
    });
    const [url, opts] = lastCall();
    const u = String(url);
    expect(u).toContain("/api/companies?");
    expect(u).toContain("market=US");
    expect(u).toContain("q=acme+corp");
    expect(u).toContain("min_need=60");
    expect(u).toContain("high_confidence=true");
    expect(u).toContain("sort=need_score");
    expect(u).toContain("limit=10");
    expect(u).toContain("offset=20");
    expect((opts as RequestInit).cache).toBe("no-store");
  });

  it("omits empty filters but keeps default limit and offset", async () => {
    await getCompanies({});
    const u = String(lastCall()[0]);
    expect(u).not.toContain("market=");
    expect(u).not.toContain("q=");
    expect(u).not.toContain("high_confidence=");
    expect(u).toContain("limit=50");
    expect(u).toContain("offset=0");
  });

  it("drops a zero minimum need", async () => {
    await getCompanies({ minNeed: 0 });
    expect(String(lastCall()[0])).not.toContain("min_need=");
  });
});
