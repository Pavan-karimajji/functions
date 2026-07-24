// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Zeroth-order motion model: pos' = pos.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include "utils/models/motion_model.hpp"

namespace adas::df::utils::models {

template <typename T>
State<T> predictConstantPosition(const State<T>& state, T /*dtS*/) {
    State<T> next = state;
    return next;
}

}  // namespace adas::df::utils::models
