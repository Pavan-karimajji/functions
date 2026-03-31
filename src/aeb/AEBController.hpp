#pragma once
#include "functions/IAEBController.hpp"

namespace adas { namespace functions {

class AEBController : public IAEBController {
public:
    AEBController() = default;
    ~AEBController() override = default;

    adas::control::ControlCommand evaluate(
        const adas::perception::TrackList& tracks,
        const adas::common::VehicleState& vehicle_state) override;

    bool is_active() const override;

private:
    bool active_ = false;
    // TODO: TTC calculation, brake profile, state machine
};

}} // namespace adas::functions
