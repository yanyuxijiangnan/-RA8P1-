#ifndef APPLICATIONS_HX711_HX711_H_
#define APPLICATIONS_HX711_HX711_H_

#include <rtthread.h>
#include <rtdevice.h>

#define HX711_SCK_PIN   BSP_IO_PORT_01_PIN_12   
#define HX711_DOUT_PIN  BSP_IO_PORT_01_PIN_13   

#define GAP_VALUE       106.5f

extern rt_uint32_t hx711_buffer;
extern rt_uint32_t weight_maopi;
extern rt_int32_t  weight_shiwu;
extern rt_uint8_t  flag_error;

void hx711_init(void);
rt_uint32_t hx711_read(void);
void hx711_get_maopi(void);
void hx711_get_weight(void);
void HX711_Init(void);

#endif 
