#include "proto_stubs.hpp"
#include "AEBController.hpp"

namespace adas { namespace functions {

adas::control::ControlCommand AEBController::evaluate(
    const adas::perception::TrackList& tracks,
    const adas::common::VehicleState& vehicle_state) {
    adas::control::ControlCommand cmd;
    // TODO: Implement AEB logic
    // 1. Find most dangerous object (min TTC)
    // 2. Calculate TTC: distance / closing_speed
    // 3. If TTC < threshold_brake â†’ full brake request
    // 4. If TTC < threshold_warn â†’ FCW warning only
    // 5. Apply brake profile (ramp up)
    return cmd;
}

bool AEBController::is_active() const { return active_; }

}} // namespace adas::functions

