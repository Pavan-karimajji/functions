// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Time-to-collision entry points: constant-velocity and
///   constant-acceleration closing kinematics.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include <algorithm>

#include "mathlib/scalar.h"

namespace adas::df::utils::colldet {

// TTC is capped at 40s rather than left unbounded: no supported function
// needs to distinguish "not closing" from "closing in an hour" and an
// unbounded value can't be logged/thresholded uniformly.
template <typename T>
inline constexpr T kMaxTtcS = T{40};

// Longitudinal constant-velocity TTC: gapM ahead of ego, closingSpeedMps > 0
// means closing. Returns kMaxTtcS when not ahead-and-closing (AEB's
// "ahead + closing -> finite TTC, else capped" guard, docs/df_utils_plan.md §5).
template <typename T>
T constantVelocityTtcS(T gapM, T closingSpeedMps) {
    if (gapM > T{0} && closingSpeedMps > T{0}) {
        return std::min(gapM / closingSpeedMps, kMaxTtcS<T>);
    }
    return kMaxTtcS<T>;
}

// Longitudinal constant-acceleration TTC: closingSpeedMps > 0 closing,
// closingAccelMps2 > 0 additional closing acceleration. Solves
// 1/2*a*t^2 + v*t - gap = 0 for the smallest positive root via
// mathlib::solveQuadratic; falls back to the constant-velocity form when
// closingAccelMps2 is zero (solveQuadratic requires a non-zero leading
// coefficient).
template <typename T>
T constantAccelerationTtcS(T gapM, T closingSpeedMps, T closingAccelMps2) {
    if (gapM <= T{0}) {
        return kMaxTtcS<T>;
    }
    if (closingAccelMps2 == T{0}) {
        return constantVelocityTtcS(gapM, closingSpeedMps);
    }
    T root{};
    if (mathlib::solveQuadratic<T>(T{0.5} * closingAccelMps2, closingSpeedMps, -gapM, root)) {
        return std::min(root, kMaxTtcS<T>);
    }
    return kMaxTtcS<T>;
}

// Time until a moving point reaches a static boundary: (boundaryM -
// positionM) / relativeSpeedMps, valid (t >= 0) only when the point is
// actually moving toward the boundary; diverging or stationary (zero
// relative speed) returns +inf. Unlike constantVelocityTtcS (which bakes in
// an "ahead + closing" sign convention for a specific gap), this is
// direction-agnostic: it works whichever side of the boundary positionM
// starts on, as long as the closing-sign check (docs/df_utils_plan.md §11)
// holds. Direct fit for LDW (time to lane-boundary crossing) and AEB's
// lateral-corridor scope alike.
template <typename T>
T timeToLineCrossingS(T boundaryM, T positionM, T relativeSpeedMps) {
    if (relativeSpeedMps == T{0}) {
        return kMaxTtcS<T>;
    }
    const T gapM = boundaryM - positionM;
    const T t = gapM / relativeSpeedMps;
    return (t >= T{0}) ? std::min(t, kMaxTtcS<T>) : kMaxTtcS<T>;
}

}  // namespace adas::df::utils::colldet
