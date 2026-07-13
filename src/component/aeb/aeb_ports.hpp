// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   AEB's require/provide port structs (AebReqPorts, AebProPorts).

#pragma once

#include "component/common/framework/ports.hpp"

#include "PerceptionCore__Outputs/gen_object_list.pb.h"
#include "VehSigProvider__Outputs/veh_dyn.pb.h"
#include "Aeb__Outputs/aeb_outputs.pb.h"
#include "common/comp_state.pb.h"

namespace adas::df {

// AEB's require-ports (plan.md §5.6). "objects", never "tracks".
struct AebReqPorts {
  ReqPort<adas::perception::GenObjectList> emGenObjList;
  ReqPort<adas::common::VehDyn> egoDyn;
};

// AEB's provide-ports. outputs is AEB's own warning/reaction output —
// there is no separate FCW component. compState is the mandatory heartbeat
// every function publishes (plan.md §5.4).
struct AebProPorts {
  ProPort<adas::df::AebOutputs> outputs;
  ProPort<adas::df::CompState> compState;
};

}  // namespace adas::df
