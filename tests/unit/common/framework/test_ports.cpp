#include <gtest/gtest.h>

#include "component/common/framework/ports.hpp"

namespace adas::df {
namespace {

TEST(PortsTest, ReqPortDefaultsToInvalid) {
  ReqPort<int> port;
  EXPECT_FALSE(port.valid);
  EXPECT_DOUBLE_EQ(port.ageS, 0.0);
}

TEST(PortsTest, ReqPortHoldsAssignedDataAndAge) {
  ReqPort<int> port;
  port.data = 42;
  port.ageS = 0.05;
  port.valid = true;
  EXPECT_TRUE(port.valid);
  EXPECT_EQ(port.data, 42);
  EXPECT_DOUBLE_EQ(port.ageS, 0.05);
}

TEST(PortsTest, ProPortDefaultsToNotUpdated) {
  ProPort<int> port;
  EXPECT_FALSE(port.updated);
}

}  // namespace
}  // namespace adas::df
