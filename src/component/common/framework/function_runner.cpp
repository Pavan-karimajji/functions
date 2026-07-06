#include "component/common/framework/function_runner.hpp"

namespace adas::functions {

void FunctionRunner::registerFunction(IFunction& function) {
  functions_.push_back(&function);
}

void FunctionRunner::exec(double dtS) {
  for (IFunction* function : functions_) {
    function->exec(dtS);
  }
}

}  // namespace adas::functions
