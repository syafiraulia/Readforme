#!/usr/bin/env python3
"""
buku_ke_mp3.py: ubah buku EPUB atau PDF jadi file MP3 per bab, dengan suara
neural Bahasa Indonesia (Ardi = cowok, Gadis = cewek) lewat library edge-tts.

Pasang sekali:
    pip install edge-tts pypdf mutagen
(pypdf hanya perlu untuk PDF, mutagen hanya untuk judul bab di tag MP3; keduanya opsional)

Contoh:
    python buku_ke_mp3.py buku.epub                      # suara Gadis, tempo normal
    python buku_ke_mp3.py buku.epub -v ardi -r 1.1       # suara Ardi, 10% lebih cepat
    python buku_ke_mp3.py buku.pdf --pages-per-file 15   # PDF dipecah per 15 halaman
    python buku_ke_mp3.py buku.epub --list               # lihat daftar bab saja
    python buku_ke_mp3.py buku.epub --only 3-5,8         # hanya bab tertentu

Catatan: edge-tts memakai layanan online Microsoft Edge lewat jalur tidak resmi.
Gratis dan tanpa kunci API, tapi butuh internet dan bisa berhenti jalan sewaktu-waktu.
"""
import argparse
import asyncio
import posixpath
import re
import sys
import urllib.parse
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

VOICES = {"ardi": "id-ID-ArdiNeural", "gadis": "id-ID-GadisNeural"}
HEADS = {"h1", "h2", "h3", "h4", "h5", "h6"}
BLOCK = HEADS | {"p", "div", "li", "blockquote", "pre", "dd", "dt", "figcaption",
                 "td", "th", "tr", "caption", "section", "article", "ul", "ol", "table"}
SKIP = {"script", "style", "svg", "rt", "head"}


def norm(s):
    s = s.replace("­", "").replace("​", "").replace("﻿", "")
    return re.sub(r"\s+", " ", s).strip()


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


# ------------------------------------------------------------------ EPUB
class Blocks(HTMLParser):
    """Ambil teks per blok (paragraf, judul, dst.) dari satu halaman XHTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.buf, self.skip, self.head = [], [], 0, False

    def flush(self):
        t = norm("".join(self.buf))
        self.buf = []
        if t:
            self.out.append((t, self.head))

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        elif tag in BLOCK:
            self.flush()
            self.head = tag in HEADS
        elif tag == "br":
            self.buf.append(" ")

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK:
            self.flush()
            self.head = False

    def handle_data(self, d):
        if not self.skip:
            self.buf.append(d)

    def close(self):
        super().close()
        self.flush()


class NavAnchors(HTMLParser):
    """Kumpulkan tautan (href, teks) di dalam elemen <nav>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.navs, self.in_nav, self.href, self.txt = [], None, None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "nav":
            self.in_nav = {"toc": "toc" in (a.get("epub:type") or ""), "links": []}
            self.navs.append(self.in_nav)
        elif tag == "a" and self.in_nav is not None and a.get("href"):
            self.href, self.txt = a["href"], []

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.in_nav["links"].append((self.href, norm("".join(self.txt))))
            self.href = None
        elif tag == "nav":
            self.in_nav = None

    def handle_data(self, d):
        if self.href is not None:
            self.txt.append(d)


def resolve(base, href):
    href = urllib.parse.unquote(href.split("#")[0])
    return posixpath.normpath(posixpath.join(base, href))


def read_epub(path):
    z = zipfile.ZipFile(path)
    lower = {n.lower(): n for n in z.namelist()}

    def get(p):
        n = p if p in z.namelist() else lower.get(p.lower())
        return z.read(n) if n else None

    container = get("META-INF/container.xml")
    if not container:
        sys.exit("Ini bukan file EPUB yang valid.")
    root = next((e for e in ET.fromstring(container).iter() if local(e.tag) == "rootfile"), None)
    if root is None:
        sys.exit("Struktur EPUB rusak (rootfile tidak ditemukan).")
    opf_path = root.get("full-path")
    opf = ET.fromstring(get(opf_path))
    base = posixpath.dirname(opf_path)

    def meta(name):
        e = next((x for x in opf.iter() if local(x.tag) == name and (x.text or "").strip()), None)
        return norm(e.text) if e is not None else ""

    manifest = {}
    spine = []
    spine_toc = None
    for e in opf.iter():
        n = local(e.tag)
        if n == "item":
            manifest[e.get("id")] = (e.get("href", ""), e.get("media-type", ""), e.get("properties", ""))
        elif n == "itemref":
            spine.append(e.get("idref"))
        elif n == "spine":
            spine_toc = e.get("toc")

    toc = {}

    def add_toc(toc_path, href, title):
        if href and title:
            toc.setdefault(resolve(posixpath.dirname(toc_path), href), title)

    nav_item = next((v for v in manifest.values() if "nav" in v[2].split()), None)
    if nav_item:
        np_ = resolve(base, nav_item[0])
        raw = get(np_)
        if raw:
            p = NavAnchors()
            p.feed(raw.decode("utf-8", "replace"))
            nav = next((n for n in p.navs if n["toc"]), p.navs[0] if p.navs else None)
            for href, title in (nav["links"] if nav else []):
                add_toc(np_, href, title)
    if not toc:
        ncx = manifest.get(spine_toc) or next(
            (v for v in manifest.values() if v[1] == "application/x-dtbncx+xml"), None)
        if ncx:
            np_ = resolve(base, ncx[0])
            raw = get(np_)
            if raw:
                for pt in ET.fromstring(raw).iter():
                    if local(pt.tag) != "navPoint":
                        continue
                    lab = next((x for x in pt.iter() if local(x.tag) == "text"), None)
                    con = next((x for x in pt.iter() if local(x.tag) == "content"), None)
                    if lab is not None and con is not None:
                        add_toc(np_, con.get("src", ""), norm(lab.text or ""))

    chapters = []  # {"title": str, "paras": [str]}
    all_blocks = []  # untuk cadangan pemecahan berdasarkan judul
    for idref in spine:
        item = manifest.get(idref)
        if not item or "nav" in item[2].split() or not re.search(r"x?html|xml", item[1]):
            continue
        dpath = resolve(base, item[0])
        raw = get(dpath)
        if not raw:
            continue
        bp = Blocks()
        bp.feed(raw.decode("utf-8", "replace"))
        bp.close()
        blocks = bp.out
        if not blocks:
            continue
        all_blocks.extend(blocks)
        total = sum(len(t) for t, _ in blocks)
        title = toc.get(dpath) or (blocks[0][0] if blocks[0][1] else None)
        paras = [t for t, _ in blocks]
        if chapters and not toc.get(dpath) and total < 300:
            chapters[-1]["paras"].extend(paras)  # halaman kecil digabung ke bab sebelumnya
        else:
            chapters.append({"title": title or "Bagian %d" % (len(chapters) + 1), "paras": paras})

    # Cadangan: satu file besar berisi banyak bab, pecah di judul.
    if len(chapters) <= 2 and sum(len(t) for t, _ in all_blocks) > 40000:
        split, cur = [], None
        for t, is_head in all_blocks:
            if is_head and (cur is None or sum(len(x) for x in cur["paras"]) > 3000):
                cur = {"title": t, "paras": []}
                split.append(cur)
            if cur is None:
                cur = {"title": "Awal", "paras": []}
                split.append(cur)
            cur["paras"].append(t)
        if len(split) > len(chapters):
            chapters = split

    if not chapters:
        sys.exit("Tidak ada teks yang bisa dibacakan di EPUB ini (mungkin berisi gambar saja atau diproteksi DRM).")
    return {"title": meta("title") or Path(path).stem, "author": meta("creator"), "chapters": chapters}


# ------------------------------------------------------------------ PDF
def clean_pdf(text):
    paras, cur = [], ""
    for line in text.splitlines():
        s = line.strip()
        if re.fullmatch(r"\d{1,4}", s):
            continue
        if not s:
            if cur:
                paras.append(cur)
            cur = ""
            continue
        if cur and re.search(r"[a-zà-ÿ]-$", cur) and re.match(r"[a-zà-ÿ]", s):
            cur = cur[:-1] + s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        paras.append(cur)
    return [norm(p) for p in paras if norm(p)]


def read_pdf(path, pages_per_file):
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("Untuk PDF, pasang dulu: pip install pypdf")
    r = PdfReader(path)
    pages = [clean_pdf(p.extract_text() or "") for p in r.pages]
    if sum(len(x) for pg in pages for x in pg) < 200:
        sys.exit("PDF ini sepertinya hasil scan (berupa gambar), jadi tidak ada teks. Jalankan OCR dulu, lalu coba lagi.")

    starts = []
    try:
        def walk(items):
            for it in items:
                if isinstance(it, list):
                    walk(it)
                else:
                    starts.append((r.get_destination_page_number(it), norm(it.title)))
        walk(r.outline)
    except Exception:
        starts = []
    starts = sorted({(p, t) for p, t in starts if p is not None and t})
    seen, uniq = set(), []
    for p, t in starts:
        if p not in seen:
            seen.add(p)
            uniq.append((p, t))
    chapters = []
    if len(uniq) >= 2:
        if uniq[0][0] > 0:
            uniq.insert(0, (0, "Awal"))
        for i, (p, t) in enumerate(uniq):
            end = uniq[i + 1][0] if i + 1 < len(uniq) else len(pages)
            paras = [x for pg in pages[p:end] for x in pg]
            if paras:
                chapters.append({"title": t, "paras": paras})
    if not chapters:
        for a in range(0, len(pages), pages_per_file):
            b = min(a + pages_per_file, len(pages))
            paras = [x for pg in pages[a:b] for x in pg]
            if paras:
                chapters.append({"title": "Halaman %d-%d" % (a + 1, b), "paras": paras})
    info = r.metadata
    title = norm(getattr(info, "title", "") or "") or Path(path).stem
    author = norm(getattr(info, "author", "") or "")
    return {"title": title, "author": author, "chapters": chapters}


# ------------------------------------------------------------------ teks → potongan
def ensure_punct(p):
    return p if re.search(r"[.!?…:;\"'”’)\]]$", p) else p + "."


def split_long(p, maxc):
    out, cur = [], ""
    for s in re.split(r"(?<=[.!?…])\s+", p):
        while len(s) > maxc:
            cut = s.rfind(", ", 0, maxc)
            if cut < maxc // 3:
                cut = s.rfind(" ", 0, maxc)
            if cut < maxc // 3:
                cut = maxc
            head, s = s[:cut + 1].strip(), s[cut + 1:].strip()
            if cur:
                out.append(cur)
                cur = ""
            out.append(head)
        if not s:
            continue
        if cur and len(cur) + 1 + len(s) > maxc:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out


def make_chunks(paras, maxc=2000):
    chunks, cur = [], ""
    for p in paras:
        p = ensure_punct(p)
        for part in ([p] if len(p) <= maxc else split_long(p, maxc)):
            if cur and len(cur) + 1 + len(part) > maxc:
                chunks.append(cur)
                cur = part
            else:
                cur = (cur + " " + part).strip()
    if cur:
        chunks.append(cur)
    return chunks


# ------------------------------------------------------------------ suara
async def synth_chunk(edge_tts, text, voice, rate, pitch, sem, retries=4):
    async with sem:
        for attempt in range(retries):
            try:
                comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
                buf = bytearray()
                async for m in comm.stream():
                    if m["type"] == "audio":
                        buf.extend(m["data"])
                if not buf:
                    raise RuntimeError("audio kosong")
                return bytes(buf)
            except Exception:
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(2 * (attempt + 1))


def tag_mp3(path, title, album, artist, track, total):
    try:
        from mutagen.id3 import ID3, TALB, TIT2, TPE1, TRCK
    except ImportError:
        return
    try:
        t = ID3()
        t.add(TIT2(encoding=3, text=title))
        t.add(TALB(encoding=3, text=album))
        if artist:
            t.add(TPE1(encoding=3, text=artist))
        t.add(TRCK(encoding=3, text="%d/%d" % (track, total)))
        t.save(path)
    except Exception:
        pass


def parse_only(spec, n):
    if not spec:
        return set(range(1, n + 1))
    keep = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            keep.update(range(int(a), int(b) + 1))
        elif part:
            keep.add(int(part))
    return {k for k in keep if 1 <= k <= n}


def safe_name(s):
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|]+', " ", s)).strip()[:60] or "bab"


async def convert(book, args, voice, rate):
    try:
        import edge_tts
    except ImportError:
        sys.exit("Pasang dulu: pip install edge-tts")
    out = Path(args.out or safe_name(book["title"]))
    out.mkdir(parents=True, exist_ok=True)
    chs = book["chapters"]
    keep = parse_only(args.only, len(chs))
    sem = asyncio.Semaphore(args.concurrency)
    for i, ch in enumerate(chs, 1):
        if i not in keep:
            continue
        fname = out / ("%02d - %s.mp3" % (i, safe_name(ch["title"])))
        if fname.exists() and not args.force:
            print("[%d/%d] sudah ada, dilewati: %s" % (i, len(chs), fname.name))
            continue
        chunks = make_chunks(ch["paras"], args.max_chars)
        print("[%d/%d] %s (%d potongan)" % (i, len(chs), ch["title"], len(chunks)), flush=True)
        tasks = [synth_chunk(edge_tts, c, voice, rate, args.pitch, sem) for c in chunks]
        parts = await asyncio.gather(*tasks)
        tmp = fname.with_suffix(".part")
        tmp.write_bytes(b"".join(parts))
        tmp.replace(fname)
        tag_mp3(str(fname), ch["title"], book["title"], book["author"], i, len(chs))
    print("Selesai. File ada di:", out.resolve())


def main():
    ap = argparse.ArgumentParser(description="Ubah EPUB/PDF jadi MP3 per bab (suara Indonesia).")
    ap.add_argument("buku", help="file .epub atau .pdf")
    ap.add_argument("-o", "--out", help="folder hasil (bawaan: nama buku)")
    ap.add_argument("-v", "--voice", default="gadis",
                    help="ardi (cowok), gadis (cewek), atau nama suara lengkap, mis. en-US-AriaNeural")
    ap.add_argument("-r", "--rate", type=float, default=1.0, help="kecepatan, 1.0 normal, 1.1 = 10%% lebih cepat")
    ap.add_argument("--pitch", default="+0Hz", help="nada, mis. -5Hz agar lebih berat")
    ap.add_argument("--pages-per-file", type=int, default=20, help="khusus PDF tanpa daftar isi")
    ap.add_argument("--only", help="hanya bab tertentu, mis. 1-3,7")
    ap.add_argument("--list", action="store_true", help="tampilkan daftar bab lalu berhenti")
    ap.add_argument("--force", action="store_true", help="buat ulang file yang sudah ada")
    ap.add_argument("--max-chars", type=int, default=2000, help="panjang tiap potongan teks")
    ap.add_argument("--concurrency", type=int, default=3, help="jumlah permintaan paralel")
    args = ap.parse_args()

    p = Path(args.buku)
    if not p.exists():
        sys.exit("File tidak ditemukan: %s" % p)
    ext = p.suffix.lower()
    if ext == ".epub":
        book = read_epub(p)
    elif ext == ".pdf":
        book = read_pdf(p, args.pages_per_file)
    else:
        sys.exit("Hanya mendukung .epub dan .pdf")

    total = sum(len(x) for c in book["chapters"] for x in c["paras"])
    print("%s%s" % (book["title"], (" · " + book["author"]) if book["author"] else ""))
    minutes = max(1, round(total / 900))  # sekitar 900 karakter per menit suara
    durasi = "%d menit" % minutes if minutes < 90 else "%.1f jam" % (minutes / 60)
    print("%d bab, sekitar %d karakter (kira-kira %s suara)\n" % (len(book["chapters"]), total, durasi))
    for i, c in enumerate(book["chapters"], 1):
        print("%3d. %s  (%d karakter)" % (i, c["title"], sum(len(x) for x in c["paras"])))
    if args.list:
        return

    voice = VOICES.get(args.voice.lower(), args.voice)
    pct = round((args.rate - 1) * 100)
    rate = "%+d%%" % pct
    print("\nSuara: %s, tempo: %s\n" % (voice, rate))
    asyncio.run(convert(book, args, voice, rate))


if __name__ == "__main__":
    main()
