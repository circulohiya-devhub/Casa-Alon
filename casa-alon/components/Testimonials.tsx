const QUOTES = [
  {
    quote:
      "We came for three nights and stayed for six. Nobody at the front desk even blinked when we changed the dates twice.",
    name: "Mika R.",
  },
  {
    quote:
      "The Horizon Room balcony at 6am is worth the whole trip by itself. Bring coffee out there before anyone wakes up.",
    name: "Theo & Pax",
  },
];

export default function Testimonials() {
  return (
    <section className="bg-tide px-6 py-24 md:px-10">
      <div className="mx-auto grid max-w-6xl gap-10 md:grid-cols-2 md:gap-16">
        {QUOTES.map((q) => (
          <blockquote key={q.name} className="max-w-measure">
            <p className="font-display text-2xl leading-snug text-foam md:text-3xl">
              &ldquo;{q.quote}&rdquo;
            </p>
            <footer className="mt-4 text-sm text-foam/60">{q.name}</footer>
          </blockquote>
        ))}
      </div>
    </section>
  );
}
