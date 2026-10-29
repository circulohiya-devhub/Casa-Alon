import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy notice — Casa Alon",
  description: "How Casa Alon's AI chat assistant uses your information.",
};

// Template privacy notice for the chat assistant. It reflects what the system
// actually does (see api/_memory.py, api/_booking.py, api/_pms.py). Have it
// reviewed against the Data Privacy Act of 2012 before real guests use the site,
// and update the contact details below.
const SECTIONS: { title: string; body: string[] }[] = [
  {
    title: "Who we are",
    body: [
      "Casa Alon Hotel, Puerto Princesa City, Palawan, is responsible for the information collected through the chat assistant on this website.",
    ],
  },
  {
    title: "About the chat assistant",
    body: [
      "Ask Alon is an AI assistant, not a person. It answers questions from our hotel information and checks live room rates and availability in our reservation system. Its replies can contain mistakes, so our front desk confirms all bookings, and you can ask for a person at any time.",
    ],
  },
  {
    title: "What we collect and why",
    body: [
      "Your chat messages, so the assistant can answer you and keep track of the conversation.",
      "If you request a reservation: your name, email address, mobile number, travel dates and number of guests, so we can send you a confirmation email, place the room on hold in our reservation system, and contact you about payment.",
      "If you ask for a person: the recent conversation, sent to our staff so they can follow up without asking you to repeat yourself.",
      "We don't collect payment details in the chat.",
    ],
  },
  {
    title: "Who processes it for us",
    body: [
      "To run the assistant, your information passes through service providers acting on our behalf: Google (the AI model, and the email account our messages are sent from), Hotelogix (our reservation system), Upstash (short-term conversation storage), Vercel (website hosting), and LangChain's LangSmith (service logs we use to check and improve the assistant's answers).",
    ],
  },
  {
    title: "How long we keep it",
    body: [
      "Chat conversations are kept for 24 hours, in our storage and in your browser. Unconfirmed reservation requests expire after 24 hours. Reservations placed in our reservation system are kept as part of your booking record. Service logs are kept for a limited period for troubleshooting.",
    ],
  },
  {
    title: "Your rights",
    body: [
      "Under the Data Privacy Act of 2012, you can ask to access, correct, or delete your personal information, or object to how we use it. To do so, or for any privacy question, email management@casaalonhotel.ph or call our front desk at +63 917 000 0000.",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-foam px-6 py-16 md:px-10">
      <div className="mx-auto max-w-measure">
        <a href="/" className="text-sm text-tide underline underline-offset-4">
          Back to Casa Alon
        </a>
        <h1 className="mt-8 font-display text-4xl text-ink md:text-5xl">Privacy notice</h1>
        <p className="mt-4 text-ink/70">How our AI chat assistant uses your information.</p>

        <div className="mt-12 space-y-10">
          {SECTIONS.map((section) => (
            <section key={section.title}>
              <h2 className="font-display text-2xl text-tide">{section.title}</h2>
              <div className="mt-3 space-y-3 text-ink/80">
                {section.body.map((paragraph) => (
                  <p key={paragraph}>{paragraph}</p>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </main>
  );
}
