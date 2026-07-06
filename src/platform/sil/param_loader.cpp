#include "param_loader.hpp"

namespace adas::functions {

ParamLoader::ParamLoader(const std::string& configPath) {
  try {
    root_ = YAML::LoadFile(configPath);
  } catch (const YAML::Exception&) {
    root_ = YAML::Node();  // missing/invalid file -> callers get defaults
  }
}

FunctionParams ParamLoader::section(const std::string& functionName) const {
  if (root_ && root_[functionName]) {
    return FunctionParams(root_[functionName]);
  }
  return FunctionParams();
}

}  // namespace adas::functions
