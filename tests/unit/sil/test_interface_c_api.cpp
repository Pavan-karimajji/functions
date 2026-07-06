#include <gtest/gtest.h>

#include <cstdint>
#include <string>
#include <vector>

#include "functions_interface_c.h"

#include "PerceptionCore__Outputs/gen_object_list.pb.h"
#include "VehSigProvider__Outputs/veh_dyn.pb.h"
#include "Aeb__Outputs/aeb_hyp_reaction.pb.h"
#include "common/comp_state.pb.h"

namespace {

std::vector<uint8_t> serialize(const google::protobuf::Message& msg) {
  std::string bytes;
  msg.SerializeToString(&bytes);
  return std::vector<uint8_t>(bytes.begin(), bytes.end());
}

}  // namespace

TEST(InterfaceCApiTest, ApiVersionIsStable) {
  EXPECT_EQ(fnApiVersion(), 1);
}

TEST(InterfaceCApiTest, RoundTripReportsRunningAndNeutralHypReaction) {
  void* handle = fnInit("");  // empty path -> ParamLoader falls back to AebFunction's own defaults
  ASSERT_NE(handle, nullptr);

  adas::perception::GenObjectList objectsMsg;  // empty list — only freshness is checked at this step
  adas::common::VehDyn egoDynMsg;
  auto objectsBytes = serialize(objectsMsg);
  auto egoDynBytes = serialize(egoDynMsg);

  FnReqBuf objects{objectsBytes.data(), objectsBytes.size(), 0.05, 1};
  FnReqBuf egoDyn{egoDynBytes.data(), egoDynBytes.size(), 0.05, 1};

  std::vector<uint8_t> hypReactionBuf(256);
  std::vector<uint8_t> compStateBuf(256);
  FnProBuf hypReaction{hypReactionBuf.data(), hypReactionBuf.size(), 0, 0};
  FnProBuf compState{compStateBuf.data(), compStateBuf.size(), 0, 0};

  EXPECT_EQ(fnExec(handle, 0.05, &objects, &egoDyn, &hypReaction, &compState), 1);

  adas::functions::CompState state;
  ASSERT_TRUE(state.ParseFromArray(compStateBuf.data(), static_cast<int>(compState.len)));
  EXPECT_EQ(state.state(), adas::functions::CompState::RUNNING);
  EXPECT_EQ(state.function(), "aeb");
  EXPECT_TRUE(compState.updated);

  adas::functions::AebHypReaction reaction;
  ASSERT_TRUE(reaction.ParseFromArray(hypReactionBuf.data(), static_cast<int>(hypReaction.len)));
  EXPECT_FALSE(reaction.b_latent_pre_warning_active());
  EXPECT_FALSE(reaction.b_dynamic_acute_warning_active());
  EXPECT_FALSE(reaction.b_pre_brake_active());
  EXPECT_TRUE(hypReaction.updated);

  fnShutdown(handle);
}

TEST(InterfaceCApiTest, MissingInputsReportError) {
  void* handle = fnInit("");
  ASSERT_NE(handle, nullptr);

  std::vector<uint8_t> hypReactionBuf(256);
  std::vector<uint8_t> compStateBuf(256);
  FnProBuf hypReaction{hypReactionBuf.data(), hypReactionBuf.size(), 0, 0};
  FnProBuf compState{compStateBuf.data(), compStateBuf.size(), 0, 0};

  // objects/egoDyn both null -> "never received this tick"
  EXPECT_EQ(fnExec(handle, 0.05, nullptr, nullptr, &hypReaction, &compState), 1);

  adas::functions::CompState state;
  ASSERT_TRUE(state.ParseFromArray(compStateBuf.data(), static_cast<int>(compState.len)));
  EXPECT_EQ(state.state(), adas::functions::CompState::ERROR);

  fnShutdown(handle);
}
