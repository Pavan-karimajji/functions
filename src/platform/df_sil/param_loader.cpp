// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   ParamLoader implementation: loads a project's YAML config file.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include "param_loader.hpp"

namespace adas::df {

ParamLoader::ParamLoader(const std::string& configPath) {
  try {
    root_ = YAML::LoadFile(configPath);
  } catch (const YAML::Exception&) {
    root_ = YAML::Node();  // missing/invalid file -> callers get defaults
  }
}

DfParams ParamLoader::section(const std::string& functionName) const {
  if (root_ && root_[functionName]) {
    return DfParams(root_[functionName]);
  }
  return DfParams();
}

DfParams ParamLoader::root() const {
  return DfParams(root_);
}

}  // namespace adas::df
