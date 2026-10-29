import Image from "next/image";
import Nav from "./Nav";
import { PHOTOS } from "./photos";

export default function Hero() {
  return (
    <section
      id="top"
      className="relative flex min-h-[92vh] flex-col justify-end overflow-hidden bg-ink"
    >
      {/* Header banner photo. Swap it in components/photos.ts. */}
      <Image
        src={PHOTOS.hero.src}
        alt={PHOTOS.hero.alt}
        fill
        priority
        sizes="100vw"
        className="object-cover"
      />
      {/* Darkens the bottom-left, where the headline sits, and the top edge
          behind the navigation, so text stays readable over any photo. */}
      <div
        className="absolute inset-0"
        aria-hidden="true"
        style={{
          background:
            "linear-gradient(to top, rgba(18,35,33,.92) 0%, rgba(18,35,33,.55) 38%, rgba(18,35,33,.10) 70%), " +
            "linear-gradient(to bottom, rgba(18,35,33,.55) 0%, rgba(18,35,33,0) 22%), " +
            "linear-gradient(to right, rgba(18,35,33,.45) 0%, rgba(18,35,33,0) 60%)",
        }}
      />

      {/* The one orchestrated motion on the page: a slow, continuous drift,
          never a per-element hover/scroll trick. */}
      <div className="absolute inset-x-0 bottom-0 h-40 overflow-hidden opacity-60">
        <svg
          viewBox="0 0 2400 160"
          className="animate-drift h-full w-[200%]"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            d="M0,96 C150,40 300,140 450,96 C600,52 750,140 900,96 C1050,52 1200,140 1350,96 C1500,52 1650,140 1800,96 C1950,52 2100,140 2250,96 L2400,96 L2400,160 L0,160 Z M1200,96 C1350,40 1500,140 1650,96 C1800,52 1950,140 2100,96 C2250,52 2400,140 2550,96 C2700,52 2850,140 3000,96 C3150,52 3300,140 3450,96 L3600,96 L3600,160 L1200,160 Z"
            fill="#7FA996"
            fillOpacity="0.25"
          />
        </svg>
      </div>

      <Nav />

      <div className="relative z-10 mx-auto w-full max-w-6xl px-6 pb-20 pt-40 md:px-10 md:pb-28">
        <p className="mb-5 text-sm text-seafoam">Puerto Princesa, Palawan</p>
        <h1 className="max-w-3xl font-display text-5xl leading-[1.08] text-foam md:text-7xl">
          Come in like the tide.
          <br />
          Leave when you&rsquo;re ready.
        </h1>
        <p className="mt-6 max-w-measure text-lg text-foam/80">
          Casa Alon is a nine-room house on Palawan&rsquo;s coast, built
          around the idea that you&rsquo;re only here once — so there&rsquo;s
          no itinerary, no rush, and nowhere you have to be.
        </p>
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <a
            href="#book"
            className="rounded-full bg-gold px-7 py-3 text-sm font-medium text-ink transition-transform hover:scale-[1.03]"
          >
            Check availability
          </a>
          <a
            href="#stay"
            className="rounded-full border border-foam/30 px-7 py-3 text-sm text-foam transition-colors hover:border-foam"
          >
            See the rooms
          </a>
        </div>
      </div>
    </section>
  );
}
