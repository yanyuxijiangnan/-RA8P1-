#ifndef APPLICATIONS_ALARM_ALARM_H_
#define APPLICATIONS_ALARM_ALARM_H_

#include <rtthread.h>
#include "src/bee_box_sensors.h"

#define ALARM_NONE          0x00
#define ALARM_MOTION        0x01
#define ALARM_TEMP_LOW      0x02
#define ALARM_TEMP_HIGH     0x04
#define ALARM_TEMP_WARN     0x08
#define ALARM_HUMI_LOW      0x10
#define ALARM_HUMI_HIGH     0x20
#define ALARM_VOC_RAW_LOW   0x40
#define ALARM_VOC_BAD       0x80

#define ALARM_SEV_NONE      0
#define ALARM_SEV_WARN      1
#define ALARM_SEV_CRITICAL  2

void Alarm_Init(void);
void Alarm_Update(const bee_box_sensor_data_t *sample);
int  Alarm_IsActive(void);
uint8_t Alarm_GetSeverity(void);

#endif 
