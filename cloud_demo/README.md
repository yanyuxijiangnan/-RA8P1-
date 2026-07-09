# Bee Box Cloud Demo

This is a tiny local demo server for the RT-Thread bee-box project.

## What it does

- accepts board uploads at `POST /api/bee-box/upload`
- exposes the latest sample at `GET /api/bee-box/latest`
- keeps a short in-memory history at `GET /api/bee-box/history`

## Run

```bash
node server.js
```

The default port is `8080`.

## Board-side defaults

The embedded project currently posts to:

- host: `192.168.1.100`
- port: `8080`
- path: `/api/bee-box/upload`

Update the macros in [bee_box_cloud.c](/D:/RT-ThreadStudio/workspace/last_over/src/bee_box_cloud.c:24) so they match the PC or cloud server IP you will actually use.
