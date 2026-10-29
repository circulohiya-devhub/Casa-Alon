/**
 * Image loader for next/image. Instead of resizing photos on Vercel, it asks
 * Unsplash's own image service for the size each screen needs (Unsplash asks
 * sites to load their photos this way).
 *
 * When the hotel's own photos replace these, put them in /public (e.g.
 * /public/photos/pool.jpg) and set that path as the `src` in
 * components/photos.ts: local paths are passed through unchanged.
 */
export default function unsplashLoader({
  src,
  width,
  quality,
}: {
  src: string;
  width: number;
  quality?: number;
}): string {
  if (!src.startsWith("https://images.unsplash.com/")) return src;
  const url = new URL(src);
  url.searchParams.set("auto", "format");
  url.searchParams.set("fit", "crop");
  url.searchParams.set("w", String(width));
  url.searchParams.set("q", String(quality ?? 70));
  return url.toString();
}
