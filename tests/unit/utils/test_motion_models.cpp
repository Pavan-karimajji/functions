// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Unit tests for the constant position/velocity/acceleration motion models.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include <gtest/gtest.h>

#include "utils/models/constant_acceleration.hpp"
#include "utils/models/constant_position.hpp"
#include "utils/models/constant_velocity.hpp"

namespace adas::df::utils::models {
namespace {

TEST(ConstantPositionTest, StateUnchanged) {
    State<double> state;
    state.pos = mathlib::CartesianPoint2D<double>(3.0, 1.0);
    state.vel = mathlib::Vec2<double>(5.0, 0.0);

    const State<double> next = predictConstantPosition(state, 2.0);

    EXPECT_DOUBLE_EQ(next.pos.x, 3.0);
    EXPECT_DOUBLE_EQ(next.pos.y, 1.0);
}

TEST(ConstantVelocityTest, AdvancesByVelTimesDt) {
    State<double> state;
    state.pos = mathlib::CartesianPoint2D<double>(0.0, 0.0);
    state.vel = mathlib::Vec2<double>(10.0, -2.0);

    const State<double> next = predictConstantVelocity(state, 0.5);

    EXPECT_DOUBLE_EQ(next.pos.x, 5.0);
    EXPECT_DOUBLE_EQ(next.pos.y, -1.0);
}

TEST(ConstantAccelerationTest, AdvancesPosAndVel) {
    State<double> state;
    state.pos = mathlib::CartesianPoint2D<double>(0.0, 0.0);
    state.vel = mathlib::Vec2<double>(10.0, 0.0);
    state.accel = mathlib::Vec2<double>(2.0, 0.0);

    const State<double> next = predictConstantAcceleration(state, 2.0);

    EXPECT_DOUBLE_EQ(next.pos.x, 24.0);  // 0 + 10*2 + 0.5*2*4
    EXPECT_DOUBLE_EQ(next.vel.x, 14.0);  // 10 + 2*2
}

}  // namespace
}  // namespace adas::df::utils::models
