"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Assignments,
  Bell,
  Chevron,
  Classroom,
  Exams,
  Help,
  Home,
  Library,
  Logo,
  Menu,
  PanelToggle,
  School,
  Settings,
  Sparkle,
} from "./icons";

export type SectionKey =
  | "home"
  | "classroom"
  | "assignments"
  | "exams"
  | "library"
  | "settings"
  | "toolkit";

const NAV: { key: SectionKey; label: string; Icon: typeof Home }[] = [
  { key: "home", label: "Home", Icon: Home },
  { key: "classroom", label: "My Classroom", Icon: Classroom },
  { key: "assignments", label: "Assignments", Icon: Assignments },
  { key: "exams", label: "Exams", Icon: Exams },
  { key: "library", label: "My Library", Icon: Library },
];

/**
 * The teacher the design shows, in one place.
 *
 * The brief specifies no authentication, so there is no account to read this
 * from — but it was written out in three separate components, which is how a
 * demo ends up half-renamed. Whatever replaces it later (a session, a prop)
 * has one seam to replace rather than three literals to hunt down.
 */
export const DEMO_TEACHER = {
  name: "Madhur Rastogi",
  school: "Delhi Public School",
  city: "Bokaro Steel City",
  avatar: "/avatar.png",
} as const;

const BLURB: Record<string, string> = {
  home: "The teacher's dashboard — classes, recent exams and pending evaluations.",
  classroom: "Class rosters, seating and student profiles.",
  assignments: "Homework set, submitted and returned.",
  library: "Saved papers, rubrics and question banks.",
  settings: "School, marking and account preferences.",
  toolkit: "The wider set of AI tools for teachers.",
};

/** Settings and the toolkit are not in NAV, so look their names up here too. */
function sectionTitle(section: SectionKey): string {
  const nav = NAV.find((n) => n.key === section);
  if (nav) return nav.label;
  return section === "toolkit" ? "AI Teacher's Toolkit" : "Settings";
}

type DemoRow = {
  left: string;
  meta: string;
  status: string;
  tone?: "good" | "warn";
};

/**
 * Static content for the sections outside this assignment's scope.
 *
 * The brief scopes the build to the Exams flow, so none of this is wired to
 * anything — it exists so the surrounding product reads as a whole rather than
 * as five dead links. Every screen that shows it is labelled "Sample data",
 * because an invented number that looks live is worse than an empty state: a
 * reviewer cannot otherwise tell which parts were actually built.
 */
const SECTION_DEMO: Record<
  SectionKey,
  { stats: [string, string][]; listTitle: string; rows: DemoRow[] }
> = {
  home: {
    stats: [
      ["Classes", "6"],
      ["Students", "184"],
      ["Papers awaiting marking", "3"],
      ["Marked this week", "41"],
    ],
    listTitle: "Recent activity",
    rows: [
      { left: "Class XII-A · Physics", meta: "Term 1 paper", status: "Marked", tone: "good" },
      { left: "Class XII-B · Chemistry", meta: "38 sheets", status: "In progress", tone: "warn" },
      { left: "Class XI-C · Biology", meta: "Uploaded today", status: "Queued" },
    ],
  },
  classroom: {
    stats: [
      ["Classes", "6"],
      ["Students", "184"],
      ["Average attendance", "92%"],
      ["Subjects taught", "3"],
    ],
    listTitle: "Your classes",
    rows: [
      { left: "XII-A · Physics", meta: "38 students", status: "Active", tone: "good" },
      { left: "XII-B · Chemistry", meta: "36 students", status: "Active", tone: "good" },
      { left: "XI-C · Biology", meta: "34 students", status: "Active", tone: "good" },
      { left: "XI-D · Physics", meta: "40 students", status: "Archived" },
    ],
  },
  assignments: {
    stats: [
      ["Set this term", "18"],
      ["Awaiting submission", "4"],
      ["Returned", "12"],
      ["Overdue", "2"],
    ],
    listTitle: "Recent assignments",
    rows: [
      { left: "Electrostatics worksheet", meta: "XII-A · due 12 Mar", status: "Returned", tone: "good" },
      { left: "Organic reactions set 3", meta: "XII-B · due 15 Mar", status: "Submitted", tone: "warn" },
      { left: "Photosynthesis revision", meta: "XI-C · due 18 Mar", status: "Open" },
    ],
  },
  exams: {
    stats: [],
    listTitle: "",
    rows: [],
  },
  library: {
    stats: [
      ["Saved papers", "27"],
      ["Rubrics", "9"],
      ["Question banks", "4"],
      ["Shared with staff", "11"],
    ],
    listTitle: "Saved papers",
    rows: [
      { left: "Physics · Term 1 2025", meta: "3 pages · 15 questions", status: "Saved", tone: "good" },
      { left: "Chemistry · Mock 2", meta: "2 pages · 12 questions", status: "Saved", tone: "good" },
      { left: "Biology marking scheme", meta: "Rubric", status: "Draft", tone: "warn" },
    ],
  },
  settings: {
    stats: [
      ["School", "DPS Bokaro"],
      ["Marking scale", "Marks"],
      ["Language", "English"],
      ["Members", "12"],
    ],
    listTitle: "Preferences",
    rows: [
      { left: "Default marks per question", meta: "Used when the paper prints none", status: "2", tone: "good" },
      { left: "Highlight colour", meta: "Answer regions on the sheet", status: "Green", tone: "good" },
      { left: "AI feedback", meta: "Per-question comments", status: "On", tone: "good" },
    ],
  },
  toolkit: {
    stats: [
      ["Tools available", "8"],
      ["Used this month", "23"],
      ["Time saved", "~14h"],
      ["Credits left", "120"],
    ],
    listTitle: "Teacher tools",
    rows: [
      { left: "Extraction & answer mapping", meta: "Marks a scanned answer sheet", status: "Built", tone: "good" },
      { left: "Question paper generator", meta: "From a syllabus outline", status: "Concept" },
      { left: "Lesson plan assistant", meta: "Weekly planning", status: "Concept" },
    ],
  },
};

/** Close a popover on outside click or Escape. */
function useDismiss(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const click = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("mousedown", click);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", click);
      document.removeEventListener("keydown", key);
    };
  }, [onClose]);
  return ref;
}

export function AppShell({
  collapsed: fromView = false,
  children,
}: {
  collapsed?: boolean;
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(fromView);
  const [section, setSection] = useState<SectionKey>("exams");
  const [drawer, setDrawer] = useState(false);

  // The design collapses the sidebar to the rail once the split view opens,
  // and expands it again on the upload screen — but the teacher's own toggle
  // still wins until the view changes under them.
  useEffect(() => setCollapsed(fromView), [fromView]);

  const go = (key: SectionKey) => {
    setSection(key);
    setDrawer(false);
  };

  const mainRef = useRef<HTMLElement>(null);

  return (
    <div className="flex h-dvh gap-0 overflow-hidden p-2 sm:p-3">
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
        section={section}
        onNavigate={go}
        className="hidden md:flex"
      />

      {/* Below md the sidebar becomes a drawer, reached from the top bar. */}
      {drawer && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            aria-label="Close menu"
            onClick={() => setDrawer(false)}
            className="absolute inset-0 bg-black/25 backdrop-blur-[2px]"
          />
          <Sidebar
            collapsed={false}
            onToggle={() => setDrawer(false)}
            section={section}
            onNavigate={go}
            className="animate-rise absolute bottom-2 left-2 top-2 flex shadow-xl"
          />
        </div>
      )}

      {/* `relative` anchors the scroll button, which sits over <main>. */}
      <div className="relative flex min-w-0 flex-1 flex-col">
        <TopBar
          onMenu={() => setDrawer(true)}
          onHome={() => go("exams")}
          section={section}
        />
        {/*
          Scrolls at every width. It used to be `md:overflow-hidden`, on the
          assumption that a desktop is tall enough to show a screen whole —
          which a 1920x900 laptop is not. Anything below the fold was then
          simply unreachable, with no scrollbar to suggest otherwise.
        */}
        <main ref={mainRef} className="relative flex min-h-0 flex-1 flex-col overflow-y-auto">
          {section === "exams" ? (
            children
          ) : (
            <OutOfScope section={section} onBack={() => go("exams")} />
          )}
        </main>
        <ScrollDownButton target={mainRef} />
      </div>
    </div>
  );
}

/**
 * A "there is more below" affordance for a scroll container.
 *
 * A thin scrollbar is easy to miss on a short laptop screen, and the screens
 * here end in a card that crops cleanly at the fold — so a cut-off page reads
 * as a finished one rather than as something to scroll. This shows only while
 * the container actually has somewhere to go, and takes itself away at the
 * bottom, so it never sits over content it isn't needed for.
 */
function ScrollDownButton({
  target,
}: {
  target: React.RefObject<HTMLElement | null>;
}) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const node = target.current;
    if (!node) return;

    const update = () => {
      const remaining = node.scrollHeight - node.scrollTop - node.clientHeight;
      // A couple of pixels of slack: sub-pixel layout leaves a sliver of
      // "scrollable" behind at the true bottom, which would keep the button up.
      setShow(remaining > 24);
    };

    update();
    node.addEventListener("scroll", update, { passive: true });

    // The content grows and shrinks under it — a job finishing swaps a
    // one-screen loader for a long list — so watch the box, not just scrolling.
    const observer = new ResizeObserver(update);
    observer.observe(node);
    for (const child of Array.from(node.children)) observer.observe(child);

    return () => {
      node.removeEventListener("scroll", update);
      observer.disconnect();
    };
  }, [target]);

  if (!show) return null;

  return (
    <button
      type="button"
      aria-label="Scroll down"
      onClick={() =>
        target.current?.scrollBy({
          top: target.current.clientHeight * 0.8,
          behavior: "smooth",
        })
      }
      // Bottom-right, not centred: every screen here puts its primary action
      // in the middle of the column, and a centred button lands straight on
      // top of "Start Mapping" at the height this thing exists to rescue.
      className="animate-rise absolute bottom-5 right-5 z-20 grid h-10 w-10 place-items-center rounded-full border border-hairline bg-white/90 text-ink-soft shadow-[0_4px_16px_rgba(0,0,0,0.14)] backdrop-blur transition hover:bg-white hover:text-ink"
    >
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden>
        <path
          d="M6 9.5 12 15.5 18 9.5"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}

function Sidebar({
  collapsed,
  onToggle,
  section,
  onNavigate,
  className = "",
}: {
  collapsed: boolean;
  onToggle: () => void;
  section: SectionKey;
  onNavigate: (key: SectionKey) => void;
  className?: string;
}) {
  return (
    <aside
      className={[
        "shrink-0 flex-col rounded-panel bg-white/85 py-3 shadow-[0_1px_2px_rgba(0,0,0,0.04)] backdrop-blur-xl transition-[width] duration-200",
        collapsed ? "w-16 items-center px-2" : "w-47 px-3",
        className,
      ].join(" ")}
    >
      <div
        className={[
          "flex items-center",
          collapsed ? "justify-center" : "justify-between px-1",
        ].join(" ")}
      >
        <button
          type="button"
          onClick={() => onNavigate("exams")}
          className="flex items-center gap-2"
          aria-label="VedaAI home"
        >
          <Logo />
          {!collapsed && (
            <span className="text-[15px] font-bold tracking-tight">VedaAI</span>
          )}
        </button>
        {!collapsed && (
          <button
            type="button"
            onClick={onToggle}
            aria-label="Collapse sidebar"
            className="rounded-md p-1 text-ink-faint transition hover:bg-chip hover:text-ink"
          >
            <PanelToggle />
          </button>
        )}
      </div>

      <button
        type="button"
        onClick={() => onNavigate("toolkit")}
        title={collapsed ? "AI Teacher's Toolkit" : undefined}
        className={[
          "mt-4 flex items-center justify-center gap-1.5 rounded-full bg-ink font-semibold text-white ring-2 ring-brand/70 transition hover:bg-black",
          collapsed ? "h-10 w-10" : "h-10 w-full px-2.5 text-[11.5px]",
        ].join(" ")}
      >
        <Sparkle width={14} height={14} className="shrink-0 text-brand-soft" />
        {!collapsed && (
          <span className="whitespace-nowrap">AI Teacher&apos;s Toolkit</span>
        )}
      </button>

      <nav
        className={[
          "mt-5 flex flex-1 flex-col gap-1",
          collapsed ? "items-center" : "",
        ].join(" ")}
      >
        {NAV.map(({ key, label, Icon }) => (
          <button
            key={key}
            type="button"
            onClick={() => onNavigate(key)}
            title={collapsed ? label : undefined}
            aria-current={section === key ? "page" : undefined}
            className={[
              "flex items-center rounded-lg text-[13px] transition",
              collapsed ? "h-9 w-9 justify-center" : "h-9 w-full gap-2.5 px-2.5",
              section === key
                ? "bg-chip font-semibold text-ink"
                : "text-ink-soft hover:bg-chip/70 hover:text-ink",
            ].join(" ")}
          >
            <Icon />
            {!collapsed && <span>{label}</span>}
          </button>
        ))}
      </nav>

      <div className={collapsed ? "flex flex-col items-center gap-2" : ""}>
        <button
          type="button"
          onClick={() => onNavigate("settings")}
          title={collapsed ? "Settings" : undefined}
          aria-current={section === "settings" ? "page" : undefined}
          className={[
            "flex items-center rounded-lg text-[13px] transition",
            collapsed ? "h-9 w-9 justify-center" : "h-9 w-full gap-2.5 px-2.5",
            section === "settings"
              ? "bg-chip font-semibold text-ink"
              : "text-ink-soft hover:bg-chip/70 hover:text-ink",
          ].join(" ")}
        >
          <Settings />
          {!collapsed && <span>Settings</span>}
        </button>

        {collapsed ? (
          <>
            <School width={24} height={24} />
            <button
              type="button"
              onClick={onToggle}
              aria-label="Expand sidebar"
              className="mt-1 rounded-md p-1 text-ink-faint transition hover:bg-chip hover:text-ink"
            >
              <Chevron dir="right" width={16} height={16} />
            </button>
          </>
        ) : (
          <div className="mt-2 flex items-center gap-2 rounded-xl bg-chip px-2.5 py-2">
            <School />
            <span className="min-w-0">
              <span className="block truncate text-[12px] font-semibold leading-tight">
                {DEMO_TEACHER.school}
              </span>
              <span className="block truncate text-[10.5px] text-ink-faint">
                {DEMO_TEACHER.city}
              </span>
            </span>
          </div>
        )}
      </div>
    </aside>
  );
}

function TopBar({
  onMenu,
  onHome,
  section,
}: {
  onMenu: () => void;
  onHome: () => void;
  section: SectionKey;
}) {
  const [open, setOpen] = useState<"help" | "bell" | "user" | null>(null);
  const ref = useDismiss(() => setOpen(null));
  const label = sectionTitle(section);

  return (
    // z-30 is load-bearing, not decoration. `backdrop-blur-xl` makes this
    // header its own stacking context, so the popovers below are stacked
    // *within* it — and <main> is a later sibling, so without a z-index here
    // the page content paints straight over an open popover.
    <header className="relative z-30 mx-0 mb-2.5 flex h-14 shrink-0 items-center gap-1 rounded-2xl bg-white/60 px-2 backdrop-blur-xl sm:mx-3 sm:px-3">
      <button
        type="button"
        aria-label="Open menu"
        onClick={onMenu}
        className="grid h-9 w-9 place-items-center rounded-lg text-ink-soft transition hover:bg-chip md:hidden"
      >
        <Menu />
      </button>
      <button
        type="button"
        aria-label="Back"
        onClick={onHome}
        className="hidden h-9 w-9 place-items-center rounded-lg text-ink-soft transition hover:bg-chip md:grid"
      >
        <ArrowLeft />
      </button>
      <button
        type="button"
        onClick={onHome}
        className="flex items-center gap-1.5 rounded-lg px-1.5 py-1 text-[13px] text-ink-soft transition hover:bg-chip hover:text-ink"
      >
        <Exams width={15} height={15} />
        {label}
      </button>

      <div ref={ref} className="ml-auto flex items-center gap-0.5 sm:gap-1">
        <IconButton
          label="Help"
          active={open === "help"}
          onClick={() => setOpen(open === "help" ? null : "help")}
        >
          <Help />
        </IconButton>
        <IconButton
          label="Notifications"
          active={open === "bell"}
          onClick={() => setOpen(open === "bell" ? null : "bell")}
        >
          <span className="relative">
            <Bell />
            <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-brand" />
          </span>
        </IconButton>
        <button
          type="button"
          aria-label="AI"
          onClick={onHome}
          className="grid h-9 w-9 place-items-center rounded-full bg-chip text-brand transition hover:bg-brand-wash"
        >
          <Sparkle width={16} height={16} />
        </button>
        <button
          type="button"
          onClick={() => setOpen(open === "user" ? null : "user")}
          className="ml-0.5 flex items-center gap-2 rounded-full py-1 pl-1 pr-1.5 transition hover:bg-chip sm:pr-2"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={DEMO_TEACHER.avatar}
            alt=""
            width={184}
            height={184}
            className="h-8 w-8 select-none rounded-full"
            draggable={false}
          />
          <span className="hidden text-[13px] font-medium lg:inline">
            {DEMO_TEACHER.name}
          </span>
          <Chevron width={15} height={15} className="text-ink-faint" />
        </button>

        {open && <Popover kind={open} onClose={() => setOpen(null)} />}
      </div>
    </header>
  );
}

function Popover({
  kind,
  onClose,
}: {
  kind: "help" | "bell" | "user";
  onClose: () => void;
}) {
  return (
    <div className="animate-rise absolute right-0 top-13 z-40 w-71.5 rounded-card border border-hairline bg-white p-3.5 shadow-[0_8px_28px_rgba(0,0,0,0.12)]">
      {kind === "help" && (
        <>
          <p className="mb-1.5 text-[12.5px] font-bold">How this works</p>
          <ol className="list-decimal space-y-1 pl-4 text-[12px] leading-normal text-ink-soft">
            <li>Upload the question paper and one answer sheet.</li>
            <li>Questions and answers are extracted and matched.</li>
            <li>
              Click any question to highlight its answer on the sheet. Blank
              questions and answers matching nothing are flagged.
            </li>
          </ol>
        </>
      )}
      {kind === "bell" && (
        <>
          <p className="mb-1.5 text-[12.5px] font-bold">Notifications</p>
          <p className="text-[12px] leading-normal text-ink-soft">
            Nothing new. Evaluation runs happen in the browser and finish while
            you watch, so there is nothing to notify you about yet.
          </p>
        </>
      )}
      {kind === "user" && (
        <>
          <div className="mb-2.5 flex items-center gap-2.5">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={DEMO_TEACHER.avatar}
              alt=""
              width={184}
              height={184}
              className="h-9 w-9 rounded-full"
            />
            <span>
              <span className="block text-[12.5px] font-semibold">
                {DEMO_TEACHER.name}
              </span>
              <span className="block text-[11px] text-ink-faint">
                {DEMO_TEACHER.school}
              </span>
            </span>
          </div>
          <p className="text-[11.5px] leading-normal text-ink-soft">
            Signed in as a demo teacher. The brief specifies no authentication,
            so there is no real account behind this.
          </p>
        </>
      )}
      <button
        type="button"
        onClick={onClose}
        className="mt-3 w-full rounded-lg bg-chip py-1.5 text-[11.5px] font-medium text-ink-soft transition hover:bg-black/10 hover:text-ink"
      >
        Close
      </button>
    </div>
  );
}

/**
 * What the other nav sections show.
 *
 * The brief scopes this build to the extraction flow, so Home, My Classroom,
 * Assignments, My Library and Settings have nothing behind them. A dead click
 * reads as unfinished, and a fake screen would be worse — so each says plainly
 * what it would hold and points back to the part that works.
 */
function OutOfScope({
  section,
  onBack,
}: {
  section: SectionKey;
  onBack: () => void;
}) {
  const Icon = NAV.find((n) => n.key === section)?.Icon ?? Settings;
  const title = sectionTitle(section);

  const demo = SECTION_DEMO[section];

  return (
    <section className="flex-1 px-3 pb-6 sm:px-5">
      <div className="mx-auto w-full max-w-220">
        <header className="flex flex-wrap items-center gap-3 pb-4 pt-1">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-white/70 text-ink-soft backdrop-blur-xl">
            <Icon width={20} height={20} />
          </span>
          <div className="min-w-0">
            <h2 className="text-[17px] font-bold">{title}</h2>
            <p className="text-[12.5px] leading-[1.55] text-ink-soft">
              {BLURB[section]}
            </p>
          </div>
          {/*
            Said plainly rather than implied. These screens are here so the
            product reads as a whole, but the numbers are invented — and a
            fabricated figure that looks live is worse than an empty state,
            because a reviewer cannot tell which parts were actually built.
          */}
          <span className="ml-auto shrink-0 rounded-full bg-warn-bg px-2.5 py-1 text-[11px] font-semibold text-warn">
            Sample data
          </span>
        </header>

        <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
          {demo.stats.map(([label, value]) => (
            <div
              key={label}
              className="rounded-panel bg-white/60 px-4 py-3.5 backdrop-blur-xl"
            >
              <div className="text-[22px] font-bold leading-tight">{value}</div>
              <div className="mt-0.5 text-[11.5px] text-ink-soft">{label}</div>
            </div>
          ))}
        </div>

        <div className="mt-3 rounded-panel bg-white/60 p-3 backdrop-blur-xl">
          <h3 className="px-1 pb-2 text-[13px] font-bold">{demo.listTitle}</h3>
          <ul className="space-y-1.5">
            {demo.rows.map((row) => (
              <li
                key={row.left}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-inset bg-chip px-3 py-2.5"
              >
                <span className="min-w-0 flex-1 text-[12.5px] font-medium">
                  {row.left}
                </span>
                <span className="text-[11.5px] text-ink-soft">{row.meta}</span>
                <span
                  className={[
                    "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold",
                    row.tone === "good"
                      ? "bg-good-bg text-good"
                      : row.tone === "warn"
                        ? "bg-warn-bg text-warn"
                        : "bg-black/5 text-ink-soft",
                  ].join(" ")}
                >
                  {row.status}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3 rounded-panel bg-white/60 px-4 py-3.5 backdrop-blur-xl">
          <p className="min-w-0 flex-1 text-[12px] leading-[1.55] text-ink-soft">
            The working flow in this build is <strong>Exams</strong> — upload,
            question extraction, answer mapping, highlighting and grading.
          </p>
          <button
            type="button"
            onClick={onBack}
            className="inline-flex h-10 shrink-0 items-center gap-2 rounded-full bg-ink px-5 text-[13px] font-semibold text-white transition hover:bg-black"
          >
            <Exams width={15} height={15} />
            Go to Exams
          </button>
        </div>
      </div>
    </section>
  );
}

function IconButton({
  label,
  children,
  onClick,
  active,
}: {
  label: string;
  children: React.ReactNode;
  onClick?: () => void;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className={[
        "grid h-9 w-9 place-items-center rounded-lg transition",
        active ? "bg-chip text-ink" : "text-ink-soft hover:bg-chip",
      ].join(" ")}
    >
      {children}
    </button>
  );
}
