import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import {
  Activity,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ArrowUpRight,
  BarChart3,
  Bookmark,
  BookOpen,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  Command,
  Database,
  ExternalLink,
  FileText,
  Filter,
  GripVertical,
  Home,
  Layers,
  Loader2,
  LogOut,
  Menu,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Users,
  X,
} from "lucide-react";
import type {
  Detail,
  Match,
  Offering,
  Overview,
  Page,
  Person,
  Source,
} from "../shared/types";
import "@fontsource-variable/manrope";
import "@fontsource-variable/dm-sans";
import "./style.css";
const money = (v: number | null) =>
  v === null
    ? "—"
    : v >= 1e9
      ? `$${(v / 1e9).toFixed(2).replace(/0$/, "")}B`
      : v >= 1e6
        ? `$${(v / 1e6).toFixed(0)}M`
        : `$${v.toLocaleString()}`;
const date = (v: string | null) =>
  v
    ? new Date(v + "T12:00:00Z").toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "UTC",
      })
    : "—";
const price = (v: number | null) => (v === null ? "—" : `$${v.toFixed(2)}`);
const nav = [
  ["overview", "Overview", Home],
  ["activity", "IPO Activity", BarChart3],
  ["people", "People Search", Users],
  ["saved", "Saved / Watchlist", Bookmark],
  ["methodology", "Methodology", BookOpen],
] as const;
type View = (typeof nav)[number][0];
let client: SupabaseClient | null = null;
let demo = false;
class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = client
    ? (await client.auth.getSession()).data.session?.access_token
    : null;
  const r = await fetch("/api" + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    cache: "no-store",
  });
  const data = await r.json();
  if (!r.ok) throw new ApiError(data.error || "Unable to load data.", r.status);
  return data;
}
function Logo() {
  return (
    <div className="brand">
      <div className="brand-mark">
        <Layers size={23} />
      </div>
      <span>
        IPO Roll<span className="brand-dot">.</span>
      </span>
    </div>
  );
}
function Badge({ stage }: { stage: string }) {
  return (
    <span className={"badge " + (stage === "Priced" ? "blue" : "teal")}>
      {stage}
    </span>
  );
}
function CompanyIcon({ name }: { name: string }) {
  return (
    <span className={"company-icon tone-" + (name.charCodeAt(0) % 4)}>
      {name.slice(0, 1)}
    </span>
  );
}
function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty">
      <Search size={29} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
function SourceLink({ source }: { source: Source }) {
  return source.url && source.url.startsWith("https://") ? (
    <a className="text-link" href={source.url} target="_blank" rel="noreferrer">
      View source <ExternalLink size={13} />
    </a>
  ) : (
    <span className="muted small">
      Illustrative source · no external document
    </span>
  );
}
function Highlight({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const at = text.toLowerCase().indexOf(query.toLowerCase());
  return at < 0 ? (
    <>{text}</>
  ) : (
    <>
      {text.slice(0, at)}
      <mark>{text.slice(at, at + query.length)}</mark>
      {text.slice(at + query.length)}
    </>
  );
}
function App() {
  const [view, setView] = useState<View>(
    (location.hash.slice(1) as View) || "overview",
  );
  const [config, setConfig] = useState<{
    demo: boolean;
    configured: boolean;
  } | null>(null);
  const [session, setSession] = useState(false);
  const [fatal, setFatal] = useState("");
  const [mobile, setMobile] = useState(false);
  const [global, setGlobal] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [saved, setSaved] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    fetch("/api/config")
      .then((r) => r.json())
      .then(async (c) => {
        demo = c.demo;
        setConfig(c);
        if (c.demo) {
          setSession(true);
          try {
            setSaved(
              JSON.parse(localStorage.getItem("ipo-roll-demo-saved") || "[]"),
            );
          } catch {}
          return;
        }
        if (c.configured) {
          client = createClient(c.url, c.key);
          const { data } = await client.auth.getSession();
          setSession(!!data.session);
          client.auth.onAuthStateChange((_e, s) => setSession(!!s));
        }
      })
      .catch(() =>
        setFatal("Unable to connect to the workspace. Refresh to retry."),
      );
  }, []);
  useEffect(() => {
    if (session && !demo)
      api<{ ids: string[] }>("/saved")
        .then((d) => setSaved(d.ids))
        .catch((e) => setFatal(e.message));
  }, [session]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
      if (e.key === "Escape") {
        setSelected(null);
        setMobile(false);
      }
    };
    const onHash = () => {
      const v = location.hash.slice(1);
      if (nav.some((n) => n[0] === v)) setView(v as View);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("hashchange", onHash);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("hashchange", onHash);
    };
  }, []);
  function go(v: View) {
    setView(v);
    location.hash = v;
    setMobile(false);
    setSelected(null);
  }
  async function toggle(id: string) {
    const next = saved.includes(id)
      ? saved.filter((x) => x !== id)
      : [...saved, id];
    try {
      if (demo)
        localStorage.setItem("ipo-roll-demo-saved", JSON.stringify(next));
      else
        await api("/saved/" + id, {
          method: "PUT",
          body: JSON.stringify({ saved: next.includes(id) }),
        });
      setSaved(next);
      setNotice(
        next.includes(id)
          ? "Added to your watchlist"
          : "Removed from your watchlist",
      );
      setTimeout(() => setNotice(""), 2200);
    } catch (e) {
      setNotice((e as Error).message);
    }
  }
  if (fatal)
    return (
      <div className="full-state">
        <Logo />
        <ShieldCheck />
        <h2>Workspace unavailable</h2>
        <p>{fatal}</p>
        <button className="button primary" onClick={() => location.reload()}>
          Try again
        </button>
        {client && (
          <button
            className="button"
            onClick={async () => {
              await client?.auth.signOut();
              location.reload();
            }}
          >
            Sign out
          </button>
        )}
      </div>
    );
  if (!config)
    return (
      <div className="full-state">
        <Logo />
        <Loader2 className="spin" />
        <p>Opening your research workspace…</p>
      </div>
    );
  if (!session) return <Login configured={config.configured} />;
  return (
    <div className="shell">
      <aside className={"sidebar " + (mobile ? "open" : "")}>
        <Logo />
        <div className="workspace-label">RESEARCH WORKSPACE</div>
        <nav aria-label="Main navigation">
          {nav.map(([key, label, Icon]) => (
            <button
              key={key}
              className={"nav-item " + (view === key ? "active" : "")}
              onClick={() => go(key)}
              aria-current={view === key ? "page" : undefined}
            >
              <Icon size={19} />
              <span>{label}</span>
              {key === "saved" && saved.length > 0 && (
                <small>{saved.length}</small>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="source-status">
            <ShieldCheck size={17} />
            <div>
              Evidence comes first<span>Public sources. Clear provenance.</span>
            </div>
          </div>
          <button
            className="profile"
            onClick={() =>
              config.demo
                ? setNotice("Sample workspace · saves stay in this browser")
                : client?.auth.signOut()
            }
          >
            <span className="avatar">{config.demo ? "DR" : "IR"}</span>
            <span>
              {config.demo ? "Design review" : "Research workspace"}
              <small>
                {config.demo ? "Sample data only" : "Authenticated access"}
              </small>
            </span>
            {!config.demo && <LogOut size={16} />}
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button
            className="icon-button mobile-toggle"
            aria-label="Toggle navigation"
            onClick={() => setMobile(!mobile)}
          >
            <Menu size={20} />
          </button>
          <form
            className="global-search"
            onSubmit={(e) => {
              e.preventDefault();
              go("activity");
              setRevision((x) => x + 1);
            }}
          >
            <Search size={16} />
            <input
              ref={searchRef}
              aria-label="Search companies"
              placeholder="Search companies or tickers…"
              value={global}
              onChange={(e) => setGlobal(e.target.value)}
            />
            <kbd>⌘ K</kbd>
          </form>
          <div className="topbar-right">
            <span className="environment">
              <i />
              {config.demo ? "SAMPLE WORKSPACE" : "STAGING WORKSPACE"}
            </span>
            <button
              className="icon-button"
              aria-label="Read methodology"
              onClick={() => go("methodology")}
            >
              <BookOpen size={18} />
            </button>
          </div>
        </header>
        <main>
          {view === "overview" && (
            <OverviewScreen
              open={setSelected}
              navigate={go}
              saved={saved}
              toggle={toggle}
            />
          )}{" "}
          {(view === "activity" || view === "saved") && (
            <ActivityScreen
              key={view + revision}
              initialQuery={global}
              onlySaved={view === "saved"}
              saved={saved}
              toggle={toggle}
              open={setSelected}
            />
          )}{" "}
          {view === "people" && <PeopleScreen open={setSelected} />}{" "}
          {view === "methodology" && <Methodology />}
        </main>
        <footer>
          <span>
            <ShieldCheck size={13} /> Public-source research. Evidence at every
            step.
          </span>
          <span>
            {config.demo
              ? "Fictional examples for design review"
              : "Private research workspace"}{" "}
            · IPO Roll
          </span>
        </footer>
      </div>
      {selected && (
        <DetailDrawer
          id={selected}
          close={() => setSelected(null)}
          saved={saved.includes(selected)}
          toggle={() => toggle(selected)}
        />
      )}{" "}
      {notice && (
        <div className="toast" role="status">
          <Check size={17} />
          {notice}
          <button
            aria-label="Dismiss notification"
            onClick={() => setNotice("")}
          >
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
function Login({ configured }: { configured: boolean }) {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <div className="login">
      <div className="login-brand">
        <Logo />
        <div className="eyebrow">THE IPO RESEARCH WORKSPACE</div>
        <h1>
          See the offering.
          <br />
          Know the people.
          <br />
          <em>Follow the evidence.</em>
        </h1>
        <p>Public-source intelligence, designed for deeper research.</p>
      </div>
      <form
        className="login-card"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          const result = await client?.auth.signInWithPassword({
            email,
            password,
          });
          if (result?.error)
            setError("Unable to sign in. Check your email and password.");
          setBusy(false);
        }}
      >
        <ShieldCheck className="teal-text" />
        <h2>Welcome to IPO Roll</h2>
        <p>Sign in to your research workspace.</p>
        {configured ? (
          <>
            <label>
              Email address
              <input
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            <button className="button primary" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
              <ArrowRight size={16} />
            </button>
            <p className="small muted">Staging access is invite-only.</p>
          </>
        ) : (
          <p>The staging connection is awaiting configuration.</p>
        )}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </form>
    </div>
  );
}
function OverviewScreen({
  open,
  navigate,
  saved,
  toggle,
}: {
  open: (id: string) => void;
  navigate: (v: View) => void;
  saved: string[];
  toggle: (id: string) => void;
}) {
  const [data, setData] = useState<Overview | null>(null),
    [rows, setRows] = useState<Offering[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api<Overview>("/overview"), api<Page<Offering>>("/offerings")])
      .then(([a, b]) => {
        setData(a);
        setRows(b.items.slice(0, 5));
      })
      .catch((e) => setError(e.message));
  }, []);
  if (error) return <Empty title="Research unavailable" text={error} />;
  if (!data) return <Loading />;
  const max = Math.max(
    4,
    Math.ceil(
      Math.max(1, ...data.months.flatMap((m) => [m.filed, m.priced])) / 4,
    ) * 4,
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">YOUR RESEARCH, IN PERSPECTIVE</div>
          <h1>
            The IPO landscape,
            <br className="small-break" /> in focus
            <span className="teal-text">.</span>
          </h1>
          <p>Track offerings. Explore people. Follow the evidence.</p>
        </div>
        <button className="button" onClick={() => navigate("activity")}>
          Explore IPO activity
          <ArrowUpRight size={16} />
        </button>
      </div>
      <div className="stats">
        {[
          [
            Layers,
            "IPOs tracked",
            data.tracked,
            "Qualifying operating companies",
          ],
          [FileText, "Pre-pricing", data.filed, "Active filing stage"],
          [CheckCheck, "Priced", data.priced, "Final terms confirmed"],
          [
            BarChart3,
            "Median offering size",
            money(data.median),
            "Known base offering values",
          ],
        ].map(([Icon, label, value, sub], i) => {
          const I = Icon as typeof Layers;
          return (
            <div className="stat" key={i}>
              <div>
                <span>{String(label)}</span>
                <I size={18} />
              </div>
              <strong>{String(value)}</strong>
              <small>{String(sub)}</small>
            </div>
          );
        })}
      </div>
      <div className="overview-grid">
        <section className="panel chart-panel">
          <div className="panel-title">
            <h2>
              <BarChart3 size={18} />
              IPO activity
            </h2>
            <span className="legend">
              <i className="teal-dot" />
              Filed
              <i className="blue-dot" />
              Priced
            </span>
          </div>
          <p className="panel-subtitle">
            Initial filings and pricing events by month
          </p>
          {data.months.length ? (
            <div
              className="chart"
              role="img"
              aria-label={data.months
                .map((m) => `${m.month}: ${m.filed} filed, ${m.priced} priced`)
                .join("; ")}
            >
              <div className="chart-grid">
                {[1, 0.75, 0.5, 0.25, 0].map((n) => (
                  <div key={n}>
                    <span>{Math.round(max * n)}</span>
                  </div>
                ))}
              </div>
              <div className="chart-bars">
                {data.months.map((m) => (
                  <div className="bar-month" key={m.month}>
                    <div className="bar-pair">
                      <div
                        className="bar filed"
                        style={{ height: `${(m.filed / max) * 100}%` }}
                      >
                        <span>{m.filed}</span>
                      </div>
                      <div
                        className="bar priced"
                        style={{ height: `${(m.priced / max) * 100}%` }}
                      >
                        <span>{m.priced}</span>
                      </div>
                    </div>
                    <small>
                      {new Date(m.month + "-15").toLocaleDateString("en-US", {
                        month: "short",
                      })}
                    </small>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <Empty
              title="No published activity yet"
              text="The first approved research release will appear here."
            />
          )}
          <div className="chart-foot">
            <span>Monthly activity</span>
            <span>
              {demo
                ? "Illustrative dataset"
                : data.updatedAt
                  ? `Updated ${new Date(data.updatedAt).toLocaleString()}`
                  : "Awaiting approved release"}
            </span>
          </div>
        </section>
        <section className="panel developments">
          <div className="panel-title">
            <h2>
              <Activity size={18} />
              Latest developments
            </h2>
            <button className="text-link" onClick={() => navigate("activity")}>
              View all
              <ArrowRight size={13} />
            </button>
          </div>
          {data.events.slice(0, 4).map((e) => (
            <button
              className="development"
              key={e.id}
              onClick={() => open(e.offeringId)}
            >
              <span
                className={"event-dot " + (e.type === "Priced" ? "blue" : "")}
              />
              <div>
                <small>
                  {date(e.date)}
                  <span>{e.type}</span>
                </small>
                <strong>{e.company}</strong>
                <p>{e.summary}</p>
              </div>
              <ArrowUpRight size={15} />
            </button>
          ))}
        </section>
      </div>
      <section className="panel">
        <div className="panel-title">
          <h2>
            <Layers size={18} />
            Offerings to explore
          </h2>
          <button className="text-link" onClick={() => navigate("activity")}>
            View all offerings
            <ArrowRight size={14} />
          </button>
        </div>
        <table className="mini-table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Stage</th>
              <th>Filing price</th>
              <th>Final IPO price</th>
              <th>Offering value</th>
              <th>
                <Bookmark size={14} />
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr key={o.id}>
                <td>
                  <button className="company-cell" onClick={() => open(o.id)}>
                    <CompanyIcon name={o.company} />
                    <span>
                      <strong>{o.company}</strong>
                      <small>{o.sector || o.ticker}</small>
                    </span>
                  </button>
                </td>
                <td>
                  <Badge stage={o.stage} />
                </td>
                <td>{o.filingPrice || "—"}</td>
                <td>{price(o.finalPrice)}</td>
                <td>{money(o.value)}</td>
                <td>
                  <SaveButton
                    saved={saved.includes(o.id)}
                    click={() => toggle(o.id)}
                    name={o.company}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <Empty
            title="Ready for the first research release"
            text="No unpublished or unverified records are shown."
          />
        )}
      </section>
      <RecentActivity open={open} />
      <button className="search-callout" onClick={() => navigate("people")}>
        <span className="callout-icon">
          <Users size={23} />
        </span>
        <span>
          <strong>Discover the people behind the IPO.</strong>
          <small>
            Search education, experience and affiliations in sourced
            biographies.
          </small>
        </span>
        <ArrowRight size={22} />
      </button>
    </>
  );
}
function RecentActivity({ open }: { open: (id: string) => void }) {
  const [events, setEvents] = useState<Overview["events"]>([]);
  useEffect(() => {
    api<Overview>("/overview")
      .then((d) => setEvents(d.events))
      .catch(() => {});
  }, []);
  return events.length ? (
    <div className="recent-strip">
      <span>
        <Activity size={14} />
        Recent Activity
      </span>
      <div className="recent-window">
        <div className="recent-track">
          {[0, 1].map((copy) => (
            <div
              className="recent-set"
              key={copy}
              aria-hidden={copy === 1 ? true : undefined}
            >
              {events.map((e) => (
                <button
                  tabIndex={copy === 1 ? -1 : 0}
                  key={e.id}
                  onClick={() => open(e.offeringId)}
                >
                  <i />
                  <strong>{e.company}</strong>
                  <span>
                    {e.type} · {date(e.date)}
                  </span>
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  ) : null;
}
function SaveButton({
  saved,
  click,
  name,
}: {
  saved: boolean;
  click: () => void;
  name: string;
}) {
  return (
    <button
      className={"icon-button " + (saved ? "saved" : "")}
      aria-label={`${saved ? "Unsave" : "Save"} ${name}`}
      aria-pressed={saved}
      onClick={click}
    >
      <Bookmark size={17} fill={saved ? "currentColor" : "none"} />
    </button>
  );
}
const defaultColumns = [
  "Company",
  "Ticker",
  "Form",
  "Stage",
  "Filed",
  "Pricing date",
  "Offering value",
  "Filing price",
  "Final IPO price",
  "Current price",
  "Public signals",
];
function ActivityScreen({
  initialQuery,
  onlySaved,
  saved,
  toggle,
  open,
}: {
  initialQuery: string;
  onlySaved: boolean;
  saved: string[];
  toggle: (id: string) => void;
  open: (id: string) => void;
}) {
  const [q, setQ] = useState(initialQuery),
    [stage, setStage] = useState(""),
    [min, setMin] = useState(""),
    [page, setPage] = useState(1),
    [data, setData] = useState<Page<Offering> | null>(null),
    [error, setError] = useState(""),
    [columns, setColumns] = useState<string[]>(() => {
      try {
        const v = JSON.parse(
          localStorage.getItem("ipo-roll-columns") || "null",
        );
        return Array.isArray(v) &&
          v.length === defaultColumns.length &&
          new Set(v).size === v.length &&
          v.every((c) => defaultColumns.includes(c))
          ? v
          : defaultColumns;
      } catch {
        return defaultColumns;
      }
    }),
    [controls, setControls] = useState(false),
    [drag, setDrag] = useState("");
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      api<Page<Offering>>(
        `/offerings?q=${encodeURIComponent(q)}&stage=${encodeURIComponent(stage)}&min=${min || 0}&page=${page}&saved=${onlySaved ? "1" : "0"}&ids=${demo ? encodeURIComponent(saved.join(",")) : ""}`,
      )
        .then((d) => {
          if (active) {
            setData(d);
            setError("");
          }
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    }, 150);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [q, stage, min, page, saved.join(",")]);
  function move(from: string, to: string) {
    const a = [...columns];
    a.splice(a.indexOf(from), 1);
    a.splice(a.indexOf(to), 0, from);
    setColumns(a);
    localStorage.setItem("ipo-roll-columns", JSON.stringify(a));
  }
  const items = data?.items || [];
  function cell(c: string, o: Offering) {
    switch (c) {
      case "Company":
        return (
          <button className="company-cell" onClick={() => open(o.id)}>
            <CompanyIcon name={o.company} />
            <span>
              <strong>{o.company}</strong>
              <small>{o.sector}</small>
            </span>
          </button>
        );
      case "Ticker":
        return <span className="ticker">{o.ticker || "—"}</span>;
      case "Form":
        return o.form;
      case "Stage":
        return <Badge stage={o.stage} />;
      case "Filed":
        return date(o.filed);
      case "Pricing date":
        return date(o.pricingDate);
      case "Offering value":
        return money(o.value);
      case "Filing price":
        return o.filingPrice || "—";
      case "Final IPO price":
        return price(o.finalPrice);
      case "Current price":
        return (
          <span title="Published only with licensed, fresh, identity-verified market data">
            {price(o.currentPrice)}
          </span>
        );
      default:
        return <span className="signals">{o.signals.join(" · ") || "—"}</span>;
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            {onlySaved
              ? "YOUR RESEARCH LIST"
              : "FROM FIRST FILING TO FINAL PRICING"}
          </div>
          <h1>
            {onlySaved ? "Your watchlist" : "IPO Activity"}
            <span className="teal-text">.</span>
          </h1>
          <p>
            {onlySaved
              ? "Keep the offerings that matter within reach."
              : "Every offering. Every material change. One clear view."}
          </p>
        </div>
        <span className="count-pill">
          {onlySaved ? saved.length : data?.total || 0} offerings
        </span>
      </div>
      <div className="toolbar">
        <div className="input-search">
          <Search size={16} />
          <input
            aria-label="Filter companies"
            placeholder="Company or ticker"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <select
          aria-label="Stage filter"
          value={stage}
          onChange={(e) => {
            setStage(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All stages</option>
          <option>Pre-pricing</option>
          <option>Priced</option>
        </select>
        <select
          aria-label="Offering size filter"
          value={min}
          onChange={(e) => {
            setMin(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Any size</option>
          {[100, 250, 500, 1000, 5000].map((n) => (
            <option value={n * 1e6} key={n}>
              {money(n * 1e6)}+
            </option>
          ))}
        </select>
        <button
          className={"button " + (controls ? "selected" : "")}
          onClick={() => setControls(!controls)}
          aria-expanded={controls}
        >
          <SlidersHorizontal size={15} />
          Columns
        </button>
        <button
          className="text-link"
          onClick={() => {
            setQ("");
            setStage("");
            setMin("");
            setPage(1);
          }}
        >
          Clear filters
        </button>
      </div>
      {controls && (
        <div className="column-controls">
          <p>Drag table headers, or move columns with these buttons.</p>
          {columns.map((c, i) => (
            <span key={c}>
              {c}
              <button
                disabled={i === 0}
                aria-label={`Move ${c} left`}
                onClick={() => move(c, columns[i - 1])}
              >
                <ArrowLeft size={12} />
              </button>
              <button
                disabled={i === columns.length - 1}
                aria-label={`Move ${c} right`}
                onClick={() => {
                  const a = [...columns];
                  [a[i], a[i + 1]] = [a[i + 1], a[i]];
                  setColumns(a);
                  localStorage.setItem("ipo-roll-columns", JSON.stringify(a));
                }}
              >
                <ArrowRight size={12} />
              </button>
            </span>
          ))}
          <button
            className="text-link"
            onClick={() => {
              setColumns(defaultColumns);
              localStorage.removeItem("ipo-roll-columns");
            }}
          >
            Reset order
          </button>
        </div>
      )}
      <RecentActivity open={open} />
      <section className="panel table-panel">
        {error ? (
          <Empty title="Unable to load offerings" text={error} />
        ) : !data ? (
          <Loading />
        ) : (
          <>
            <div className="table-scroll">
              <table className="research-table">
                <thead>
                  <tr>
                    {columns.map((c) => (
                      <th
                        key={c}
                        draggable
                        onDragStart={() => setDrag(c)}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={() => {
                          if (drag && drag !== c) move(drag, c);
                          setDrag("");
                        }}
                      >
                        {c}
                        <GripVertical size={10} />
                      </th>
                    ))}
                    <th>Save</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((o) => (
                    <tr key={o.id}>
                      {columns.map((c) => (
                        <td key={c}>{cell(c, o)}</td>
                      ))}
                      <td>
                        <SaveButton
                          saved={saved.includes(o.id)}
                          name={o.company}
                          click={() => toggle(o.id)}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!items.length && (
              <Empty
                title={
                  onlySaved ? "No saved offerings" : "No matching offerings"
                }
                text={
                  onlySaved
                    ? "Save an offering with its bookmark button."
                    : "Try a different company, stage or offering size."
                }
              />
            )}
            <div className="table-footer">
              <span>
                {items.length} shown · {data.total + " total"}{" "}
              </span>
              <div>
                <button
                  className="icon-button"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                  aria-label="Previous page"
                >
                  <ArrowLeft size={15} />
                </button>
                <span>Page {page}</span>
                <button
                  className="icon-button"
                  disabled={page * 25 >= data.total}
                  onClick={() => setPage(page + 1)}
                  aria-label="Next page"
                >
                  <ArrowRight size={15} />
                </button>
              </div>
            </div>
          </>
        )}
      </section>
      <div className="information-note">
        <ShieldCheck size={17} />
        <span>
          Blank fields mean a value is unavailable or not verified. Current
          prices require licensed, fresh, issuer-matched quotes.
        </span>
      </div>
    </>
  );
}
function PeopleScreen({ open }: { open: (id: string) => void }) {
  const [q, setQ] = useState("University of Michigan"),
    [submitted, setSubmitted] = useState(""),
    [relationship, setRelationship] = useState(""),
    [matches, setMatches] = useState<Match[]>([]),
    [selected, setSelected] = useState<Match | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(1);
  const seq = useRef(0);
  async function search(value = q, rel = relationship, p = 1) {
    if (value.trim().length < 2) {
      setError("Enter at least two characters.");
      return;
    }
    const s = ++seq.current;
    setBusy(true);
    setError("");
    setSubmitted(value.trim());
    setPage(p);
    try {
      const data = await api<Page<Match>>(
        `/people/search?q=${encodeURIComponent(value.trim())}&relationship=${encodeURIComponent(rel)}&page=${p}`,
      );
      if (s === seq.current) {
        setMatches(data.items);
        setSelected(data.items[0] || null);
        setTotal(data.total);
      }
    } catch (e) {
      if (s === seq.current) {
        setMatches([]);
        setSelected(null);
        setError((e as Error).message);
      }
    } finally {
      if (s === seq.current) setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">PEOPLE INTELLIGENCE</div>
          <h1>
            Find the people
            <br />
            behind the IPO<span className="teal-text">.</span>
          </h1>
          <p>Search public biographies. See the evidence.</p>
        </div>
        <span className="subtle-seal">
          <ShieldCheck size={20} />
          Evidence-led research
        </span>
      </div>
      <form
        className="hero-search"
        onSubmit={(e) => {
          e.preventDefault();
          search();
        }}
      >
        <Search size={22} />
        <input
          aria-label="Search biographies"
          maxLength={160}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="University, employer, experience or name…"
        />
        <button className="button primary" disabled={busy}>
          {busy ? (
            <Loader2 className="spin" size={18} />
          ) : (
            <>
              Search
              <ArrowRight size={17} />
            </>
          )}
        </button>
      </form>
      <div className="search-options">
        <select
          aria-label="Relationship filter"
          value={relationship}
          onChange={(e) => {
            setRelationship(e.target.value);
            if (submitted) search(submitted, e.target.value);
          }}
        >
          <option value="">All relationships</option>
          <option>Beneficial owner</option>
          <option>Director</option>
          <option>Executive</option>
        </select>
        <span>
          <FileText size={14} />
          Person-specific evidence only
        </span>
        <button
          className="text-link"
          onClick={() => {
            setQ("");
            setSubmitted("");
            setMatches([]);
            setSelected(null);
            setError("");
          }}
        >
          Clear
        </button>
      </div>
      {!submitted && (
        <div className="suggestions">
          <span>Try a search</span>
          {[
            "University of Michigan",
            "Goldman Sachs",
            "Harvard Business School",
            "automotive",
          ].map((term) => (
            <button
              key={term}
              onClick={() => {
                setQ(term);
                search(term);
              }}
            >
              {term}
              <ArrowUpRight size={12} />
            </button>
          ))}
        </div>
      )}
      {busy ? (
        <Loading />
      ) : error ? (
        <Empty title="Search unavailable" text={error} />
      ) : submitted ? (
        <div className={"people-layout " + (!selected ? "no-evidence" : "")}>
          <section>
            <div className="result-heading">
              <strong>
                {new Set(matches.map((m) => m.offeringId)).size} companies on
                this page <span>· {total} matching people</span>
              </strong>
              <small>
                {demo ? "Illustrative results" : "Sourced biography results"}
              </small>
            </div>
            {matches.map((m) => (
              <article
                key={m.id}
                className={
                  "match-card " + (selected?.id === m.id ? "chosen" : "")
                }
              >
                <div className="match-company">
                  <CompanyIcon name={m.company} />
                  <strong>{m.company}</strong>
                  <Badge stage={m.stage} />
                  <button
                    className="icon-button"
                    aria-label={`Open ${m.company}`}
                    onClick={() => open(m.offeringId)}
                  >
                    <ArrowUpRight size={17} />
                  </button>
                </div>
                <div className="match-person">
                  <span className="avatar">
                    {m.person.name
                      .split(" ")
                      .map((s) => s[0])
                      .slice(0, 2)
                      .join("")}
                  </span>
                  <div>
                    <h3>{m.person.name}</h3>
                    <p>
                      {m.person.role} <span>·</span> {m.person.relationship}
                    </p>
                  </div>
                </div>
                <blockquote>
                  “<Highlight text={m.evidence.excerpt} query={submitted} />”
                </blockquote>
                <div className="match-source">
                  <FileText size={16} />
                  <div>
                    <strong>{m.evidence.title}</strong>
                    <small>
                      {date(m.evidence.date)} · {m.matchType}
                    </small>
                  </div>
                  <button className="text-link" onClick={() => setSelected(m)}>
                    View evidence
                    <ArrowRight size={13} />
                  </button>
                </div>
              </article>
            ))}
            {!matches.length && (
              <Empty
                title="No supported matches found"
                text="Try another name or phrase. No match means no matching evidence in the available corpus, not proof of no affiliation."
              />
            )}
            {total > 25 && (
              <div className="table-footer">
                <button
                  className="button"
                  disabled={page === 1}
                  onClick={() => search(submitted, relationship, page - 1)}
                >
                  Previous
                </button>
                <span>Page {page}</span>
                <button
                  className="button"
                  disabled={page * 25 >= total}
                  onClick={() => search(submitted, relationship, page + 1)}
                >
                  Next
                </button>
              </div>
            )}
          </section>
          {selected && (
            <aside className="panel evidence-panel">
              <div className="panel-title">
                <h2>Evidence trail</h2>
                <button
                  className="icon-button"
                  aria-label="Close evidence panel"
                  onClick={() => setSelected(null)}
                >
                  <X size={16} />
                </button>
              </div>
              <p className="panel-subtitle">
                Follow the source from person to IPO.
              </p>
              <ol>
                <li>
                  <small>Person</small>
                  <div>
                    <strong>{selected.person.name}</strong>
                    <p>{selected.person.role}</p>
                  </div>
                </li>
                <li>
                  <small>Biography evidence</small>
                  <div>
                    “
                    <Highlight
                      text={selected.evidence.excerpt}
                      query={submitted}
                    />
                    ”
                  </div>
                </li>
                <li>
                  <small>Source</small>
                  <div>
                    <FileText size={18} />
                    <strong>{selected.evidence.title}</strong>
                    <p>{selected.evidence.locator}</p>
                    <SourceLink source={selected.evidence} />
                  </div>
                </li>
                <li>
                  <small>IPO relationship</small>
                  <div>
                    <strong>{selected.person.relationship}</strong>
                    <p>{selected.person.source.excerpt}</p>
                  </div>
                </li>
                <li>
                  <small>Company</small>
                  <button onClick={() => open(selected.offeringId)}>
                    <strong>{selected.company}</strong>
                    <ArrowUpRight size={15} />
                  </button>
                </li>
              </ol>
              <div className="evidence-foot">
                <ShieldCheck size={14} />
                {demo
                  ? "Illustrative sample, not a verified record."
                  : "Text matches do not imply unstated affiliations."}
              </div>
            </aside>
          )}
        </div>
      ) : (
        <div className="search-intro">
          <div className="intro-orbit">
            <Users size={28} />
          </div>
          <h2>
            A name is a starting point.
            <br />
            Evidence makes the connection.
          </h2>
          <p>
            Explore the people associated with an offering through their public
            education, career and experience.
          </p>
          <div>
            <span>
              <FileText size={15} />
              Sourced biographies
            </span>
            <span>
              <Layers size={15} />
              IPO relationships
            </span>
            <span>
              <ShieldCheck size={15} />
              No inferred affiliations
            </span>
          </div>
        </div>
      )}
    </>
  );
}
function DetailDrawer({
  id,
  close,
  saved,
  toggle,
}: {
  id: string;
  close: () => void;
  saved: boolean;
  toggle: () => void;
}) {
  const [data, setData] = useState<Detail | null>(null),
    [error, setError] = useState(""),
    [person, setPerson] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    ref.current?.focus();
    let active = true;
    api<Detail>("/offerings/" + id)
      .then((d) => {
        if (active) {
          setData(d);
          setPerson(d.people[0]?.id || null);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
      document.body.style.overflow = old;
      previous?.focus();
    };
  }, [id]);
  return (
    <div className="drawer-backdrop" onClick={close}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Company research"
        tabIndex={-1}
        ref={ref}
        className="detail-drawer"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Escape") close();
          if (e.key === "Tab") {
            const nodes = ref.current?.querySelectorAll<HTMLElement>(
              "button:not(:disabled),a[href],input,select",
            );
            if (nodes?.length) {
              const first = nodes[0],
                last = nodes[nodes.length - 1];
              if (
                e.shiftKey &&
                (document.activeElement === first ||
                  document.activeElement === ref.current)
              ) {
                e.preventDefault();
                last.focus();
              } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
              }
            }
          }
        }}
      >
        <div className="drawer-top">
          <span className="eyebrow">COMPANY RESEARCH</span>
          <button
            className="icon-button"
            aria-label="Close company detail"
            onClick={close}
          >
            <X size={22} />
          </button>
        </div>
        {error ? (
          <Empty title="Detail unavailable" text={error} />
        ) : !data ? (
          <Loading />
        ) : (
          <>
            <div className="detail-title">
              <CompanyIcon name={data.company} />
              <div>
                <h2>{data.company}</h2>
                <p>
                  {data.ticker} · {data.sector || "Operating company"}
                </p>
              </div>
              <SaveButton saved={saved} click={toggle} name={data.company} />
            </div>
            <Badge stage={data.stage} />
            <div className="lifecycle">
              <div>
                <i />
                <small>Filed</small>
                <strong>{date(data.filed)}</strong>
              </div>
              <div>
                <i className={data.pricingDate ? "" : "pending"} />
                <small>{data.pricingDate ? "Priced" : "Pricing pending"}</small>
                <strong>{date(data.pricingDate)}</strong>
              </div>
            </div>
            <div className="detail-metrics">
              {[
                ["Filing price", data.filingPrice || "—"],
                ["Final IPO price", price(data.finalPrice)],
                ["Offering value", money(data.value)],
              ].map(([label, value]) => (
                <div key={label}>
                  <small>{label}</small>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <h3 className="section-heading">
              People & ownership <span>{data.people.length}</span>
            </h3>
            <p className="muted">
              People with a source-supported relationship to this offering.
            </p>
            {data.people.map((p) => (
              <div className="person-accordion" key={p.id}>
                <button
                  className="person-toggle"
                  aria-expanded={person === p.id}
                  onClick={() => setPerson(person === p.id ? null : p.id)}
                >
                  <span className="avatar">
                    {p.name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")
                      .slice(0, 2)}
                  </span>
                  <span>
                    <strong>{p.name}</strong>
                    <small>
                      {p.role} · {p.relationship}
                    </small>
                  </span>
                  <ChevronDown
                    className={person === p.id ? "rotated" : ""}
                    size={17}
                  />
                </button>
                {person === p.id && (
                  <div className="person-body">
                    {p.biography && <p>{p.biography}</p>}
                    <div className="ownership-facts">
                      {p.shares !== null && (
                        <div>
                          <small>Disclosed shares</small>
                          <strong>{p.shares.toLocaleString()}</strong>
                        </div>
                      )}
                      {p.percent !== null && (
                        <div>
                          <small>Disclosed ownership</small>
                          <strong>{p.percent}%</strong>
                        </div>
                      )}
                    </div>
                    <div className="source-box">
                      <FileText size={17} />
                      <div>
                        <strong>{p.source.title}</strong>
                        <p>{p.source.excerpt}</p>
                        <SourceLink source={p.source} />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {!data.people.length && (
              <Empty
                title="No people published yet"
                text="A missing record does not imply there are no beneficial owners."
              />
            )}
            <div className="source-box offering-source">
              <ShieldCheck size={18} />
              <div>
                <strong>Offering source</strong>
                <p>
                  {data.source.title} · {date(data.source.date)}
                </p>
                <SourceLink source={data.source} />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
function Methodology() {
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">THE STANDARD BEHIND THE RESEARCH</div>
          <h1>
            Evidence is the foundation<span className="teal-text">.</span>
          </h1>
          <p>
            Understand what we track, what we show, and what we leave blank.
          </p>
        </div>
        <ShieldCheck className="methodology-icon" size={45} />
      </div>
      <div className="methodology-grid">
        {[
          [
            FileText,
            "01",
            "Public sources, clear provenance",
            "Filing facts come from SEC documents and authoritative public sources. Each published biography match retains its person-specific passage, source and IPO relationship.",
          ],
          [
            Filter,
            "02",
            "Operating-company IPOs",
            "The research scope excludes SPACs and non-operating investment products. Offering size is a filter, not a minimum inclusion rule.",
          ],
          [
            BarChart3,
            "03",
            "Different prices, different meanings",
            "Preliminary Filing Price is preserved separately from Final IPO Price. Pricing Date is not automatically the filing date. Current quotes require licensing, freshness and issuer identity checks.",
          ],
          [
            Users,
            "04",
            "People Search without guessing",
            "Search matches named people and their public biography text. A phrase appearing in a source does not by itself establish an affiliation. Only explicit, person-specific evidence supports that claim.",
          ],
          [
            ShieldCheck,
            "05",
            "Unknown stays unknown",
            "Missing, contradictory or unverified values remain blank. An institutional holding is not automatically a fund manager’s personal holding. We do not estimate unsupported ownership.",
          ],
          [
            Database,
            "06",
            "Coverage, honestly stated",
            demo
              ? "This workspace uses fictional sample companies and biographies to demonstrate the interface. No sample is a real filing, affiliation, quote or ownership claim."
              : "This is the initial staging build. Only approved research is published. Biography collection and validation are separate from importing existing offering records.",
          ],
        ].map(([Icon, num, title, text]) => {
          const I = Icon as typeof FileText;
          return (
            <section className="panel method-card" key={String(num)}>
              <div>
                <I size={23} />
                <span>{String(num)}</span>
              </div>
              <h2>{String(title)}</h2>
              <p>{String(text)}</p>
            </section>
          );
        })}
      </div>
      <div className="information-note">
        <BookOpen size={18} />
        <span>
          Research coverage is not exhaustive. No matching evidence is not proof
          that a relationship does not exist.
        </span>
      </div>
    </>
  );
}
function Loading() {
  return (
    <div className="loading" role="status">
      <Loader2 className="spin" size={24} />
      <span>Loading research…</span>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
