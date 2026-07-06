#include <gtest/gtest.h>

#include "component/aeb/aeb_function.hpp"

namespace adas::functions {
namespace {

FunctionParams testParams() {
  return FunctionParams(YAML::Load(
      "max_age_objects_s: 0.2\n"
      "max_age_ego_dyn_s: 0.2\n"));
}

TEST(AebFunctionTest, RunningWhenBothInputsFreshAndValid) {
  AebReqPorts reqPorts;
  reqPorts.emGenObjList.valid = true;
  reqPorts.emGenObjList.ageS = 0.05;
  reqPorts.egoDyn.valid = true;
  reqPorts.egoDyn.ageS = 0.05;
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_EQ(fn.compState().state(), adas::functions::CompState::RUNNING);
  EXPECT_EQ(fn.compState().function(), "aeb");
  EXPECT_TRUE(proPorts.compState.updated);
}

TEST(AebFunctionTest, ErrorWhenObjectsStale) {
  AebReqPorts reqPorts;
  reqPorts.emGenObjList.valid = true;
  reqPorts.emGenObjList.ageS = 5.0;  // older than max_age_objects_s
  reqPorts.egoDyn.valid = true;
  reqPorts.egoDyn.ageS = 0.05;
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_EQ(fn.compState().state(), adas::functions::CompState::ERROR);
}

TEST(AebFunctionTest, ErrorWhenEgoDynNeverReceived) {
  AebReqPorts reqPorts;
  reqPorts.emGenObjList.valid = true;
  reqPorts.emGenObjList.ageS = 0.05;
  reqPorts.egoDyn.valid = false;  // never received
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_EQ(fn.compState().state(), adas::functions::CompState::ERROR);
}

TEST(AebFunctionTest, CompStateIsNotInitializedBeforeFirstExec) {
  AebReqPorts reqPorts;
  AebProPorts proPorts;
  AebFunction fn(reqPorts, proPorts);

  // No init()/exec() yet — proto zero-value default already reports this
  // correctly, no extra code needed.
  EXPECT_EQ(fn.compState().state(), adas::functions::CompState::NOT_INITIALIZED);
}

TEST(AebFunctionTest, HypReactionAlwaysPublishedWithNoStageActive) {
  AebReqPorts reqPorts;
  reqPorts.emGenObjList.valid = true;
  reqPorts.emGenObjList.ageS = 0.05;
  reqPorts.egoDyn.valid = true;
  reqPorts.egoDyn.ageS = 0.05;
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_TRUE(proPorts.hypReaction.updated);
  EXPECT_FALSE(proPorts.hypReaction.data.b_latent_pre_warning_active());
  EXPECT_FALSE(proPorts.hypReaction.data.b_dynamic_acute_warning_active());
  EXPECT_FALSE(proPorts.hypReaction.data.b_pre_brake_active());
}

}  // namespace
}  // namespace adas::functions
