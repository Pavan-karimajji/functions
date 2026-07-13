// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Unit tests for DfParams' YAML section accessor.

#include <gtest/gtest.h>

#include "component/common/framework/df_params.hpp"

namespace adas::df {
namespace {

// No ParamLoader/file involved on purpose — DfParams is tested against
// an in-memory YAML::Load() string, proving the accessor/fallback behavior
// in isolation from any disk I/O.

TEST(DfParamsTest, ReadsExistingKey) {
  DfParams params(YAML::Load("max_age_objects_s: 0.2"));
  EXPECT_DOUBLE_EQ(params.get<double>("max_age_objects_s", -1.0), 0.2);
}

TEST(DfParamsTest, MissingKeyFallsBackToCallerDefault) {
  DfParams params(YAML::Load("max_age_objects_s: 0.2"));
  EXPECT_DOUBLE_EQ(params.get<double>("does_not_exist", 42.0), 42.0);
}

TEST(DfParamsTest, DefaultConstructedFallsBackToCallerDefaultEverywhere) {
  DfParams params;  // stands in for "missing section" (ParamLoader::section() returns this)
  EXPECT_DOUBLE_EQ(params.get<double>("anything", 7.0), 7.0);
}

}  // namespace
}  // namespace adas::df
