import { PHOTOS } from "./photos";

// One credit per photographer, linking to their photos on Unsplash.
const CREDITS = Object.values(PHOTOS).reduce<{ credit: string; page: string }[]>(
  (list, photo) =>
    list.some((c) => c.credit === photo.credit) ? list : [...list, { credit: photo.credit, page: photo.page }],
  [],
);

export default function Footer() {
  return (
    <footer className="bg-ink px-6 py-10 md:px-10">
      <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 text-sm text-foam/50 md:flex-row md:items-center">
        <span className="font-display text-foam/80">Casa Alon</span>
        <span>Puerto Princesa, Palawan, Philippines</span>
        <a href="/privacy" className="underline-offset-4 hover:text-foam hover:underline">
          Privacy notice
        </a>
        <span>&copy; {new Date().getFullYear()} Casa Alon</span>
      </div>
      <p className="mx-auto mt-6 max-w-6xl text-xs leading-relaxed text-foam/40">
        Photos from Unsplash by{" "}
        {CREDITS.map((c, i) => (
          <span key={c.credit}>
            <a href={c.page} className="underline underline-offset-2 hover:text-foam/80" target="_blank" rel="noopener">
              {c.credit}
            </a>
            {i < CREDITS.length - 2 ? ", " : i === CREDITS.length - 2 ? " and " : "."}
          </span>
        ))}
      </p>
    </footer>
  );
}
