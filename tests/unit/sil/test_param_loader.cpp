#include <gtest/gtest.h>

#include "param_loader.hpp"

namespace adas::functions {
namespace {

// ADAS_FUNCTIONS_TEST_FIXTURE_DIR is injected by tests/CMakeLists.txt.
constexpr auto kFunctionParamsFixture = ADAS_FUNCTIONS_TEST_FIXTURE_DIR "/function_params_test.yaml";
constexpr auto kEgoParamsFixture = ADAS_FUNCTIONS_TEST_FIXTURE_DIR "/ego_params_test.yaml";

TEST(ParamLoaderTest, SectionReadsExistingKeyFromNamedSection) {
  ParamLoader loader(kFunctionParamsFixture);
  FunctionParams aeb = loader.section("aeb");
  EXPECT_DOUBLE_EQ(aeb.get<double>("AEB_MAX_AGE_OBJECTS_S", -1.0), 0.2);
}

TEST(ParamLoaderTest, SectionMissingSectionFallsBackToCallerDefault) {
  ParamLoader loader(kFunctionParamsFixture);
  FunctionParams acc = loader.section("acc");  // fixture has no "acc:" section
  EXPECT_DOUBLE_EQ(acc.get<double>("ANYTHING", 7.0), 7.0);
}

TEST(ParamLoaderTest, RootReadsFlatTopLevelKey) {
  ParamLoader loader(kEgoParamsFixture);
  EXPECT_DOUBLE_EQ(loader.root().get<double>("EGO_WHEELBASE_M", -1.0), 2.7);
}

TEST(ParamLoaderTest, RootMissingKeyFallsBackToCallerDefault) {
  ParamLoader loader(kEgoParamsFixture);
  EXPECT_DOUBLE_EQ(loader.root().get<double>("DOES_NOT_EXIST", 42.0), 42.0);
}

TEST(ParamLoaderTest, MissingFileFallsBackToCallerDefaultEverywhere) {
  ParamLoader loader("does/not/exist.yaml");
  EXPECT_DOUBLE_EQ(loader.section("aeb").get<double>("AEB_MAX_AGE_OBJECTS_S", 9.0), 9.0);
  EXPECT_DOUBLE_EQ(loader.root().get<double>("EGO_WHEELBASE_M", 9.0), 9.0);
}

}  // namespace
}  // namespace adas::functions
