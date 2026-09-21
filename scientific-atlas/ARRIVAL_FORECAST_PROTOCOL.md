# Scientific Data Atlas — ARRIVAL FORECAST Protocol

Version: 0.1
Established: 2026-09-21

## Purpose

Extend YOU ARE HERE from a static reference state into a **temporal neighborhood model** capable of identifying plausible future arrivals.

"Arrival" is deliberately broader than spacecraft.

It may describe:
- natural bodies
- spacecraft
- probes
- meteoroids/comets/asteroids
- electromagnetic signals
- neutrinos/gravitational signals where modelled
- atmospheric or geophysical phenomena
- biological/ecological arrivals
- human transport
- scientific datasets or information arriving from external archives
- hypothetical technological or cultural arrivals

The archive must distinguish observed trajectories from speculative scenarios.

## 1. Arrival object

Every arrival forecast is an object:

ArrivalPrediction
- target
- source/origin
- carrier/object
- state vector or propagation model
- observation epoch
- arrival window
- arrival condition
- reference frame
- time scale
- model/version
- assumptions
- uncertainty/covariance
- evidence
- prediction status
- verification event

## 2. Arrival classes

### OBSERVED_TRACK

A real object/signal with a measured trajectory.

### PREDICTED_NATURAL

A natural phenomenon propagated from observations.

### SCHEDULED_HUMAN

A known launch, transit, landing, pass, delivery, or other planned event.

### HYPOTHETICAL

A physically permitted but currently unobserved scenario.

### SEARCH_TARGET

A defined search region/window generated from models.

### SPECULATIVE

A scenario whose premises are substantially uncertain or not empirically established.

Never mix these statuses in one ranking.

## 3. Arrival condition

"Arrival" must have an explicit definition.

Examples:
- crosses geofence
- reaches altitude
- enters atmosphere
- reaches orbital sphere
- crosses heliopause
- reaches a detector
- reaches a communication horizon
- intersects observation cone
- comes within distance d
- satisfies velocity threshold
- becomes detectable above signal-to-noise threshold

Without an arrival condition, an arrival prediction is not reproducible.

## 4. Propagation

Preserve:
- initial state
- epoch
- frame
- time scale
- equations/model
- perturbations
- numerical integrator
- step size where material
- physical constants/version
- ephemeris version
- covariance
- process noise
- observations used
- residuals

For celestial objects, retain the original ephemeris or trajectory solution alongside every regenerated solution.

## 5. Arrival window

Never store only one future timestamp when uncertainty matters.

Use:

- earliest plausible arrival
- central/best-estimate arrival
- latest plausible arrival
- confidence/credible interval
- covariance or equivalent uncertainty representation

Example:

arrival_window:
  earliest = 2410-04-03T...
  median   = 2410-04-11T...
  latest   = 2410-04-24T...
  confidence = 0.95

Exact representation depends on the propagation problem.

## 6. Reverse trajectory

Every forecast should support inverse exploration:

future arrival
    ↓
possible trajectory
    ↓
possible origin
    ↓
historical observations

This creates a bridge between YOU ARE HERE and archaeological evidence.

## 7. Reachability graph

Add temporal edges:

- will_pass
- may_pass
- intersects
- likely_arrives
- possible_arrival
- observed_arrival
- missed_expected_arrival
- delayed
- trajectory_updated
- origin_candidate
- signal_backtrace
- detection_window
- communication_window

Every edge carries model and confidence metadata.

## 8. Arrival horizons

Maintain multiple horizons:

H0: days–years
H1: decades
H2: centuries
H3: millennia
H4: deep time

Long-horizon predictions should not be presented with the same visual confidence as short-horizon trajectory solutions.

## 9. Detectability layer

A physical arrival does not imply observable arrival.

For every signal/object, model separately:

physical_arrival
→ observational_visibility
→ instrument_detection
→ archive_capture
→ human recognition

This is especially important for:
- electromagnetic signals
- faint small bodies
- transient astronomical events
- historical archives
- future communication attempts

## 10. Arrival vs visitation

Do not infer intent from trajectory.

The archive should distinguish:

ARRIVAL:
an object/event reaches the defined boundary.

VISITATION:
an interpreted purpose/intent claim.

The second requires independent evidence.

## 11. Null-arrival records

Expected arrivals that do not occur are scientifically valuable.

Preserve:
- prediction version
- expected window
- observations used
- actual observations
- discrepancy
- updated model
- reason for revision when established

Prediction failure is evidence.

## 12. Continuous updating

A prediction should become a version chain:

P0 initial prediction
  ↓
P1 new observation
  ↓
P2 revised trajectory
  ↓
P3 arrival window narrowed
  ↓
P4 arrival confirmed / missed / reclassified

Never overwrite P0.

## 13. Search for unrecognized arrivals

The atlas may generate discovery targets where:
- a predicted object should have appeared but did not
- an unexplained observation lies near a predicted trajectory
- independent archives contain coincident transient observations
- different domains record the same temporal event
- a historical anomaly becomes explainable under a modern propagation model

These are **search hypotheses**, not discoveries.

## 14. Cross-correlation

Arrival forecasts should automatically correlate with:
- astronomical catalogs
- spacecraft ephemerides
- historical observation archives
- atmospheric records
- seismic/infrasound records
- electromagnetic transient catalogs
- radar observations
- satellite tracking
- biological observation databases
- historical shipping/aviation records
- archival timestamps

Any relationship must retain its source and confidence.

## 15. Long-term "arrivals"

For deep-time civilization-independent preservation, an arrival can also mean a future researcher encountering the archive.

The system should therefore preserve:

archive_availability_window
  → expected mirror locations
  → dependency risk
  → migration deadlines
  → future recovery pathways

Thus the Atlas forecasts not only physical arrivals, but **information's future survivability**.

## 16. YOU ARE HERE + ARRIVAL

The combined model becomes:

PAST
  ↓
YOU WERE HERE
  ↓
CURRENT STATE
  ↓
YOU ARE HERE
  ↓
REACHABILITY FIELD
  ↓
POTENTIAL ARRIVALS
  ↓
FUTURE OBSERVATIONS
  ↓
YOU MAY BE THERE

## 17. Anti-prognostication rule

Forecast confidence must follow the physics and evidence.

Never turn:
- possibility into probability
- probability into certainty
- trajectory into intention
- coincidence into causation
- model output into observation

The system must make uncertainty more visible as prediction horizon increases.

## 18. Core principle

**A coordinate tells us where something is. A trajectory tells us where it can go. An arrival model tells us when it can intersect a defined boundary.**

The Atlas should preserve all three.
