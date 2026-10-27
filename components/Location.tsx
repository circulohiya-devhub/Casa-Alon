export default function Location() {
  return (
    <section id="location" className="bg-foam px-6 py-24 md:px-10">
      <div className="mx-auto grid max-w-6xl gap-10 md:grid-cols-2 md:gap-20">
        <div>
          <h2 className="font-display text-4xl text-ink md:text-5xl">
            Getting here
          </h2>
          <div className="mt-6 max-w-measure space-y-4 text-ink/80">
            <p>
              Casa Alon sits on the coast road outside Puerto Princesa,
              about twenty minutes from the airport and fifteen from the
              market by bike.
            </p>
            <p>
              We&rsquo;ll arrange an airport pickup for any arrival — just
              send your flight details after you book.
            </p>
          </div>
          <dl className="mt-10 grid grid-cols-2 gap-6 text-sm">
            <div>
              <dt className="text-ink/50">Address</dt>
              <dd className="mt-1 text-ink">
                Sitio Alon, Barangay San Pedro
                <br />
                Puerto Princesa, Palawan
              </dd>
            </div>
            <div>
              <dt className="text-ink/50">Check-in / check-out</dt>
              <dd className="mt-1 text-ink">2:00 PM / 11:00 AM</dd>
            </div>
          </dl>
        </div>
        <div
          className="min-h-[320px] rounded-sm"
          style={{
            background:
              "radial-gradient(circle at 70% 30%, #7FA996 0%, #1F3A3D 60%, #122321 100%)",
          }}
          aria-hidden="true"
        />
      </div>
    </section>
  );
}
