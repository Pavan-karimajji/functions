#include <gtest/gtest.h>

#include "component/common/framework/function_params.hpp"

namespace adas::functions {
namespace {

// No ParamLoader/file involved on purpose — FunctionParams is tested against
// an in-memory YAML::Load() string, proving the accessor/fallback behavior
// in isolation from any disk I/O.

TEST(FunctionParamsTest, ReadsExistingKey) {
  FunctionParams params(YAML::Load("max_age_objects_s: 0.2"));
  EXPECT_DOUBLE_EQ(params.get<double>("max_age_objects_s", -1.0), 0.2);
}

TEST(FunctionParamsTest, MissingKeyFallsBackToCallerDefault) {
  FunctionParams params(YAML::Load("max_age_objects_s: 0.2"));
  EXPECT_DOUBLE_EQ(params.get<double>("does_not_exist", 42.0), 42.0);
}

TEST(FunctionParamsTest, DefaultConstructedFallsBackToCallerDefaultEverywhere) {
  FunctionParams params;  // stands in for "missing section" (ParamLoader::section() returns this)
  EXPECT_DOUBLE_EQ(params.get<double>("anything", 7.0), 7.0);
}

}  // namespace
}  // namespace adas::functions
