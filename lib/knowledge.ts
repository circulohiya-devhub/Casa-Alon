/**
 * Placeholder knowledge base for the "Ask Alon" chatbot.
 *
 * This is the easiest place to start: each entry becomes one retrievable
 * chunk in the vector store built in lib/rag.ts. Replace the content below
 * with real details about the property, or swap this whole module out for
 * a loader that pulls from a live source instead — e.g. LangChain's
 * GoogleDriveLoader / a Google Docs export, matching the approach already
 * used in the hotel-inquiry-rag project, or a fetch against the Hotelogix
 * API for live rates and availability.
 */

export type KnowledgeDoc = {
  id: string;
  topic: string;
  content: string;
};

export const KNOWLEDGE_BASE: KnowledgeDoc[] = [
  {
    id: "overview",
    topic: "Property overview",
    content:
      "Casa Alon is a nine-room boutique hotel in Puerto Princesa, Palawan, Philippines. It is built around a relaxed, unstructured philosophy: no fixed activity schedule, flexible stays, and an emphasis on slow mornings. The name 'Alon' means 'wave' in Filipino.",
  },
  {
    id: "rooms-tide",
    topic: "Tide Room",
    content:
      "The Tide Room is a 22 sqm garden-facing studio with a queen bed, sleeps 2 guests, and rates start from PHP 4,800 per night including breakfast. It is the quietest room category in the house.",
  },
  {
    id: "rooms-horizon",
    topic: "Horizon Room",
    content:
      "The Horizon Room is a 30 sqm sea-facing room on the second floor with a private balcony, a king bed, and a daybed. It sleeps 2-3 guests and rates start from PHP 6,900 per night including breakfast.",
  },
  {
    id: "rooms-driftwood",
    topic: "Driftwood Loft",
    content:
      "The Driftwood Loft is a 45 sqm two-level suite with a private terrace and a soaking tub. It sleeps up to 4 guests and rates start from PHP 9,500 per night including breakfast. It is the largest and most private room category.",
  },
  {
    id: "amenities",
    topic: "Amenities",
    content:
      "Casa Alon's amenities include an unheated saltwater pool open from sunrise, direct beach access with two complimentary kayaks, the Low Tide Bar (open from 5pm), a coworking nook with fast wifi and a desk, complimentary all-day breakfast, and complimentary bicycles for the 15-minute ride into town.",
  },
  {
    id: "policies",
    topic: "Check-in, check-out and policies",
    content:
      "Check-in time is 2:00 PM and check-out time is 11:00 AM. Early check-in and late check-out can be arranged on request, subject to availability. Breakfast is included with every room rate.",
  },
  {
    id: "location",
    topic: "Location and transport",
    content:
      "Casa Alon is located on the coast road outside Puerto Princesa, about 20 minutes from Puerto Princesa International Airport and 15 minutes by bicycle from the public market. Airport pickup can be arranged after booking by sharing flight details.",
  },
  {
    id: "booking",
    topic: "Booking and contact",
    content:
      "Guests can book directly by emailing stay@casaalon.com or calling +63 900 000 0000, which avoids OTA commissions. A direct online booking widget is planned for a future update to the website.",
  },
];
