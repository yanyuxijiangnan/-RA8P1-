#ifndef APPLICATIONS_AUDIO_ANALYSIS_BEE_AUDIO_ANALYSIS_H_
#define APPLICATIONS_AUDIO_ANALYSIS_BEE_AUDIO_ANALYSIS_H_

#include <rtthread.h>
#include "MAX9814/max9814.h"

#define BEE_FFT_SIZE            1024    
#define BEE_SAMPLE_RATE         8000    

#define BEE_BAND_LOW_MIN        150     
#define BEE_BAND_LOW_MAX        280     
#define BEE_BAND_MID_MIN        300     
#define BEE_BAND_MID_MAX        500     
#define BEE_BAND_HIGH_MIN       600     
#define BEE_BAND_HIGH_MAX       1500    
#define BEE_BAND_VHIGH_MIN      1500
#define BEE_BAND_VHIGH_MAX      3500    

typedef struct {
    float low_band_energy;      
    float mid_band_energy;      
    float high_band_energy;     
    float vhigh_band_energy;    
    float total_energy;         
    float spectral_centroid;    
    float spectral_flatness;    
    float dominant_freq;        
    float dominant_magnitude;   
    float rms;                  
    float zero_cross_rate;      
} bee_audio_features_t;

typedef struct {
    bee_sound_state_t state;           
    float             confidence;      
    const char       *state_name;      
    uint32_t          timestamp;       
    bee_audio_features_t features;     
} bee_audio_result_t;

int  bee_audio_analysis_init(void);
int  bee_audio_analysis_start(void);
int  bee_audio_analysis_stop(void);
int  bee_audio_get_result(bee_audio_result_t *result, rt_int32_t timeout_ms);
void bee_audio_features_print(const bee_audio_features_t *f);
const char* bee_audio_state_name(bee_sound_state_t state);

#endif 
