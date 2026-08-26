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

const BLURB: Record<string, string> = {
  home: "The teacher's dashboard — classes, recent exams and pending evaluations.",
  classroom: "Class rosters, seating and student profiles.",
  assignments: "Homework set, submitted and returned.",
  library: "Saved papers, rubrics and question banks.",
  settings: "School, marking and account preferences.",
  toolkit: "The wider set of AI tools for teachers.",
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
                Delhi Public School
              </span>
              <span className="block truncate text-[10.5px] text-ink-faint">
                Bokaro Steel City
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
  const label = NAV.find((n) => n.key === section)?.label ?? "Exams";

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
            src="/avatar.png"
            alt=""
            width={184}
            height={184}
            className="h-8 w-8 select-none rounded-full"
            draggable={false}
          />
          <span className="hidden text-[13px] font-medium lg:inline">
            Madhur Rastogi
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
              src="/avatar.png"
              alt=""
              width={184}
              height={184}
              className="h-9 w-9 rounded-full"
            />
            <span>
              <span className="block text-[12.5px] font-semibold">
                Madhur Rastogi
              </span>
              <span className="block text-[11px] text-ink-faint">
                Delhi Public School
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
  const nav = NAV.find((n) => n.key === section);
  const Icon = nav?.Icon ?? Settings;
  const title =
    nav?.label ??
    (section === "toolkit" ? "AI Teacher's Toolkit" : "Settings");

  return (
    <section className="flex flex-1 items-center justify-center px-4 pb-8">
      <div className="w-full max-w-105 rounded-panel bg-white/60 px-6 py-9 text-center backdrop-blur-xl">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-chip text-ink-soft">
          <Icon width={22} height={22} />
        </span>
        <h2 className="mt-3.5 text-[17px] font-bold">{title}</h2>
        <p className="mt-1.5 text-[12.5px] leading-[1.55] text-ink-soft">
          {BLURB[section]}
        </p>
        <p className="mt-3 text-[12px] leading-[1.55] text-ink-faint">
          This assignment implements the <strong>Exams</strong> flow — upload,
          extraction, answer mapping and grading. The rest of the product is
          shown for context and is deliberately not built.
        </p>
        <button
          type="button"
          onClick={onBack}
          className="mt-5 inline-flex h-10 items-center gap-2 rounded-full bg-ink px-5 text-[13px] font-semibold text-white transition hover:bg-black"
        >
          <Exams width={15} height={15} />
          Go to Exams
        </button>
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
