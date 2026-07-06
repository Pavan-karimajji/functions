#pragma once

#include <vector>

#include "component/common/framework/i_function.hpp"

namespace adas::functions {

// Registers functions in a fixed order and executes them cyclically
// (plan.md §5.3: event-in, cyclic-execute). The host (SIL DLL, CarMaker
// binding, eventual ROS2 wrapper) owns the clock and calls exec(dtS) once
// per tick — FunctionRunner never reads time itself.
class FunctionRunner {
public:
  void registerFunction(IFunction& function);
  void exec(double dtS);

private:
  std::vector<IFunction*> functions_;  // registration order == execution order
};

}  // namespace adas::functions
