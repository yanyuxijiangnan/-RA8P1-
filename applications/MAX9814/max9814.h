#ifndef APPLICATIONS_MAX9814_MAX9814_H_
#define APPLICATIONS_MAX9814_MAX9814_H_

#include <rtthread.h>
#include <rtdevice.h>
#include "hal_data.h"

#define MAX9814_SAMPLE_RATE         8000    
#define MAX9814_FRAME_SAMPLES       1024    
#define MAX9814_BUFFER_SIZE         (MAX9814_FRAME_SAMPLES * 4)  
#define MAX9814_ADC_CHANNEL         ADC_CHANNEL_18

typedef enum {
    BEE_SOUND_NORMAL        = 0,    
    BEE_SOUND_SWARM_PRELUDE = 1,    
    BEE_SOUND_QUEEN_MISSING = 2,    
    BEE_SOUND_HORNET_INVADE = 3,    
    BEE_SOUND_ABNORMAL      = 4,    
} bee_sound_state_t;

extern const char *bee_sound_state_names[];

typedef struct {
    int16_t  samples[MAX9814_FRAME_SAMPLES];  
    uint32_t sample_count;                      
    uint32_t timestamp;                         
    float    rms;                               
    float    peak;                              
} max9814_frame_t;

typedef struct {
    struct rt_adc_device *adc_dev;          
    struct rt_timer     *sample_timer;      
    int16_t              buffer[MAX9814_BUFFER_SIZE]; 
    volatile uint32_t    buf_write_idx;     
    volatile uint32_t    buf_read_idx;      
    volatile uint32_t    buf_count;         
    volatile uint8_t     frame_ready;       
    max9814_frame_t      current_frame;     
    float                current_rms;       
    float                current_peak;      
    rt_mutex_t           mutex;             
    uint8_t              running;           
    uint32_t frame_seq;
} max9814_dev_t;

int       max9814_init(void);
int       max9814_start(void);
int       max9814_stop(void);
int       max9814_read_frame(max9814_frame_t *frame, rt_int32_t timeout_ms);
float     max9814_get_rms(void);
float     max9814_get_peak(void);
int       max9814_is_running(void);
void      max9814_reset_buffer(void);

#endif 
