#include <gtest/gtest.h>

#include "param_loader.hpp"

namespace adas::functions {
namespace {

// ADAS_FUNCTIONS_TEST_FIXTURE_DIR/ADAS_FUNCTIONS_PROJECTS_DIR are injected by
// tests/CMakeLists.txt.
constexpr auto kFunctionParamsFixture = ADAS_FUNCTIONS_TEST_FIXTURE_DIR "/function_params_test.yaml";
constexpr auto kEgoParamsFixture = ADAS_FUNCTIONS_TEST_FIXTURE_DIR "/ego_params_test.yaml";
constexpr auto kBaseDefault = ADAS_FUNCTIONS_PROJECTS_DIR "/base/default.yaml";
constexpr auto kProjAlphaDefault = ADAS_FUNCTIONS_PROJECTS_DIR "/proj_alpha/default.yaml";

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

// Real projects/base and projects/proj_alpha default.yaml files (not
// synthetic fixtures) — proves the project-scoped calibration mechanism
// (plan.md item 9, docs/project_scoped_params.md): pointing fnInit's
// configPath at a different project folder genuinely loads different
// numbers, with zero merge/override logic (each file is a complete,
// standalone set).
TEST(ParamLoaderTest, BaseAndProjAlphaLoadDifferentAebCalibration) {
  ParamLoader base(kBaseDefault);
  ParamLoader projAlpha(kProjAlphaDefault);

  EXPECT_DOUBLE_EQ(base.section("aeb").get<double>("AEB_TTC_BRAKE_THRESHOLD_S", -1.0), 1.2);
  EXPECT_DOUBLE_EQ(projAlpha.section("aeb").get<double>("AEB_TTC_BRAKE_THRESHOLD_S", -1.0), 1.4);
}

TEST(ParamLoaderTest, RealBaseFileMatchesFormerConfigDefaultYamlValues) {
  ParamLoader base(kBaseDefault);
  FunctionParams aeb = base.section("aeb");
  EXPECT_DOUBLE_EQ(aeb.get<double>("AEB_MAX_AGE_OBJECTS_S", -1.0), 0.2);
  EXPECT_DOUBLE_EQ(aeb.get<double>("AEB_MAX_AGE_EGO_DYN_S", -1.0), 0.2);
}

}  // namespace
}  // namespace adas::functions
