// Template: new function component in modules/df (plan.md §5.6)
// Replace <Fn>/<fn> with the function name (e.g. Acc/acc). File names snake_case:
//   src/component/<fn>/<fn>_ports.hpp, <fn>_function.hpp, <fn>_function.cpp
// Naming rules: .claude/skills/naming_conventions.md ("objects" never "tracks").

#pragma once

#include "component/common/framework/ports.hpp"
#include "component/common/framework/i_function.hpp"

// Generated proto headers from modules/interfaces — the ONLY allowed data types
// on ports (sensor-agnostic constraint, plan.md item 2).
#include "PerceptionCore__Outputs/gen_object_list.pb.h"  // adas::perception::GenObjectList
#include "VehSigProvider__Outputs/veh_dyn.pb.h"           // adas::common::VehDyn
#include "common/comp_state.pb.h"                        // adas::functions::CompState

namespace adas::functions {

// Require-ports: what this function consumes. One member per input.
struct <Fn>ReqPorts {
  ReqPort<adas::perception::GenObjectList> emGenObjList;
  ReqPort<adas::common::VehDyn>            egoDyn;
  // add further req ports here — additive only
};

// Provide-ports: what this function produces. compState is mandatory (heartbeat).
struct <Fn>ProPorts {
  // ProPort<adas::functions::XyzOutput> xyzOutput;  // function-level output(s)
  ProPort<adas::functions::CompState> compState;
  // NEVER a ControlCommand here — demands go to the arbiter (plan.md §5.4)
};

class <Fn>Function final : public IFunction {
public:
  <Fn>Function(const <Fn>ReqPorts& reqPorts, <Fn>ProPorts& proPorts);

  void init(const FunctionParams& params) override;  // reads <fn>: config section
  void exec(double dtS) override;                     // one cycle; no clock reads, no I/O
  const adas::functions::CompState& compState() const override;

private:
  const <Fn>ReqPorts& reqPorts_;
  <Fn>ProPorts&       proPorts_;
  // calibration read in init(): e.g. maxAgeObjectsS_, maxAgeEgoDynS_
};

}  // namespace adas::functions
