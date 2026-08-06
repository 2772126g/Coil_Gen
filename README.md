# PCB Reaction Wheel Stator Generator

A Python tool for generating, validating, visualising, and exporting a PCB-integrated motor stator winding for a CubeSat reaction wheel.

The project generates a multi-layer PCB winding geometry from a defined winding specification, checks manufacturing feasibility, validates electrical topology, produces engineering visualisations, and exports the copper geometry into a KiCad-compatible PCB file.

---

# Project Purpose

The aim of this tool is to support the design of a compact PCB motor stator for a CubeSat reaction wheel system.

The generator allows winding parameters to be changed and automatically updates:

- coil geometry
- layer utilisation
- phase distribution
- via transitions
- copper routing geometry
- KiCad output
- design visualisations

This enables rapid design iteration before PCB layout integration.

---

# Current Features

## Parametric Winding Generation

The winding geometry is generated from a central specification file.

Current supported parameters include:

- number of poles
- number of phases
- number of coils
- copper layers
- trace width
- spacing
- coil arc angle
- annular stator dimensions
- turns per layer

The generator automatically calculates:

- achievable turns
- radial and tangential fill
- series turns per phase
- winding feasibility

---

## Manufacturing Feasibility Check

Before generating geometry, the tool checks whether the winding can physically fit.

Current checks:

- radial conductor packing
- tangential conductor packing
- available coil arc width
- target turns per layer

---

## Multi-Layer PCB Coil Generation

The generator creates:

- individual coil geometry
- multi-layer winding stacks
- buried/blind via transitions
- phase grouping
- star connection point

---

## Winding Validation

The generated winding is automatically checked for:

### Topology

- coil continuity
- phase chain connectivity
- star connection

### Manufacturing Constraints

- via spacing
- coil radius clearance
- layer transitions

---

## Visualisation Generation

The tool automatically generates PNG engineering drawings.

Available views:

### Phase View

Shows coils coloured by electrical phase.

Useful for:

- winding arrangement
- phase balance
- coil ordering

### Layer View

Shows copper distribution by PCB layer.

Useful for:

- stack-up inspection
- layer utilisation

### Individual Layer Views

Each copper layer is exported separately.

Useful for:

- PCB layout checking
- manufacturing review

Old generated images are automatically removed before regeneration.

---

## KiCad Export

The generator exports the copper geometry into the generated output folder


Currently exported:

- copper segments
- PCB layers
- buried/blind vias
- phase nets

The exporter is intentionally board-independent.

The generated winding can therefore be placed onto different PCB layouts.

---

# Running the Generator

From the project root:

```bash
python3 src/main.py


