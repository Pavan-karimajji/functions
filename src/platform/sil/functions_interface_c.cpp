#include "functions_interface_c.h"

#include <cstring>
#include <iostream>
#include <string>

#include "param_loader.hpp"
#include "component/common/framework/function_runner.hpp"
#include "component/common/framework/ports.hpp"

#ifdef ADAS_FN_AEB_ENABLED
#include "component/aeb/aeb_function.hpp"
#endif

namespace {

// Populates one ReqPort from a host-supplied buffer: valid only if the host
// marked it valid AND the bytes actually parse as T. Shared by every
// function's req ports (currently just AEB's two).
//
// Deliberately does NOT require buf->data != nullptr: an all-default message
// (e.g. an empty GenObjectList — "no objects visible this cycle", a normal,
// valid reading) serializes to zero bytes, and an empty std::vector's
// data() can legitimately be nullptr. ParseFromArray(nullptr, 0) is
// well-defined and returns true — the host's own `valid` flag is the
// authoritative "was something received" signal, not the pointer's nullness.
template <typename T>
void updateReqPort(adas::functions::ReqPort<T>& port, const FnReqBuf* buf) {
  if (buf != nullptr && buf->valid != 0 &&
      port.data.ParseFromArray(buf->data, static_cast<int>(buf->len))) {
    port.ageS = buf->ageS;
    port.valid = true;
  } else {
    port.valid = false;
  }
}

// Serializes msg into buf (if buf is non-null and big enough) and reports
// `updated`. Returns false only on a genuine failure (buffer too small) —
// buf == nullptr just means "caller doesn't want this output", not an error.
bool writeProBuf(const google::protobuf::Message& msg, bool updated, FnProBuf* buf) {
  if (buf == nullptr) {
    return true;
  }
  buf->updated = updated ? 1 : 0;
  std::string bytes;
  if (buf->data == nullptr || !msg.SerializeToString(&bytes) || bytes.size() > buf->cap) {
    buf->len = 0;
    return false;
  }
  std::memcpy(buf->data, bytes.data(), bytes.size());
  buf->len = bytes.size();
  return true;
}

// The DLL's composition root state. Growing this struct (and the #ifdef
// blocks in fnInit/fnExec below) is how a second function gets added —
// see add_function.md step 3.
struct FnHandle {
#ifdef ADAS_FN_AEB_ENABLED
  adas::functions::AebReqPorts aebReqPorts;
  adas::functions::AebProPorts aebProPorts;
  adas::functions::AebFunction aebFunction{aebReqPorts, aebProPorts};
#endif
  adas::functions::FunctionRunner runner;
};

}  // namespace

extern "C" {

int fnApiVersion(void) { return 1; }

void* fnInit(const char* configPath) {
  // No exception ever crosses the extern "C" boundary (rule 12 / SWR-DLL-05) —
  // nothing here is known to throw today, this is defensive against a future
  // change, and mandatory for non-C++ hosts that couldn't catch one anyway.
  try {
    auto* handle = new FnHandle();
    adas::functions::ParamLoader loader(configPath != nullptr ? configPath : "");

    // Placeholder: proves projects/base/ego_params.yaml reads end-to-end
    // through ParamLoader::root(). Read-only, not consumed by any function/port yet —
    // real wiring is plan.md item 2's job, once AEB's TTC/target-selection
    // logic knows exactly which fields it needs (docs/ego_params.md rule 8).
    adas::functions::ParamLoader egoLoader(ADAS_EGO_PARAMS_PATH);
    std::cout << "[ego_params placeholder] EGO_LENGTH_M="
              << egoLoader.root().get<double>("EGO_LENGTH_M", -1.0)
              << " EGO_WHEELBASE_M="
              << egoLoader.root().get<double>("EGO_WHEELBASE_M", -1.0)
              << " EGO_MASS_KG="
              << egoLoader.root().get<double>("EGO_MASS_KG", -1.0)
              << "\n";

#ifdef ADAS_FN_AEB_ENABLED
    handle->aebFunction.init(loader.section("aeb"));
    handle->runner.registerFunction(handle->aebFunction);
#endif

    return handle;
  } catch (...) {
    return nullptr;
  }
}

int fnExec(void* handleOpaque, double dtS,
            const FnReqBuf* objects, const FnReqBuf* egoDyn,
            FnProBuf* hypReaction, FnProBuf* compState) {
  if (handleOpaque == nullptr) {
    return 0;
  }
  auto* handle = static_cast<FnHandle*>(handleOpaque);

  try {
#ifdef ADAS_FN_AEB_ENABLED
    updateReqPort(handle->aebReqPorts.emGenObjList, objects);
    updateReqPort(handle->aebReqPorts.egoDyn, egoDyn);
#endif

    handle->runner.exec(dtS);

    bool ok = true;
#ifdef ADAS_FN_AEB_ENABLED
    ok = writeProBuf(handle->aebProPorts.hypReaction.data, handle->aebProPorts.hypReaction.updated, hypReaction) && ok;
    ok = writeProBuf(handle->aebProPorts.compState.data, handle->aebProPorts.compState.updated, compState) && ok;
#else
    if (hypReaction != nullptr) hypReaction->updated = 0;
    if (compState != nullptr) compState->updated = 0;
#endif
    return ok ? 1 : 0;
  } catch (...) {
    return 0;
  }
}

void fnShutdown(void* handleOpaque) {
  try {
    delete static_cast<FnHandle*>(handleOpaque);
  } catch (...) {
    // Nothing more to do — swallow, per rule 12.
  }
}

}  // extern "C"
