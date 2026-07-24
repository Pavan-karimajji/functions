// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   First-order motion model: pos' = pos + vel * dt.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include "utils/models/motion_model.hpp"

namespace adas::df::utils::models {

template <typename T>
State<T> predictConstantVelocity(const State<T>& state, T dtS) {
    State<T> next = state;
    next.pos = mathlib::CartesianPoint2D<T>(state.pos.x + state.vel.x * dtS,
                                             state.pos.y + state.vel.y * dtS);
    return next;
}

}  // namespace adas::df::utils::models
