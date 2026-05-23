# CircuitShelf Roadmap

## Completed MVPs

- Parts Inventory + Project Finder
  - Store the user's real lab parts in Postgres.
  - Match inventory against indexed books, datasheets, and extracted component intelligence.
  - Show buildable project candidates, missing parts, substitutions when available, and source evidence.
  - Allow promising candidates to become Bench plans.

- Photo-based bench check
  - Let a user upload a breadboard or wiring photo.
  - Save the photo with a Bench plan and generate a plan-specific manual inspection checklist.
  - Analyze photo quality, edge density, dominant colors, and wire-like color pixels.
  - Future work: real visual wire tracing and mistake detection.

- Source-to-bench traceability
  - Every Bench step should link back to exact document pages, chunks, images, and pinout evidence.
  - Useful for trust, debugging, and learning why a step exists.

- Circuit simulator export
  - Generate Bench markdown, LTspice starter notes, and Falstad/CircuitJS drawing notes from a Bench plan.
  - Generate starter SPICE/CircuitJS topologies for recognized LED/resistor and 555 timer plans.
  - Future work: infer broader node-level schematics for op-amp, transistor, sensor, and microcontroller circuits.

- Learning mode
  - Turn Bench plans into guided lessons.
  - Walk through plan steps with learning prompts before moving to the next step.
  - Explain why each power, ground, resistor, capacitor, and signal connection exists.

## Future Deepening

- Real photo-based wire tracing and component recognition.
- Wider simulator netlist generation for common circuit families.
- KiCad schematic export once node-level circuit inference exists.
- Learning-mode answer grading using the local model.
