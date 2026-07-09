#!/usr/bin/env python3

"""
LoRa Receiver -> OneNET Gateway

功能：
1. 串口接收LoRa数据
2. CRC校验
3. MQTT连接OneNET
4. 属性上报
5. 回复Topic监听
6. 自动保活
"""

import json
import struct
import time
import base64
import hmac
from hashlib import sha1
from urllib.parse import quote

import serial
import paho.mqtt.client as mqtt



PRODUCT_ID = "6R93N8mVU1"
DEVICE_NAME = "lora_sensor_01"
DEVICE_KEY = "Q0ZRMWNqZjlkNGtaVm1SNjJCSWxHVlhleXJacTAwaFk="

BROKER = "mqtts.heclouds.com"
PORT = 1883

UPLOAD_TOPIC = (
    f"$sys/{PRODUCT_ID}/{DEVICE_NAME}/thing/property/post"
)

REPLY_TOPIC = (
    f"$sys/{PRODUCT_ID}/{DEVICE_NAME}/thing/property/post/reply"
)


SERIAL_PORT = "COM14"
SERIAL_BAUD = 9600


SENSOR_SYNC = 0xAA
SENSOR_LEN = 32
FRAME_LEN = 34

VISION_SYNC = 0xBB
VISION_LEN = 8
VISION_FRAME_LEN = 12

AUDIO_STATE_MAP = {
    0: "Normal",
    1: "SwarmPrelude",
    2: "QueenMissing",
    3: "HornetInvade",
    4: "Abnormal",
}

FLAG_SHT31  = 0x01
FLAG_SGP40  = 0x02
FLAG_BH1750 = 0x04
FLAG_BMI088 = 0x08
FLAG_AUDIO  = 0x10


client = None
connected = False

last_sensor_seq = -1
last_vision_seq = -1

TEMP_HIGH = 35.0
TEMP_LOW = 10.0

HUMI_HIGH = 60.0
HUMI_LOW = 30.0

CO2_LIMIT = 30000

HIVE_STATE_MAP = {
    0: "Normal",
    1: "HighActivity",
    2: "Swarming",
    3: "LowActivity",
    4: "Disturbed",
    0xFF: "Init",
}


def crc8(data):

    crc = 0xFF

    for b in data:
        crc ^= b

        for _ in range(8):

            if crc & 0x80:
                crc = ((crc << 1) ^ 0x31) & 0xFF
            else:
                crc = (crc << 1) & 0xFF

    return crc



def generate_token():

    version = "2018-10-31"

    res = f"products/{PRODUCT_ID}/devices/{DEVICE_NAME}"

    et = str(int(time.time()) + 86400)

    method = "sha1"

    sign_content = (
        f"{et}\n"
        f"{method}\n"
        f"{res}\n"
        f"{version}"
    )

    key = base64.b64decode(DEVICE_KEY)

    sign = hmac.new(
        key,
        sign_content.encode(),
        sha1
    ).digest()

    sign = base64.b64encode(sign).decode()

    token = (
        f"version={version}"
        f"&res={quote(res)}"
        f"&et={et}"
        f"&method={method}"
        f"&sign={quote(sign)}"
    )

    return token



def on_connect(client_obj, userdata, flags, reason_code, properties):

    global connected

    if reason_code == 0:

        connected = True

        print("\n✅ OneNET连接成功")

        client_obj.subscribe(
            REPLY_TOPIC,
            qos=1
        )

        print("✅ 已订阅Reply Topic")
        print(REPLY_TOPIC)

    else:

        print(f"❌ MQTT连接失败 rc={reason_code}")


def on_disconnect(client_obj, userdata, flags, reason_code, properties):

    global connected

    connected = False

    print("❌ MQTT已断开")


def on_message(client_obj, userdata, msg):

    print()
    print("========== OneNET回复 ==========")

    try:
        print(msg.payload.decode())
    except Exception:
        print(msg.payload)

    print("================================")



def mqtt_connect():

    global client

    token = generate_token()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=DEVICE_NAME
    )

    client.username_pw_set(
        PRODUCT_ID,
        token
    )

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    client.connect(
        BROKER,
        PORT,
        keepalive=60
    )

    client.loop_start()

    for _ in range(20):

        if connected:
            return True

        time.sleep(0.5)

    return False



def upload_data(data):

    global client

    if not connected:

        print("⚠️ MQTT未连接")
        return False

    payload = {
        "id": str(int(time.time())),
        "version": "1.0",
        "params": {
            "Temperature": {
                "value": data["Temperature"]
            },
            "Humidity": {
                "value": data["Humidity"]
            },
            "VOC": {
                "value": data["VOC"]
            },
            "Lux": {
                "value": data["Lux"]
            },
            "MotionStable": {
                "value": data["MotionStable"]
            },
            "TempAlarm": {
                "value": data["TempAlarm"]
            },
            "HumiAlarm": {
                "value": data["HumiAlarm"]
            },
            "CO2Alarm": {
                "value": data["CO2Alarm"]
            },
            "AudioState": {
                "value": data["AudioState"]
            },
            "AudioConfidence": {
                "value": data["AudioConfidence"]
            },
            "AudioAlarm": {
                "value": data["AudioAlarm"]
            }
        }
    }

    msg = json.dumps(payload)

    print()
    print("========== MQTT上传 ==========")
    print(msg)
    print("==============================")

    result = client.publish(
        UPLOAD_TOPIC,
        msg,
        qos=1
    )

    return result.rc == mqtt.MQTT_ERR_SUCCESS


def upload_vision_data(data):

    global client

    if not connected:

        print("⚠️ MQTT未连接")
        return False

    payload = {
        "id": str(int(time.time())),
        "version": "1.0",
        "params": {
            "HiveState": {
                "value": data["HiveState"]
            },
            "BeeCount": {
                "value": data["BeeCount"]
            },
            "ActivityPct": {
                "value": data["ActivityPct"]
            },
            "MotionPct": {
                "value": data["MotionPct"]
            },
            "AvgBeeSizePx": {
                "value": data["AvgBeeSizePx"]
            },
            "BeeColorPct": {
                "value": data["BeeColorPct"]
            },
        }
    }

    msg = json.dumps(payload)

    print()
    print("========== MQTT视觉上传 ==========")
    print(msg)
    print("==================================")

    result = client.publish(
        UPLOAD_TOPIC,
        msg,
        qos=1
    )

    return result.rc == mqtt.MQTT_ERR_SUCCESS



def decode_sensor_frame(frame):

    global last_sensor_seq

    if len(frame) != FRAME_LEN:
        return None

    if frame[0] != SENSOR_SYNC:
        return None

    if frame[1] != SENSOR_LEN:
        return None

    if crc8(frame[:-1]) != frame[-1]:
        return None

    seq = frame[30]

    if seq == last_sensor_seq:
        return None

    last_sensor_seq = seq

    flags = frame[4]
    temp = struct.unpack_from(">h", frame, 5)[0] / 100.0
    humi = struct.unpack_from(">H", frame, 7)[0] / 100.0
    voc  = struct.unpack_from(">H", frame, 9)[0]
    lux  = struct.unpack_from(">H", frame, 11)[0]
    motion_stable = (frame[29] >> 4) & 0x01

    audio_state = frame[31]
    audio_confidence = frame[32]
    audio_name = AUDIO_STATE_MAP.get(audio_state, "Unknown")
    audio_valid = bool(flags & FLAG_AUDIO)


    if temp < TEMP_LOW:
        temp_abnormal = 1
    elif temp > TEMP_HIGH:
        temp_abnormal = 2
    else:
        temp_abnormal = 0

    if humi < HUMI_LOW:
        humi_abnormal = 1
    elif humi > HUMI_HIGH:
        humi_abnormal = 2
    else:
        humi_abnormal = 0

    co2_abnormal = voc < CO2_LIMIT

    audio_alarm = 0
    if audio_valid and audio_state != 0 and audio_confidence > 55:
        audio_alarm = audio_state

    return {
        "Temperature": round(temp, 1),
        "Humidity": round(humi, 1),
        "VOC": int(voc),
        "Lux": int(lux),
        "MotionStable": int(motion_stable),
        "TempAlarm": int(temp_abnormal),
        "HumiAlarm": int(humi_abnormal),
        "CO2Alarm": int(co2_abnormal),
        "AudioState": audio_name,
        "AudioConfidence": int(audio_confidence),
        "AudioAlarm": int(audio_alarm),
    }



def decode_vision_frame(frame):

    global last_vision_seq

    if len(frame) != VISION_FRAME_LEN:
        return None

    if frame[0] != VISION_SYNC:
        return None

    if frame[1] != VISION_LEN:
        return None

    if crc8(frame[:-1]) != frame[-1]:
        return None

    seq = frame[10]

    if seq == last_vision_seq:
        return None

    last_vision_seq = seq

    hive_state = frame[4]
    bee_count = frame[5]
    activity_pct = frame[6]
    motion_pct = frame[7]
    avg_bee_size = frame[8] * 10
    bee_color_pct = frame[9]

    hive_name = HIVE_STATE_MAP.get(hive_state, "Unknown")

    return {
        "HiveState": hive_name,
        "HiveStateCode": int(hive_state),
        "BeeCount": int(bee_count),
        "ActivityPct": int(activity_pct),
        "MotionPct": int(motion_pct),
        "AvgBeeSizePx": int(avg_bee_size),
        "BeeColorPct": int(bee_color_pct),
    }



def run():

    print(f"🔌 打开串口 {SERIAL_PORT}")

    try:

        ser = serial.Serial(
            SERIAL_PORT,
            SERIAL_BAUD,
            timeout=0.5
        )

    except Exception as e:

        print("❌ 串口打开失败")
        print(e)
        return

    print("🔗 正在连接OneNET...")

    if not mqtt_connect():

        print("❌ OneNET连接失败")
        return

    print("✅ 网关启动成功")
    print("⏳ 等待LoRa数据...\n")

    while True:

        try:

            if ser.in_waiting >= 2:

                header = ser.read(2)

                sync = header[0]
                dlen = header[1]

                if (
                    sync == SENSOR_SYNC
                    and dlen == SENSOR_LEN
                ):

                    payload = ser.read(SENSOR_LEN)

                    if len(payload) == SENSOR_LEN:

                        frame = header + payload

                        data = decode_sensor_frame(frame)
                        if data:
                            print(f"📥 传感器: {data}")
                            upload_data(data)

                elif (
                    sync == VISION_SYNC
                    and dlen == VISION_LEN
                ):

                    payload = ser.read(VISION_LEN)

                    if len(payload) == VISION_LEN:

                        frame = header + payload

                        data = decode_vision_frame(frame)
                        if data:
                            print(f"📸 视觉: {data}")
                            upload_vision_data(data)

            time.sleep(0.05)

        except KeyboardInterrupt:

            print("\n退出")
            break

        except Exception as e:

            print("异常:")
            print(e)


if __name__ == "__main__":
    run()