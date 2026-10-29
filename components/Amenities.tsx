import Image from "next/image";
import { PHOTOS, type Photo } from "./photos";

type Amenity = { name: string; note: string; span: string; photo?: Photo };

const AMENITIES: Amenity[] = [
  {
    name: "Saltwater pool",
    note: "Unheated, unchlorinated, open from sunrise.",
    span: "md:col-span-2 md:row-span-2",
    photo: PHOTOS.pool,
  },
  {
    name: "Beach access & kayaks",
    note: "Two kayaks, free to take out whenever.",
    span: "",
  },
  {
    name: "Low Tide Bar",
    note: "Opens at 5, closes when the last guest leaves.",
    span: "",
  },
  {
    name: "Coworking nook",
    note: "Fast wifi and a proper desk, for the one day you have to work.",
    span: "md:col-span-2",
  },
  {
    name: "All-day breakfast",
    note: "Local, simple, included.",
    span: "",
  },
  {
    name: "Bikes into town",
    note: "Fifteen minutes to the market, free to borrow.",
    span: "",
  },
];

export default function Amenities() {
  return (
    <section id="amenities" className="bg-tide px-6 py-24 md:px-10">
      <div className="mx-auto max-w-6xl">
        <h2 className="max-w-measure font-display text-4xl text-foam md:text-5xl">
          On the property
        </h2>

        <div className="mt-14 grid gap-4 md:grid-cols-4 md:grid-rows-2">
          {AMENITIES.map((item) => (
            <div
              key={item.name}
              className={`relative flex flex-col justify-end overflow-hidden border border-foam/15 p-6 ${
                item.photo ? "min-h-[320px]" : ""
              } ${item.span}`}
            >
              {item.photo && (
                <>
                  <Image
                    src={item.photo.src}
                    alt={item.photo.alt}
                    fill
                    sizes="(min-width: 768px) 50vw, 100vw"
                    className="object-cover"
                  />
                  <div
                    className="absolute inset-0 bg-gradient-to-t from-tide via-tide/40 to-transparent"
                    aria-hidden="true"
                  />
                </>
              )}
              <p className="relative font-display text-xl text-foam">{item.name}</p>
              <p className="relative mt-2 text-sm text-foam/75">{item.note}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
