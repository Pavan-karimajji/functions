// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Angle reasoning helpers (normalize/bearing/heading error), built on
///   mathlib's trig kernels (docs/df_utils_plan.md §2 boundary note).
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include "mathlib/geometry.h"
#include "mathlib/scalar.h"

namespace adas::df::utils::geometry {

// Wraps angleRad into (-pi, pi].
template <typename T>
T normalizeAngleRad(T angleRad) {
    constexpr T kPi = T{3.14159265358979323846};
    constexpr T kTwoPi = T{2} * kPi;
    T wrapped = mathlib::fmod(angleRad + kPi, kTwoPi);
    if (wrapped < T{0}) {
        wrapped += kTwoPi;
    }
    return wrapped - kPi;
}

// Ego-relative bearing (0 = +x forward, +90deg = +y left, R-COORD-1) of a
// displacement vector, normalized into (-pi, pi].
template <typename T>
T relativeBearingRad(const mathlib::Vec2<T>& displacement) {
    return normalizeAngleRad(mathlib::heading_of(displacement));
}

// Shortest signed angular difference targetRad - currentRad, normalized into
// (-pi, pi] (e.g. lane-heading vs. ego-heading error).
template <typename T>
T headingErrorRad(T currentRad, T targetRad) {
    return normalizeAngleRad(targetRad - currentRad);
}

}  // namespace adas::df::utils::geometry
