// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Shared motion-model state (pos/vel/accel) predicted forward by dtS.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include "mathlib/geometry.h"

namespace adas::df::utils::models {

// Ego-relative kinematic state (R-COORD-1: +x forward, +y left). Each
// concrete model (constant_position/velocity/acceleration) predicts a new
// State from an old one over dtS; which fields it updates depends on the
// model's own order (see the sibling headers).
template <typename T>
struct State {
    mathlib::CartesianPoint2D<T> pos{};
    mathlib::Vec2<T> vel{};
    mathlib::Vec2<T> accel{};
};

}  // namespace adas::df::utils::models
