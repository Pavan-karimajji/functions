#pragma once

#include "common/comp_state.pb.h"
#include "component/common/framework/function_params.hpp"

namespace adas::functions {

// Lifecycle contract every function implements (plan.md §5.6). Concrete
// functions own their req/pro port structs directly (see
// .claude/templates/function_ports_template.hpp) — IFunction only fixes the
// three calls the runner/host need: one-time init, per-tick exec, and a way
// to read back the mandatory CompState heartbeat.
class IFunction {
public:
  virtual ~IFunction() = default;

  // One-time setup. Reads this function's own config section via params
  // (e.g. AebFunction reads the "aeb:" section) — never the whole file.
  virtual void init(const FunctionParams& params) = 0;

  // One cycle. dtS comes from the host (§5.3) — no clock reads, no I/O.
  virtual void exec(double dtS) = 0;

  virtual const adas::functions::CompState& compState() const = 0;
};

}  // namespace adas::functions
