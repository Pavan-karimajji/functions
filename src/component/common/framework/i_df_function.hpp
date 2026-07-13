// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   IDfFunction: lifecycle contract every df function implements.

#pragma once

#include "common/comp_state.pb.h"
#include "component/common/framework/df_params.hpp"

namespace adas::df {

// Lifecycle contract every function implements (plan.md §5.6). Concrete
// functions own their req/pro port structs directly (see
// .claude/templates/function_ports_template.hpp) — IDfFunction only fixes the
// three calls the runner/host need: one-time init, per-tick exec, and a way
// to read back the mandatory CompState heartbeat.
class IDfFunction {
public:
  virtual ~IDfFunction() = default;

  // One-time setup. Reads this function's own config section via params
  // (e.g. AebFunction reads the "aeb:" section) — never the whole file.
  virtual void init(const DfParams& params) = 0;

  // One cycle. dtS comes from the host (§5.3) — no clock reads, no I/O.
  virtual void exec(double dtS) = 0;

  virtual const adas::df::CompState& compState() const = 0;
};

}  // namespace adas::df
