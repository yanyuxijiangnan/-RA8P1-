#include"Pump.h"
#include"hal_data.h"
#include <rtthread.h>

#define Pump_ON  rt_pin_write(Pump_PIN,1)
#define Pump_OFF rt_pin_write(Pump_PIN,0)

static rt_timer_t timer = RT_NULL;

void Pump_Proc_timing(void)
{
    Pump_ON;
    int cnt=0;
    while(cnt<5000)
    {
        cnt++;
    }
    Pump_OFF;
}

static void my_work(void *p)
{
    rt_kprintf("执行喂蜜\n");
    Pump_Proc_timing();
}

static int timer_init(void)
{
    timer = rt_timer_create("mytimer", my_work, RT_NULL,
                            rt_tick_from_millisecond(30000),
                            RT_TIMER_FLAG_PERIODIC);
    if (timer != RT_NULL) {
        rt_timer_start(timer);
    }

    return 0;
}

void Pump_Init(void)
{
    rt_pin_mode(Pump_PIN, 0x00);
    Pump_OFF;
    timer_init();
}

