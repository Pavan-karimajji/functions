#include <gtest/gtest.h>

#include <cstdint>
#include <string>
#include <vector>

#include "df_interface_c.h"

#include "PerceptionCore__Outputs/gen_object_list.pb.h"
#include "VehSigProvider__Outputs/veh_dyn.pb.h"
#include "Aeb__Outputs/aeb_outputs.pb.h"
#include "common/comp_state.pb.h"

namespace {

// ADAS_DF_PROJECTS_DIR is injected by tests/CMakeLists.txt.
constexpr auto kBaseDefault = ADAS_DF_PROJECTS_DIR "/base/default.yaml";
constexpr auto kProjAlphaDefault = ADAS_DF_PROJECTS_DIR "/proj_alpha/default.yaml";

std::vector<uint8_t> serialize(const google::protobuf::Message& msg) {
  std::string bytes;
  msg.SerializeToString(&bytes);
  return std::vector<uint8_t>(bytes.begin(), bytes.end());
}

adas::perception::GenObjectList oneClosingObject(float distX, float vrelX, uint32_t uiId) {
  adas::perception::GenObjectList objectsMsg;
  auto* obj = objectsMsg.add_objects();
  obj->mutable_kinematic()->set_f_dist_x(distX);
  obj->mutable_kinematic()->set_f_vrel_x(vrelX);
  obj->mutable_general()->set_ui_id(uiId);
  return objectsMsg;
}

}  // namespace

TEST(InterfaceCApiTest, ApiVersionIsStable) {
  EXPECT_EQ(dfApiVersion(), 1);
}

// CompState reporting is deliberately not implemented yet (deferred to the
// detailed AEB rework, docs/df_aeb_ttc_blueprint.md) — the buffer stays at
// its neutral/not-updated default all the way through the C API too.
TEST(InterfaceCApiTest, RoundTripReportsNeutralAebOutputsAndDeferredCompState) {
  void* handle = dfInit("");  // empty path -> ParamLoader falls back to AebFunction's own defaults
  ASSERT_NE(handle, nullptr);

  adas::perception::GenObjectList objectsMsg;  // empty list — only freshness is checked at this step
  adas::common::VehDyn egoDynMsg;
  auto objectsBytes = serialize(objectsMsg);
  auto egoDynBytes = serialize(egoDynMsg);

  DfReqBuf objects{objectsBytes.data(), objectsBytes.size(), 0.05, 1};
  DfReqBuf egoDyn{egoDynBytes.data(), egoDynBytes.size(), 0.05, 1};

  std::vector<uint8_t> aebOutputsBuf(256);
  std::vector<uint8_t> compStateBuf(256);
  DfProBuf aebOutputs{aebOutputsBuf.data(), aebOutputsBuf.size(), 0, 0};
  DfProBuf compState{compStateBuf.data(), compStateBuf.size(), 0, 0};

  EXPECT_EQ(dfExec(handle, 0.05, &objects, &egoDyn, &aebOutputs, &compState), 1);

  adas::df::CompState state;
  ASSERT_TRUE(state.ParseFromArray(compStateBuf.data(), static_cast<int>(compState.len)));
  EXPECT_EQ(state.state(), adas::df::CompState::NOT_INITIALIZED);
  EXPECT_FALSE(compState.updated);

  adas::df::AebOutputs outputs;
  ASSERT_TRUE(outputs.ParseFromArray(aebOutputsBuf.data(), static_cast<int>(aebOutputs.len)));
  EXPECT_FALSE(outputs.b_latent_pre_warning_active());
  EXPECT_FALSE(outputs.b_dynamic_acute_warning_active());
  EXPECT_FALSE(outputs.b_pre_brake_active());
  EXPECT_TRUE(aebOutputs.updated);

  dfShutdown(handle);
}

TEST(InterfaceCApiTest, MissingInputsProduceNeutralOutputs) {
  void* handle = dfInit("");
  ASSERT_NE(handle, nullptr);

  std::vector<uint8_t> aebOutputsBuf(256);
  DfProBuf aebOutputs{aebOutputsBuf.data(), aebOutputsBuf.size(), 0, 0};

  // objects/egoDyn both null -> "never received this tick"
  EXPECT_EQ(dfExec(handle, 0.05, nullptr, nullptr, &aebOutputs, nullptr), 1);

  adas::df::AebOutputs outputs;
  ASSERT_TRUE(outputs.ParseFromArray(aebOutputsBuf.data(), static_cast<int>(aebOutputs.len)));
  EXPECT_FALSE(outputs.b_latent_pre_warning_active());
  EXPECT_EQ(outputs.critical_obj_id(), 0u);

  dfShutdown(handle);
}

TEST(InterfaceCApiTest, EndToEndWarningThroughDll) {
  void* handle = dfInit(kBaseDefault);  // AEB_TTC_PRE_WARNING_THRESHOLD_S: 1.0
  ASSERT_NE(handle, nullptr);

  auto objectsMsg = oneClosingObject(/*distX=*/5.0f, /*vrelX=*/-10.0f, /*uiId=*/42);  // TTC 0.5s
  adas::common::VehDyn egoDynMsg;
  auto objectsBytes = serialize(objectsMsg);
  auto egoDynBytes = serialize(egoDynMsg);

  DfReqBuf objects{objectsBytes.data(), objectsBytes.size(), 0.05, 1};
  DfReqBuf egoDyn{egoDynBytes.data(), egoDynBytes.size(), 0.05, 1};

  std::vector<uint8_t> aebOutputsBuf(256);
  DfProBuf aebOutputs{aebOutputsBuf.data(), aebOutputsBuf.size(), 0, 0};

  EXPECT_EQ(dfExec(handle, 0.05, &objects, &egoDyn, &aebOutputs, nullptr), 1);

  adas::df::AebOutputs outputs;
  ASSERT_TRUE(outputs.ParseFromArray(aebOutputsBuf.data(), static_cast<int>(aebOutputs.len)));
  EXPECT_TRUE(outputs.b_latent_pre_warning_active());
  EXPECT_EQ(outputs.critical_obj_id(), 42u);

  dfShutdown(handle);
}

TEST(InterfaceCApiTest, ThresholdIsProjectScoped) {
  // Same object, TTC ~1.1s: below proj_alpha's 1.2s threshold, not below base's 1.0s.
  auto objectsMsg = oneClosingObject(/*distX=*/11.0f, /*vrelX=*/-10.0f, /*uiId=*/1);
  adas::common::VehDyn egoDynMsg;
  auto objectsBytes = serialize(objectsMsg);
  auto egoDynBytes = serialize(egoDynMsg);
  DfReqBuf objects{objectsBytes.data(), objectsBytes.size(), 0.05, 1};
  DfReqBuf egoDyn{egoDynBytes.data(), egoDynBytes.size(), 0.05, 1};

  void* baseHandle = dfInit(kBaseDefault);
  ASSERT_NE(baseHandle, nullptr);
  std::vector<uint8_t> baseBuf(256);
  DfProBuf baseOutputs{baseBuf.data(), baseBuf.size(), 0, 0};
  EXPECT_EQ(dfExec(baseHandle, 0.05, &objects, &egoDyn, &baseOutputs, nullptr), 1);
  adas::df::AebOutputs baseResult;
  ASSERT_TRUE(baseResult.ParseFromArray(baseBuf.data(), static_cast<int>(baseOutputs.len)));
  EXPECT_FALSE(baseResult.b_latent_pre_warning_active());
  dfShutdown(baseHandle);

  void* projAlphaHandle = dfInit(kProjAlphaDefault);
  ASSERT_NE(projAlphaHandle, nullptr);
  std::vector<uint8_t> projAlphaBuf(256);
  DfProBuf projAlphaOutputs{projAlphaBuf.data(), projAlphaBuf.size(), 0, 0};
  EXPECT_EQ(dfExec(projAlphaHandle, 0.05, &objects, &egoDyn, &projAlphaOutputs, nullptr), 1);
  adas::df::AebOutputs projAlphaResult;
  ASSERT_TRUE(projAlphaResult.ParseFromArray(projAlphaBuf.data(), static_cast<int>(projAlphaOutputs.len)));
  EXPECT_TRUE(projAlphaResult.b_latent_pre_warning_active());
  dfShutdown(projAlphaHandle);
}
