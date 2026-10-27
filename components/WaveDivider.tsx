type WaveDividerProps = {
  from?: string;
  to?: string;
  flip?: boolean;
};

/**
 * A single hand-drawn tide line. Used sparingly as the page's one recurring
 * structural device — it marks where one "tide" of content ends and the
 * next begins, rather than decorating every section edge.
 */
export default function WaveDivider({
  from = "#FAF6EE",
  to = "#EFE6D8",
  flip = false,
}: WaveDividerProps) {
  return (
    <div
      aria-hidden="true"
      className={flip ? "rotate-180" : undefined}
      style={{ lineHeight: 0, backgroundColor: from }}
    >
      <svg
        viewBox="0 0 1200 80"
        preserveAspectRatio="none"
        className="h-10 w-full md:h-16"
      >
        <path
          d="M0,40 C150,80 350,0 600,40 C850,80 1050,0 1200,40 L1200,80 L0,80 Z"
          fill={to}
        />
      </svg>
    </div>
  );
}
