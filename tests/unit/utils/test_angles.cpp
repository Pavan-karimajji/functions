// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Unit tests for normalizeAngleRad / relativeBearingRad / headingErrorRad.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include <gtest/gtest.h>

#include "utils/geometry/angles.hpp"

namespace adas::df::utils::geometry {
namespace {

constexpr double kPi = 3.14159265358979323846;

TEST(NormalizeAngleRadTest, WrapsAboveTwoPi) {
    EXPECT_NEAR(normalizeAngleRad(2.5 * kPi), 0.5 * kPi, 1e-9);
}

TEST(NormalizeAngleRadTest, WrapsNegative) {
    EXPECT_NEAR(normalizeAngleRad(-1.5 * kPi), 0.5 * kPi, 1e-9);
}

TEST(NormalizeAngleRadTest, StaysWithinRangeAtBoundary) {
    const double wrapped = normalizeAngleRad(kPi);
    EXPECT_GT(wrapped, -kPi - 1e-9);
    EXPECT_LE(wrapped, kPi + 1e-9);
}

TEST(RelativeBearingRadTest, StraightAheadIsZero) {
    EXPECT_NEAR(relativeBearingRad(mathlib::Vec2<double>(10.0, 0.0)), 0.0, 1e-9);
}

TEST(RelativeBearingRadTest, DirectlyLeftIsHalfPi) {
    EXPECT_NEAR(relativeBearingRad(mathlib::Vec2<double>(0.0, 10.0)), 0.5 * kPi, 1e-9);
}

TEST(HeadingErrorRadTest, ZeroWhenEqual) {
    EXPECT_NEAR(headingErrorRad(0.3, 0.3), 0.0, 1e-9);
}

TEST(HeadingErrorRadTest, ShortestSignedDifference) {
    EXPECT_NEAR(headingErrorRad(-0.9 * kPi, 0.9 * kPi), -0.2 * kPi, 1e-9);
}

}  // namespace
}  // namespace adas::df::utils::geometry
