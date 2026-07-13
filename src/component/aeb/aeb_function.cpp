// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   AEB function's CV-TTC exec() implementation (plan.md item 3).

#include "component/aeb/aeb_function.hpp"

#include <algorithm>
#include <cstdint>
#include <limits>

#include "component/common/framework/object_limits.hpp"

namespace adas::df {

AebFunction::AebFunction(const AebReqPorts& reqPorts, AebProPorts& proPorts)
    : reqPorts_(reqPorts), proPorts_(proPorts) {}

void AebFunction::init(const DfParams& params) {
  maxAgeObjectsS_ = params.get<double>("AEB_MAX_AGE_OBJECTS_S", maxAgeObjectsS_);
  maxAgeEgoDynS_ = params.get<double>("AEB_MAX_AGE_EGO_DYN_S", maxAgeEgoDynS_);
  ttcPreWarningThresholdS_ =
      params.get<double>("AEB_TTC_PRE_WARNING_THRESHOLD_S", ttcPreWarningThresholdS_);
}

void AebFunction::exec(double dtS) {
  (void)dtS;  // CV-TTC is a pure function of the current ports; dt unused
              // (docs/df_aeb_ttc_blueprint.md §3.2)

  // CompState reporting is deliberately not implemented yet (deferred to the
  // detailed AEB rework) — proPorts_.compState is never touched here.

  const bool objectsFresh =
      reqPorts_.emGenObjList.valid && reqPorts_.emGenObjList.ageS <= maxAgeObjectsS_;
  const bool egoDynFresh = reqPorts_.egoDyn.valid && reqPorts_.egoDyn.ageS <= maxAgeEgoDynS_;

  adas::df::AebOutputs out;  // default-constructed: all 8 stage flags false, critical_obj_id 0

  if (objectsFresh && egoDynFresh) {
    // Constant-velocity TTC over ego-relative kinematics (rear-axle origin,
    // +x forward, +y left). Only objects ahead of and closing on ego can fire;
    // the minimum-TTC object among those wins ties by list order.
    double minTtcS = std::numeric_limits<double>::infinity();
    std::uint32_t criticalId = 0;
    // Bounded to kMaxGenObjects regardless of how many the incoming message
    // actually contains (object_limits.hpp) - caps worst-case execution time
    // and guards against a malformed/oversized message crossing the C API
    // boundary, mirroring the reference's fixed-array EM_N_OBJECTS budget.
    const auto& objects = reqPorts_.emGenObjList.data.objects();
    const int numObjects = std::min(objects.size(), static_cast<int>(kMaxGenObjects));
    for (int i = 0; i < numObjects; ++i) {
      const auto& obj = objects.Get(i);
      const float dx = obj.kinematic().f_dist_x();
      const float vrelX = obj.kinematic().f_vrel_x();
      if (dx > 0.0f && vrelX < 0.0f) {
        const double ttcS = static_cast<double>(dx) / -static_cast<double>(vrelX);
        if (ttcS < minTtcS) {
          minTtcS = ttcS;
          criticalId = obj.general().ui_id();
        }
      }
    }

    const bool fired = minTtcS < ttcPreWarningThresholdS_;  // strictly less: equality does not fire
    out.set_b_latent_pre_warning_active(fired);
    out.set_critical_obj_id(fired ? criticalId : 0);
  }
  // Stale input: no TTC math runs, neutral AebOutputs (all-false) is published —
  // matches the always-publish contract every function honors.

  proPorts_.outputs.data = out;
  proPorts_.outputs.updated = true;
}

const adas::df::CompState& AebFunction::compState() const {
  return proPorts_.compState.data;
}

}  // namespace adas::df
