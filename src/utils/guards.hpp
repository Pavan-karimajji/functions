// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Numeric guards (safe division, range membership) — generic-shaped but
///   not standard enough across components to earn a mathlib slot
///   (docs/df_utils_plan.md §11).
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

namespace adas::df::utils {

// Pushes x away from zero to at least epsilonAbs in magnitude, preserving
// sign (0 maps to +epsilonAbs). Guards a denominator against division blow-up
// without the caller needing its own zero-check. epsilonAbs must be > 0 -
// caller's responsibility (same convention as mathlib::solveQuadratic owning
// a non-zero `a`).
template <typename T>
constexpr T safeDivisor(T x, T epsilonAbs) {
    if (x < T{0}) {
        return (x > -epsilonAbs) ? -epsilonAbs : x;
    }
    return (x < epsilonAbs) ? epsilonAbs : x;
}

// Open-interval membership test: lo < x < hi.
template <typename T>
constexpr bool isInsideRange(T x, T lo, T hi) {
    return (x > lo) && (x < hi);
}

}  // namespace adas::df::utils
