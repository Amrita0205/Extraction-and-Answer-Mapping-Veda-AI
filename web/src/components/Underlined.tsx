/**
 * The design underlines the leading letter of "Question(s)" wherever it
 * appears — the headline, the segmented control, the list header. It is small
 * enough to miss and consistent enough to be deliberate, so it lives in one
 * place rather than being re-typed at each call site.
 */
export function Underlined({ children }: { children: string }) {
  const [first, ...rest] = children;
  return (
    <>
      <span className="relative">
        {first}
        <span className="absolute -bottom-0.5 left-0 h-0.375 w-full rounded bg-current" />
      </span>
      {rest.join("")}
    </>
  );
}
