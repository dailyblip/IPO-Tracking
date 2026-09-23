import express, {
  type Request,
  type Response,
  type NextFunction,
} from "express";
import helmet from "helmet";
import { rateLimit } from "express-rate-limit";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { details, overview, pageOfferings, searchPeople } from "./demo.js";
export type Config = {
  demo: boolean;
  url?: string;
  key?: string;
  production?: boolean;
};
export function createApp(config: Config) {
  if (config.demo && config.production)
    throw new Error("Sample mode is forbidden in production");
  const app = express();
  app.disable("x-powered-by");
  app.use(
    helmet({
      contentSecurityPolicy: config.production
        ? {
            directives: {
              defaultSrc: ["'self'"],
              scriptSrc: ["'self'"],
              styleSrc: ["'self'", "'unsafe-inline'"],
              connectSrc: ["'self'", ...(config.url ? [config.url] : [])],
              imgSrc: ["'self'", "data:"],
              objectSrc: ["'none'"],
              frameAncestors: ["'none'"],
            },
          }
        : false,
    }),
  );
  app.use(express.json({ limit: "16kb" }));
  app.use(
    "/api",
    rateLimit({
      windowMs: 60000,
      limit: 120,
      standardHeaders: "draft-8",
      legacyHeaders: false,
    }),
  );
  app.use("/api", (_req, res, next) => {
    res.set("Cache-Control", "no-store");
    next();
  });
  app.get("/api/config", (_req, res) =>
    res.json({
      demo: config.demo,
      url: config.url || null,
      key: config.key || null,
      configured: !!(config.url && config.key),
    }),
  );
  app.get("/api/health", (_req, res) =>
    res.json({ status: "ok", mode: config.demo ? "sample" : "staging" }),
  );
  app.use("/api", async (req: Request, res: Response, next: NextFunction) => {
    try {
      if (config.demo) {
        next();
        return;
      }
      if (!config.url || !config.key) {
        res
          .status(503)
          .json({ error: "The staging connection has not been configured." });
        return;
      }
      const token = req.headers.authorization?.match(/^Bearer (.+)$/)?.[1];
      if (!token) {
        res
          .status(401)
          .json({ error: "Please sign in to access the research workspace." });
        return;
      }
      const client = createClient(config.url, config.key, {
        global: { headers: { Authorization: `Bearer ${token}` } },
        auth: { persistSession: false, autoRefreshToken: false },
      });
      const { data, error } = await client.auth.getUser(token);
      if (error || !data.user || data.user.is_anonymous) {
        res
          .status(401)
          .json({ error: "Your session has expired. Please sign in again." });
        return;
      }
      const access = await client.rpc("ipo_roll_has_access");
      if (access.error) {
        res.status(503).json({ error: "Unable to verify workspace access." });
        return;
      }
      if (!access.data) {
        res
          .status(403)
          .json({
            error:
              "Your account has not been granted access to the staging workspace.",
          });
        return;
      }
      res.locals.client = client;
      next();
    } catch {
      res
        .status(503)
        .json({ error: "Authentication is temporarily unavailable." });
    }
  });
  const rpc = async (
    res: Response,
    name: string,
    args: Record<string, unknown> = {},
  ) => {
    const c = res.locals.client as SupabaseClient;
    const { data, error } = await c.rpc(name, args);
    if (error) {
      res
        .status(503)
        .json({ error: "Research data is temporarily unavailable." });
      return;
    }
    if (name === "ipo_roll_detail" && !data) {
      res.status(404).json({ error: "Offering not found." });
      return;
    }
    res.json(data);
  };
  const query = (req: Request, key: string) =>
    typeof req.query[key] === "string" ? req.query[key].trim() : "";
  app.get("/api/overview", async (_req, res) =>
    config.demo ? res.json(overview()) : rpc(res, "ipo_roll_overview"),
  );
  app.get("/api/offerings", async (req, res) => {
    const q = query(req, "q"),
      stage = query(req, "stage"),
      min = Number(query(req, "min") || 0),
      page = Number(query(req, "page") || 1);
    if (
      q.length > 160 ||
      !["", "Priced", "Pre-pricing"].includes(stage) ||
      !Number.isFinite(min) ||
      min < 0 ||
      !Number.isInteger(page) ||
      page < 1 ||
      page > 1000
    ) {
      res.status(400).json({ error: "Invalid filters." });
      return;
    }
    const onlySaved = query(req, "saved") === "1";
    const ids = query(req, "ids").split(",").filter(Boolean).slice(0, 200);
    return config.demo
      ? res.json(
          pageOfferings(q, stage, min, page, onlySaved ? ids : undefined),
        )
      : rpc(res, "ipo_roll_offerings", {
          p_query: q,
          p_stage: stage,
          p_min: min,
          p_page: page,
          p_saved: onlySaved,
        });
  });
  app.get("/api/offerings/:id", async (req, res) => {
    if (config.demo) {
      const d = details.find((d) => d.id === req.params.id);
      res.status(d ? 200 : 404).json(d || { error: "Offering not found." });
      return;
    }
    if (!/^[0-9a-f-]{36}$/.test(String(req.params.id))) {
      res.status(400).json({ error: "Invalid offering." });
      return;
    }
    return rpc(res, "ipo_roll_detail", { p_id: req.params.id });
  });
  app.get("/api/people/search", async (req, res) => {
    const q = query(req, "q"),
      relationship = query(req, "relationship");
    const page = Number(query(req, "page") || 1);
    if (
      q.length < 2 ||
      q.length > 160 ||
      !["", "Beneficial owner", "Director", "Executive"].includes(
        relationship,
      ) ||
      !Number.isInteger(page) ||
      page < 1 ||
      page > 1000
    ) {
      res
        .status(400)
        .json({ error: "Enter 2–160 characters and valid filters." });
      return;
    }
    if (config.demo) {
      const found = searchPeople(q, relationship);
      res.json({
        items: found.slice((page - 1) * 25, page * 25),
        total: found.length,
        page,
        pageSize: 25,
      });
      return;
    }
    return rpc(res, "ipo_roll_people_search", {
      p_query: q,
      p_relationship: relationship,
      p_page: page,
    });
  });
  // Sample saves are browser-local, never shared between visitors or stored in Supabase.
  app.get("/api/saved", async (_req, res) =>
    config.demo ? res.json({ ids: [] }) : rpc(res, "ipo_roll_saved"),
  );
  app.put("/api/saved/:id", async (req, res) => {
    if (config.demo) {
      res
        .status(400)
        .json({ error: "Sample saves are local to your browser." });
      return;
    }
    if (
      !/^[0-9a-f-]{36}$/.test(String(req.params.id)) ||
      typeof req.body?.saved !== "boolean"
    ) {
      res.status(400).json({ error: "Invalid save request." });
      return;
    }
    return rpc(res, "ipo_roll_set_saved", {
      p_id: req.params.id,
      p_saved: req.body.saved,
    });
  });
  app.use("/api", (_req, res) =>
    res.status(404).json({ error: "Endpoint not found." }),
  );
  app.use((err: unknown, _req: Request, res: Response, next: NextFunction) => {
    if (res.headersSent) {
      next(err);
      return;
    }
    res.status(500).json({ error: "The request could not be completed." });
  });
  return app;
}
