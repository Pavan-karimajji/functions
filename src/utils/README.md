# `df/utils` — the mathlib↔utils boundary

## The mathlib↔utils boundary (the frozen rule)

**Rule.** *Generic, stateless numeric primitives usable by any component go in
`mathlib`. df-domain algorithmic math — anything that encodes how a driving
function reasons about motion, time-to-collision, or geometry — goes in
`df/utils`.*

### Precedent: `cml`

The reference `cml` (Common Math Library) is exactly the **generic** tier. Its
folders are `misc`, `trigo`, `interpol`, `vector`, `matrix`, `stat`, …
`Min`/`Max`/`Mod`/`Round`/`Sign`/`Abs`, `CalcRoots`, `boundedLinInterpol`,
`atan2`/`cos` kernels. It has **no** TTC, **no** predictors, **no** collision
detection. Those live in the FCT/`acdc` tier (`acdc2 emp/prediction`,
`emp/colldet`, `adas_rad_fct cd/`) — which is the `df/utils` analog.
`cml : mathlib :: acdc-emp : df/utils`.

### Op-placement table

| Operation | Home | Why |
|---|---|---|
| `sin/cos/tan/atan2`, `sqrt/pow/fmod/abs` | **mathlib** (present) | generic kernels |
| `min/max` | **mathlib** (present) | generic |
| `sign`, `clamp`, `lerp` / bounded-linear-interpolation | **mathlib** (add) | generic, `cml misc`/`interpol` precedent; any component may need them |
| `solveQuadratic` (smallest positive root) | **mathlib** (add) | generic root-finding, `cml CalcRoots` precedent; the const-accel TTC calls *down* into it |
| `normalizeAngleRad`, `relativeBearingRad`, `headingErrorRad` | **df/utils** | angle **reasoning** a driving function does; user-directed to df/utils |
| Constant pos/vel/accel motion models | **df/utils** | df-domain prediction |
| `constantVelocityTtcS`, `constantAccelerationTtcS` | **df/utils** | time-to-collision is FCT math |
| corridor / OBB overlap / MTD (later) | **df/utils** | collision geometry |

**Boundary note on angles.** Raw angle-wrap could be argued generic (`cml`
keeps `ModTwoPi` in `misc`), but per the item-23 direction, angle operations
that df's algorithms perform live in `df/utils`. The raw trig kernels they call
(`atan2`, `cos`) stay in `mathlib`. If a **non-df** consumer (perception-core,
vdy) ever needs raw angle-wrap, promote just that primitive down to `mathlib`
(the "add the missing op to mathlib" reflex, R-MATH-1) — the df-facing helpers
in `df/utils` then become thin wrappers over it.

## Shape

```
utils/
├── models/     constant position/velocity/acceleration motion models (family)
├── colldet/    time-to-collision (AEB's consumer today)
├── geometry/   angle reasoning (normalize/bearing/heading error)
└── curves/     reserved — clothoid/polynomial, seeded when LKA needs it
```

Header-only, templated on `T` (`float`/`double`), built on mathlib's
`Vec2`/`CartesianPoint2D`/scalar kernels. Namespace `adas::df::utils::{models,colldet,geometry}`.
