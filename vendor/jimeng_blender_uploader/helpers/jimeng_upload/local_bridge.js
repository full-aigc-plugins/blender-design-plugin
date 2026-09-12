#!/usr/bin/env node

"use strict";

const crypto = require("crypto");
const fs = require("fs");
const http = require("http");
const path = require("path");
const { URL } = require("url");

const DefaultTargetUrl = "https://jimeng.jianying.com/ai-tool/home";
const DefaultTtlMs = 30 * 60 * 1000;
const DefaultCloseAfterDownloadMs = 60 * 1000;

function parseArgs(argv) {
  const args = {
    prompt: "",
    url: DefaultTargetUrl,
    ttlMs: DefaultTtlMs,
    closeAfterDownloadMs: DefaultCloseAfterDownloadMs,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i];
    if (!item.startsWith("--")) {
      continue;
    }

    const key = item.slice(2);
    const value = argv[i + 1];
    if (value === undefined || value.startsWith("--")) {
      args[key] = true;
    } else {
      args[key] = value;
      i += 1;
    }
  }

  if (args["ttl-ms"] !== undefined) {
    args.ttlMs = Number(args["ttl-ms"]);
  }
  if (args["close-after-download-ms"] !== undefined) {
    args.closeAfterDownloadMs = Number(args["close-after-download-ms"]);
  }

  return args;
}

function emit(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

function base64Url(value) {
  return Buffer.from(value, "utf8")
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function isAllowedOrigin(origin) {
  if (!origin) {
    return false;
  }

  try {
    const url = new URL(origin);
    const host = url.hostname;
    const isDreaminaHost =
      url.protocol === "https:" &&
      (host === "jimeng.jianying.com" ||
        host.endsWith(".jianying.com") ||
        host === "dreamina.capcut.com" ||
        host.endsWith(".capcut.com"));
    const isLocalDevHost =
      (url.protocol === "http:" || url.protocol === "https:") &&
      (host === "localhost" || host === "127.0.0.1" || host === "::1");

    return isDreaminaHost || isLocalDevHost;
  } catch (_error) {
    return false;
  }
}

function writeCorsHeaders(req, res) {
  const origin = req.headers.origin;
  if (isAllowedOrigin(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }

  res.setHeader("Vary", "Origin");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Access-Control-Allow-Private-Network", "true");
}

function sendJson(req, res, statusCode, payload) {
  writeCorsHeaders(req, res);
  res.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  res.end(JSON.stringify(payload));
}

function contentDispositionHeader(filePath) {
  const filename = path.basename(filePath || "blender-render.mp4").replace(/[\r\n]/g, "_");
  const fallback = filename.replace(/[^\x20-\x7E]/g, "_").replace(/"/g, "_");

  return `inline; filename="${fallback}"; filename*=UTF-8''${encodeURIComponent(filename)}`;
}

function makeRedirectUrl(targetUrl, resourceInfoUrl) {
  const url = new URL(targetUrl || DefaultTargetUrl);
  if (url.pathname.replace(/\/$/, "") === "/ai-tool") {
    url.pathname = "/ai-tool/home";
  }
  url.searchParams.set("channel", "blender");
  url.searchParams.set("thirdparty_id", base64Url(resourceInfoUrl));
  return url.toString();
}

function tokenFromUrl(reqUrl) {
  try {
    return new URL(reqUrl, "http://127.0.0.1").searchParams.get("token") || "";
  } catch (_error) {
    return "";
  }
}

function createShutdownScheduler(server) {
  let timer = null;
  let deadline = Number.POSITIVE_INFINITY;

  return function scheduleShutdown(delayMs) {
    const nextDeadline = Date.now() + Math.max(0, delayMs);
    if (timer && nextDeadline >= deadline) {
      return;
    }

    if (timer) {
      clearTimeout(timer);
    }
    deadline = nextDeadline;
    timer = setTimeout(() => {
      server.close(() => {
        process.exit(0);
      });
      setTimeout(() => process.exit(0), 2000).unref();
    }, Math.max(0, delayMs));
    timer.unref();
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const videoPath = args.video ? path.resolve(args.video) : "";

  if (!videoPath || !fs.existsSync(videoPath)) {
    emit({ status: "failed", reason: `Video file does not exist: ${videoPath}` });
    process.exit(2);
  }

  const token = crypto.randomBytes(24).toString("base64url");
  const expiresAt = Date.now() + Number(args.ttlMs || DefaultTtlMs);
  const prompt = String(args.prompt || "");

  let scheduleShutdown = null;

  const server = http.createServer((req, res) => {
    if (!req.url) {
      sendJson(req, res, 400, { status: "failed", code: "BAD_REQUEST" });
      return;
    }

    if (req.method === "OPTIONS") {
      writeCorsHeaders(req, res);
      res.writeHead(204);
      res.end();
      return;
    }

    if (req.method !== "GET") {
      sendJson(req, res, 405, { status: "failed", code: "METHOD_NOT_ALLOWED" });
      return;
    }

    const requestUrl = new URL(req.url, "http://127.0.0.1");
    if (tokenFromUrl(req.url) !== token) {
      sendJson(req, res, 403, { status: "failed", code: "INVALID_TOKEN" });
      return;
    }

    if (Date.now() > expiresAt) {
      sendJson(req, res, 410, { status: "failed", code: "TOKEN_EXPIRED" });
      scheduleShutdown(0);
      return;
    }

    if (requestUrl.pathname === "/resouce_info" || requestUrl.pathname === "/resource_info") {
      const address = server.address();
      const port = address && typeof address === "object" ? address.port : 0;
      sendJson(req, res, 200, {
        file_url: `http://127.0.0.1:${port}/file?token=${encodeURIComponent(token)}`,
        prompt,
      });
      return;
    }

    if (requestUrl.pathname !== "/file") {
      sendJson(req, res, 404, { status: "failed", code: "NOT_FOUND" });
      return;
    }

    let stat;
    try {
      stat = fs.statSync(videoPath);
    } catch (_error) {
      sendJson(req, res, 404, { status: "failed", code: "FILE_NOT_FOUND" });
      return;
    }

    writeCorsHeaders(req, res);
    res.writeHead(200, {
      "Content-Type": "video/mp4",
      "Content-Length": stat.size,
      "Content-Disposition": contentDispositionHeader(videoPath),
      "Cache-Control": "no-store",
    });

    const stream = fs.createReadStream(videoPath);
    stream.on("error", () => {
      if (!res.headersSent) {
        sendJson(req, res, 500, { status: "failed", code: "FILE_READ_FAILED" });
      } else {
        res.destroy();
      }
    });
    res.on("finish", () => {
      scheduleShutdown(Number(args.closeAfterDownloadMs || DefaultCloseAfterDownloadMs));
    });
    stream.pipe(res);
  });

  scheduleShutdown = createShutdownScheduler(server);
  scheduleShutdown(Number(args.ttlMs || DefaultTtlMs));

  server.on("error", (error) => {
    emit({
      status: "failed",
      reason: String(error && error.message ? error.message : error),
    });
    process.exit(3);
  });

  server.listen(0, "127.0.0.1", () => {
    const address = server.address();
    const port = address && typeof address === "object" ? address.port : 0;
    const resourceInfoUrl = `http://127.0.0.1:${port}/resouce_info?token=${encodeURIComponent(token)}`;

    emit({
      status: "ready",
      port,
      pid: process.pid,
      resource_info_url: resourceInfoUrl,
      redirect_url: makeRedirectUrl(args.url, resourceInfoUrl),
      expires_at: expiresAt,
      video: videoPath,
    });
  });

  process.on("SIGTERM", () => scheduleShutdown(0));
  process.on("SIGINT", () => scheduleShutdown(0));
}

main().catch((error) => {
  emit({
    status: "failed",
    reason: String(error && error.message ? error.message : error),
  });
  process.exit(1);
});
