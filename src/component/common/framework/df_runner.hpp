// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   DfRunner: registers functions and executes them cyclically each tick.

#pragma once

#include <vector>

#include "component/common/framework/i_df_function.hpp"

namespace adas::df {

// Registers functions in a fixed order and executes them cyclically
// (plan.md §5.3: event-in, cyclic-execute). The host (SIL DLL, CarMaker
// binding, eventual ROS2 wrapper) owns the clock and calls exec(dtS) once
// per tick — DfRunner never reads time itself.
class DfRunner {
public:
  void registerFunction(IDfFunction& function);
  void exec(double dtS);

private:
  std::vector<IDfFunction*> functions_;  // registration order == execution order
};

}  // namespace adas::df
