export default function CTA() {
  return (
    <section id="book" className="bg-sand px-6 py-28 md:px-10">
      <div className="mx-auto max-w-3xl text-center">
        <h2 className="font-display text-4xl text-ink md:text-5xl">
          Nine rooms. Book direct, pay less than the OTAs.
        </h2>
        <p className="mx-auto mt-5 max-w-measure text-ink/70">
          Email or call us directly and we&rsquo;ll hold the room ourselves —
          no commission, no markup. A booking widget can go right here once
          it&rsquo;s wired up.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
          <a
            href="mailto:stay@casaalon.com"
            className="rounded-full bg-tide px-7 py-3 text-sm font-medium text-foam transition-transform hover:scale-[1.03]"
          >
            stay@casaalon.com
          </a>
          <a
            href="tel:+639000000000"
            className="rounded-full border border-tide/30 px-7 py-3 text-sm text-tide transition-colors hover:border-tide"
          >
            +63 900 000 0000
          </a>
        </div>
      </div>
    </section>
  );
}
