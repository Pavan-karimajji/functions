// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Unit tests for the mathlib scalar additions consumed via df/utils
///   (mapRangeClamped, lowPassFilter, roundToNearest; docs/df_utils_plan.md
///   §11). Exercised from df's test harness since mathlib has no unit test
///   suite of its own yet.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include <gtest/gtest.h>

#include "mathlib/scalar.h"

namespace mathlib {
namespace {

TEST(MapRangeClampedTest, InteriorValueInterpolatesLinearly) {
    EXPECT_DOUBLE_EQ(mapRangeClamped(5.0, 0.0, 10.0, 0.0, 100.0), 50.0);
}

TEST(MapRangeClampedTest, BelowInMinClampsToOutMin) {
    EXPECT_DOUBLE_EQ(mapRangeClamped(-5.0, 0.0, 10.0, 0.0, 100.0), 0.0);
}

TEST(MapRangeClampedTest, AboveInMaxClampsToOutMax) {
    EXPECT_DOUBLE_EQ(mapRangeClamped(15.0, 0.0, 10.0, 0.0, 100.0), 100.0);
}

TEST(MapRangeClampedTest, ExactBoundsMapToExactOutputs) {
    EXPECT_DOUBLE_EQ(mapRangeClamped(0.0, 0.0, 10.0, 20.0, 40.0), 20.0);
    EXPECT_DOUBLE_EQ(mapRangeClamped(10.0, 0.0, 10.0, 20.0, 40.0), 40.0);
}

TEST(MapRangeClampedTest, ReversedOutputRangeStillClamps) {
    EXPECT_DOUBLE_EQ(mapRangeClamped(-5.0, 0.0, 10.0, 100.0, 0.0), 100.0);
    EXPECT_DOUBLE_EQ(mapRangeClamped(15.0, 0.0, 10.0, 100.0, 0.0), 0.0);
    EXPECT_DOUBLE_EQ(mapRangeClamped(5.0, 0.0, 10.0, 100.0, 0.0), 50.0);
}

TEST(LowPassFilterTest, BlendsByAlpha) {
    EXPECT_DOUBLE_EQ(lowPassFilter(0.0, 10.0, 0.5), 5.0);
}

TEST(LowPassFilterTest, ZeroAlphaKeepsFiltered) {
    EXPECT_DOUBLE_EQ(lowPassFilter(3.0, 10.0, 0.0), 3.0);
}

TEST(LowPassFilterTest, OneAlphaPassesRawThrough) {
    EXPECT_DOUBLE_EQ(lowPassFilter(3.0, 10.0, 1.0), 10.0);
}

TEST(LowPassFilterTest, NegativeAlphaClampsToZero) {
    EXPECT_DOUBLE_EQ(lowPassFilter(3.0, 10.0, -1.0), 3.0);
}

TEST(LowPassFilterTest, AboveOneAlphaClampsToOne) {
    EXPECT_DOUBLE_EQ(lowPassFilter(3.0, 10.0, 2.0), 10.0);
}

TEST(RoundToNearestTest, RoundsDownBelowHalf) {
    EXPECT_EQ((roundToNearest<int>(2.4)), 2);
}

TEST(RoundToNearestTest, RoundsUpAboveHalf) {
    EXPECT_EQ((roundToNearest<int>(2.6)), 3);
}

TEST(RoundToNearestTest, ExactHalfRoundsAwayFromZero) {
    EXPECT_EQ((roundToNearest<int>(2.5)), 3);
    EXPECT_EQ((roundToNearest<int>(-2.5)), -3);
}

TEST(RoundToNearestTest, NegativeValues) {
    EXPECT_EQ((roundToNearest<int>(-2.4)), -2);
    EXPECT_EQ((roundToNearest<int>(-2.6)), -3);
}

TEST(RoundToNearestTest, Zero) {
    EXPECT_EQ((roundToNearest<int>(0.0)), 0);
}

}  // namespace
}  // namespace mathlib
