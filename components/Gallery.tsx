const TILES = [
  { bg: "linear-gradient(160deg, #7FA996, #1F3A3D)", tall: true },
  { bg: "linear-gradient(160deg, #EFE6D8, #C9962C)", tall: false },
  { bg: "linear-gradient(160deg, #1F3A3D, #122321)", tall: false },
  { bg: "linear-gradient(160deg, #C9962C, #122321)", tall: true },
  { bg: "linear-gradient(160deg, #7FA996, #EFE6D8)", tall: false },
  { bg: "linear-gradient(160deg, #122321, #1F3A3D)", tall: false },
];

export default function Gallery() {
  return (
    <section id="gallery" className="bg-sand px-6 py-24 md:px-10">
      <div className="mx-auto max-w-6xl">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-4xl text-ink md:text-5xl">
            Around the house
          </h2>
          <p className="hidden text-sm text-ink/50 md:block">
            Placeholder tiles — drop in real photography here.
          </p>
        </div>

        <div className="mt-12 grid grid-cols-2 gap-3 md:grid-cols-3">
          {TILES.map((tile, i) => (
            <div
              key={i}
              className={`rounded-sm ${tile.tall ? "aspect-[3/4]" : "aspect-square"}`}
              style={{ background: tile.bg }}
              aria-hidden="true"
            />
          ))}
        </div>
      </div>
    </section>
  );
}
