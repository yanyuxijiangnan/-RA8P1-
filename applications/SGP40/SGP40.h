#ifndef APPLICATIONS_SGP40_SGP40_H_
#define APPLICATIONS_SGP40_SGP40_H_

#include <rtthread.h>
#include <rtdevice.h>

int bee_hive_air_quality(uint16_t voc_raw, int32_t temp_centi, uint32_t humi_centi);
void bee_hive_air_quality_reset(void);

#endif 
