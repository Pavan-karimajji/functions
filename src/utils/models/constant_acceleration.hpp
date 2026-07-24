// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Second-order motion model: pos' = pos + vel*dt + 1/2*accel*dt^2;
///   vel' = vel + accel*dt.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include "utils/models/motion_model.hpp"

namespace adas::df::utils::models {

template <typename T>
State<T> predictConstantAcceleration(const State<T>& state, T dtS) {
    State<T> next;
    next.pos = mathlib::CartesianPoint2D<T>(
        state.pos.x + state.vel.x * dtS + T{0.5} * state.accel.x * dtS * dtS,
        state.pos.y + state.vel.y * dtS + T{0.5} * state.accel.y * dtS * dtS);
    next.vel = mathlib::Vec2<T>(state.vel.x + state.accel.x * dtS,
                                 state.vel.y + state.accel.y * dtS);
    next.accel = state.accel;
    return next;
}

}  // namespace adas::df::utils::models
