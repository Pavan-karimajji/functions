// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Constant-curvature (driven-curve) lateral offset — the lateral offset
///   of a constant-radius arc at a given longitudinal distance.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include "mathlib/scalar.h"

namespace adas::df::utils::curves {

// Lateral offset (ego +y, R-COORD-1) of a constant-radius arc of
// curveRadiusM at longitudinalDistM ahead: y = R +/- sqrt(R^2 - x^2), picking
// the root of smaller magnitude (the near branch of the circle, not the far
// side). Returns 0 when longitudinalDistM is beyond the arc's reach
// (|longitudinalDistM| > |curveRadiusM|) - the curve simply doesn't extend
// that far, so there is no offset to report. curveRadiusM's sign encodes
// curve direction (matching whatever sign convention the caller's curvature
// source uses); longitudinalDistM is expected non-negative (a distance
// ahead).
template <typename T>
T lateralOffsetOnCurveM(T longitudinalDistM, T curveRadiusM) {
    const T radicand = curveRadiusM * curveRadiusM - longitudinalDistM * longitudinalDistM;
    if (radicand <= T{0}) {
        return T{0};
    }
    const T sqrtRadicand = mathlib::sqrt(radicand);
    const T offsetNear = curveRadiusM - sqrtRadicand;
    const T offsetFar = curveRadiusM + sqrtRadicand;
    return (mathlib::abs(offsetNear) < mathlib::abs(offsetFar)) ? offsetNear : offsetFar;
}

}  // namespace adas::df::utils::curves
