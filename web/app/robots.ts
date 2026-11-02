import type { MetadataRoute } from "next";

// This is a public demo, so it should not appear in search results.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", disallow: "/" },
  };
}
