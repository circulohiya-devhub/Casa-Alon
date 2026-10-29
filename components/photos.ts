/**
 * Every photo on the landing page, in one place. These are free photos from
 * Unsplash (https://unsplash.com/license), used as placeholders until the
 * hotel's own photography is ready. To swap one out, change its `src` here:
 * any images.unsplash.com address works as-is; for your own photos, see
 * lib/unsplash-loader.ts.
 */
export type Photo = {
  src: string;
  alt: string;
  credit: string;
  page: string; // the photo's Unsplash page, for credits
};

const unsplash = (id: string) => `https://images.unsplash.com/${id}`;

export const PHOTOS = {
  hero: {
    src: unsplash("photo-1633416963871-182a155ab86a"),
    alt: "Beach cottages and a pier on the shore at BM Beach, Barangay San Pedro, Puerto Princesa",
    credit: "Michael Maga-ao",
    page: "https://unsplash.com/photos/3qhvbUj47mQ",
  },
  tideRoom: {
    src: unsplash("photo-1702255489644-392758161f1f"),
    alt: "A quiet hotel room with a bed, an armchair and a window",
    credit: "Wes Hicks",
    page: "https://unsplash.com/photos/T6WRDVQBn8M",
  },
  horizonRoom: {
    src: unsplash("photo-1729606188713-814d1b7bf893"),
    alt: "A bedroom opening onto a balcony with a view of the water",
    credit: "Antonio Araujo",
    page: "https://unsplash.com/photos/mbOoyHwNsWU",
  },
  driftwoodLoft: {
    src: unsplash("photo-1696522627202-4b9a36078087"),
    alt: "Breakfast fruit on a table on a terrace overlooking the sea at sunrise",
    credit: "Altınay Dinç",
    page: "https://unsplash.com/photos/8NR6riMfTGE",
  },
  pool: {
    src: unsplash("photo-1678434701613-384d4f9d7587"),
    alt: "Aerial view of a pool surrounded by palm trees beside the beach",
    credit: "Simon Pallard",
    page: "https://unsplash.com/photos/aykNlz3m_XM",
  },
  coast: {
    src: unsplash("photo-1676123648517-005f71a03bcf"),
    alt: "Aerial view of turquoise water and a long beach at Alimanguan, San Vicente, Palawan",
    credit: "Michael Maga-ao",
    page: "https://unsplash.com/photos/JRShmDvtxeY",
  },
  sunrise: {
    src: unsplash("photo-1714746977531-6be2235cb63a"),
    alt: "Sunrise over the sea and a rocky headland in El Nido, Palawan",
    credit: "Omri D. Cohen",
    page: "https://unsplash.com/photos/C9W8fr6rzfg",
  },
  kayak: {
    src: unsplash("photo-1752892730981-0c0ef804777a"),
    alt: "A kayak on calm turquoise water",
    credit: "Javardh",
    page: "https://unsplash.com/photos/i_mcVjuzZd4",
  },
} satisfies Record<string, Photo>;
