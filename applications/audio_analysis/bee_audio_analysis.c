
#include "bee_audio_analysis.h"
#include <math.h>
#include <stdlib.h>

#define DBG_TAG "bee_audio"
#define DBG_LVL DBG_LOG
#include <rtdbg.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846f
#endif

#define SWARM_ENERGY_RATIO      1.8f    
#define HORNET_HIGH_RATIO       2.5f    
#define QUEEN_FLATNESS_THRESH   0.55f   
#define ABNORMAL_ZCR_VARIANCE  0.3f    
#define MIN_CONFIDENCE          0.55f   

#define SMOOTH_FRAMES           3

static uint16_t fft_rev10[1024];

typedef struct { float re, im; } complex_t;

typedef struct {
    complex_t        fft_buf[BEE_FFT_SIZE];      
    float            window[BEE_FFT_SIZE];        
    float            power_spectrum[BEE_FFT_SIZE/2]; 
    bee_audio_features_t features;               
    bee_audio_result_t   result;                 

    bee_sound_state_t smooth_states[SMOOTH_FRAMES];
    uint8_t           smooth_idx;

    struct rt_thread  thread;
    rt_uint8_t        thread_stack[4096];
    volatile uint8_t  running;
} bee_audio_ctx_t;

static bee_audio_ctx_t g_ctx = {0};


static void fft_gen_rev_table(uint16_t *table, int n)
{
    int bits = 0;
    while ((1 << bits) < n) bits++;
    for (int i = 0; i < n; i++) {
        int rev = 0;
        for (int j = 0; j < bits; j++) {
            if (i & (1 << j)) rev |= (1 << (bits - 1 - j));
        }
        table[i] = rev;
    }
}

static void fft_rad2(complex_t *x, int n)
{
    for (int i = 0; i < n; i++) {
        uint16_t rev = fft_rev10[i];
        if (i < rev) {
            complex_t tmp = x[i];
            x[i] = x[rev];
            x[rev] = tmp;
        }
    }

    int stages = 0;
    for (int tmp = n; tmp > 1; tmp >>= 1) stages++;
    for (int s = 1; s <= stages; s++) {
        int m = 1 << s;
        float ang = -2.0f * M_PI / m;
        complex_t wm = {cosf(ang), sinf(ang)};
        for (int k = 0; k < n; k += m) {
            complex_t w = {1.0f, 0.0f};
            for (int j = 0; j < m/2; j++) {
                complex_t t = {
                    w.re * x[k + j + m/2].re - w.im * x[k + j + m/2].im,
                    w.re * x[k + j + m/2].im + w.im * x[k + j + m/2].re
                };
                complex_t u = x[k + j];
                x[k + j].re = u.re + t.re;
                x[k + j].im = u.im + t.im;
                x[k + j + m/2].re = u.re - t.re;
                x[k + j + m/2].im = u.im - t.im;
                float tmp_re = w.re * wm.re - w.im * wm.im;
                float tmp_im = w.re * wm.im + w.im * wm.re;
                w.re = tmp_re;
                w.im = tmp_im;
            }
        }
    }
}


static void hanning_window(float *w, int n)
{
    for (int i = 0; i < n; i++) {
        w[i] = 0.5f * (1.0f - cosf(2.0f * M_PI * i / (n - 1)));
    }
}


static float band_energy(const float *ps, int bins, float sample_rate,
                          float f_low, float f_high)
{
    int bin_start = (int)(f_low * bins * 2.0f / sample_rate);
    int bin_end   = (int)(f_high * bins * 2.0f / sample_rate);
    if (bin_start < 0) bin_start = 0;
    if (bin_end > bins) bin_end = bins;
    if (bin_start >= bin_end) return 0.0f;

    float energy = 0.0f;
    for (int i = bin_start; i < bin_end; i++) {
        energy += ps[i];
    }
    return energy;
}

static float spectral_centroid(const float *ps, int bins, float sample_rate)
{
    float sum_fx = 0.0f, sum_x = 0.0f;
    for (int i = 0; i < bins; i++) {
        float f = i * sample_rate / (bins * 2.0f);
        sum_fx += f * ps[i];
        sum_x += ps[i];
    }
    if (sum_x < 1e-10f) return 0.0f;
    return sum_fx / sum_x;
}

static float spectral_flatness(const float *ps, int n)
{
    double log_sum = 0.0;
    double lin_sum = 0.0;
    int count = 0;
    for (int i = 0; i < n; i++) {
        if (ps[i] > 1e-10f) {
            log_sum += log(ps[i]);
            lin_sum += ps[i];
            count++;
        }
    }
    if (count == 0 || lin_sum < 1e-10) return 0.0f;
    float geometric_mean = expf(log_sum / count);
    float arithmetic_mean = lin_sum / count;
    if (arithmetic_mean < 1e-10f) return 0.0f;
    return geometric_mean / arithmetic_mean;
}

static float dominant_freq(const float *ps, int bins, float sample_rate, float *magnitude)
{
    float max_val = 0.0f;
    int max_bin = 0;
    for (int i = 0; i < bins; i++) {
        if (ps[i] > max_val) {
            max_val = ps[i];
            max_bin = i;
        }
    }
    if (magnitude) *magnitude = max_val;
    return max_bin * sample_rate / (bins * 2.0f);
}

static float zero_crossing_rate(const int16_t *samples, int n)
{
    int crosses = 0;
    for (int i = 1; i < n; i++) {
        if ((samples[i] >= 0) != (samples[i-1] >= 0)) crosses++;
    }
    return (float)crosses / n;
}

static int extract_features(const max9814_frame_t *frame, bee_audio_features_t *f)
{
    RT_ASSERT(frame != RT_NULL);
    RT_ASSERT(f != RT_NULL);

    int n = BEE_FFT_SIZE;

    for (int i = 0; i < n; i++) {
        float win_val = g_ctx.window[i];
        float s = (float)frame->samples[i] / 32768.0f;
        g_ctx.fft_buf[i].re = s * win_val;
        g_ctx.fft_buf[i].im = 0.0f;
    }

    fft_rad2(g_ctx.fft_buf, n);

    int half_n = n / 2;
    for (int i = 0; i < half_n; i++) {
        float re = g_ctx.fft_buf[i].re;
        float im = g_ctx.fft_buf[i].im;
        g_ctx.power_spectrum[i] = (re * re + im * im) / (n * n);
    }

    float sr = BEE_SAMPLE_RATE;
    f->low_band_energy   = band_energy(g_ctx.power_spectrum, half_n, sr,
                                        BEE_BAND_LOW_MIN, BEE_BAND_LOW_MAX);
    f->mid_band_energy   = band_energy(g_ctx.power_spectrum, half_n, sr,
                                        BEE_BAND_MID_MIN, BEE_BAND_MID_MAX);
    f->high_band_energy  = band_energy(g_ctx.power_spectrum, half_n, sr,
                                        BEE_BAND_HIGH_MIN, BEE_BAND_HIGH_MAX);
    f->vhigh_band_energy = band_energy(g_ctx.power_spectrum, half_n, sr,
                                        BEE_BAND_VHIGH_MIN, BEE_BAND_VHIGH_MAX);
    f->total_energy = f->low_band_energy + f->mid_band_energy +
                      f->high_band_energy + f->vhigh_band_energy;

    f->spectral_centroid  = spectral_centroid(g_ctx.power_spectrum, half_n, sr);
    f->spectral_flatness  = spectral_flatness(g_ctx.power_spectrum, half_n);
    f->dominant_freq      = dominant_freq(g_ctx.power_spectrum, half_n, sr,
                                           &f->dominant_magnitude);
    f->rms                = frame->rms;
    f->zero_cross_rate    = zero_crossing_rate(frame->samples,
                                                frame->sample_count);

    return RT_EOK;
}


static void classify_bee_state(const bee_audio_features_t *f,
                                bee_audio_result_t *r)
{
    r->confidence = 0.0f;
    r->state = BEE_SOUND_NORMAL;

    if (f->total_energy < 1e-10f) {
        r->state = BEE_SOUND_NORMAL;
        r->confidence = 0.6f;
        return;
    }

    float low_ratio  = f->low_band_energy / f->total_energy;
    float mid_ratio  = f->mid_band_energy / f->total_energy;
    float high_ratio = f->high_band_energy / f->total_energy;
    float mid_low_ratio = (f->low_band_energy > 1e-8f) ?
                          f->mid_band_energy / f->low_band_energy : 0.0f;
    float high_low_ratio = (f->low_band_energy > 1e-8f) ?
                           f->high_band_energy / f->low_band_energy : 0.0f;

    if (high_low_ratio > HORNET_HIGH_RATIO && high_ratio > 0.30f) {
        r->state = BEE_SOUND_HORNET_INVADE;
        r->confidence = 0.65f + (high_ratio - 0.30f) * 0.5f;
        if (r->confidence > 0.95f) r->confidence = 0.95f;
        return;
    }

    if (mid_low_ratio > SWARM_ENERGY_RATIO &&
        f->spectral_centroid > 280.0f &&
        f->total_energy > 0.001f) {
        r->state = BEE_SOUND_SWARM_PRELUDE;
        r->confidence = 0.6f + (mid_low_ratio - SWARM_ENERGY_RATIO) * 0.2f;
        if (r->confidence > 0.9f) r->confidence = 0.9f;
        return;
    }

    if (f->spectral_flatness > QUEEN_FLATNESS_THRESH && low_ratio < 0.35f) {
        r->state = BEE_SOUND_QUEEN_MISSING;
        r->confidence = 0.5f + (f->spectral_flatness - QUEEN_FLATNESS_THRESH) * 1.5f;
        if (r->confidence > 0.85f) r->confidence = 0.85f;
        return;
    }

    if (f->zero_cross_rate > 0.25f && low_ratio < 0.40f) {
        r->state = BEE_SOUND_ABNORMAL;
        r->confidence = 0.5f + (f->zero_cross_rate - 0.25f) * 2.0f;
        if (r->confidence > 0.9f) r->confidence = 0.9f;
        return;
    }

    if (low_ratio > 0.40f && f->spectral_flatness < 0.40f) {
        r->state = BEE_SOUND_NORMAL;
        r->confidence = 0.7f + low_ratio * 0.3f;
        if (r->confidence > 0.98f) r->confidence = 0.98f;
        return;
    }

    r->state = BEE_SOUND_NORMAL;
    r->confidence = 0.50f;
}

static bee_sound_state_t smooth_state(bee_sound_state_t new_state)
{
    g_ctx.smooth_states[g_ctx.smooth_idx] = new_state;
    g_ctx.smooth_idx = (g_ctx.smooth_idx + 1) % SMOOTH_FRAMES;

    bee_sound_state_t first = g_ctx.smooth_states[0];
    for (int i = 1; i < SMOOTH_FRAMES; i++) {
        if (g_ctx.smooth_states[i] != first) {
            return BEE_SOUND_NORMAL; 
        }
    }
    return first; 
}


static void bee_audio_thread_entry(void *param)
{
    max9814_frame_t frame;
    uint32_t last_log = 0;

    LOG_I("Bee audio analysis thread started");

    while (g_ctx.running) {
        int ret = max9814_read_frame(&frame, 2000);
        if (ret != RT_EOK) {
            LOG_W("Frame read timeout or error: %d", ret);
            continue;
        }

        bee_audio_features_t features;
        extract_features(&frame, &features);
        g_ctx.features = features;

        bee_audio_result_t raw_result;
        raw_result.timestamp = frame.timestamp;
        classify_bee_state(&features, &raw_result);

        raw_result.state = smooth_state(raw_result.state);

        raw_result.state_name = bee_sound_state_names[raw_result.state];
        raw_result.features = features;
        g_ctx.result = raw_result;

        if (raw_result.state != BEE_SOUND_NORMAL &&
            raw_result.confidence > MIN_CONFIDENCE) {
            rt_kprintf("\n[BEE ALERT] State: %s (conf=%.2f), domFreq=%.0fHz\n",
                       raw_result.state_name, raw_result.confidence,
                       features.dominant_freq);
        }
    }

    LOG_I("Bee audio analysis thread stopped");
}


int bee_audio_analysis_init(void)
{
    if (g_ctx.thread_stack[0] != 0) {
        LOG_W("Already initialized");
        return RT_EOK;
    }

    g_ctx.result.state = BEE_SOUND_NORMAL;
    g_ctx.result.confidence = 0.0f;
    g_ctx.result.state_name = bee_sound_state_names[BEE_SOUND_NORMAL];
    g_ctx.result.timestamp = 0;

    fft_gen_rev_table((uint16_t *)fft_rev10, BEE_FFT_SIZE);

    hanning_window(g_ctx.window, BEE_FFT_SIZE);

    for (int i = 0; i < SMOOTH_FRAMES; i++) {
        g_ctx.smooth_states[i] = BEE_SOUND_NORMAL;
    }
    g_ctx.smooth_idx = 0;

    LOG_I("Bee audio analysis initialized, FFT=%d point, sample_rate=%dHz",
          BEE_FFT_SIZE, BEE_SAMPLE_RATE);
    return RT_EOK;
}

int bee_audio_analysis_start(void)
{
    if (g_ctx.running) {
        LOG_W("Already running");
        return RT_EOK;
    }

    g_ctx.running = 1;

    rt_err_t ret = rt_thread_init(&g_ctx.thread,
                                   "bee_audio",
                                   bee_audio_thread_entry,
                                   RT_NULL,
                                   g_ctx.thread_stack,
                                   sizeof(g_ctx.thread_stack),
                                   4,  
                                   10);
    if (ret != RT_EOK) {
        LOG_E("Thread init failed: %d", ret);
        g_ctx.running = 0;
        return -RT_ERROR;
    }

    rt_thread_startup(&g_ctx.thread);
    LOG_I("Bee audio analysis started");
    return RT_EOK;
}

int bee_audio_analysis_stop(void)
{
    if (!g_ctx.running) return RT_EOK;

    g_ctx.running = 0;
    rt_thread_delay(2);
    rt_thread_detach(&g_ctx.thread);

    LOG_I("Bee audio analysis stopped");
    return RT_EOK;
}

int bee_audio_get_result(bee_audio_result_t *result, rt_int32_t timeout_ms)
{
    RT_ASSERT(result != RT_NULL);

    rt_memcpy(result, &g_ctx.result, sizeof(bee_audio_result_t));
    return RT_EOK;
}

void bee_audio_features_print(const bee_audio_features_t *f)
{
    rt_kprintf("Audio Features:\n");
    rt_kprintf("  Low band (150-280Hz):   %.6f\n", f->low_band_energy);
    rt_kprintf("  Mid band (300-500Hz):   %.6f\n", f->mid_band_energy);
    rt_kprintf("  High band (600-1500Hz): %.6f\n", f->high_band_energy);
    rt_kprintf("  VHigh band (1500-3500): %.6f\n", f->vhigh_band_energy);
    rt_kprintf("  Total energy:           %.6f\n", f->total_energy);
    rt_kprintf("  Spectral centroid:      %.1f Hz\n", f->spectral_centroid);
    rt_kprintf("  Spectral flatness:      %.4f\n", f->spectral_flatness);
    rt_kprintf("  Dominant freq:          %.1f Hz (mag=%.4f)\n",
               f->dominant_freq, f->dominant_magnitude);
    rt_kprintf("  RMS:                    %.1f\n", f->rms);
    rt_kprintf("  Zero-cross rate:        %.4f\n", f->zero_cross_rate);
}

const char* bee_audio_state_name(bee_sound_state_t state)
{
    if (state >= BEE_SOUND_NORMAL && state <= BEE_SOUND_ABNORMAL) {
        return bee_sound_state_names[state];
    }
    return "Unknown";
}
