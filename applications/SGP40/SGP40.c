#include"SGP40.h"
#define HIVE_AQ_WINDOW_SIZE      30      
#define HIVE_AQ_WARMUP_MS        10000   
#define HIVE_AQ_DRIFT_ALARM      800     
#define HIVE_AQ_STABLE_BAND      400     
#define HIVE_AQ_HUMI_ALARM       8500    
#define HIVE_AQ_TEMP_RISE_ALARM  200     

typedef struct {
    uint16_t voc_history[HIVE_AQ_WINDOW_SIZE];
    uint32_t humi_history[HIVE_AQ_WINDOW_SIZE];
    int32_t  temp_history[HIVE_AQ_WINDOW_SIZE];  
    uint8_t  idx;
    uint16_t count;              
    uint16_t window_count;       
    uint16_t baseline_voc;       
    int32_t  baseline_temp;      
    rt_bool_t baseline_set;     
    rt_bool_t last_result;      
    uint32_t last_stable_tick;
    uint8_t  alarm_count;        
    uint8_t  good_count;         
} hive_aq_context_t;

static hive_aq_context_t g_hive_aq = {0};

int bee_hive_air_quality(uint16_t voc_raw, int32_t temp_centi, uint32_t humi_centi)
{
    hive_aq_context_t *ctx = &g_hive_aq;
    uint32_t now = rt_tick_get();
    int i;
    int32_t voc_sum = 0;
    int32_t temp_sum = 0;
    int32_t humi_sum = 0;
    uint16_t voc_avg;
    int32_t  temp_avg;
    uint16_t humi_avg;
    int32_t voc_drift;
    int32_t temp_rise;
    rt_bool_t alarm = RT_FALSE;

    if (ctx->count == 0) {
        ctx->last_stable_tick = now;
    }
    ctx->count++;

    ctx->voc_history[ctx->idx] = voc_raw;
    ctx->humi_history[ctx->idx] = humi_centi;
    ctx->temp_history[ctx->idx] = temp_centi;
    ctx->idx = (ctx->idx + 1) % HIVE_AQ_WINDOW_SIZE;
    if (ctx->window_count < HIVE_AQ_WINDOW_SIZE) {
        ctx->window_count++;
    }

    if (ctx->count % 15 == 0) {
        rt_kprintf("[hive] cnt=%u, win=%u, ms=%u, base=%d\n",
                   ctx->count, ctx->window_count,
                   now - ctx->last_stable_tick, ctx->baseline_set);
    }

    if ((now - ctx->last_stable_tick) < HIVE_AQ_WARMUP_MS) {
        return -1;  
    }

    if (!ctx->baseline_set) {
        for (i = 0; i < ctx->window_count; i++) {
            voc_sum += ctx->voc_history[i];
            temp_sum += ctx->temp_history[i];
        }
        if (ctx->window_count > 0) {
            ctx->baseline_voc = (uint16_t)(voc_sum / ctx->window_count);
            ctx->baseline_temp = (int32_t)(temp_sum / ctx->window_count);
        } else {
            ctx->baseline_voc = voc_raw;
            ctx->baseline_temp = temp_centi;
        }
        ctx->baseline_set = RT_TRUE;
    }

    voc_sum = 0; temp_sum = 0; humi_sum = 0;
    for (i = 0; i < ctx->window_count; i++) {
        uint8_t pos = (ctx->idx + HIVE_AQ_WINDOW_SIZE - ctx->window_count + i) % HIVE_AQ_WINDOW_SIZE;
        voc_sum += ctx->voc_history[pos];
        humi_sum += ctx->humi_history[pos];
        temp_sum += ctx->temp_history[pos];
    }
    voc_avg = (uint16_t)(voc_sum / ctx->window_count);
    humi_avg = (uint16_t)(humi_sum / ctx->window_count);
    temp_avg = (int32_t)(temp_sum / ctx->window_count);

    voc_drift = (int32_t)voc_avg - (int32_t)ctx->baseline_voc;
    temp_rise = (int32_t)temp_avg - (int32_t)ctx->baseline_temp;

    if (voc_drift < -500 || humi_avg > 7500) {
        alarm = RT_TRUE;
    }
    if (voc_drift > -200 && voc_drift < 300 && humi_avg < 7000) {
    }

    if (humi_avg > HIVE_AQ_HUMI_ALARM) {
        rt_kprintf("[hive] ALARM: humidity %u.%02u%%\n", humi_avg/100, humi_avg%100);
        alarm = RT_TRUE;
    }
    if (temp_rise > HIVE_AQ_TEMP_RISE_ALARM) {
        rt_kprintf("[hive] ALARM: temp rise +%d.%02dC\n", (int)temp_rise/100, (int)temp_rise%100);
        alarm = RT_TRUE;
    }

    if (alarm) {
        ctx->alarm_count++;
        ctx->good_count = 0;
        if (ctx->alarm_count >= 3) {
            ctx->last_result = 0;
            return 0;
        }
    } else {
        ctx->good_count++;
        ctx->alarm_count = 0;
        if (voc_avg < ctx->baseline_voc + 200) {
            ctx->baseline_voc = (ctx->baseline_voc * 7 + voc_avg) / 8;
        }
        ctx->baseline_temp = (ctx->baseline_temp * 7 + temp_avg) / 8;
        if (ctx->good_count >= 3) {
            ctx->last_result = 1;
            return 1;
        }
    }

    return ctx->last_result ? 1 : 0;
}

void bee_hive_air_quality_reset(void)
{
    memset(&g_hive_aq, 0, sizeof(g_hive_aq));
    rt_kprintf("[hive] air quality monitor reset\n");
}
