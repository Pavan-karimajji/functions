// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Unit tests for constant-velocity and constant-acceleration TTC.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include <gtest/gtest.h>

#include "utils/colldet/ttc.hpp"

namespace adas::df::utils::colldet {
namespace {

TEST(ConstantVelocityTtcTest, GapOverClosingSpeed) {
    EXPECT_DOUBLE_EQ(constantVelocityTtcS(10.0, 5.0), 2.0);
}

TEST(ConstantVelocityTtcTest, RecedingIsCapped) {
    EXPECT_EQ(constantVelocityTtcS(10.0, -5.0), kMaxTtcS<double>);
}

TEST(ConstantVelocityTtcTest, BehindEgoIsCapped) {
    EXPECT_EQ(constantVelocityTtcS(-10.0, 5.0), kMaxTtcS<double>);
}

TEST(ConstantVelocityTtcTest, RawResultAboveCapIsClamped) {
    EXPECT_EQ(constantVelocityTtcS(1000.0, 1.0), kMaxTtcS<double>);
}

TEST(ConstantAccelerationTtcTest, FallsBackToConstantVelocityWhenAccelZero) {
    EXPECT_DOUBLE_EQ(constantAccelerationTtcS(10.0, 5.0, 0.0), 2.0);
}

TEST(ConstantAccelerationTtcTest, SmallestPositiveRootOfClosingAccel) {
    // 1/2*2*t^2 + 4*t - 10 = 0  ->  t^2 + 4t - 10 = 0  ->  t = -2 + sqrt(14)
    const double expected = -2.0 + std::sqrt(14.0);
    EXPECT_NEAR(constantAccelerationTtcS(10.0, 4.0, 2.0), expected, 1e-9);
}

TEST(ConstantAccelerationTtcTest, BehindEgoIsCapped) {
    EXPECT_EQ(constantAccelerationTtcS(-10.0, 5.0, 1.0), kMaxTtcS<double>);
}

TEST(TimeToLineCrossingTest, ApproachingFromBelowBoundary) {
    // position 2, boundary 10, closing at 4 m/s -> 2s to cross
    EXPECT_DOUBLE_EQ(timeToLineCrossingS(10.0, 2.0, 4.0), 2.0);
}

TEST(TimeToLineCrossingTest, ApproachingFromAboveBoundaryNegativeSpeed) {
    // position 12, boundary 10, moving at -4 m/s -> 0.5s to cross
    EXPECT_DOUBLE_EQ(timeToLineCrossingS(10.0, 12.0, -4.0), 0.5);
}

TEST(TimeToLineCrossingTest, DivergingBelowBoundaryIsCapped) {
    // position 2, boundary 10, moving away at -4 m/s -> never crosses
    EXPECT_EQ(timeToLineCrossingS(10.0, 2.0, -4.0), kMaxTtcS<double>);
}

TEST(TimeToLineCrossingTest, ReceedingAboveBoundaryIsCapped) {
    // position 12, boundary 10, moving further away at +4 m/s -> never crosses
    EXPECT_EQ(timeToLineCrossingS(10.0, 12.0, 4.0), kMaxTtcS<double>);
}

TEST(TimeToLineCrossingTest, AlreadyAtBoundaryWithMotionCrossesNow) {
    EXPECT_DOUBLE_EQ(timeToLineCrossingS(10.0, 10.0, 5.0), 0.0);
}

TEST(TimeToLineCrossingTest, ZeroRelativeSpeedIsCapped) {
    EXPECT_EQ(timeToLineCrossingS(10.0, 2.0, 0.0), kMaxTtcS<double>);
}

}  // namespace
}  // namespace adas::df::utils::colldet
