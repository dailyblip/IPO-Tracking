import { createApp } from "./app.js";
import express from "express";
import { resolve } from "node:path";
const production = process.env.NODE_ENV === "production";
const app = createApp({
  demo: process.env.IPO_ROLL_DEMO === "1",
  url: process.env.SUPABASE_URL,
  key: process.env.SUPABASE_PUBLISHABLE_KEY,
  production,
});
if (production) {
  app.use(express.static(resolve("dist"), { index: false }));
  app.get("/{*path}", (_req, res) => res.sendFile(resolve("dist/index.html")));
} else {
  const { createServer } = await import("vite");
  const vite = await createServer({
    server: { middlewareMode: true },
    appType: "spa",
  });
  app.use(vite.middlewares);
}
app.listen(
  Number(process.env.PORT || 4100),
  process.env.HOST || "127.0.0.1",
  () =>
    console.log(
      `IPO Roll available on port ${process.env.PORT || 4100} (${process.env.IPO_ROLL_DEMO === "1" ? "sample" : "staging"} mode)`,
    ),
);
