"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { pageUrl } from "@/lib/api";
import type { PageInfo, Region } from "@/lib/types";
import { Chevron, Minus, Plus } from "./icons";

const ZOOMS = [60, 80, 100, 125, 150, 200];

/**
 * The answer sheet, with the selected answer's region highlighted.
 *
 * Regions arrive as page fractions, so the overlay is positioned in percent
 * and stays correct at any zoom or container width — no pixel maths, nothing
 * to recompute on resize.
 */
export function AnswerSheet({
  pages,
  regions,
  label,
}: {
  pages: PageInfo[];
  regions: Region[];
  label: string | null;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<(HTMLDivElement | null)[]>([]);
  const highlight = useRef<HTMLDivElement | null>(null);
  const [zoom, setZoom] = useState(100);
  const [current, setCurrent] = useState(0);
  // Bumped whenever a page image finishes loading. Scrolling before the image
  // has laid out lands on the wrong offset, so the scroll waits for this.
  const [layout, setLayout] = useState(0);

  const first = regions[0];

  // Bring the highlight into view when the teacher picks a different question.
  useEffect(() => {
    if (!first || !highlight.current) return;
    const frame = requestAnimationFrame(() => {
      highlight.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
    return () => cancelAnimationFrame(frame);
  }, [first, layout, zoom]);

  // Keep the pager honest whether the teacher used the chevrons or just scrolled.
  const onScroll = useCallback(() => {
    const container = scroller.current;
    if (!container) return;
    const middle = container.scrollTop + container.clientHeight / 2;
    let index = 0;
    pageRefs.current.forEach((node, i) => {
      if (node && node.offsetTop <= middle) index = i;
    });
    setCurrent(index);
  }, []);

  const step = (delta: number) => {
    const next = Math.min(pages.length - 1, Math.max(0, current + delta));
    const target = pageRefs.current[next];
    if (target && scroller.current) {
      scroller.current.scrollTo({ top: target.offsetTop - 8, behavior: "smooth" });
    }
  };

  const zoomBy = (delta: number) => {
    const index = ZOOMS.indexOf(zoom);
    const next = ZOOMS[Math.min(ZOOMS.length - 1, Math.max(0, index + delta))];
    setZoom(next);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[20px] bg-white">
      <header className="flex h-12 shrink-0 items-center gap-2 bg-ink px-3 text-white">
        <span className="shrink-0 whitespace-nowrap text-[13px] font-semibold">
          Answer Sheet
        </span>

        <div className="ml-auto flex items-center gap-1.5">
          <span className="flex items-center gap-1 rounded-full bg-white/10 px-1.5 py-1">
            <button
              type="button"
              aria-label="Zoom out"
              onClick={() => zoomBy(-1)}
              className="grid h-6 w-6 place-items-center rounded-full transition hover:bg-white/15"
            >
              <Minus width={13} height={13} />
            </button>
            <span className="min-w-[42px] text-center text-[11.5px] tabular-nums">
              {zoom}%
            </span>
            <button
              type="button"
              aria-label="Zoom in"
              onClick={() => zoomBy(1)}
              className="grid h-6 w-6 place-items-center rounded-full transition hover:bg-white/15"
            >
              <Plus width={13} height={13} />
            </button>
          </span>

          <span className="flex items-center gap-1 rounded-full bg-white/10 px-1.5 py-1">
            <button
              type="button"
              aria-label="Previous page"
              onClick={() => step(-1)}
              disabled={current === 0}
              className="grid h-6 w-6 place-items-center rounded-full transition hover:bg-white/15 disabled:opacity-35"
            >
              <Chevron dir="left" width={13} height={13} />
            </button>
            <span className="text-[11.5px] tabular-nums">
              Page {current + 1} of {pages.length}
            </span>
            <button
              type="button"
              aria-label="Next page"
              onClick={() => step(1)}
              disabled={current >= pages.length - 1}
              className="grid h-6 w-6 place-items-center rounded-full transition hover:bg-white/15 disabled:opacity-35"
            >
              <Chevron dir="right" width={13} height={13} />
            </button>
          </span>
        </div>
      </header>

      <div
        ref={scroller}
        onScroll={onScroll}
        className="no-scrollbar min-h-0 flex-1 overflow-auto bg-[#fafafa] px-3 py-3"
      >
        <div
          className="mx-auto space-y-4"
          style={{ width: `${zoom}%`, maxWidth: zoom > 100 ? "none" : "100%" }}
        >
          {pages.map((page, index) => (
            <div
              key={page.index}
              ref={(node) => {
                pageRefs.current[index] = node;
              }}
              className="relative overflow-hidden rounded-lg bg-white shadow-[0_1px_6px_rgba(0,0,0,0.08)]"
            >
              {/* Plain <img>: these are one-off PNGs served by the API, so
                  next/image would add a loader hop for no benefit. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={pageUrl(page.url)}
                alt={`Answer sheet page ${page.index + 1}`}
                width={page.width}
                height={page.height}
                className="block w-full select-none"
                draggable={false}
                onLoad={() => setLayout((n) => n + 1)}
              />

              {regions
                .filter((region) => region.page === page.index)
                .map((region, i) => (
                  <Highlight
                    key={`${region.page}-${i}`}
                    region={region}
                    label={label}
                    showTag={i === 0}
                    innerRef={
                      region === first
                        ? (node) => {
                            highlight.current = node;
                          }
                        : undefined
                    }
                  />
                ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Highlight({
  region,
  label,
  showTag,
  innerRef,
}: {
  region: Region;
  label: string | null;
  showTag: boolean;
  innerRef?: (node: HTMLDivElement | null) => void;
}) {
  return (
    <div
      ref={innerRef}
      className="pointer-events-none absolute animate-rise rounded-[6px] border-2 border-highlight-line bg-highlight-fill shadow-[0_0_0_1.5px_#fff]"
      style={{
        left: `${region.x0 * 100}%`,
        top: `${region.y0 * 100}%`,
        width: `${(region.x1 - region.x0) * 100}%`,
        height: `${(region.y1 - region.y0) * 100}%`,
      }}
    >
      {showTag && label && (
        <span className="absolute -top-[9px] left-0 rounded-[4px] bg-highlight-tag px-1.5 py-[1px] text-[9.5px] font-bold leading-[14px] text-white">
          {label}
        </span>
      )}
    </div>
  );
}
