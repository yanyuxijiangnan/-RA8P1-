#include "HX711.h"
#include <board.h>

rt_uint32_t hx711_buffer = 0;
rt_uint32_t weight_maopi = 0;
rt_int32_t  weight_shiwu = 0;
rt_uint8_t  flag_error = 0;
static rt_bool_t g_hx711_initialized = RT_FALSE;

void hx711_init(void)
{
    R_BSP_PinAccessEnable();
    R_BSP_PinWrite(HX711_SCK_PIN, BSP_IO_LEVEL_LOW);
    R_BSP_PinAccessDisable();

    rt_thread_mdelay(100);  
    g_hx711_initialized = RT_TRUE;
}

rt_uint32_t hx711_read(void)
{
    rt_uint32_t count = 0;
    rt_uint8_t i;

    uint32_t pin_cfg_out = IOPORT_CFG_PORT_DIRECTION_OUTPUT |
                           IOPORT_CFG_PORT_OUTPUT_HIGH |
                           IOPORT_CFG_NMOS_ENABLE;

    R_IOPORT_PinCfg(&g_ioport_ctrl, HX711_DOUT_PIN, pin_cfg_out);
    R_BSP_PinAccessEnable();
    R_BSP_PinWrite(HX711_DOUT_PIN, BSP_IO_LEVEL_HIGH);  
    R_BSP_PinAccessDisable();

    rt_hw_us_delay(10);

    uint32_t pin_cfg_in = IOPORT_CFG_PORT_DIRECTION_INPUT |
                          IOPORT_CFG_PULLUP_ENABLE;
    R_IOPORT_PinCfg(&g_ioport_ctrl, HX711_DOUT_PIN, pin_cfg_in);

    rt_hw_us_delay(10);

    R_BSP_PinAccessEnable();
    R_BSP_PinWrite(HX711_SCK_PIN, BSP_IO_LEVEL_LOW);
    R_BSP_PinAccessDisable();

    rt_tick_t start = rt_tick_get();
    while (1)
    {
        R_BSP_PinAccessEnable();
        bsp_io_level_t level = R_BSP_PinRead(HX711_DOUT_PIN);
        R_BSP_PinAccessDisable();

        if (level == BSP_IO_LEVEL_LOW)
            break;

        if (rt_tick_get() - start > rt_tick_from_millisecond(100))
        {
            flag_error = 1;
            return 0;
        }
        rt_thread_yield();
    }

    rt_base_t level = rt_hw_interrupt_disable();

    R_BSP_PinAccessEnable();

    for (i = 0; i < 24; i++)
    {
        R_BSP_PinWrite(HX711_SCK_PIN, BSP_IO_LEVEL_HIGH);
        count = count << 1;

        rt_hw_us_delay(1);

        R_BSP_PinWrite(HX711_SCK_PIN, BSP_IO_LEVEL_LOW);

        if (R_BSP_PinRead(HX711_DOUT_PIN) == BSP_IO_LEVEL_HIGH)
        {
            count++;
        }

        rt_hw_us_delay(1);
    }

    R_BSP_PinWrite(HX711_SCK_PIN, BSP_IO_LEVEL_HIGH);
    rt_hw_us_delay(1);
    R_BSP_PinWrite(HX711_SCK_PIN, BSP_IO_LEVEL_LOW);
    rt_hw_us_delay(1);

    R_BSP_PinAccessDisable();

    rt_hw_interrupt_enable(level);

    count ^= 0x800000;

    return count;
}

void hx711_get_maopi(void)
{
    weight_maopi = hx711_read();
}

void hx711_get_weight(void)
{
    hx711_buffer = hx711_read();

    if (hx711_buffer > weight_maopi)
    {
        weight_shiwu = (rt_int32_t)(hx711_buffer - weight_maopi);
        weight_shiwu = (rt_int32_t)((float)weight_shiwu /GAP_VALUE);
    }
    else
    {
        weight_shiwu = 0;
    }
}

void HX711_Init(void)
{
    hx711_init();
    rt_kprintf("[bee] HX711 initialized, taring...\n");
    hx711_get_maopi();
    rt_thread_mdelay(1000);
    hx711_get_maopi();  
    rt_kprintf("[bee] HX711 tare done, zero=%lu\n", weight_maopi);
}
