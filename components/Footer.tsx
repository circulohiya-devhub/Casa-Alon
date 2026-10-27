export default function Footer() {
  return (
    <footer className="bg-ink px-6 py-10 md:px-10">
      <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 text-sm text-foam/50 md:flex-row md:items-center">
        <span className="font-display text-foam/80">Casa Alon</span>
        <span>Puerto Princesa, Palawan, Philippines</span>
        <span>&copy; {new Date().getFullYear()} Casa Alon</span>
      </div>
    </footer>
  );
}
