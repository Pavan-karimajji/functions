// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   df_sil.dll's C-API implementation (dfInit/dfExec/dfShutdown).
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include "df_interface_c.h"

#include <cstring>
#include <string>

#include "param_loader.hpp"
#include "component/common/framework/df_runner.hpp"
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
void updateReqPort(adas::df::ReqPort<T>& port, const DfReqBuf* buf) {
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
bool writeProBuf(const google::protobuf::Message& msg, bool updated, DfProBuf* buf) {
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
// blocks in dfInit/dfExec below) is how a second function gets added —
// see add_function.md step 3.
struct DfHandle {
#ifdef ADAS_FN_AEB_ENABLED
  adas::df::AebReqPorts aebReqPorts;
  adas::df::AebProPorts aebProPorts;
  adas::df::AebFunction aebFunction{aebReqPorts, aebProPorts};
#endif
  adas::df::DfRunner runner;
};

}  // namespace

extern "C" {

int dfApiVersion(void) {
  return 1;
}

void* dfInit(const char* configPath) {
  // No exception ever crosses the extern "C" boundary (rule 12 / SWR-DLL-05) —
  // nothing here is known to throw today, this is defensive against a future
  // change, and mandatory for non-C++ hosts that couldn't catch one anyway.
  try {
    auto* handle = new DfHandle();
    adas::df::ParamLoader loader(configPath != nullptr ? configPath : "");

#ifdef ADAS_FN_AEB_ENABLED
    handle->aebFunction.init(loader.section("aeb"));
    handle->runner.registerFunction(handle->aebFunction);
#endif

    return handle;
  } catch (...) {
    return nullptr;
  }
}

int dfExec(void* handleOpaque, double dtS, const DfReqBuf* objects, const DfReqBuf* egoDyn,
           DfProBuf* aebOutputs, DfProBuf* compState) {
  if (handleOpaque == nullptr) {
    return 0;
  }
  auto* handle = static_cast<DfHandle*>(handleOpaque);

  try {
#ifdef ADAS_FN_AEB_ENABLED
    updateReqPort(handle->aebReqPorts.emGenObjList, objects);
    updateReqPort(handle->aebReqPorts.egoDyn, egoDyn);
#endif

    handle->runner.exec(dtS);

    bool ok = true;
#ifdef ADAS_FN_AEB_ENABLED
    ok = writeProBuf(handle->aebProPorts.outputs.data, handle->aebProPorts.outputs.updated,
                     aebOutputs) &&
         ok;
    ok = writeProBuf(handle->aebProPorts.compState.data, handle->aebProPorts.compState.updated,
                     compState) &&
         ok;
#else
    if (aebOutputs != nullptr) aebOutputs->updated = 0;
    if (compState != nullptr) compState->updated = 0;
#endif
    return ok ? 1 : 0;
  } catch (...) {
    return 0;
  }
}

void dfShutdown(void* handleOpaque) {
  try {
    delete static_cast<DfHandle*>(handleOpaque);
  } catch (...) {
    // Nothing more to do — swallow, per rule 12.
  }
}

}  // extern "C"
