#include "proto_stubs.hpp"
#include "AEBController.hpp"

namespace adas { namespace functions {

adas::control::ControlCommand AEBController::evaluate(
    const adas::perception::GenObjectList& objects,
    const adas::common::VehDyn& vehDyn) {
    adas::control::ControlCommand cmd;
    // TODO: Implement AEB logic
    // 1. Find most dangerous object (min TTC)
    // 2. Calculate TTC: distance / closing_speed
    // 3. If TTC < threshold_brake â†’ full brake request
    // 4. If TTC < threshold_warn -> warning only (AEB's warning stage, no brake request)
    // 5. Apply brake profile (ramp up)
    return cmd;
}

bool AEBController::is_active() const { return active_; }

}} // namespace adas::functions

