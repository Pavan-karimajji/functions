// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   DfRunner implementation: registers and cyclically executes functions.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include "component/common/framework/df_runner.hpp"

namespace adas::df {

void DfRunner::registerFunction(IDfFunction& function) {
  functions_.push_back(&function);
}

void DfRunner::exec(double dtS) {
  for (IDfFunction* function : functions_) {
    function->exec(dtS);
  }
}

}  // namespace adas::df
