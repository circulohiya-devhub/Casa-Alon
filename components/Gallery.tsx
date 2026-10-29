import Image from "next/image";
import { PHOTOS } from "./photos";

// One large photo beside two stacked ones: the coastline leads, and the
// smaller frames show what a day here looks like.
export default function Gallery() {
  return (
    <section id="gallery" className="bg-sand px-6 py-24 md:px-10">
      <div className="mx-auto max-w-6xl">
        <h2 className="font-display text-4xl text-ink md:text-5xl">Around the house</h2>
        <p className="mt-4 max-w-measure text-ink/70">
          Palawan&rsquo;s coast is the reason to come: turquoise water, long empty
          beaches, and mornings worth getting up for.
        </p>

        <div className="mt-12 grid gap-3 md:grid-cols-[1.6fr_1fr] md:grid-rows-2">
          <figure className="relative aspect-[4/3] overflow-hidden rounded-sm md:row-span-2 md:aspect-auto">
            <Image
              src={PHOTOS.coast.src}
              alt={PHOTOS.coast.alt}
              fill
              sizes="(min-width: 768px) 60vw, 100vw"
              className="object-cover"
            />
          </figure>
          <figure className="relative aspect-[4/3] overflow-hidden rounded-sm">
            <Image
              src={PHOTOS.sunrise.src}
              alt={PHOTOS.sunrise.alt}
              fill
              sizes="(min-width: 768px) 40vw, 100vw"
              className="object-cover"
            />
          </figure>
          <figure className="relative aspect-[4/3] overflow-hidden rounded-sm">
            <Image
              src={PHOTOS.kayak.src}
              alt={PHOTOS.kayak.alt}
              fill
              sizes="(min-width: 768px) 40vw, 100vw"
              className="object-cover"
            />
          </figure>
        </div>
      </div>
    </section>
  );
}
