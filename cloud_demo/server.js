const http = require("http");
const { URL } = require("url");

const PORT = Number(process.env.PORT || 8080);
const HISTORY_LIMIT = 60;

function nowIso() {
  return new Date().toISOString();
}

function numberOrZero(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
}

function boolOrFalse(value) {
  return value === true || value === 1 || value === "1";
}

function computeTilt(sample) {
  const ax = numberOrZero(sample.accel_milli_ms2_x);
  const ay = numberOrZero(sample.accel_milli_ms2_y);
  const az = numberOrZero(sample.accel_milli_ms2_z);
  const roll = Math.atan2(ay, az) * 180 / Math.PI;
  const pitch = Math.atan2(-ax, Math.sqrt(ay * ay + az * az)) * 180 / Math.PI;

  return {
    roll_deg: Number(roll.toFixed(2)),
    pitch_deg: Number(pitch.toFixed(2)),
  };
}

function normalizePayload(payload) {
  const sample = {
    device_id: payload.device_id || "unknown-device",
    last_update_tick: numberOrZero(payload.last_update_tick),
    temperature_centi_c: numberOrZero(payload.temperature_centi_c),
    humidity_centi_rh: numberOrZero(payload.humidity_centi_rh),
    voc_raw: numberOrZero(payload.voc_raw),
    light_lux: numberOrZero(payload.light_lux),
    accel_milli_ms2_x: numberOrZero(payload.accel_milli_ms2_x),
    accel_milli_ms2_y: numberOrZero(payload.accel_milli_ms2_y),
    accel_milli_ms2_z: numberOrZero(payload.accel_milli_ms2_z),
    gyro_milli_dps_x: numberOrZero(payload.gyro_milli_dps_x),
    gyro_milli_dps_y: numberOrZero(payload.gyro_milli_dps_y),
    gyro_milli_dps_z: numberOrZero(payload.gyro_milli_dps_z),
    sht31_ready: boolOrFalse(payload.sht31_ready),
    sgp40_ready: boolOrFalse(payload.sgp40_ready),
    bh1750_ready: boolOrFalse(payload.bh1750_ready),
    bmi088_ready: boolOrFalse(payload.bmi088_ready),
    camera_url: payload.camera_url || "",
    updated_at: nowIso(),
  };

  return {
    ...sample,
    tilt: computeTilt(sample),
  };
}

let latest = normalizePayload({
  device_id: "demo-device",
  temperature_centi_c: 2635,
  humidity_centi_rh: 6120,
  voc_raw: 168,
  light_lux: 42,
  accel_milli_ms2_x: 120,
  accel_milli_ms2_y: -85,
  accel_milli_ms2_z: 9780,
  gyro_milli_dps_x: 0,
  gyro_milli_dps_y: 0,
  gyro_milli_dps_z: 0,
  sht31_ready: true,
  sgp40_ready: true,
  bh1750_ready: true,
  bmi088_ready: true,
});

const history = [latest];

let latestVision = {
  frame_type: "vision",
  device_id: "demo-device",
  bee_count: 0,
  activity_pct: 0,
  hive_state: 0,
  hive_state_name: "NORMAL",
  motion_pct: 0,
  avg_bee_size_px: 0,
  bee_color_pct: 0,
  lora_seq: 0,
  updated_at: nowIso(),
};

const visionHistory = [latestVision];

function sendJson(res, statusCode, body) {
  const text = JSON.stringify(body, null, 2);
  res.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  });
  res.end(text);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let chunks = "";
    req.on("data", (chunk) => {
      chunks += chunk;
      if (chunks.length > 1024 * 1024) {
        reject(new Error("request body too large"));
        req.destroy();
      }
    });
    req.on("end", () => resolve(chunks));
    req.on("error", reject);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http:

  if (req.method === "OPTIONS") {
    return sendJson(res, 200, { ok: true });
  }

  if (req.method === "GET" && url.pathname === "/api/bee-box/latest") {
    return sendJson(res, 200, latest);
  }

  if (req.method === "GET" && url.pathname === "/api/bee-box/history") {
    return sendJson(res, 200, {
      count: history.length,
      items: history,
    });
  }

  if (req.method === "POST" && url.pathname === "/api/bee-box/upload") {
    try {
      const raw = await readBody(req);
      const payload = JSON.parse(raw || "{}");
      latest = normalizePayload(payload);
      history.unshift(latest);
      history.length = Math.min(history.length, HISTORY_LIMIT);

      return sendJson(res, 200, {
        ok: true,
        device_id: latest.device_id,
        updated_at: latest.updated_at,
      });
    } catch (error) {
      return sendJson(res, 400, {
        ok: false,
        error: error.message,
      });
    }
  }

  if (req.method === "POST" && url.pathname === "/api/bee-box/vision") {
    try {
      const raw = await readBody(req);
      const payload = JSON.parse(raw || "{}");
      latestVision = {
        frame_type: "vision",
        device_id: payload.device_id || "unknown-device",
        bee_count: numberOrZero(payload.bee_count),
        activity_pct: numberOrZero(payload.activity_pct),
        hive_state: numberOrZero(payload.hive_state),
        hive_state_name: payload.hive_state_name || "UNKNOWN",
        motion_pct: numberOrZero(payload.motion_pct),
        avg_bee_size_px: numberOrZero(payload.avg_bee_size_px),
        bee_color_pct: numberOrZero(payload.bee_color_pct),
        lora_seq: numberOrZero(payload.lora_seq),
        updated_at: nowIso(),
      };
      visionHistory.unshift(latestVision);
      visionHistory.length = Math.min(visionHistory.length, HISTORY_LIMIT);

      return sendJson(res, 200, {
        ok: true,
        device_id: latestVision.device_id,
        hive_state_name: latestVision.hive_state_name,
        updated_at: latestVision.updated_at,
      });
    } catch (error) {
      return sendJson(res, 400, {
        ok: false,
        error: error.message,
      });
    }
  }

  if (req.method === "GET" && url.pathname === "/api/bee-box/vision") {
    return sendJson(res, 200, latestVision);
  }

  if (req.method === "GET" && url.pathname === "/api/bee-box/vision-history") {
    return sendJson(res, 200, {
      count: visionHistory.length,
      items: visionHistory,
    });
  }

  return sendJson(res, 404, {
    ok: false,
    error: "not found",
  });
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`[bee-cloud-demo] listening on http:
});
