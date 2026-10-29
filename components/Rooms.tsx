import Image from "next/image";
import { PHOTOS, type Photo } from "./photos";

type Room = {
  name: string;
  size: string;
  sleeps: string;
  rate: string;
  description: string;
  photo: Photo;
};

const ROOMS: Room[] = [
  {
    name: "Tide Room",
    size: "22 sqm",
    sleeps: "2 guests",
    rate: "from ₱4,800/night",
    description:
      "A garden-facing studio with a queen bed, a reading corner, and shutters that stay open most of the day. The quietest rooms in the house.",
    photo: PHOTOS.tideRoom,
  },
  {
    name: "Horizon Room",
    size: "30 sqm",
    sleeps: "2–3 guests",
    rate: "from ₱6,900/night",
    description:
      "Second floor, sea-facing, with a private balcony and a daybed for the afternoon nap you didn't plan on taking. Best light in the house.",
    photo: PHOTOS.horizonRoom,
  },
  {
    name: "Driftwood Loft",
    size: "45 sqm",
    sleeps: "4 guests",
    rate: "from ₱9,500/night",
    description:
      "A two-level suite with a private terrace and a soaking tub built into reclaimed wood. For the trip you're not telling anyone the real price of.",
    photo: PHOTOS.driftwoodLoft,
  },
];

export default function Rooms() {
  return (
    <section id="stay" className="bg-foam px-6 py-24 md:px-10">
      <div className="mx-auto max-w-6xl">
        <h2 className="max-w-measure font-display text-4xl text-ink md:text-5xl">
          Nine rooms, three moods
        </h2>
        <p className="mt-4 max-w-measure text-ink/70">
          Every room looks out on something — a garden, the water, or both.
          Rates are per night, run high in dry season, and always include
          breakfast.
        </p>

        <div className="mt-16 space-y-16">
          {ROOMS.map((room, i) => (
            <div
              key={room.name}
              className={`grid items-center gap-8 md:grid-cols-2 md:gap-16 ${
                i % 2 === 1 ? "md:[&>*:first-child]:order-2" : ""
              }`}
            >
              <div className="relative aspect-[4/3] w-full overflow-hidden rounded-sm bg-sand">
                <Image
                  src={room.photo.src}
                  alt={room.photo.alt}
                  fill
                  sizes="(min-width: 768px) 50vw, 100vw"
                  className="object-cover"
                />
              </div>
              <div>
                <h3 className="font-display text-2xl text-tide md:text-3xl">
                  {room.name}
                </h3>
                <p className="mt-2 text-sm text-ink/60">
                  {room.size}, {room.sleeps}
                  <span className="block">{room.rate}</span>
                </p>
                <p className="mt-4 max-w-measure text-ink/80">
                  {room.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
