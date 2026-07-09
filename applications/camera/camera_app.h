#ifndef APPLICATIONS_CAMERA_CAMERA_APP_H_
#define APPLICATIONS_CAMERA_CAMERA_APP_H_

#include <rtthread.h>
#include <stdint.h>

#define CAM_IMAGE_WIDTH        320
#define CAM_IMAGE_HEIGHT       240
#define CAM_IMAGE_FORMAT_RGB565  0
#define CAM_IMAGE_BUF_SIZE     (CAM_IMAGE_WIDTH * CAM_IMAGE_HEIGHT * 2)

#define CAM_UART_NAME           "uart8"

rt_err_t camera_app_init(void);
rt_err_t camera_app_capture_and_send(void);
rt_err_t camera_app_auto_start(void);

#endif 
