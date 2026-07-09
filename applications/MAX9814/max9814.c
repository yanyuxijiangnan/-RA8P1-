
#include "max9814.h"
#include"hal_data.h"
#include <math.h>
#include <stdlib.h>

#define DBG_TAG "max9814"
#define DBG_LVL DBG_LOG
#include <rtdbg.h>

#define SAMPLE_PERIOD_US    125
#define SAMPLES_PER_TICK    8

#define MAX9814_THREAD_PRIORITY     20
#define MAX9814_THREAD_STACK_SIZE   2048

const char *bee_sound_state_names[] = {
    "Normal",
    "Swarm Prelude",
    "Queen Missing",
    "Hornet Invasion",
    "Abnormal",
};

static max9814_dev_t g_max9814 = {0};
static struct rt_thread g_sample_thread;
static rt_uint8_t g_sample_thread_stack[2048];

static float calc_rms(int16_t *samples, uint32_t count)
{
    if (count == 0) return 0.0f;
    double sum = 0.0;
    for (uint32_t i = 0; i < count; i++) {
        sum += (double)samples[i] * samples[i];
    }
    return (float)sqrt(sum / count);
}

static float calc_peak(int16_t *samples, uint32_t count)
{
    if (count == 0) return 0.0f;
    int16_t peak = 0;
    for (uint32_t i = 0; i < count; i++) {
        int16_t abs_val = abs(samples[i]);
        if (abs_val > peak) peak = abs_val;
    }
    return (float)peak;
}

static int16_t adc_to_sample(uint32_t adc_val)
{
    int32_t centered = (int32_t)adc_val - 32768;
    if (centered > 32767) centered = 32767;
    if (centered < -32768) centered = -32768;
    return (int16_t)centered;
}

static void buffer_push(int16_t sample)
{
    uint32_t next = (g_max9814.buf_write_idx + 1) % MAX9814_BUFFER_SIZE;
    if (next == g_max9814.buf_read_idx) {
        g_max9814.buf_read_idx = (g_max9814.buf_read_idx + 1) % MAX9814_BUFFER_SIZE;
    }
    g_max9814.buffer[g_max9814.buf_write_idx] = sample;
    g_max9814.buf_write_idx = next;
}

static int16_t buffer_pop(void)
{
    if (g_max9814.buf_read_idx == g_max9814.buf_write_idx) {
        return 0;
    }
    int16_t sample = g_max9814.buffer[g_max9814.buf_read_idx];
    g_max9814.buf_read_idx = (g_max9814.buf_read_idx + 1) % MAX9814_BUFFER_SIZE;
    return sample;
}

static uint32_t buffer_available(void)
{
    if (g_max9814.buf_write_idx >= g_max9814.buf_read_idx) {
        return g_max9814.buf_write_idx - g_max9814.buf_read_idx;
    } else {
        return MAX9814_BUFFER_SIZE - g_max9814.buf_read_idx + g_max9814.buf_write_idx;
    }
}

static uint32_t max9814_adc_read_hal(void)
{
    uint16_t result = 0;

    fsp_err_t err = R_ADC_B_ScanStart(&g_adc0_ctrl);
    if (err != FSP_SUCCESS)
        return 32768;

    rt_hw_us_delay(50);

    err = R_ADC_B_Read(&g_adc0_ctrl, ADC_CHANNEL_18, &result);
    if (err != FSP_SUCCESS)
        return 32768;

    return (uint32_t)result;
}

static void max9814_sample_thread_entry(void *param)
{
    uint32_t sample_count = 0;
    uint32_t frame_pos = 0;

    LOG_I("MAX9814 sample thread started, rate=%dHz", MAX9814_SAMPLE_RATE);

    while (g_max9814.running) {
        for (int i = 0; i < SAMPLES_PER_TICK && g_max9814.running; i++) {
            uint32_t adc_val = max9814_adc_read_hal();
            int16_t sample = adc_to_sample(adc_val);

            buffer_push(sample);

            g_max9814.current_frame.samples[frame_pos] = sample;
            frame_pos++;
            sample_count++;

            if (frame_pos >= MAX9814_FRAME_SAMPLES) {
                g_max9814.current_frame.sample_count = MAX9814_FRAME_SAMPLES;
                g_max9814.current_frame.timestamp = rt_tick_get();
                g_max9814.current_frame.rms = calc_rms(
                    g_max9814.current_frame.samples, MAX9814_FRAME_SAMPLES);
                g_max9814.current_frame.peak = calc_peak(
                    g_max9814.current_frame.samples, MAX9814_FRAME_SAMPLES);

                rt_mutex_take(g_max9814.mutex, RT_WAITING_FOREVER);
                g_max9814.current_rms = g_max9814.current_frame.rms;
                g_max9814.current_peak = g_max9814.current_frame.peak;
                g_max9814.frame_seq++;
                g_max9814.frame_ready = 1;
                rt_mutex_release(g_max9814.mutex);

                frame_pos = 0;
            }
        }
        rt_thread_mdelay(1);  
    }

    LOG_I("MAX9814 sample thread stopped, total samples=%lu", sample_count);
}

int max9814_init(void)
{
    if (g_max9814.adc_dev != RT_NULL) {
        LOG_W("MAX9814 already initialized");
        return RT_EOK;
    }

    g_max9814.adc_dev = (struct rt_adc_device *)rt_device_find("adc0");
    if (g_max9814.adc_dev == RT_NULL) {
        LOG_E("ADC device 'adc0' not found");
        return -RT_ERROR;
    }

    rt_err_t ret = rt_adc_enable(g_max9814.adc_dev, MAX9814_ADC_CHANNEL);
    if (ret != RT_EOK) {
        LOG_E("ADC channel %d enable failed: %d", MAX9814_ADC_CHANNEL, ret);
        return -RT_ERROR;
    }

    g_max9814.buf_write_idx = 0;
    g_max9814.buf_read_idx = 0;
    g_max9814.buf_count = 0;
    g_max9814.frame_ready = 0;
    g_max9814.running = 0;

    g_max9814.mutex = rt_mutex_create("max9814_mtx", RT_IPC_FLAG_FIFO);
    if (g_max9814.mutex == RT_NULL) {
        LOG_E("Create mutex failed");
        return -RT_ERROR;
    }

    LOG_I("MAX9814 initialized, ADC=adc0, ch=%d, rate=%dHz",
          MAX9814_ADC_CHANNEL, MAX9814_SAMPLE_RATE);

    return RT_EOK;
}

int max9814_start(void)
{
    if (g_max9814.adc_dev == RT_NULL) {
        LOG_E("MAX9814 not initialized");
        return -RT_ERROR;
    }

    if (g_max9814.running) {
        LOG_W("MAX9814 already running");
        return RT_EOK;
    }

    g_max9814.running = 1;
    g_max9814.frame_ready = 0;

    rt_err_t ret = rt_thread_init(&g_sample_thread,
                                  "max9814",
                                  max9814_sample_thread_entry,
                                  RT_NULL,
                                  g_sample_thread_stack,
                                  sizeof(g_sample_thread_stack),
                                  MAX9814_THREAD_PRIORITY,
                                  5);
    if (ret != RT_EOK) {
        LOG_E("Thread init failed: %d", ret);
        g_max9814.running = 0;
        return -RT_ERROR;
    }

    rt_thread_startup(&g_sample_thread);

    LOG_I("MAX9814 capture started");
    return RT_EOK;
}

int max9814_stop(void)
{
    if (!g_max9814.running) {
        return RT_EOK;
    }

    g_max9814.running = 0;

    rt_thread_delay(2); 

    rt_thread_detach(&g_sample_thread);

    LOG_I("MAX9814 capture stopped");
    return RT_EOK;
}

int max9814_read_frame(max9814_frame_t *frame, rt_int32_t timeout_ms)
{
    static uint32_t last_seq = 0;
    rt_tick_t start = rt_tick_get();
    rt_tick_t timeout_ticks = rt_tick_from_millisecond(timeout_ms);

    while (g_max9814.frame_seq == last_seq) {
        rt_thread_delay(1);
        if (timeout_ms > 0 && rt_tick_get() - start > timeout_ticks) {
            return -RT_ETIMEOUT;
        }
    }

    rt_mutex_take(g_max9814.mutex, RT_WAITING_FOREVER);
    rt_memcpy(frame, &g_max9814.current_frame, sizeof(max9814_frame_t));
    last_seq = g_max9814.frame_seq;
    rt_mutex_release(g_max9814.mutex);

    return RT_EOK;
}

float max9814_get_rms(void)
{
    return g_max9814.current_rms;
}

float max9814_get_peak(void)
{
    return g_max9814.current_peak;
}

int max9814_is_running(void)
{
    return g_max9814.running;
}

void max9814_reset_buffer(void)
{
    rt_mutex_take(g_max9814.mutex, RT_WAITING_FOREVER);
    g_max9814.buf_write_idx = 0;
    g_max9814.buf_read_idx = 0;
    g_max9814.buf_count = 0;
    g_max9814.frame_ready = 0;
    rt_mutex_release(g_max9814.mutex);
}
