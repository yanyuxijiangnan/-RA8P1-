#include "Alarm.h"

static uint8_t  g_alarm_flags    = ALARM_NONE;
static uint8_t  g_alarm_severity = ALARM_SEV_NONE;

void Alarm_Init(void)
{
    g_alarm_flags    = ALARM_NONE;
    g_alarm_severity = ALARM_SEV_NONE;
}

void Alarm_Update(const bee_box_sensor_data_t *sample)
{
    uint8_t flags    = ALARM_NONE;
    uint8_t severity = ALARM_SEV_NONE;

    if (sample->motion_stable == 1)
    {
        flags |= ALARM_MOTION;
    }

    if (sample->sht31_ready)
    {
        int32_t temp = sample->temperature_centi_c / 100;

        if (temp > 35)
        {
            flags |= ALARM_TEMP_HIGH;
        }
        if (temp < 10)
        {
            flags |= ALARM_TEMP_LOW;
        }
        if (temp > 30)
        {
            flags |= ALARM_TEMP_WARN;
        }
    }

    if (sample->sht31_ready)
    {
        uint32_t humi = sample->humidity_centi_rh / 100;

        if (humi > 60)
        {
            flags |= ALARM_HUMI_HIGH;
        }
        if (humi < 30)
        {
            flags |= ALARM_HUMI_LOW;
        }
    }

    if (sample->sgp40_ready)
    {
        if (sample->voc_raw < 30000)
        {
            flags |= ALARM_VOC_RAW_LOW;
        }
        if (sample->voc_index < 100)
        {
            flags |= ALARM_VOC_BAD;
        }
    }

    if (flags & (ALARM_MOTION | ALARM_TEMP_HIGH | ALARM_TEMP_LOW |
                 ALARM_HUMI_HIGH | ALARM_HUMI_LOW | ALARM_VOC_RAW_LOW))
    {
        severity = ALARM_SEV_CRITICAL;
    }
    else if (flags & (ALARM_TEMP_WARN | ALARM_VOC_BAD))
    {
        severity = ALARM_SEV_WARN;
    }
    else
    {
        severity = ALARM_SEV_NONE;
    }

    g_alarm_flags    = flags;
    g_alarm_severity = severity;
}

int Alarm_IsActive(void)
{
    return (g_alarm_severity != ALARM_SEV_NONE) ? 1 : 0;
}

uint8_t Alarm_GetSeverity(void)
{
    return g_alarm_severity;
}
