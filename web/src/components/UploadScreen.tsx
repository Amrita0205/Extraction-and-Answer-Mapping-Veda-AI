"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, Close, PdfBadge, UploadCloud } from "./icons";

const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPT = ".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff";

export function UploadScreen({
  onStart,
  error,
}: {
  onStart: (questionPaper: File, answerSheet: File) => void;
  error?: string | null;
}) {
  const [paper, setPaper] = useState<File | null>(null);
  const [sheet, setSheet] = useState<File | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  const ready = Boolean(paper && sheet);
  const message = localError ?? error;

  const accept = (file: File | null, set: (f: File | null) => void) => {
    setLocalError(null);
    if (file && file.size > MAX_BYTES) {
      setLocalError(`${file.name} is larger than the 10MB limit.`);
      return;
    }
    set(file);
  };

  return (
    <section className="flex flex-1 items-center justify-center px-3 pb-6 sm:px-6">
      <div className="w-full max-w-[880px] text-center">
        <Heading />
        <p className="mt-2.5 text-[14px] text-ink-soft">
          Upload both files to get started
        </p>

        <div className="mt-5 flex justify-center">
          {/* Extracted from the Figma design — rings, badges and figure are one
              asset so the composition matches exactly. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/hero-teacher.png"
            alt=""
            width={600}
            height={600}
            className="h-[132px] w-[132px] select-none sm:h-[156px] sm:w-[156px]"
            draggable={false}
          />
        </div>

        <div className="mt-5 rounded-panel bg-white/55 p-3 backdrop-blur-xl sm:p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Dropzone
              label="Question Paper"
              file={paper}
              onFile={(f) => accept(f, setPaper)}
            />
            <Dropzone
              label="Answer Sheet"
              file={sheet}
              onFile={(f) => accept(f, setSheet)}
            />
          </div>
        </div>

        <div className="mt-6">
          <button
            type="button"
            disabled={!ready}
            onClick={() => paper && sheet && onStart(paper, sheet)}
            className={[
              "inline-flex h-12 items-center gap-2 rounded-full px-7 text-[14px] font-semibold transition",
              ready
                ? "bg-ink text-white hover:bg-black"
                : "cursor-not-allowed bg-black/10 text-ink-faint",
            ].join(" ")}
          >
            Start Mapping
            <ArrowRight width={17} height={17} />
          </button>
          <p className="mt-3 text-[12px] text-ink-faint">
            Once both files are uploaded, you&apos;ll be able to map answers with
            questions
          </p>
          {message && (
            <p className="mt-3 text-[13px] font-medium text-bad">{message}</p>
          )}
        </div>
      </div>
    </section>
  );
}

/**
 * The design gives the headline two treatments: plain dark on a phone, and
 * orange on a peach wash from the small breakpoint up. The underline sits
 * under the "Q" alone in both.
 */
function Heading() {
  return (
    <h1 className="text-[26px] font-bold leading-[1.2] tracking-[-0.01em] sm:text-[38px]">
      Upload{" "}
      <span className="relative inline-block sm:px-2 sm:text-brand">
        <span className="absolute inset-x-0 -inset-y-0.5 -z-10 hidden rounded-[6px] bg-brand-wash sm:block" />
        <span className="relative">
          Q
          <span className="absolute -bottom-0.5 left-0 h-[2px] w-full rounded bg-current" />
        </span>
        uestion Paper &amp; Answer Sheets
      </span>
    </h1>
  );
}

function Dropzone({
  label,
  file,
  onFile,
}: {
  label: string;
  file: File | null;
  onFile: (file: File | null) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const pages = usePageCount(file);

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        onFile(e.dataTransfer.files?.[0] ?? null);
      }}
      className={[
        // The dashed frame stays put once a file is chosen — the chip drops
        // into it rather than replacing it.
        "flex h-[150px] items-center justify-center rounded-2xl border border-dashed bg-white/45 px-4 transition sm:h-[190px]",
        over ? "border-brand bg-brand-wash/60" : "border-black/15",
        file ? "" : "cursor-pointer hover:border-brand/50",
      ].join(" ")}
      onClick={file ? undefined : () => input.current?.click()}
    >
      {file ? (
        <div className="relative flex w-full max-w-[330px] items-center gap-3 rounded-[12px] bg-chip px-3.5 py-3">
          <PdfBadge />
          <span className="min-w-0 flex-1 text-left">
            <span className="block truncate text-[14px] font-semibold">
              {file.name}
            </span>
            <span className="block text-[12px] text-ink-faint">
              {formatSize(file.size)}
              {pages ? ` • ${pages} ${pages === 1 ? "Page" : "Pages"}` : ""}
            </span>
          </span>
          <button
            type="button"
            aria-label={`Remove ${file.name}`}
            onClick={(event) => {
              event.stopPropagation();
              onFile(null);
              if (input.current) input.current.value = "";
            }}
            className="absolute -right-3 -top-3 grid h-7 w-7 place-items-center rounded-full bg-ink text-white shadow-sm transition hover:bg-black"
          >
            <Close width={14} height={14} />
          </button>
        </div>
      ) : (
        <span className="flex flex-col items-center gap-2">
          <span className="grid h-10 w-10 place-items-center rounded-[10px] bg-chip text-ink-soft">
            <UploadCloud width={18} height={18} />
          </span>
          <span className="text-[15px] font-semibold">
            Upload <span className="text-brand">{label}</span>
          </span>
          <span className="text-[11.5px] text-ink-faint">Max 10MB</span>
        </span>
      )}

      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />
    </div>
  );
}

/**
 * Page count for the file chip, read off the PDF itself.
 *
 * Counting `/Type /Page` in the raw bytes is the cheap trick — it avoids
 * pulling a PDF parser into the bundle for one line of caption text, and it is
 * only a caption, so a miss just omits the count rather than showing a wrong
 * one. Non-PDFs are a single page by definition here.
 */
function usePageCount(file: File | null): number | null {
  const [pages, setPages] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!file) {
      setPages(null);
      return;
    }
    if (file.type && !file.type.includes("pdf")) {
      setPages(1);
      return;
    }

    file
      .arrayBuffer()
      .then((buffer) => {
        if (cancelled) return;
        const text = new TextDecoder("latin1").decode(new Uint8Array(buffer));
        const matches = text.match(/\/Type\s*\/Page[^s]/g);
        setPages(matches?.length ? matches.length : null);
      })
      .catch(() => {
        if (!cancelled) setPages(null);
      });

    return () => {
      cancelled = true;
    };
  }, [file]);

  return pages;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${Math.round(bytes / (1024 * 1024))}MB`;
}
