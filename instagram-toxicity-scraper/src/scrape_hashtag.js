#!/usr/bin/env node
/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');

const dotenv = require('dotenv');
const InstaTouch = require('instatouch');
const pLimit = require('p-limit');

dotenv.config();

const DEFAULT_DELAY_MS = Number(process.env.SCRAPER_DELAY_MS || 1500);

function parseArgs(argv) {
  const args = {
    hashtag: 'mobilelegends',
    count: 40,
    maxComments: 80,
    out: null,
    session: process.env.INSTAGRAM_SESSION_ID || '',
    delayMs: DEFAULT_DELAY_MS,
    concurrency: 2,
  };

  for (let idx = 2; idx < argv.length; idx += 1) {
    const key = argv[idx];
    const next = argv[idx + 1];
    switch (key) {
      case '--hashtag':
        args.hashtag = next;
        idx += 1;
        break;
      case '--count':
        args.count = Number(next);
        idx += 1;
        break;
      case '--max-comments':
        args.maxComments = Number(next);
        idx += 1;
        break;
      case '--out':
        args.out = next;
        idx += 1;
        break;
      case '--session':
        args.session = next;
        idx += 1;
        break;
      case '--delay-ms':
        args.delayMs = Number(next);
        idx += 1;
        break;
      case '--concurrency':
        args.concurrency = Math.max(1, Number(next));
        idx += 1;
        break;
      case '--help':
      case '-h':
        printHelp();
        process.exit(0);
        break;
      default:
        if (key.startsWith('--')) {
          console.warn(`Argumen tidak dikenal: ${key}`);
        }
        break;
    }
  }

  if (!args.out) {
    const outName = `${args.hashtag.replace(/[^a-z0-9]/gi, '').toLowerCase()}_comments.jsonl`;
    args.out = path.join(__dirname, '..', 'data', 'raw', outName);
  }

  if (!args.session) {
    console.warn('Peringatan: session Instagram tidak ditemukan. Banyak endpoint memerlukan sessionid.');
  }

  return args;
}

function printHelp() {
  console.log(`Instagram hashtag comment scraper

Usage:
  node src/scrape_hashtag.js --hashtag mobilelegends --count 60 --max-comments 120 --out data/raw/mobilelegends_comments.jsonl

Options:
  --hashtag <slug>        Hashtag target tanpa # (default: mobilelegends)
  --count <n>             Jumlah maksimum post yang di-scan (default: 40)
  --max-comments <n>      Jumlah komentar per post (default: 80)
  --out <path>            Lokasi file JSONL output
  --session <id>          Override sessionid Instagram (default baca dari .env)
  --delay-ms <n>          Jeda antar permintaan dalam milidetik (default: 1500)
  --concurrency <n>       Jumlah permintaan komentar paralel (default: 2)
  --help                  Tampilkan bantuan ini
`);
}

function ensureDir(targetPath) {
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
}

function toSessionString(sessionId) {
  if (!sessionId) {
    return '';
  }
  return sessionId.startsWith('sessionid=') ? sessionId : `sessionid=${sessionId}`;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchHashtagPosts(hashtag, count, sessionString, timeout) {
  const options = {
    count,
    session: sessionString,
    filetype: 'na',
    download: false,
    zip: false,
    mediaType: 'all',
    timeout,
    proxy: '',
  };
  const result = await InstaTouch.hashtag(hashtag, options);
  return result.collector || [];
}

async function fetchCommentsForPost(post, sessionString, maxComments, timeout) {
  const shortcode = post.shortcode || post.code || post.id;
  if (!shortcode) {
    return [];
  }
  const postUrl = `https://www.instagram.com/p/${shortcode}/`;
  const options = {
    session: sessionString,
    count: maxComments,
    filetype: 'na',
    download: false,
    zip: false,
    timeout,
  };
  const result = await InstaTouch.comments(postUrl, options);
  const comments = result.collector || [];
  return comments.slice(0, maxComments);
}

function normaliseRecord(post, comment) {
  return {
    fetched_at: new Date().toISOString(),
    source: 'instagram',
    post: {
      id: post.id,
      shortcode: post.shortcode,
      type: post.type,
      taken_at_timestamp: post.taken_at_timestamp,
      caption: post.description,
      likes: post.likes,
      comments_count: post.comments,
      owner: post.owner ? {
        id: post.owner.id,
        username: post.owner.username,
      } : null,
      hashtags: post.hashtags || [],
      location: post.location || null,
    },
    comment: {
      id: comment.id,
      text: comment.text,
      created_at: comment.created_at,
      likes: comment.likes,
      owner: comment.owner ? {
        id: comment.owner.id,
        username: comment.owner.username,
        is_verified: comment.owner.is_verified,
      } : null,
    },
  };
}

async function writeJsonl(pathName, records) {
  ensureDir(pathName);
  const stream = fs.createWriteStream(pathName, { flags: 'w', encoding: 'utf-8' });
  for (const record of records) {
    stream.write(`${JSON.stringify(record)}\n`);
  }
  await new Promise((resolve, reject) => {
    stream.end(() => resolve());
    stream.on('error', reject);
  });
}

async function main() {
  const args = parseArgs(process.argv);
  const sessionString = toSessionString(args.session);

  console.log(`Menggunakan session: ${sessionString || '(kosong)'}`);
  console.log(`Scraping hashtag #${args.hashtag} (posts: ${args.count}, comments/post: ${args.maxComments})`);

  const posts = await fetchHashtagPosts(args.hashtag, args.count, sessionString, args.delayMs);
  console.log(`Post ditemukan: ${posts.length}`);
  if (!posts.length) {
    console.warn('Tidak ada post yang dikembalikan. Periksa sessionid atau hashtag.');
    return;
  }

  const limiter = pLimit(args.concurrency);
  const aggregated = [];

  const tasks = posts.map((post, idx) => limiter(async () => {
    if (idx > 0 && args.delayMs > 0) {
      await delay(args.delayMs);
    }
    try {
      const comments = await fetchCommentsForPost(post, sessionString, args.maxComments, args.delayMs);
      if (!comments.length) {
        console.warn(`Komentar kosong untuk post ${post.shortcode || post.id}`);
      }
      comments.forEach((comment) => {
        const record = normaliseRecord(post, comment);
        aggregated.push(record);
      });
    } catch (error) {
      console.error(`Gagal mengambil komentar untuk post ${post.shortcode || post.id}:`, error.message);
    }
  }));

  await Promise.all(tasks);

  if (!aggregated.length) {
    console.warn('Tidak ada komentar yang berhasil dikumpulkan.');
    return;
  }

  await writeJsonl(args.out, aggregated);
  console.log(`Selesai. Total komentar tersimpan: ${aggregated.length}. File: ${args.out}`);
}

main().catch((error) => {
  console.error('Kesalahan fatal:', error);
  process.exit(1);
});
