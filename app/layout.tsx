import type { Metadata } from "next";
import { Fraunces, Work_Sans } from "next/font/google";
import Script from "next/script";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

const workSans = Work_Sans({
  subsets: ["latin"],
  variable: "--font-work-sans",
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Casa Alon — Puerto Princesa",
  description:
    "A small coastal hotel in Puerto Princesa, Palawan, built for slow mornings and no itinerary.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${fraunces.variable} ${workSans.variable} font-body`}>
        {children}
        <Script
          src="/widget.js"
          data-api-url="/api/chat"
          data-hotel="Casa Alon Hotel"
          data-phone="+63 917 000 0000"
          data-greeting="Hi, I'm Ask Alon. I can tell you about rooms, rates, amenities, or how to get here — what do you want to know?"
          strategy="afterInteractive"
        />
      </body>
    </html>
  );
}
