#include "LED.h"
#include "hal_data.h"
#include "my_Alarm/Alarm.h"

#define LED_BLINK_CRITICAL_MS  200
#define LED_BLINK_WARN_MS      500

static rt_tick_t g_led_last_toggle = 0;
static int       g_led_on          = 0;

void LED_Init(void)
{
    rt_pin_mode(LED_PIN, 0x00);
    rt_pin_write(LED_PIN, 0);
    g_led_last_toggle = rt_tick_get();
    g_led_on          = 0;
}

void LED_Proc(void)
{
    uint8_t  severity = Alarm_GetSeverity();
    rt_tick_t now     = rt_tick_get();
    rt_tick_t interval;

    if (severity == ALARM_SEV_NONE)
    {
        if (g_led_on)
        {
            rt_pin_write(LED_PIN, 0);
            g_led_on = 0;
        }
        g_led_last_toggle = now;
        return;
    }

    interval = (severity == ALARM_SEV_CRITICAL)
               ? rt_tick_from_millisecond(LED_BLINK_CRITICAL_MS)
               : rt_tick_from_millisecond(LED_BLINK_WARN_MS);

    if (now - g_led_last_toggle >= interval)
    {
        g_led_on = !g_led_on;
        rt_pin_write(LED_PIN, g_led_on ? 1 : 0);
        g_led_last_toggle = now;
    }
}
