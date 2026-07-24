// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Unit tests for lateralOffsetOnCurveM (docs/df_utils_plan.md §11).
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include <gtest/gtest.h>

#include <cmath>

#include "utils/curves/curve_offset.hpp"

namespace adas::df::utils::curves {
namespace {

TEST(LateralOffsetOnCurveTest, PositiveRadiusPicksNearBranch) {
    const double radius = 100.0;
    const double dist = 10.0;
    const double expected = radius - std::sqrt(radius * radius - dist * dist);
    EXPECT_NEAR(lateralOffsetOnCurveM(dist, radius), expected, 1e-9);
    EXPECT_GT(lateralOffsetOnCurveM(dist, radius), 0.0);
}

TEST(LateralOffsetOnCurveTest, NegativeRadiusPicksNearBranch) {
    const double radius = -100.0;
    const double dist = 10.0;
    const double expected = radius + std::sqrt(radius * radius - dist * dist);
    EXPECT_NEAR(lateralOffsetOnCurveM(dist, radius), expected, 1e-9);
    EXPECT_LT(lateralOffsetOnCurveM(dist, radius), 0.0);
}

TEST(LateralOffsetOnCurveTest, DistBeyondRadiusReturnsZero) {
    EXPECT_DOUBLE_EQ(lateralOffsetOnCurveM(20.0, 10.0), 0.0);
}

TEST(LateralOffsetOnCurveTest, DistExactlyAtRadiusReturnsZero) {
    EXPECT_DOUBLE_EQ(lateralOffsetOnCurveM(10.0, 10.0), 0.0);
}

TEST(LateralOffsetOnCurveTest, ZeroDistanceReturnsZeroOffset) {
    EXPECT_NEAR(lateralOffsetOnCurveM(0.0, 100.0), 0.0, 1e-9);
}

}  // namespace
}  // namespace adas::df::utils::curves
