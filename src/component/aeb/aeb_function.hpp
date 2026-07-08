#pragma once

#include "component/common/framework/i_df_function.hpp"
#include "component/aeb/aeb_ports.hpp"

namespace adas::df {

// AEB skeleton (plan.md §5.7 Step 4): input-validity/staleness checks +
// compState update + a neutral (no-stage-active) AebHypReaction every cycle.
// No target selection/TTC/warning-state-machine yet (Step 7+).
class AebFunction final : public IDfFunction {
public:
  AebFunction(const AebReqPorts& reqPorts, AebProPorts& proPorts);

  void init(const DfParams& params) override;
  void exec(double dtS) override;
  const adas::functions::CompState& compState() const override;

private:
  const AebReqPorts& reqPorts_;
  AebProPorts&       proPorts_;

  double maxAgeObjectsS_ = 0.2;   // overwritten by init(); this is just a safe fallback
  double maxAgeEgoDynS_ = 0.2;
};

}  // namespace adas::df
