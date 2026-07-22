// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   Unit tests for DfRunner's registration/execution order.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include <gtest/gtest.h>

#include <vector>

#include "component/common/framework/df_runner.hpp"

namespace adas::df {
namespace {

// Fake IDfFunction that records its own id into a shared vector on each exec() —
// enough to assert both "registration order == exec order" and "every
// registered function runs each tick", without needing a real function.
class RecordingFunction final : public IDfFunction {
public:
  RecordingFunction(int id, std::vector<int>& execLog) : id_(id), execLog_(execLog) {}

  void init(const DfParams&) override {}
  void exec(double) override {
    execLog_.push_back(id_);
  }
  const adas::df::CompState& compState() const override {
    return compState_;
  }

private:
  int id_;
  std::vector<int>& execLog_;
  adas::df::CompState compState_;
};

TEST(DfRunnerTest, ExecutesRegisteredFunctionsInRegistrationOrder) {
  std::vector<int> execLog;
  RecordingFunction first(1, execLog);
  RecordingFunction second(2, execLog);
  RecordingFunction third(3, execLog);

  DfRunner runner;
  runner.registerFunction(first);
  runner.registerFunction(second);
  runner.registerFunction(third);

  runner.exec(0.05);

  EXPECT_EQ(execLog, (std::vector<int>{1, 2, 3}));
}

TEST(DfRunnerTest, ExecRunsEveryRegisteredFunctionOnEachTick) {
  std::vector<int> execLog;
  RecordingFunction only(1, execLog);

  DfRunner runner;
  runner.registerFunction(only);
  runner.exec(0.05);
  runner.exec(0.05);

  EXPECT_EQ(execLog.size(), 2u);
}

}  // namespace
}  // namespace adas::df
