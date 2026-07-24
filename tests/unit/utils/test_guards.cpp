// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Unit tests for safeDivisor / isInsideRange (docs/df_utils_plan.md §11).
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include <gtest/gtest.h>

#include "utils/guards.hpp"

namespace adas::df::utils {
namespace {

TEST(SafeDivisorTest, AlreadyClearOfEpsilonUnchanged) {
    EXPECT_DOUBLE_EQ(safeDivisor(5.0, 0.01), 5.0);
    EXPECT_DOUBLE_EQ(safeDivisor(-5.0, 0.01), -5.0);
}

TEST(SafeDivisorTest, SmallPositiveClampsToEpsilon) {
    EXPECT_DOUBLE_EQ(safeDivisor(0.001, 0.01), 0.01);
}

TEST(SafeDivisorTest, SmallNegativeClampsToNegativeEpsilon) {
    EXPECT_DOUBLE_EQ(safeDivisor(-0.001, 0.01), -0.01);
}

TEST(SafeDivisorTest, ZeroClampsToPositiveEpsilon) {
    EXPECT_DOUBLE_EQ(safeDivisor(0.0, 0.01), 0.01);
}

TEST(SafeDivisorTest, ExactlyEpsilonUnchanged) {
    EXPECT_DOUBLE_EQ(safeDivisor(0.01, 0.01), 0.01);
    EXPECT_DOUBLE_EQ(safeDivisor(-0.01, 0.01), -0.01);
}

TEST(IsInsideRangeTest, InsideIsTrue) {
    EXPECT_TRUE(isInsideRange(5.0, 0.0, 10.0));
}

TEST(IsInsideRangeTest, BelowLowerIsFalse) {
    EXPECT_FALSE(isInsideRange(-1.0, 0.0, 10.0));
}

TEST(IsInsideRangeTest, AboveUpperIsFalse) {
    EXPECT_FALSE(isInsideRange(11.0, 0.0, 10.0));
}

TEST(IsInsideRangeTest, AtLowerBoundaryIsFalse) {
    EXPECT_FALSE(isInsideRange(0.0, 0.0, 10.0));
}

TEST(IsInsideRangeTest, AtUpperBoundaryIsFalse) {
    EXPECT_FALSE(isInsideRange(10.0, 0.0, 10.0));
}

}  // namespace
}  // namespace adas::df::utils
