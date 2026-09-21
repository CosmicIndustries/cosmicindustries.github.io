# Scientific Data Atlas — YOU ARE HERE Anchor Registry

Version: 0.1
Snapshot: 2026-09-21

## Purpose

A future reader should be able to reconstruct **where and when the archive's observations occurred** without knowing modern language or trusting one coordinate system.

"YOU ARE HERE" is therefore represented as a layered state:

**mathematics -> physical units -> time -> celestial frame -> solar-system state -> terrestrial frame -> local site -> observation**

No one layer is sufficient.

## 1. Mathematical anchors

These have no dependence on Earth's physical artifacts or political conventions.

- Natural numbers: 0, 1, 2, 3...
- Prime sequence
- Integer ratios
- Equality / inequality
- Euclidean geometry
- Circle geometry
- pi (π)
- e
- irrationality demonstrations
- dimensional analysis
- symmetry
- vector arithmetic
- coordinate transformations

### Recommended bootstrap examples

- circumference / diameter = π
- exponential growth / natural logarithm relationship = e
- Pythagorean relationship
- prime factorization
- binary and positional numeral demonstrations
- negative-number and zero demonstrations

Preserve these in symbolic, numeric, diagrammatic, and textual forms.

## 2. SI defining constants

The current SI is defined using seven exact defining constants:

| Anchor | Exact value | Role |
|---|---:|---|
| caesium hyperfine frequency Δν_Cs | 9,192,631,770 Hz | defines second |
| speed of light c | 299,792,458 m/s | defines metre with second |
| Planck constant h | 6.62607015×10^-34 J s | defines kilogram through SI relationships |
| elementary charge e | 1.602176634×10^-19 C | defines ampere through charge/time |
| Boltzmann constant k | 1.380649×10^-23 J/K | defines kelvin |
| Avogadro constant N_A | 6.02214076×10^23 mol^-1 | defines mole |
| luminous efficacy K_cd | 683 lm/W | defines candela |

These are exact by the current SI definition, not experimental estimates.

Source: BIPM SI defining constants.

## 3. Fundamental-physics variants

The Atlas must preserve complete historical CODATA tables, not merely current values.

Known revision series:

- 1969
- 1973
- 1986
- 1998
- 2002
- 2006
- 2010
- 2014
- 2018
- 2022
- 2026 adjustment: future/current-work transition at this snapshot; preserve separately when released

The 2022 adjustment is currently the latest published CODATA set at this snapshot. NIST states that the 2026 adjustment is the next scheduled adjustment, with qualifying evidence through 31 December 2026.

Important measured/derived anchors to preserve include:

- fine-structure constant α
- gravitational constant G
- electron/proton/neutron masses
- electron/proton charge and magnetic moments
- Planck reduced constant ħ
- atomic mass constant
- Rydberg constant
- Bohr radius
- classical electron radius
- Compton wavelengths
- Josephson and von Klitzing relations
- Boltzmann and molar-gas constants
- radiation constants
- particle masses and energy equivalents
- weak/electroweak constants where included
- all recommended correlation coefficients/covariances

CODATA relationships and covariance matter because constants are not independent measurements.

## 4. Astronomical distance anchors

### Astronomical unit

1 au = 149,597,870,700 m exactly.

The AU is an exact defined length, not a measured present-day Earth-Sun distance.

### Light travel

Retain:

- c
- light-second
- light-minute
- light-hour
- light-day
- light-year as a derived unit

Use the physical relation first and human-readable units second.

## 5. IAU nominal solar and planetary anchors

IAU 2015 Resolution B3 established exact nominal conversion constants for standardized stellar/planetary comparisons.

### Solar

- nominal solar radius R^N_sun = 6.957×10^8 m
- nominal total solar irradiance S^N_sun = 1361 W/m²
- nominal solar luminosity L^N_sun = 3.828×10^26 W
- nominal solar effective temperature T^N_eff,sun = 5772 K
- nominal solar mass parameter (GM)^N_sun = 1.3271244×10^20 m³/s²

### Earth

- nominal equatorial radius R^N_E,e = 6378.1 km
- nominal polar radius R^N_E,p = 6356.8 km
- nominal terrestrial mass parameter (GM)^N_E = 3.986004×10^14 m³/s²

### Jupiter

- nominal equatorial radius R^N_J,e = 71492 km
- nominal polar radius R^N_J,p = 66854 km
- nominal jovian mass parameter (GM)^N_J = 1.2668653×10^17 m³/s²

These nominal quantities are exact conversion standards, not declarations of the true physical values. Actual estimates retain uncertainties and can change with observations.

## 6. Celestial reference frame ladder

### ICRS / ICRF

Primary inertial/celestial reference system.

Current radio realization:
- ICRF3

Current optical realization:
- Gaia-CRF3

Historical variants must remain linked:

ICRF1 -> ICRF2 -> ICRF3
HCRF -> Gaia-CRF3

Record frame, realization, epoch, and transformation metadata with every celestial coordinate.

## 7. Solar-system state

A celestial "here" requires a reference origin and ephemeris.

Minimum state:

- origin
- frame
- epoch
- time scale
- position x,y,z
- velocity vx,vy,vz
- uncertainty/covariance
- ephemeris source/version

Recommended origins:

- Solar System Barycenter
- Sun center
- Earth-Moon barycenter
- Earth center
- observer

SPICE explicitly models states as position + velocity relative to a defined frame and supports frame/time transformations; preserve the kernels and versions used to create a state.

## 8. Time ladder

Never store a date without a time scale.

### Core scales

- TAI — International Atomic Time
- UTC — civil time with leap seconds
- UT1 — Earth-rotation time
- TT — Terrestrial Time
- TCG — Geocentric Coordinate Time
- TCB — Barycentric Coordinate Time
- TDB — Barycentric Dynamical Time

### Key relationships

TT = TAI + 32.184 s exactly by convention.

UTC differs from TAI by an integer number of leap seconds.

UT1 differs from UTC according to measured Earth rotation.

TCG, TCB and TDB involve relativistic coordinate-time conventions and must retain their defining constants and epoch conventions.

Also preserve historical:

- UT0
- UT2
- ET
- TDT
- historical Julian/Ephemeris time conventions

## 9. Earth orientation

A terrestrial location is not fully defined by latitude/longitude.

Preserve Earth Orientation Parameters:

- x pole coordinate
- y pole coordinate
- UT1−UTC
- length-of-day offset
- celestial pole offsets
- rates where supplied
- formal errors

IERS provides current and historical EOP series.

Current IERS products include C04 series aligned with ITRF2020-u2024.

## 10. Terrestrial reference frame ladder

### ITRS

Conceptual Earth-centered Earth-fixed terrestrial reference system.

### ITRF

Realizations include:

ITRF89
ITRF90
ITRF91
ITRF92
ITRF93
ITRF94
ITRF96
ITRF97
ITRF2000
ITRF2005
ITRF2008
ITRF2014
ITRF2020
ITRF2020-u2023
ITRF2020-u2024

Each realization supplies station positions and velocities with uncertainties.

### GNSS operational variants

IGS reference history includes:

IGS14
IGb14
IGS20
IGb20
IGc20

At this snapshot, IGS reports IGc20 as the current operational reference frame beginning GPS week 2401 on 11 January 2026.

## 11. WGS 84

WGS 84 remains a practical navigation reference system.

Preserve:

- WGS 84 realization
- ellipsoid parameters
- geocentric reference
- Earth Gravitational Model version
- World Magnetic Model version
- coordinate transformation history

Never silently equate a WGS84 coordinate with an ITRF coordinate without documenting the realization/epoch and transformation.

NGA states WGS84 is Earth-centered/Earth-fixed and aligned to ITRF to within 1 cm in each 3D component for its stated realization.

## 12. Local coordinate

The terminal "YOU ARE HERE" record should be:

{
  "epoch": "...",
  "time_scale": "...",
  "celestial_frame": "...",
  "solar_system_origin": "...",
  "solar_system_position_m": [x,y,z],
  "solar_system_velocity_m_s": [vx,vy,vz],
  "earth_frame": "...",
  "earth_orientation": {
    "UT1_minus_UTC_s": "...",
    "pole_x_arcsec": "...",
    "pole_y_arcsec": "...",
    "LOD_s": "..."
  },
  "terrestrial_position": {
    "x_m": "...",
    "y_m": "...",
    "z_m": "..."
  },
  "geodetic": {
    "latitude_deg": "...",
    "longitude_deg": "...",
    "ellipsoidal_height_m": "..."
  },
  "vertical_datum": "...",
  "local_gravity_m_s2": "...",
  "uncertainty": "...",
  "reference_realization": "...",
  "source": "..."
}

The geodetic coordinates are a rendering of the state, not the canonical identity of the observer.

## 13. Optional expanded cosmic context

For deep-time orientation, additionally preserve:

- Galactic longitude/latitude
- Galactocentric position/velocity
- Galactic Standard of Rest convention
- Local Standard of Rest convention
- solar peculiar velocity convention
- Local Group velocity convention
- CMB dipole direction and velocity
- epoch of the galactic coordinate convention
- Milky Way reference assumptions

These are model-dependent and must carry a version and uncertainty.

They must never be presented as absolute rest.

## 14. "YOU ARE HERE" redundancy

A robust marker should permit reconstruction through several independent paths:

PATH A:
mathematics -> SI -> Earth frame -> local position

PATH B:
atomic frequency -> time -> Earth rotation -> terrestrial frame

PATH C:
spectral lines -> celestial frame -> ephemeris -> Earth state

PATH D:
GNSS observations -> ITRF/WGS84 -> local position

PATH E:
astronomical observations -> ICRF/Gaia -> Solar System state -> Earth

PATH F:
geophysical observations -> EOP -> terrestrial orientation

If several paths converge, the location/time interpretation becomes substantially more robust.

## 15. What is actually invariant?

Classify every anchor:

EXACT_MATHEMATICAL
EXACT_BY_DEFINITION
OBSERVABLE_PHYSICAL
MEASURED_ESTIMATE
MODEL_DEPENDENT
CONVENTION
REALIZATION
DERIVED
HISTORICAL

Do not call a model or convention a universal constant.

## 16. Future update rule

Never replace an old anchor.

Instead:

anchor
  -> version 2019
  -> version 2022
  -> version 2026
  -> version future

Likewise:

frame
  -> ITRF2014
  -> ITRF2020
  -> ITRF2020-u2023
  -> ITRF2020-u2024
  -> future realization

This allows a future researcher to reconstruct exactly what "YOU ARE HERE" meant at the original observation epoch.

## 17. Final bootstrap symbol

The Atlas should eventually render a universal marker:

**⊙ YOU ARE HERE**

with a machine-readable state behind it.

The symbol is merely the interface.

The real object is the complete, versioned, uncertainty-aware state vector and its transformations.

## Primary reference families

- BIPM SI defining constants
- NIST/CODATA recommended constants
- IAU resolutions
- IERS conventions and EOP
- ITRF realizations
- IGS realizations
- NGA WGS84
- ICRF / Gaia-CRF
- JPL NAIF SPICE kernels and frame definitions

These sources themselves are preserved as provenance records rather than treated as eternal endpoints.
