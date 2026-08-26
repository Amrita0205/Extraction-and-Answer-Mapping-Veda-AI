"use client";

import { useEffect, useState } from "react";
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
  PanelToggle,
  School,
  Settings,
  Sparkle,
} from "./icons";

const NAV = [
  { label: "Home", Icon: Home },
  { label: "My Classroom", Icon: Classroom },
  { label: "Assignments", Icon: Assignments },
  { label: "Exams", Icon: Exams, active: true },
  { label: "My Library", Icon: Library },
];

/**
 * The chrome from the design: a sidebar that collapses to a 64px icon rail,
 * and a glass top bar. The upload screens show it expanded; the loading and
 * mapping screens show the rail, which is what gives the split view its width.
 */
export function AppShell({
  collapsed: fromView = false,
  children,
}: {
  collapsed?: boolean;
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(fromView);

  // The design collapses the sidebar to the rail once the split view opens,
  // and expands it again on the upload screen — but the teacher's own toggle
  // still wins until the view changes under them.
  useEffect(() => setCollapsed(fromView), [fromView]);

  return (
    <div className="flex h-dvh gap-0 overflow-hidden p-2.5 sm:p-3">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex min-h-0 flex-1 flex-col overflow-y-auto sm:overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}

function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <aside
      className={[
        "hidden shrink-0 flex-col rounded-[20px] bg-white/85 py-3 shadow-[0_1px_2px_rgba(0,0,0,0.04)] backdrop-blur-xl transition-[width] duration-200 sm:flex",
        collapsed ? "w-16 items-center px-2" : "w-[188px] px-3",
      ].join(" ")}
    >
      <div
        className={[
          "flex items-center",
          collapsed ? "justify-center" : "justify-between px-1",
        ].join(" ")}
      >
        <span className="flex items-center gap-2">
          <Logo />
          {!collapsed && (
            <span className="text-[15px] font-bold tracking-tight">VedaAI</span>
          )}
        </span>
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
        {NAV.map(({ label, Icon, active }) => (
          <button
            key={label}
            type="button"
            title={collapsed ? label : undefined}
            className={[
              "flex items-center rounded-lg text-[13px] transition",
              collapsed ? "h-9 w-9 justify-center" : "h-9 w-full gap-2.5 px-2.5",
              active
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
          title={collapsed ? "Settings" : undefined}
          className={[
            "flex items-center rounded-lg text-[13px] text-ink-soft transition hover:bg-chip/70 hover:text-ink",
            collapsed ? "h-9 w-9 justify-center" : "h-9 w-full gap-2.5 px-2.5",
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

function TopBar() {
  return (
    <header className="mx-0 mb-2.5 flex h-14 items-center gap-2 rounded-[16px] bg-white/60 px-3 backdrop-blur-xl sm:mx-3">
      <button
        type="button"
        aria-label="Back"
        className="grid h-9 w-9 place-items-center rounded-lg text-ink-soft transition hover:bg-chip"
      >
        <ArrowLeft />
      </button>
      <span className="flex items-center gap-1.5 text-[13px] text-ink-soft">
        <Exams width={15} height={15} />
        Exams
      </span>

      <div className="ml-auto flex items-center gap-1">
        <IconButton label="Help">
          <Help />
        </IconButton>
        <IconButton label="Notifications">
          <span className="relative">
            <Bell />
            <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-brand" />
          </span>
        </IconButton>
        <button
          type="button"
          aria-label="AI"
          className="grid h-9 w-9 place-items-center rounded-full bg-chip text-brand transition hover:bg-brand-wash"
        >
          <Sparkle width={16} height={16} />
        </button>
        <span className="ml-1 flex items-center gap-2 rounded-full py-1 pl-1 pr-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/avatar.png"
            alt=""
            width={184}
            height={184}
            className="h-8 w-8 select-none rounded-full"
            draggable={false}
          />
          <span className="hidden text-[13px] font-medium sm:inline">
            Madhur Rastogi
          </span>
          <Chevron width={15} height={15} className="text-ink-faint" />
        </span>
      </div>
    </header>
  );
}

function IconButton({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      className="grid h-9 w-9 place-items-center rounded-lg text-ink-soft transition hover:bg-chip"
    >
      {children}
    </button>
  );
}
