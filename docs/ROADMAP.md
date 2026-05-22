# CircuitShelf Roadmap

## Current Focus

- Parts Inventory + Project Finder
  - Store the user's real lab parts in Postgres.
  - Match inventory against indexed books, datasheets, and extracted component intelligence.
  - Show buildable project candidates, missing parts, substitutions when available, and source evidence.
  - Allow promising candidates to become Bench plans.

## Next Standout Features

- Photo-based bench check
  - Let a user upload a breadboard or wiring photo.
  - Compare the photo against a Bench plan and flag likely wiring mistakes.

- Source-to-bench traceability
  - Every Bench step should link back to exact document pages, chunks, images, and pinout evidence.
  - Useful for trust, debugging, and learning why a step exists.

- Circuit simulator export
  - Generate starter circuits for tools such as Falstad, LTspice, or KiCad from a build card or Bench plan.
  - Start with simple resistor/LED/555/op-amp circuits before attempting broader coverage.

- Learning mode
  - Turn Bench plans into guided lessons.
  - Ask short questions before revealing the next connection or measurement.
  - Explain why each power, ground, resistor, capacitor, and signal connection exists.
