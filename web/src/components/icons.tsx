/** Inline SVG so the app ships with no icon dependency and no network fetch. */

type P = React.SVGProps<SVGSVGElement>;

const base = (props: P) => ({
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  ...props,
});

export const Logo = (props: P) => (
  <svg width={26} height={26} viewBox="0 0 32 32" fill="none" {...props}>
    <rect width="32" height="32" rx="9" fill="#303030" />
    <path
      d="M9 10.5 16 22l7-11.5"
      stroke="#fff"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <circle cx="16" cy="12" r="1.9" fill="#ff5623" />
  </svg>
);

/**
 * The brand sparkle: one large four-point star with a smaller one below-left,
 * a small one to the right and a dot upper-left — the arrangement used on the
 * processing screen in the design.
 */
export const Sparkle = (props: P) => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor" {...props}>
    <path d="M13.6 2c.5 5.1 2.3 6.9 7.4 7.4-5.1.5-6.9 2.3-7.4 7.4-.5-5.1-2.3-6.9-7.4-7.4C11.3 8.9 13.1 7.1 13.6 2Z" />
    <path d="M8.8 11.8c.3 3.2 1.4 4.3 4.6 4.6-3.2.3-4.3 1.4-4.6 4.6-.3-3.2-1.4-4.3-4.6-4.6 3.2-.3 4.3-1.4 4.6-4.6Z" />
    <path d="M18.8 12.8c.16 1.66.74 2.24 2.4 2.4-1.66.16-2.24.74-2.4 2.4-.16-1.66-.74-2.24-2.4-2.4 1.66-.16 2.24-.74 2.4-2.4Z" />
    <circle cx="7.1" cy="8.4" r="1.05" />
  </svg>
);

export const PanelToggle = (props: P) => (
  <svg {...base(props)}>
    <rect x="3" y="4" width="18" height="16" rx="3" />
    <path d="M9.5 4v16" />
  </svg>
);

export const Home = (props: P) => (
  <svg {...base(props)}>
    <rect x="3.5" y="3.5" width="7" height="7" rx="2" />
    <rect x="13.5" y="3.5" width="7" height="7" rx="2" />
    <rect x="3.5" y="13.5" width="7" height="7" rx="2" />
    <rect x="13.5" y="13.5" width="7" height="7" rx="2" />
  </svg>
);

export const Classroom = (props: P) => (
  <svg {...base(props)}>
    <rect x="3" y="5" width="18" height="13" rx="2.5" />
    <path d="m3 14 4.2-3.6 3.4 2.8 3-2.4L21 15" />
    <circle cx="8.6" cy="9.1" r="1.2" />
  </svg>
);

export const Assignments = (props: P) => (
  <svg {...base(props)}>
    <path d="M6 3.5h8.5L19 8v12.5H6z" />
    <path d="M14 3.5V8h4.6M9 13h6M9 16.5h4" />
  </svg>
);

export const Exams = (props: P) => (
  <svg {...base(props)}>
    <rect x="5" y="4" width="14" height="17" rx="2.4" />
    <path d="M9 3h6v3H9z" />
    <path d="M9 12h6M9 16h4" />
  </svg>
);

export const Library = (props: P) => (
  <svg {...base(props)}>
    <path d="M12 3.6a8.4 8.4 0 1 0 8.4 8.4H12z" />
    <path d="M14.8 3.9A8.4 8.4 0 0 1 20.1 9.2h-5.3z" />
  </svg>
);

export const ArrowRight = (props: P) => (
  <svg {...base(props)}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

export const Settings = (props: P) => (
  <svg {...base(props)}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 14.5a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.2a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.2a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.2a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.2a1.6 1.6 0 0 0-1.4 1Z" />
  </svg>
);

export const Help = (props: P) => (
  <svg {...base(props)}>
    <circle cx="12" cy="12" r="8.6" />
    <path d="M9.8 9.4a2.3 2.3 0 1 1 3.1 2.2c-.6.25-.9.8-.9 1.45v.35" />
    <path d="M12 16.6h.01" />
  </svg>
);

export const Bell = (props: P) => (
  <svg {...base(props)}>
    <path d="M18 9a6 6 0 1 0-12 0c0 5-2 6.5-2 6.5h16S18 14 18 9Z" />
    <path d="M13.7 19a2 2 0 0 1-3.4 0" />
  </svg>
);

export const ArrowLeft = (props: P) => (
  <svg {...base(props)}>
    <path d="M19 12H5M11 6l-6 6 6 6" />
  </svg>
);

export const Chevron = ({
  dir = "down",
  ...props
}: P & { dir?: "up" | "down" | "left" | "right" }) => {
  const rotate = { down: 0, left: 90, up: 180, right: 270 }[dir];
  return (
    <svg {...base(props)} style={{ transform: `rotate(${rotate}deg)` }}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
};

export const UploadCloud = (props: P) => (
  <svg {...base(props)}>
    <path d="M12 15V4.5M8.4 8.1 12 4.5l3.6 3.6" />
    <path d="M5 15v3.2A1.8 1.8 0 0 0 6.8 20h10.4a1.8 1.8 0 0 0 1.8-1.8V15" />
  </svg>
);

export const Close = (props: P) => (
  <svg {...base(props)}>
    <path d="m7 7 10 10M17 7 7 17" />
  </svg>
);

export const Plus = (props: P) => (
  <svg {...base(props)}>
    <path d="M12 5.5v13M5.5 12h13" />
  </svg>
);

export const Minus = (props: P) => (
  <svg {...base(props)}>
    <path d="M5.5 12h13" />
  </svg>
);

export const Menu = (props: P) => (
  <svg {...base(props)}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </svg>
);

export const PdfBadge = (props: P) => (
  <svg width={34} height={34} viewBox="0 0 34 34" fill="none" {...props}>
    <rect width="34" height="34" rx="8" fill="#ffe9e2" />
    <path
      d="M12 9h7l4 4v12H12z"
      stroke="#c0350a"
      strokeWidth="1.6"
      strokeLinejoin="round"
    />
    <path d="M19 9v4h4" stroke="#c0350a" strokeWidth="1.6" strokeLinejoin="round" />
    <text
      x="17"
      y="22.5"
      textAnchor="middle"
      fontSize="6.5"
      fontWeight="700"
      fill="#c0350a"
      fontFamily="inherit"
    >
      PDF
    </text>
  </svg>
);

export const School = (props: P) => (
  <svg width={28} height={28} viewBox="0 0 28 28" fill="none" {...props}>
    <circle cx="14" cy="14" r="13" fill="#f1f6ee" stroke="#d6e3d0" />
    <path
      d="M14 6.5 20 10v3.5c0 4-2.6 6.6-6 8-3.4-1.4-6-4-6-8V10z"
      stroke="#34ac15"
      strokeWidth="1.4"
      strokeLinejoin="round"
    />
  </svg>
);
