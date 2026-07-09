#ifndef __BMI088_AGENT_H__
#define __BMI088_AGENT_H__

#include <rtthread.h>

#define BMI08X_SPI_RD_MASK                          UINT8_C(0x80)
#define BMI08X_SPI_WR_MASK                          UINT8_C(0x7F)

#define BMI08X_SOFT_RESET_CMD                       UINT8_C(0xB6)

#define BMI08X_ACCEL_PWR_ACTIVE_CMD                 UINT8_C(0x00)
#define BMI08X_ACCEL_PWR_SUSPEND_CMD                UINT8_C(0x03)

#define BMI08X_ACCEL_POWER_DISABLE_CMD              UINT8_C(0x00)
#define BMI08X_ACCEL_POWER_ENABLE_CMD               UINT8_C(0x04)

#define BMI08X_ACCEL_PM_ACTIVE                      UINT8_C(0x00)
#define BMI08X_ACCEL_PM_SUSPEND                     UINT8_C(0x03)

#define BMI08X_GYRO_PM_NORMAL                       UINT8_C(0x00)
#define BMI08X_GYRO_PM_DEEP_SUSPEND                 UINT8_C(0x20)
#define BMI08X_GYRO_PM_SUSPEND                      UINT8_C(0x80)

#define BMI08X_ACCEL_BW_OSR4                        UINT8_C(0x00)
#define BMI08X_ACCEL_BW_OSR2                        UINT8_C(0x01)
#define BMI08X_ACCEL_BW_NORMAL                      UINT8_C(0x02)

#define BMI08X_ACCEL_ODR_12_5_HZ                    UINT8_C(0x05)
#define BMI08X_ACCEL_ODR_25_HZ                      UINT8_C(0x06)
#define BMI08X_ACCEL_ODR_50_HZ                      UINT8_C(0x07)
#define BMI08X_ACCEL_ODR_100_HZ                     UINT8_C(0x08)
#define BMI08X_ACCEL_ODR_200_HZ                     UINT8_C(0x09)
#define BMI08X_ACCEL_ODR_400_HZ                     UINT8_C(0x0A)
#define BMI08X_ACCEL_ODR_800_HZ                     UINT8_C(0x0B)
#define BMI08X_ACCEL_ODR_1600_HZ                    UINT8_C(0x0C)
#define BMI088_ACCEL_RANGE_3G                       UINT8_C(0x00)
#define BMI088_ACCEL_RANGE_6G                       UINT8_C(0x01)
#define BMI088_ACCEL_RANGE_12G                      UINT8_C(0x02)
#define BMI088_ACCEL_RANGE_24G                      UINT8_C(0x03)

#define BMI08X_GYRO_RANGE_2000_DPS                  UINT8_C(0x00)
#define BMI08X_GYRO_RANGE_1000_DPS                  UINT8_C(0x01)
#define BMI08X_GYRO_RANGE_500_DPS                   UINT8_C(0x02)
#define BMI08X_GYRO_RANGE_250_DPS                   UINT8_C(0x03)
#define BMI08X_GYRO_RANGE_125_DPS                   UINT8_C(0x04)

#define BMI08X_GYRO_BW_532_ODR_2000_HZ              UINT8_C(0x00)
#define BMI08X_GYRO_BW_230_ODR_2000_HZ              UINT8_C(0x01)
#define BMI08X_GYRO_BW_116_ODR_1000_HZ              UINT8_C(0x02)
#define BMI08X_GYRO_BW_47_ODR_400_HZ                UINT8_C(0x03)
#define BMI08X_GYRO_BW_23_ODR_200_HZ                UINT8_C(0x04)
#define BMI08X_GYRO_BW_12_ODR_100_HZ                UINT8_C(0x05)
#define BMI08X_GYRO_BW_64_ODR_200_HZ                UINT8_C(0x06)
#define BMI08X_GYRO_BW_32_ODR_100_HZ                UINT8_C(0x07)
#define BMI08X_GYRO_ODR_RESET_VAL                   UINT8_C(0x80)

#define BMI08X_ACCEL_DATA_SYNC_MODE_OFF 0x00
#define BMI08X_ACCEL_DATA_SYNC_MODE_400HZ 0x01
#define BMI08X_ACCEL_DATA_SYNC_MODE_1000HZ 0x02
#define BMI08X_ACCEL_DATA_SYNC_MODE_2000HZ 0x03

#define BMI08X_ACCEL_SOFTRESET_DELAY_MS             UINT8_C(1)
#define BMI08X_GYRO_SOFTRESET_DELAY_MS              UINT8_C(30)
#define BMI08X_GYRO_POWER_MODE_CONFIG_DELAY         UINT8_C(30)
#define BMI08X_POWER_CONFIG_DELAY                   UINT8_C(50)

#define GRAVITY_EARTH (9.80665f)
#define deg2rad (3.1415926 / 180.0f)
#define rad2deg (180.0f / 3.1415926)

typedef enum
{
    ACC_CHIP_ID_REG             = 0x00,
    ACC_ERR_REG                 = 0x02,
    ACC_STATUS_REG              = 0x03,
    ACC_X_LSB_REG               = 0x12,
    ACC_X_MSB_REG               = 0x13,
    ACC_Y_LSB_REG               = 0x14,
    ACC_Y_MSB_REG               = 0x15,
    ACC_Z_LSB_REG               = 0x16,
    ACC_Z_MSB_REG               = 0x17,
    TEMP_MSB_REG                = 0x22,
    TEMP_LSB_REG                = 0x23,
    ACC_CONF_REG                = 0x40,
    ACC_RANGE_REG               = 0x41,
    INT1_IO_CTRL_REG            = 0x53,
    INT2_IO_CTRL_REG            = 0x54,
    ACC_SELF_TEST_REG           = 0x6D,
    ACC_PWR_CONF_REG            = 0x7C,
    ACC_PWR_CTRL_REG            = 0x7D,
    ACC_SOFTRESET_REG           = 0x7E
} bmi088a_reg_list_t;

typedef enum
{
    GYRO_CHIP_ID_REG            = 0x00,
    RATE_X_LSB_REG              = 0x02,
    RATE_X_MSB_REG              = 0x03,
    RATE_Y_LSB_REG              = 0x04,
    RATE_Y_MSB_REG              = 0x05,
    RATE_Z_LSB_REG              = 0x06,
    RATE_Z_MSB_REG              = 0x07,
    GYRO_INT_STAT_1_REG         = 0x0A,
    GYRO_RANGE_REG              = 0x0F,
    GYRO_BANDWIDTH_REG          = 0x10,
    GYRO_LPM1_REG               = 0x11,
    GYRO_SOFTRESET_REG          = 0x14,
    GYRO_INT_CTRL_REG           = 0x15
} bmi088g_reg_list_t;

enum bmi08x_intf {
BMI08X_I2C_INTF,
BMI08X_SPI_INTF
};

struct bmi08x_cfg
{
uint8_t power;
uint8_t range;
uint8_t bw;
uint8_t odr;
};

struct bmi08x_dev
{
uint8_t accel_chip_id;
uint8_t gyro_chip_id;
rt_base_t accel_id;
rt_base_t gyro_id;
rt_device_t accel_bus;
rt_device_t gyro_bus;
enum bmi08x_intf intf;
struct bmi08x_cfg accel_cfg;
struct bmi08x_cfg gyro_cfg;
const uint8_t *config_file_ptr;
uint8_t read_write_len;
};

struct bmi088_3axes
{
    rt_int16_t x;
    rt_int16_t y;
    rt_int16_t z;
};

struct bmi088_data
{
    float x;
    float y;
    float z;
};

struct bmi08x_dev *bmi088_init(const char *acc_name, const char *gyro_name);
void bmi088_deinit(struct bmi08x_dev *dev);
rt_err_t bmi088a_set_power_mode(struct bmi08x_dev *dev);
rt_err_t bmi088g_set_power_mode(struct bmi08x_dev *dev);
rt_err_t bmi088a_set_meas_conf(struct bmi08x_dev *dev);
rt_err_t bmi088g_set_meas_conf(struct bmi08x_dev *dev);
rt_size_t bmi088_get_accel(struct bmi08x_dev *dev, struct bmi088_data *buf);
rt_size_t bmi088_get_gyro(struct bmi08x_dev *dev, struct bmi088_data *buf);


#endif
