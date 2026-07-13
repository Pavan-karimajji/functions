#include <gtest/gtest.h>

#include <cstddef>

#include "component/aeb/aeb_function.hpp"
#include "component/common/framework/object_limits.hpp"

namespace adas::df {
namespace {

DfParams testParams() {
  return DfParams(
      YAML::Load("AEB_MAX_AGE_OBJECTS_S: 0.2\n"
                 "AEB_MAX_AGE_EGO_DYN_S: 0.2\n"
                 "AEB_TTC_PRE_WARNING_THRESHOLD_S: 1.0\n"));
}

adas::perception::GenObject makeObject(float distX, float vrelX, uint32_t uiId,
                                       uint32_t contributingSensors = 0) {
  adas::perception::GenObject obj;
  obj.mutable_kinematic()->set_f_dist_x(distX);
  obj.mutable_kinematic()->set_f_vrel_x(vrelX);
  obj.mutable_general()->set_ui_id(uiId);
  obj.mutable_general()->set_contributingsensors(contributingSensors);
  return obj;
}

void setFreshInputs(AebReqPorts& reqPorts) {
  reqPorts.emGenObjList.valid = true;
  reqPorts.emGenObjList.ageS = 0.05;
  reqPorts.egoDyn.valid = true;
  reqPorts.egoDyn.ageS = 0.05;
}

TEST(AebFunctionTest, CompStateIsNotInitializedBeforeFirstExec) {
  AebReqPorts reqPorts;
  AebProPorts proPorts;
  AebFunction fn(reqPorts, proPorts);

  // No init()/exec() yet — proto zero-value default already reports this
  // correctly, no extra code needed.
  EXPECT_EQ(fn.compState().state(), adas::df::CompState::NOT_INITIALIZED);
}

// CompState reporting is deliberately not implemented yet (deferred to the
// detailed AEB rework, docs/df_aeb_ttc_blueprint.md) — exec() never touches
// proPorts_.compState, even on an otherwise-normal cycle.
TEST(AebFunctionTest, CompStateStaysNotInitializedAfterExec) {
  AebReqPorts reqPorts;
  setFreshInputs(reqPorts);
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_EQ(fn.compState().state(), adas::df::CompState::NOT_INITIALIZED);
  EXPECT_FALSE(proPorts.compState.updated);
}

TEST(AebFunctionTest, NoWarningWithEmptyObjectList) {
  AebReqPorts reqPorts;
  setFreshInputs(reqPorts);
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_TRUE(proPorts.outputs.updated);
  EXPECT_FALSE(proPorts.outputs.data.b_latent_pre_warning_active());
  EXPECT_EQ(proPorts.outputs.data.critical_obj_id(), 0u);
  EXPECT_FALSE(proPorts.outputs.data.b_dynamic_acute_warning_active());
  EXPECT_FALSE(proPorts.outputs.data.b_pre_brake_active());
}

TEST(AebFunctionTest, WarningFiresWhenTtcBelowThreshold) {
  AebReqPorts reqPorts;
  setFreshInputs(reqPorts);
  *reqPorts.emGenObjList.data.add_objects() =
      makeObject(/*distX=*/5.0f, /*vrelX=*/-10.0f, /*uiId=*/7);  // TTC 0.5s
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_TRUE(proPorts.outputs.data.b_latent_pre_warning_active());
  EXPECT_EQ(proPorts.outputs.data.critical_obj_id(), 7u);
}

TEST(AebFunctionTest, ContributingSensorsFieldDoesNotAffectTtcOutcome) {
  for (uint32_t bits : {0u, 0x1u, 0x2u, 0x3u}) {
    AebReqPorts reqPorts;
    setFreshInputs(reqPorts);
    *reqPorts.emGenObjList.data.add_objects() =
        makeObject(/*distX=*/5.0f, /*vrelX=*/-10.0f, /*uiId=*/7, bits);  // TTC 0.5s
    AebProPorts proPorts;

    AebFunction fn(reqPorts, proPorts);
    fn.init(testParams());
    fn.exec(0.05);

    EXPECT_TRUE(proPorts.outputs.data.b_latent_pre_warning_active()) << "bits=" << bits;
    EXPECT_EQ(proPorts.outputs.data.critical_obj_id(), 7u) << "bits=" << bits;
  }
}

TEST(AebFunctionTest, NoWarningWhenTtcAboveThreshold) {
  AebReqPorts reqPorts;
  setFreshInputs(reqPorts);
  *reqPorts.emGenObjList.data.add_objects() = makeObject(50.0f, -10.0f, 1);  // TTC 5s
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_FALSE(proPorts.outputs.data.b_latent_pre_warning_active());
  EXPECT_EQ(proPorts.outputs.data.critical_obj_id(), 0u);
}

TEST(AebFunctionTest, TtcEqualToThresholdDoesNotFire) {
  AebReqPorts reqPorts;
  setFreshInputs(reqPorts);
  *reqPorts.emGenObjList.data.add_objects() = makeObject(10.0f, -10.0f, 1);  // TTC exactly 1.0s
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_FALSE(proPorts.outputs.data.b_latent_pre_warning_active());
}

TEST(AebFunctionTest, RecedingObjectNeverWarns) {
  AebReqPorts reqPorts;
  setFreshInputs(reqPorts);
  *reqPorts.emGenObjList.data.add_objects() = makeObject(5.0f, 10.0f, 1);  // moving away
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_FALSE(proPorts.outputs.data.b_latent_pre_warning_active());
}

TEST(AebFunctionTest, ZeroRelativeVelocityIgnored) {
  AebReqPorts reqPorts;
  setFreshInputs(reqPorts);
  *reqPorts.emGenObjList.data.add_objects() = makeObject(5.0f, 0.0f, 1);
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_FALSE(proPorts.outputs.data.b_latent_pre_warning_active());
}

TEST(AebFunctionTest, ObjectBehindEgoIgnored) {
  AebReqPorts reqPorts;
  setFreshInputs(reqPorts);
  *reqPorts.emGenObjList.data.add_objects() = makeObject(-5.0f, -10.0f, 1);  // behind rear axle
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_FALSE(proPorts.outputs.data.b_latent_pre_warning_active());
}

TEST(AebFunctionTest, MinTtcObjectWins) {
  AebReqPorts reqPorts;
  setFreshInputs(reqPorts);
  *reqPorts.emGenObjList.data.add_objects() = makeObject(8.0f, -10.0f, 3);  // TTC 0.8s
  *reqPorts.emGenObjList.data.add_objects() = makeObject(4.0f, -10.0f, 9);  // TTC 0.4s, lower
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_TRUE(proPorts.outputs.data.b_latent_pre_warning_active());
  EXPECT_EQ(proPorts.outputs.data.critical_obj_id(), 9u);
}

// Proves the kMaxGenObjects bound (object_limits.hpp, docs/df_carla_bridge_blueprint.md,
// 2026-07-09) is real, not cosmetic: a would-fire object placed past the
// compile-time budget is never even looked at, even though every earlier
// slot is a genuinely ineligible (receding) object.
TEST(AebFunctionTest, ObjectsBeyondMaxGenObjectsAreIgnored) {
  AebReqPorts reqPorts;
  setFreshInputs(reqPorts);
  for (std::size_t i = 0; i < kMaxGenObjects; ++i) {
    *reqPorts.emGenObjList.data.add_objects() =
        makeObject(5.0f, 10.0f, static_cast<uint32_t>(i + 1));  // receding, never fires
  }
  *reqPorts.emGenObjList.data.add_objects() = makeObject(
      1.0f, -10.0f,
      999);  // TTC 0.1s, would fire - but it's object index kMaxGenObjects, one past the bound
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_FALSE(proPorts.outputs.data.b_latent_pre_warning_active());
  EXPECT_EQ(proPorts.outputs.data.critical_obj_id(), 0u);
}

TEST(AebFunctionTest, ThresholdReadFromParams) {
  AebReqPorts reqPorts;
  setFreshInputs(reqPorts);
  *reqPorts.emGenObjList.data.add_objects() = makeObject(20.0f, -10.0f, 1);  // TTC 2.0s
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(DfParams(
      YAML::Load("AEB_MAX_AGE_OBJECTS_S: 0.2\n"
                 "AEB_MAX_AGE_EGO_DYN_S: 0.2\n"
                 "AEB_TTC_PRE_WARNING_THRESHOLD_S: 3.0\n")));  // would not fire at the default 1.0
  fn.exec(0.05);

  EXPECT_TRUE(proPorts.outputs.data.b_latent_pre_warning_active());
}

TEST(AebFunctionTest, ObjectsStaleSuppressesWarning) {
  AebReqPorts reqPorts;
  reqPorts.emGenObjList.valid = true;
  reqPorts.emGenObjList.ageS = 5.0;  // stale
  reqPorts.egoDyn.valid = true;
  reqPorts.egoDyn.ageS = 0.05;
  *reqPorts.emGenObjList.data.add_objects() = makeObject(5.0f, -10.0f, 7);  // would fire if fresh
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_FALSE(proPorts.outputs.data.b_latent_pre_warning_active());
  EXPECT_EQ(proPorts.outputs.data.critical_obj_id(), 0u);
}

TEST(AebFunctionTest, EgoDynNeverReceivedSuppressesWarning) {
  AebReqPorts reqPorts;
  reqPorts.emGenObjList.valid = true;
  reqPorts.emGenObjList.ageS = 0.05;
  reqPorts.egoDyn.valid = false;                                            // never received
  *reqPorts.emGenObjList.data.add_objects() = makeObject(5.0f, -10.0f, 7);  // would fire if fresh
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_FALSE(proPorts.outputs.data.b_latent_pre_warning_active());
  EXPECT_EQ(proPorts.outputs.data.critical_obj_id(), 0u);
}

TEST(AebFunctionTest, StaleInputsSuppressWarning) {
  AebReqPorts reqPorts;
  reqPorts.emGenObjList.valid = true;
  reqPorts.emGenObjList.ageS = 0.05;
  reqPorts.egoDyn.valid = true;
  reqPorts.egoDyn.ageS = 5.0;                                               // stale
  *reqPorts.emGenObjList.data.add_objects() = makeObject(5.0f, -10.0f, 7);  // would fire if fresh
  AebProPorts proPorts;

  AebFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_FALSE(proPorts.outputs.data.b_latent_pre_warning_active());
  EXPECT_EQ(proPorts.outputs.data.critical_obj_id(), 0u);
}

}  // namespace
}  // namespace adas::df
