/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    // Photos are served at the right size by Unsplash's image service.
    loader: "custom",
    loaderFile: "./lib/unsplash-loader.ts",
  },
};

export default nextConfig;
