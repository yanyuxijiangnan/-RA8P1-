#include "camera_app.h"

#include <rtdevice.h>
#include <rthw.h>
#include <string.h>

#ifdef BSP_USING_MIPI_CSI_CAMERA
#include "hal_data.h"

#define CAMERA_ACTIVE_IMAGE_WIDTH   640
#define CAMERA_ACTIVE_IMAGE_HEIGHT  480
#define CAMERA_IMAGE_BYTE_PER_PIXEL 2
#define CAMERA_CAPTURE_IMAGE_WIDTH  CAMERA_ACTIVE_IMAGE_WIDTH
#define CAMERA_CAPTURE_IMAGE_HEIGHT CAMERA_ACTIVE_IMAGE_HEIGHT

fsp_err_t camera_init(bool use_test_mode);
void camera_user_callback_set(void (*p_callback)(void *));
void camera_image_buffer_initialize(void);
void camera_capture_start(void);
uint32_t camera_data_ready_buffer_pointer_get(void);
void camera_capture_post_process(void);
#endif

#ifdef RT_USING_FINSH
#include <finsh.h>
#endif

#define CAM_SYNC_0          0xAA
#define CAM_SYNC_1          0x55
#define CAM_SYNC_2          0xAA
#define CAM_SYNC_3          0x55
#define CAM_HEADER_SIZE     13  
#define CAM_FOOTER_SIZE     1   

#define CAM_UART_CHUNK_SIZE 128

#define CAM_CAPTURE_TIMEOUT 3000

static rt_device_t  g_uart_dev = RT_NULL;
static rt_bool_t    g_camera_inited = RT_FALSE;
static rt_bool_t    g_uart_ready = RT_FALSE;

#ifdef BSP_USING_MIPI_CSI_CAMERA
static rt_bool_t    g_capture_done = RT_FALSE;

static void cam_app_vin_callback(void *arg)
{
    (void)arg;
#ifndef VIN_CFG_USE_RUNTIME_BUFFER
    camera_capture_post_process();
#endif
    g_capture_done = RT_TRUE;
}
#endif


static rt_err_t cam_uart_write_all(const uint8_t *data, uint32_t len)
{
    uint32_t remaining = len;
    uint32_t offset = 0;

    while (remaining > 0)
    {
        uint32_t chunk = (remaining > CAM_UART_CHUNK_SIZE) ? CAM_UART_CHUNK_SIZE : remaining;
        rt_size_t written = rt_device_write(g_uart_dev, 0, data + offset, chunk);
        if (written == 0)
        {
            for (volatile int _i = 0; _i < 500000; _i++);
            continue;
        }
        if (written > chunk)
        {
            return -RT_ERROR;
        }
        remaining -= written;
        offset += written;
    }
    return RT_EOK;
}


static rt_err_t cam_send_frame(const uint8_t *img_data,
                               uint16_t width, uint16_t height,
                               uint8_t format)
{
    uint8_t  header[CAM_HEADER_SIZE];
    uint8_t  checksum;
    uint32_t data_size;
    uint32_t i;

    rt_uint16_t saved_open_flag;

    if (!g_uart_ready)
        return -RT_ERROR;

    saved_open_flag = g_uart_dev->open_flag;
    g_uart_dev->open_flag &= ~RT_DEVICE_FLAG_STREAM;

    data_size = (uint32_t)width * height * 2;

    header[0] = CAM_SYNC_0;
    header[1] = CAM_SYNC_1;
    header[2] = CAM_SYNC_2;
    header[3] = CAM_SYNC_3;
    header[4] = (uint8_t)(width >> 8);
    header[5] = (uint8_t)(width & 0xFF);
    header[6] = (uint8_t)(height >> 8);
    header[7] = (uint8_t)(height & 0xFF);
    header[8] = format;
    header[9] = (uint8_t)(data_size >> 24);
    header[10] = (uint8_t)((data_size >> 16) & 0xFF);
    header[11] = (uint8_t)((data_size >> 8) & 0xFF);
    header[12] = (uint8_t)(data_size & 0xFF);

    checksum = 0;
    for (i = 0; i < data_size; i++)
        checksum ^= img_data[i];

    if (cam_uart_write_all(header, CAM_HEADER_SIZE) != RT_EOK)
    {
        g_uart_dev->open_flag = saved_open_flag;
        return -RT_ERROR;
    }
    if (cam_uart_write_all(img_data, data_size) != RT_EOK)
    {
        g_uart_dev->open_flag = saved_open_flag;
        return -RT_ERROR;
    }
    if (cam_uart_write_all(&checksum, 1) != RT_EOK)
    {
        g_uart_dev->open_flag = saved_open_flag;
        return -RT_ERROR;
    }

    g_uart_dev->open_flag = saved_open_flag;
    return RT_EOK;
}


static void cam_downsample(const uint8_t *src, int src_w, int src_h,
                           uint8_t *dst, int dst_w, int dst_h)
{
    int x, y;
    int x_ratio = (src_w << 8) / dst_w;
    int y_ratio = (src_h << 8) / dst_h;

    for (y = 0; y < dst_h; y++)
    {
        int src_y = (y * y_ratio) >> 8;
        const uint16_t *src_line = (const uint16_t *)(src + src_y * src_w * 2);
        uint16_t *dst_line = (uint16_t *)(dst + y * dst_w * 2);

        for (x = 0; x < dst_w; x++)
        {
            int src_x = (x * x_ratio) >> 8;
            dst_line[x] = src_line[src_x];
        }
    }
}


rt_err_t camera_app_init(void)
{
    if (g_camera_inited)
        return RT_EOK;

    g_uart_dev = rt_device_find(CAM_UART_NAME);
    if (g_uart_dev == RT_NULL)
    {
        rt_kprintf("[cam_app] uart %s not found\n", CAM_UART_NAME);
        return -RT_ERROR;
    }
    g_uart_ready = RT_TRUE;

#ifdef BSP_USING_MIPI_CSI_CAMERA
    {
        fsp_err_t fsp_ret;
        const char *hello = "CAM:HELLO\n";
        rt_device_write(g_uart_dev, 0, hello, rt_strlen(hello));

        fsp_ret = camera_init(RT_FALSE);
        if (fsp_ret != FSP_SUCCESS)
        {
            const char *msg = "CAM:ERR camera_init\n";
            rt_device_write(g_uart_dev, 0, msg, rt_strlen(msg));
            rt_kprintf("[cam_app] camera_init failed: %d\n", (int)fsp_ret);
            return -RT_ERROR;
        }

        camera_user_callback_set(cam_app_vin_callback);
        camera_image_buffer_initialize();

        g_camera_inited = RT_TRUE;
        {
            const char *msg = "CAM:READY\n";
            rt_device_write(g_uart_dev, 0, msg, rt_strlen(msg));
        }

        rt_kprintf("[cam_app] init ok, camera=%dx%d, uart=%s\n",
                   CAMERA_ACTIVE_IMAGE_WIDTH, CAMERA_ACTIVE_IMAGE_HEIGHT,
                   CAM_UART_NAME);
        return RT_EOK;
    }
#else
    {
        const char *msg = "CAM:ERR CONFIG_BSP_USING_MIPI_CSI_CAMERA not enabled\n";
        rt_device_write(g_uart_dev, 0, msg, rt_strlen(msg));
        rt_kprintf("[cam_app] BSP_USING_MIPI_CSI_CAMERA not enabled\n");
        return -RT_ERROR;
    }
#endif
}

rt_err_t camera_app_capture_and_send(void)
{
#ifdef BSP_USING_MIPI_CSI_CAMERA
    uint8_t *raw_buf;
    int raw_w, raw_h;
    int timeout;
    rt_err_t ret;

    static uint8_t qvga_buf[CAM_IMAGE_BUF_SIZE];

    if (!g_uart_ready)
    {
        g_uart_dev = rt_device_find(CAM_UART_NAME);
        if (g_uart_dev == RT_NULL)
        {
            rt_kprintf("[cam_app] uart %s not found\n", CAM_UART_NAME);
            return -RT_ERROR;
        }
        g_uart_ready = RT_TRUE;
    }

    if (!g_camera_inited)
    {
        rt_kprintf("[cam_app] camera not initialized\n");
        return -RT_ERROR;
    }

    g_capture_done = RT_FALSE;
    camera_capture_start();

    timeout = CAM_CAPTURE_TIMEOUT / 10;
    while (!g_capture_done && timeout > 0)
    {
        rt_thread_mdelay(10);
        timeout--;
    }

    if (!g_capture_done)
    {
        rt_kprintf("[cam_app] capture timeout\n");
        return -RT_ETIMEOUT;
    }

    raw_buf = (uint8_t *)camera_data_ready_buffer_pointer_get();
    raw_w = CAMERA_ACTIVE_IMAGE_WIDTH;
    raw_h = CAMERA_ACTIVE_IMAGE_HEIGHT;

    cam_downsample(raw_buf, raw_w, raw_h, qvga_buf, CAM_IMAGE_WIDTH, CAM_IMAGE_HEIGHT);

    ret = cam_send_frame(qvga_buf, CAM_IMAGE_WIDTH, CAM_IMAGE_HEIGHT,
                         CAM_IMAGE_FORMAT_RGB565);

    if (ret == RT_EOK)
    {
        rt_kprintf("[cam_app] frame sent: %dx%d, %d bytes\n",
                   CAM_IMAGE_WIDTH, CAM_IMAGE_HEIGHT,
                   (int)CAM_IMAGE_BUF_SIZE);
    }
    else
    {
        rt_kprintf("[cam_app] send failed: %d\n", (int)ret);
    }

    return ret;
#else
    rt_kprintf("[cam_app] camera support not compiled in\n");
    return -RT_ERROR;
#endif
}


#define CAM_AUTO_INTERVAL_MS   30000

static rt_thread_t g_auto_thread = RT_NULL;
static rt_bool_t   g_auto_running = RT_FALSE;

static void cam_auto_thread_entry(void *param)
{
    (void)param;

    rt_kprintf("[cam_app] auto capture started, interval=%dms\n", CAM_AUTO_INTERVAL_MS);

    camera_app_capture_and_send();

    while (g_auto_running)
    {
        rt_err_t ret = camera_app_capture_and_send();
        if (ret != RT_EOK)
        {
            rt_kprintf("[cam_app] capture failed: %d\n", (int)ret);
        }

        rt_tick_t elapsed = 0;
        rt_tick_t total = rt_tick_from_millisecond(CAM_AUTO_INTERVAL_MS);
        while (elapsed < total && g_auto_running)
        {
            rt_thread_mdelay(100);
            elapsed += rt_tick_from_millisecond(100);
        }
    }

    rt_kprintf("[cam_app] auto capture stopped\n");
}

rt_err_t camera_app_auto_start(void)
{
    rt_err_t ret;

    ret = camera_app_init();
    if (ret != RT_EOK)
    {
        rt_kprintf("[cam_app] init failed, err=%d\n", (int)ret);
        return ret;
    }

    if (g_auto_running)
        return RT_EOK;

    g_auto_running = RT_TRUE;
    g_auto_thread = rt_thread_create("camauto",
                                      cam_auto_thread_entry,
                                      RT_NULL,
                                      2048,
                                      20,
                                      20);
    if (g_auto_thread == RT_NULL)
    {
        g_auto_running = RT_FALSE;
        return -RT_ENOMEM;
    }

    rt_thread_startup(g_auto_thread);
    return RT_EOK;
}


#if defined(RT_USING_FINSH) && defined(BSP_USING_MIPI_CSI_CAMERA)

static void cam_cap(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    if (camera_app_capture_and_send() == RT_EOK)
    {
        rt_kprintf("[cam_cap] done\n");
    }
    else
    {
        rt_kprintf("[cam_cap] failed\n");
    }
}
MSH_CMD_EXPORT(cam_cap, Capture one photo and send via UART to PC);

static rt_thread_t g_cam_loop_thread = RT_NULL;
static rt_bool_t   g_cam_loop_running = RT_FALSE;

static void cam_cap_loop_entry(void *param)
{
    uint32_t interval_s = (uint32_t)(rt_ubase_t)param;

    rt_kprintf("[cam_loop] started, interval=%lus\n", interval_s);

    while (g_cam_loop_running)
    {
        rt_err_t ret = camera_app_capture_and_send();
        if (ret != RT_EOK)
        {
            rt_kprintf("[cam_loop] capture failed: %d\n", (int)ret);
        }

        uint32_t ticks = interval_s * RT_TICK_PER_SECOND;
        uint32_t elapsed = 0;
        while (elapsed < ticks && g_cam_loop_running)
        {
            rt_thread_mdelay(100);
            elapsed += 100;
        }
    }

    rt_kprintf("[cam_loop] stopped\n");
}

static void cam_cap_loop(int argc, char **argv)
{
    uint32_t interval_s = 10; 

    if (argc >= 2)
    {
        interval_s = (uint32_t)atol(argv[1]);
        if (interval_s < 1)
            interval_s = 1;
        if (interval_s > 3600)
            interval_s = 3600;
    }

    if (g_cam_loop_running)
    {
        g_cam_loop_running = RT_FALSE;
        if (g_cam_loop_thread)
        {
            rt_thread_delete(g_cam_loop_thread);
            g_cam_loop_thread = RT_NULL;
        }
        rt_thread_mdelay(100);
    }

    g_cam_loop_running = RT_TRUE;
    g_cam_loop_thread = rt_thread_create("camloop",
                                          cam_cap_loop_entry,
                                          (void *)(rt_ubase_t)interval_s,
                                          2048,
                                          19,
                                          20);
    if (g_cam_loop_thread)
    {
        rt_thread_startup(g_cam_loop_thread);
    }
    else
    {
        g_cam_loop_running = RT_FALSE;
        rt_kprintf("[cam_loop] thread create failed\n");
    }
}
MSH_CMD_EXPORT(cam_cap_loop, Start periodic capture with optional interval_sec);

static void cam_cap_stop(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    if (!g_cam_loop_running)
    {
        rt_kprintf("[cam_stop] no loop running\n");
        return;
    }

    g_cam_loop_running = RT_FALSE;
    if (g_cam_loop_thread)
    {
        rt_thread_delete(g_cam_loop_thread);
        g_cam_loop_thread = RT_NULL;
    }
    rt_kprintf("[cam_stop] loop stopped\n");
}
MSH_CMD_EXPORT(cam_cap_stop, Stop periodic capture loop.);

#endif 
