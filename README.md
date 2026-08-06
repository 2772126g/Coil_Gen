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
