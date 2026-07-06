#include "component/aeb/aeb_function.hpp"

namespace adas::functions {

AebFunction::AebFunction(const AebReqPorts& reqPorts, AebProPorts& proPorts)
    : reqPorts_(reqPorts), proPorts_(proPorts) {}

void AebFunction::init(const FunctionParams& params) {
  maxAgeObjectsS_ = params.get<double>("AEB_MAX_AGE_OBJECTS_S", maxAgeObjectsS_);
  maxAgeEgoDynS_ = params.get<double>("AEB_MAX_AGE_EGO_DYN_S", maxAgeEgoDynS_);
}

void AebFunction::exec(double dtS) {
  (void)dtS;  // skeleton: no algorithm reads dt yet

  const bool objectsFresh =
      reqPorts_.emGenObjList.valid && reqPorts_.emGenObjList.ageS <= maxAgeObjectsS_;
  const bool egoDynFresh =
      reqPorts_.egoDyn.valid && reqPorts_.egoDyn.ageS <= maxAgeEgoDynS_;

  adas::functions::CompState state;
  state.set_function("aeb");
  state.set_state(objectsFresh && egoDynFresh ? adas::functions::CompState::RUNNING
                                               : adas::functions::CompState::ERROR);
  proPorts_.compState.data = state;
  proPorts_.compState.updated = true;

  // Skeleton: always publish the neutral, all-flags-false reaction (default
  // construction already zero-initializes every bool). Step 7+ fills this in
  // with real target selection/TTC/warning-state-machine logic.
  proPorts_.hypReaction.data = adas::functions::AebHypReaction();
  proPorts_.hypReaction.updated = true;
}

const adas::functions::CompState& AebFunction::compState() const {
  return proPorts_.compState.data;
}

}  // namespace adas::functions
