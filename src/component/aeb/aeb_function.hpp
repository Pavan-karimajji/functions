#pragma once

#include "component/common/framework/i_df_function.hpp"
#include "component/aeb/aeb_ports.hpp"

namespace adas::df {

// AEB CV-TTC blueprint (docs/df_aeb_ttc_blueprint.md): input-validity/
// staleness checks gate a constant-velocity-TTC pre-warning decision over
// emGenObjList each cycle. Only b_latent_pre_warning_active + critical_obj_id
// are driven for real; the remaining 7 stage flags stay false — the staged
// state machine is future work (plan.md item 2). CompState reporting is
// deliberately deferred (not set by exec() at all yet) — pending the same
// detailed rework.
class AebFunction final : public IDfFunction {
public:
  AebFunction(const AebReqPorts& reqPorts, AebProPorts& proPorts);

  void init(const DfParams& params) override;
  void exec(double dtS) override;
  const adas::df::CompState& compState() const override;

private:
  const AebReqPorts& reqPorts_;
  AebProPorts&       proPorts_;

  double maxAgeObjectsS_ = 0.2;   // overwritten by init(); this is just a safe fallback
  double maxAgeEgoDynS_ = 0.2;

  // Strictly-less semantics: ttcS == threshold does not fire (docs/df_aeb_ttc_blueprint.md §3.3).
  double ttcPreWarningThresholdS_ = 1.0;
};

}  // namespace adas::df
