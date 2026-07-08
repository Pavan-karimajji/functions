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
