import { readFile } from "node:fs/promises";

const file = process.argv[2];
if (!file) {
  throw new Error("usage: node check-literature-links.mjs <markdown-file>");
}

const body = await readFile(file, "utf8");
const urls = [...body.matchAll(/https?:\/\/[^)\s]+/g)].map((match) => match[0]);
const queue = [...new Set(urls)];
const results = [];

async function check(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20_000);
  try {
    let response = await fetch(url, {
      method: "HEAD",
      redirect: "follow",
      signal: controller.signal,
      headers: { "user-agent": "Amadeus-literature-link-check/1.0" },
    });
    if (response.status === 405 || response.status === 501) {
      response = await fetch(url, {
        method: "GET",
        redirect: "follow",
        signal: controller.signal,
        headers: {
          "user-agent": "Amadeus-literature-link-check/1.0",
          range: "bytes=0-1023",
        },
      });
    }
    return {
      url,
      status: response.status,
      finalUrl: response.url,
      ok: response.status >= 200 && response.status < 400,
    };
  } catch (error) {
    return { url, status: 0, finalUrl: "", ok: false, error: error.name };
  } finally {
    clearTimeout(timeout);
  }
}

async function worker() {
  while (queue.length) {
    const url = queue.shift();
    results.push(await check(url));
  }
}

await Promise.all(Array.from({ length: 10 }, worker));
results.sort((a, b) => a.url.localeCompare(b.url));

const strictFailures = results.filter(
  (item) => item.status === 0 || item.status === 404 || item.status >= 500,
);
const accessLimited = results.filter(
  (item) => !item.ok && !strictFailures.includes(item),
);

console.log(
  JSON.stringify(
    {
      checked: results.length,
      reachable: results.filter((item) => item.ok).length,
      accessLimited: accessLimited.length,
      strictFailures: strictFailures.length,
      accessLimitedItems: accessLimited,
      strictFailureItems: strictFailures,
    },
    null,
    2,
  ),
);
