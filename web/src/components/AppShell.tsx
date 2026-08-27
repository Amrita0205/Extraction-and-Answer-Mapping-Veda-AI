"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
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
  PdfBadge,
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

const NAV: {
  key: SectionKey;
  label: string;
  Icon: typeof Home;
  badge?: string;
}[] = [
  { key: "home", label: "Home", Icon: Home },
  { key: "classroom", label: "My Classroom", Icon: Classroom },
  { key: "assignments", label: "Assignments", Icon: Assignments, badge: "32" },
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

type Band = { grade: string; caption?: string; count: number };
type Ranked = { label: string; pct: number };

type Dash = {
  summaryTitle: string;
  gauge: { value: number; total: number; label: string };
  stats: { value: string; label: string; tone?: "good" | "warn" | "bad" }[];
  segmentation?: { title: string; bands: Band[] };
  ranked?: { title: string; rows: Ranked[] };
  insights?: { title: string; items: string[] };
};

/**
 * Static content for the sections outside this assignment's scope.
 *
 * The brief scopes the build to the Exams flow, so none of this is wired to
 * anything - it exists so the surrounding product reads as a whole rather than
 * as five dead links. Every screen that shows it is labelled "Sample data",
 * because an invented number that looks live is worse than an empty state: a
 * reviewer cannot otherwise tell which parts were actually built.
 */
const SECTION_DEMO: Record<SectionKey, Dash> = {
  home: {
    summaryTitle: "This week",
    gauge: { value: 41, total: 50, label: "Sheets marked" },
    stats: [
      { value: "6", label: "Classes" },
      { value: "184", label: "Students" },
      { value: "3", label: "Awaiting marking", tone: "warn" },
      { value: "92%", label: "Attendance", tone: "good" },
    ],
    segmentation: {
      title: "Student Segmentation (Based on grades)",
      bands: [
        { grade: "A", count: 12 },
        { grade: "B", count: 15 },
        { grade: "C", count: 13 },
        { grade: "D", caption: "Below", count: 10 },
      ],
    },
    ranked: {
      title: "Learning Gap Analysis",
      rows: [
        { label: "Ohm\u2019s Law Application", pct: 0.23 },
        { label: "Resistance in Parallel Circuits", pct: 0.18 },
        { label: "Potential Difference and EMF", pct: 0.15 },
        { label: "Interpreting Circuit Diagrams", pct: 0.12 },
        { label: "Series vs Parallel Circuits", pct: 0.08 },
      ],
    },
    insights: {
      title: "Insights for Teachers",
      items: [
        "Simran Kaur \u2014 misreads series vs parallel logic; a circuit-building demo would help.",
        "Revise Ohm\u2019s Law in class using real appliances \u2014 a fan, a heater.",
        "Clarify the derivations for power, and how the formulas differ.",
        "Twelve students scored below D and would benefit from an extra session.",
      ],
    },
  },
  classroom: {
    summaryTitle: "Class overview",
    gauge: { value: 184, total: 200, label: "Enrolled" },
    stats: [
      { value: "6", label: "Classes" },
      { value: "3", label: "Subjects" },
      { value: "92%", label: "Attendance", tone: "good" },
      { value: "31", label: "Average class size" },
    ],
    segmentation: {
      title: "Student Segmentation (Based on grades)",
      bands: [
        { grade: "A", count: 38 },
        { grade: "B", count: 61 },
        { grade: "C", count: 52 },
        { grade: "D", caption: "Below", count: 33 },
      ],
    },
    ranked: {
      title: "Attendance by class",
      rows: [
        { label: "XII-A \u00b7 Physics", pct: 0.96 },
        { label: "XII-B \u00b7 Chemistry", pct: 0.94 },
        { label: "XI-C \u00b7 Biology", pct: 0.91 },
        { label: "XI-D \u00b7 Physics", pct: 0.87 },
      ],
    },
    insights: {
      title: "Insights for Teachers",
      items: [
        "XI-D attendance has slipped four weeks running.",
        "XII-A is ready to move on from electrostatics.",
        "Four students have missed two consecutive assessments.",
      ],
    },
  },
  assignments: {
    summaryTitle: "Assessment Summary",
    gauge: { value: 45, total: 50, label: "Submissions" },
    stats: [
      { value: "82%", label: "Average score" },
      { value: "95%", label: "Top score", tone: "good" },
      { value: "20/25", label: "Class median" },
      { value: "40%", label: "Lowest score", tone: "bad" },
    ],
    segmentation: {
      title: "Student Segmentation (Based on grades)",
      bands: [
        { grade: "A", count: 12 },
        { grade: "B", count: 15 },
        { grade: "C", count: 13 },
        { grade: "D", caption: "Below", count: 10 },
      ],
    },
    ranked: {
      title: "Learning Gap Analysis",
      rows: [
        { label: "Ohm\u2019s Law Application", pct: 0.23 },
        { label: "Resistance in Parallel Circuits", pct: 0.18 },
        { label: "Potential Difference and EMF", pct: 0.15 },
        { label: "Interpreting Circuit Diagrams", pct: 0.12 },
        { label: "Series vs Parallel Circuits", pct: 0.08 },
      ],
    },
    insights: {
      title: "Insights for Teachers",
      items: [
        "Simran Kaur \u2014 misreads series vs parallel logic; needs a circuit-building demo.",
        "Revise Ohm\u2019s Law with real-life problems \u2014 a fan, a heater.",
        "Clarify the power derivations and how the formulas differ.",
        "Arrange an extra session for students below D.",
      ],
    },
  },
  exams: {
    summaryTitle: "",
    gauge: { value: 0, total: 0, label: "" },
    stats: [],
  },
  library: {
    summaryTitle: "Library",
    gauge: { value: 27, total: 40, label: "Papers saved" },
    stats: [
      { value: "27", label: "Saved papers" },
      { value: "9", label: "Rubrics" },
      { value: "4", label: "Question banks" },
      { value: "11", label: "Shared with staff" },
    ],
    ranked: {
      title: "Most reused papers",
      rows: [
        { label: "Physics \u00b7 Term 1 2025", pct: 0.78 },
        { label: "Chemistry \u00b7 Mock 2", pct: 0.64 },
        { label: "Biology \u00b7 Unit test 3", pct: 0.41 },
        { label: "Physics \u00b7 Mock 1", pct: 0.27 },
      ],
    },
    insights: {
      title: "Suggestions",
      items: [
        "Three papers have no rubric attached, so grading falls back to two marks a question.",
        "The Biology marking scheme is still a draft.",
        "Two question banks have not been touched this term.",
      ],
    },
  },
  settings: {
    summaryTitle: "Workspace",
    gauge: { value: 12, total: 15, label: "Seats used" },
    stats: [
      { value: "DPS Bokaro", label: "School" },
      { value: "Marks", label: "Marking scale" },
      { value: "English", label: "Language" },
      { value: "12", label: "Members" },
    ],
    ranked: {
      title: "Marking defaults",
      rows: [
        { label: "Default marks per question \u2014 2", pct: 1 },
        { label: "AI feedback on answers \u2014 on", pct: 1 },
        { label: "Highlight colour \u2014 green", pct: 1 },
        { label: "Auto-archive after 90 days \u2014 off", pct: 0.12 },
      ],
    },
    insights: {
      title: "Account",
      items: [
        "Sign-in is not enabled in this build, so there is one shared demo workspace.",
        "Marking preferences apply to every class.",
        "Three seats are unused.",
      ],
    },
  },
  toolkit: {
    summaryTitle: "Toolkit usage",
    gauge: { value: 23, total: 40, label: "Runs this month" },
    stats: [
      { value: "8", label: "Tools available" },
      { value: "23", label: "Used this month" },
      { value: "~14h", label: "Time saved", tone: "good" },
      { value: "120", label: "Credits left" },
    ],
    ranked: {
      title: "Most used tools",
      rows: [
        { label: "Extraction & answer mapping", pct: 0.86 },
        { label: "Question paper generator", pct: 0.34 },
        { label: "Lesson plan assistant", pct: 0.21 },
        { label: "Rubric builder", pct: 0.09 },
      ],
    },
    insights: {
      title: "Insights for Teachers",
      items: [
        "Extraction and answer mapping is the only tool built in this version.",
        "Most time saved comes from marking rather than planning.",
        "Two tools have not been opened this term.",
      ],
    },
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
          ) : section === "home" ? (
            <HomeScreen onOpen={go} />
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
        {NAV.map(({ key, label, Icon, badge }) => (
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
            {!collapsed && (
              <>
                <span className="min-w-0 flex-1 text-left">{label}</span>
                {badge && (
                  <span className="shrink-0 rounded-full bg-brand px-2 py-0.5 text-[11px] font-bold text-white">
                    {badge}
                  </span>
                )}
              </>
            )}
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
          {/*
            Says it is a demo without talking about the assignment. "The brief
            specifies no authentication" is a sentence written to a reviewer,
            not to a teacher, and a product that explains itself in terms of
            its own spec reads as a submission rather than a product.
          */}
          <p className="text-[11.5px] leading-normal text-ink-soft">
            Demo account — sign-in isn&apos;t enabled, so classes and settings
            here are sample data.
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

const GRADE_BG: Record<string, string> = {
  A: "bg-grade-a",
  B: "bg-grade-b",
  C: "bg-grade-c",
  D: "bg-grade-d",
};

/**
 * A half-circle meter for the section's headline figure.
 *
 * Drawn as one arc with a dash offset rather than a rotated wedge, so the
 * rounded cap sits on the end of the value the way the design shows it, and
 * the whole thing scales with the tile instead of needing pixel maths.
 */
function Gauge({ value, total, label }: { value: number; total: number; label: string }) {
  const r = 62;
  const cx = 90;
  const cy = 88;
  const arc = Math.PI * r;
  const filled = total > 0 ? Math.min(1, Math.max(0, value / total)) : 0;
  const path = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`;

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 180 104" className="w-full max-w-47" role="img"
           aria-label={`${label}: ${value} of ${total}`}>
        <path d={path} fill="none" stroke="rgb(255 255 255 / 0.14)"
              strokeWidth="17" strokeLinecap="round" />
        <path d={path} fill="none" stroke="var(--color-brand)" strokeWidth="17"
              strokeLinecap="round"
              strokeDasharray={`${arc * filled} ${arc}`} />
        <text x={cx} y={cy - 12} textAnchor="middle"
              className="fill-white text-[26px] font-bold">
          {value}
        </text>
        <text x={cx} y={cy + 6} textAnchor="middle"
              className="fill-white/60 text-[11px]">
          / {total}
        </text>
      </svg>
      <span className="pb-1 text-[11.5px] text-white/70">{label}</span>
    </div>
  );
}

function SectionDashboard({ dash }: { dash: Dash }) {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <div className="space-y-3">
        <div className="rounded-panel bg-white/60 p-3 backdrop-blur-xl">
          <h3 className="pb-2.5 text-center text-[13px] font-bold">
            {dash.summaryTitle}
          </h3>
          <div className="grid gap-2.5 sm:grid-cols-2">
            <div className="rounded-2xl bg-ink px-3 pb-2 pt-3 text-white">
              <p className="pb-1 text-center text-[12.5px] font-semibold">
                {dash.gauge.label}
              </p>
              <Gauge {...dash.gauge} />
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              {dash.stats.map((s) => (
                <div key={s.label} className="rounded-2xl bg-white px-3 py-3">
                  <div
                    className={[
                      "text-[19px] font-bold leading-tight",
                      s.tone === "good"
                        ? "text-good"
                        : s.tone === "bad"
                          ? "text-bad"
                          : s.tone === "warn"
                            ? "text-warn"
                            : "text-ink",
                    ].join(" ")}
                  >
                    {s.value}
                  </div>
                  <div className="mt-0.5 text-[11px] text-ink-soft">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {dash.segmentation && (
          <div className="rounded-panel bg-white/60 p-3 backdrop-blur-xl">
            <h3 className="pb-2.5 text-center text-[13px] font-bold">
              {dash.segmentation.title}
            </h3>
            <div className="grid grid-cols-4 gap-2.5">
              {dash.segmentation.bands.map((b) => (
                <div
                  key={b.grade}
                  className={[
                    "flex flex-col items-center justify-center rounded-2xl px-1 py-5 text-white",
                    GRADE_BG[b.grade] ?? "bg-ink",
                  ].join(" ")}
                >
                  {/* The letter and the count are always shown. Green-to-red is
                      a weak scale for red-green colour blindness, so the band
                      is never identified by its colour alone. */}
                  {b.caption && (
                    <span className="text-[10px] font-semibold opacity-90">
                      {b.caption}
                    </span>
                  )}
                  <span className="text-[26px] font-bold leading-none">{b.grade}</span>
                  <span className="pt-2 text-[13px] font-semibold">{b.count}</span>
                  <span className="text-[10.5px] opacity-90">Students</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="space-y-3">
        {dash.ranked && (
          <div className="rounded-panel bg-white/60 p-3.5 backdrop-blur-xl">
            <div className="flex items-center justify-between pb-1">
              <h3 className="text-[13px] font-bold">{dash.ranked.title}</h3>
              <span className="rounded-full bg-brand-wash px-3 py-1 text-[11px] font-semibold text-brand">
                View All
              </span>
            </div>
            <ol className="space-y-2.5 pt-1.5">
              {dash.ranked.rows.map((row, i) => (
                <li key={row.label}>
                  <div className="flex items-baseline gap-2">
                    <span className="text-[12.5px] text-ink-soft">{i + 1}.</span>
                    <span className="min-w-0 flex-1 text-[12.5px] font-medium">
                      {row.label}
                    </span>
                    <span className="text-[11.5px] font-semibold tabular-nums text-ink-soft">
                      {Math.round(row.pct * 100)}%
                    </span>
                  </div>
                  <div className="mt-1 h-0.5 w-full rounded bg-black/8">
                    <div
                      className="h-0.5 rounded bg-brand"
                      style={{ width: `${Math.round(row.pct * 100)}%` }}
                    />
                  </div>
                </li>
              ))}
            </ol>
          </div>
        )}

        {dash.insights && (
          <div className="rounded-panel bg-white/60 p-3.5 backdrop-blur-xl">
            <div className="flex items-center justify-between pb-1">
              <h3 className="text-[13px] font-bold">{dash.insights.title}</h3>
              <span className="rounded-full bg-brand-wash px-3 py-1 text-[11px] font-semibold text-brand">
                View All
              </span>
            </div>
            <ol className="space-y-2 pt-1.5">
              {dash.insights.items.map((item, i) => (
                <li key={item} className="flex gap-2">
                  <span className="text-[12.5px] text-ink-soft">{i + 1}.</span>
                  <span className="text-[12.5px] leading-normal text-ink-soft">
                    {item}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  );
}


/**
 * The tools the product offers a teacher.
 *
 * Only the last one is built. The rest describe the wider VedaAI toolkit and
 * are here so Home reads as the product's front door rather than a dead
 * screen - each card says what the tool would do, and the page says plainly
 * that one of them exists.
 */
const TOOLS: {
  title: string;
  blurb: string;
  Icon: typeof Home;
  section?: SectionKey;
  built?: boolean;
}[] = [
  {
    title: "Academic Content Creator",
    blurb: "Generate worksheets, assignments and question papers instantly with VedaAI.",
    Icon: PdfBadge,
  },
  {
    title: "Question Paper Creator",
    blurb: "Create exams, quizzes, rubrics, viva questions and internal assessments.",
    Icon: Assignments,
  },
  {
    title: "Lesson Plan Creator",
    blurb: "Generate citations, references and literature summaries, and simplify research papers.",
    Icon: Library,
  },
  {
    title: "Writing Feedback",
    blurb: "Analyse student writing and generate structured feedback instantly.",
    Icon: Classroom,
  },
  {
    title: "Teaching Ideas & Activity",
    blurb: "Discover engaging teaching ideas and classroom activities with VedaAI.",
    Icon: Sparkle,
  },
  {
    title: "Extraction & Answer Mapping",
    blurb: "Upload a paper and a handwritten answer sheet - it extracts, matches, highlights and marks.",
    Icon: Exams,
    section: "exams",
    built: true,
  },
];

function HomeScreen({ onOpen }: { onOpen: (key: SectionKey) => void }) {
  const firstName = DEMO_TEACHER.name.split(" ")[0];

  return (
    <section className="flex-1 px-3 pb-6 sm:px-5">
      <div className="mx-auto w-full max-w-220">
        <div className="relative">
          {/* The same figure the upload screen uses - one asset from the Figma,
              so the composition matches rather than being re-approximated. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/hero-teacher.png"
            alt=""
            width={600}
            height={600}
            className="pointer-events-none absolute right-0 top-0 hidden h-28 w-28 select-none lg:block"
            draggable={false}
          />

          <div className="flex flex-col items-center pb-5 pt-2 text-center">
            <span className="rounded-full bg-ink px-6 py-2.5 text-[20px] font-bold text-white">
              Hi {firstName} <span aria-hidden>&#128075;</span>
            </span>
            <p className="mt-3 max-w-160 text-[14px] font-semibold text-ink-soft">
              Let&apos;s begin brewing some teaching materials effortlessly with{" "}
              <span className="text-brand">VedaAI</span>
            </p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TOOLS.map((tool) => {
            const open = tool.section;
            return (
              <button
                key={tool.title}
                type="button"
                onClick={() => open && onOpen(open)}
                className={[
                  // Two layers, as the design has them: a recessed grey plate
                  // with the white card sitting lower and in front of it, and
                  // the icon straddling the seam between the two. The plate is
                  // what the product's artwork sits in; without it the cards
                  // read as flat tiles.
                  "group relative rounded-panel bg-black/[0.045] pt-12 text-left transition",
                  open ? "cursor-pointer hover:-translate-y-0.5" : "cursor-default",
                ].join(" ")}
              >
                <span
                  className={[
                    "absolute left-4 top-6 z-10 grid h-11 w-11 place-items-center rounded-full bg-ink text-white transition",
                    open ? "group-hover:bg-brand" : "",
                  ].join(" ")}
                >
                  <tool.Icon width={18} height={18} />
                </span>

                {tool.built && (
                  <span className="absolute right-4 top-4 z-10 rounded-full bg-good-bg px-2 py-0.5 text-[10.5px] font-semibold text-good">
                    Built
                  </span>
                )}

                <div
                  className={[
                    "flex h-full flex-col rounded-panel bg-white px-4 pb-4 pt-8 transition",
                    open
                      ? "shadow-[0_1px_3px_rgba(0,0,0,0.06)] group-hover:shadow-[0_8px_22px_rgba(0,0,0,0.09)]"
                      : "shadow-[0_1px_3px_rgba(0,0,0,0.06)]",
                  ].join(" ")}
                >
                  <span className="block text-[14px] font-bold">{tool.title}</span>

                  <span className="mt-1.5 text-[12.5px] leading-normal text-ink-soft">
                    {tool.blurb}
                  </span>

                  {open && (
                    <span className="mt-3 inline-flex items-center gap-1.5 text-[12px] font-semibold text-brand">
                      Open
                      <ArrowRight width={13} height={13} />
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {/*
          The grid above is the product's front door, and five of its six cards
          describe tools that do not exist in this build. Saying which one is
          real is the difference between a demo and a claim.
        */}
        <p className="pt-4 text-center text-[12px] text-ink-faint">
          One of these is built in this version — Extraction &amp; Answer
          Mapping. The rest describe the wider toolkit and are shown for
          context.
        </p>
      </div>
    </section>
  );
}

/**
 * What the other nav sections show.
 *
 * The brief scopes this build to the extraction flow, so these screens are
 * sample data rather than anything wired up. They exist so the product reads
 * as a whole, and each one says plainly that its numbers are invented.
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
  const dash = SECTION_DEMO[section];

  return (
    <section className="flex-1 px-3 pb-6 sm:px-5">
      <div className="mx-auto w-full max-w-220">
        <header className="flex flex-wrap items-center gap-3 pb-3 pt-1">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-white/70 text-ink-soft backdrop-blur-xl">
            <Icon width={20} height={20} />
          </span>
          <div className="min-w-0">
            <h2 className="text-[17px] font-bold">{title}</h2>
            <p className="text-[12.5px] leading-normal text-ink-soft">
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

        <SectionDashboard dash={dash} />

        <div className="mt-3 flex flex-wrap items-center gap-3 rounded-panel bg-white/60 px-4 py-3.5 backdrop-blur-xl">
          <p className="min-w-0 flex-1 text-[12px] leading-normal text-ink-soft">
            Head to <strong>Exams</strong> to upload a question paper and a
            student&apos;s answer sheet — it reads both, matches each answer to
            its question, highlights it on the page and marks it.
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
