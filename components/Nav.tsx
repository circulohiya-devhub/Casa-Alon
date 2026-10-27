const LINKS = [
  { href: "#stay", label: "Rooms" },
  { href: "#amenities", label: "On the property" },
  { href: "#gallery", label: "Gallery" },
  { href: "#location", label: "Getting here" },
];

export default function Nav() {
  return (
    <header className="absolute inset-x-0 top-0 z-30">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6 md:px-10">
        <a href="#top" className="font-display text-xl text-foam">
          Casa Alon
        </a>
        <ul className="hidden items-center gap-8 text-sm text-foam/90 md:flex">
          {LINKS.map((link) => (
            <li key={link.href}>
              <a className="transition-colors hover:text-gold" href={link.href}>
                {link.label}
              </a>
            </li>
          ))}
        </ul>
        <a
          href="#book"
          className="rounded-full border border-foam/40 px-5 py-2 text-sm text-foam transition-colors hover:border-gold hover:text-gold"
        >
          Check availability
        </a>
      </nav>
    </header>
  );
}
