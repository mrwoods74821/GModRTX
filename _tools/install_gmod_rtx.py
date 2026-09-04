#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
TOOLS = SCRIPT_PATH.parent
TARGET = TOOLS.parent
STEAM_ROOT = Path(os.environ.get('STEAM_ROOT', '/home/elijah/.steam/steam'))
VANILLA = Path(os.environ.get('GMOD_VANILLA_PATH', str(STEAM_ROOT / 'steamapps' / 'common' / 'GarrysMod')))
CACHE = TOOLS / 'cache'

REMIX_STABLE = {
    'source': 'sambow23/dxvk-remix-gmod',
    'tag': '6d75248',
    'name': '3/21/26',
    'asset': 'remix-6d75248-gmod.zip',
    'url': 'https://github.com/sambow23/dxvk-remix-gmod/releases/download/6d75248/remix-6d75248-gmod.zip',
    'sha256': 'a05554bdffe8c48ae8d725324f0b1a44e951ed57889ef7aff13865713c0071a4',
}

FIXES_STABLE = {
    'source': 'Xenthio/garrys-mod-rtx-remixed',
    'tag': 'v0.10.0',
    'name': 'v0.10.0',
    'asset': 'gmrtx-0.10.0-launcher.zip',
    'url': 'https://github.com/Xenthio/garrys-mod-rtx-remixed/releases/download/v0.10.0/gmrtx-0.10.0-launcher.zip',
    'sha256': 'b03e969cf032b3c2d612f196c6bb347ec92cd42d6911fe59f0b7dcba939055fa',
}

SOURCE_TWEAKS = {
    'source': 'sambow23/SourceRTXTweaks',
    'branch': 'main',
    'asset': 'SourceRTXTweaks-applypatch-main.py',
    'url': 'https://raw.githubusercontent.com/sambow23/SourceRTXTweaks/main/applypatch.py',
}

EXCLUDED_GARRYSMOD_DIRS = {
    'saves', 'dupes', 'demos', 'settings', 'cache', 'materials', 'models',
    'maps', 'screenshots', 'videos', 'download', 'addons'
}

STANDARD_FIXES_IGNORE_PATTERNS = [
    'bin/.trex/*',
    'bin/d3d8to9.dll',
    'bin/d3d9.dll',
    'bin/LICENSE.txt',
    'bin/NvRemixLauncher32.exe',
    'bin/ThirdPartyLicenses-bridge.txt',
    'bin/ThirdPartyLicenses-d3d8to9.txt',
    'bin/ThirdPartyLicenses-dxvk.txt',
    'bin/win64/usd/*',
    'bin/win64/artifacts_readme.txt',
    'bin/win64/cudart64_12.dll',
    'bin/win64/d3d9.dll',
    'bin/win64/d3d9.pdb',
    'bin/win64/GFSDK_Aftermath_Lib.x64.dll',
    'bin/win64/NRC_Vulkan.dll',
    'bin/win64/NRD.dll',
    'bin/win64/NvLowLatencyVk.dll',
    'bin/win64/nvngx_dlss.dll',
    'bin/win64/nvngx_dlssd.dll',
    'bin/win64/nvngx_dlssg.dll',
    'bin/win64/NvRemixBridge.exe',
    'bin/win64/nvrtc64_120_0.dll',
    'bin/win64/nvrtc-builtins64_125.dll',
    'bin/win64/rtxio.dll',
    'bin/win64/tbb.dll',
    'bin/win64/tbbmalloc.dll',
    'bin/win64/usd_ms.dll',
]


def log(message: str) -> None:
    print(message, flush=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, destination: Path, expected_sha256: str | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and expected_sha256:
        actual = sha256_file(destination)
        if actual.lower() == expected_sha256.lower():
            log(f'Using cached {destination.name} ({actual})')
            return
        log(f'Redownloading {destination.name}; checksum mismatch {actual}')
        destination.unlink()
    elif destination.exists():
        log(f'Using cached {destination.name}')
        return

    tmp = destination.with_suffix(destination.suffix + '.part')
    if tmp.exists():
        tmp.unlink()

    log(f'Downloading {destination.name}')
    with urllib.request.urlopen(url) as response, tmp.open('wb') as out:
        total = response.headers.get('Content-Length')
        total_bytes = int(total) if total and total.isdigit() else None
        read = 0
        last = time.monotonic()
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            read += len(chunk)
            now = time.monotonic()
            if now - last >= 5:
                if total_bytes:
                    log(f'  {read / 1024 / 1024:.1f} MiB / {total_bytes / 1024 / 1024:.1f} MiB')
                else:
                    log(f'  {read / 1024 / 1024:.1f} MiB')
                last = now
    tmp.replace(destination)

    if expected_sha256:
        actual = sha256_file(destination)
        if actual.lower() != expected_sha256.lower():
            raise RuntimeError(f'{destination.name} checksum mismatch: {actual} != {expected_sha256}')
        log(f'Verified {destination.name}: {actual}')


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)


def copy_tree_contents(src: Path, dst: Path) -> int:
    count = 0
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dst / child.name
        if child.is_dir() and not child.is_symlink():
            copy_tree(child, target)
            count += sum(1 for p in child.rglob('*') if p.is_file())
        elif child.is_symlink():
            if target.exists() or target.is_symlink():
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            os.symlink(os.readlink(child), target)
            count += 1
        else:
            copy_file(child, target)
            count += 1
    return count


def symlink_force(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink():
        current = Path(os.readlink(dst))
        if current == src:
            return
        dst.unlink()
    elif dst.exists():
        return
    os.symlink(src, dst)


def setup_base_install() -> None:
    if not VANILLA.exists():
        raise RuntimeError(f'Vanilla Garry\'s Mod path is missing: {VANILLA}')
    if not (VANILLA / 'gmod.exe').exists() and not (VANILLA / 'hl2.exe').exists():
        raise RuntimeError(f'Could not find gmod.exe or hl2.exe in {VANILLA}')

    log(f'Creating RTX install at {TARGET}')
    TARGET.mkdir(parents=True, exist_ok=True)

    log('Copying bin folder')
    copy_tree(VANILLA / 'bin', TARGET / 'bin')

    if (VANILLA / 'gmod.exe').exists():
        copy_file(VANILLA / 'gmod.exe', TARGET / 'gmod.exe')
    elif (VANILLA / 'hl2.exe').exists():
        copy_file(VANILLA / 'hl2.exe', TARGET / 'hl2.exe')

    if (VANILLA / 'steam_appid.txt').exists():
        copy_file(VANILLA / 'steam_appid.txt', TARGET / 'steam_appid.txt')
    else:
        (TARGET / 'steam_appid.txt').write_text('4000', encoding='utf-8')

    src_gm = VANILLA / 'garrysmod'
    dst_gm = TARGET / 'garrysmod'
    dst_gm.mkdir(parents=True, exist_ok=True)

    log('Linking VPK files')
    for vpk in src_gm.glob('*.vpk'):
        symlink_force(vpk, dst_gm / vpk.name)

    log('Linking shared sourceengine and platform folders')
    for folder in ('sourceengine', 'platform'):
        if (VANILLA / folder).exists():
            symlink_force(VANILLA / folder, TARGET / folder)

    log('Copying garrysmod root files')
    for item in src_gm.iterdir():
        if item.is_file() and not item.name.lower().endswith(('.vpk', '.dem', '.log')):
            copy_file(item, dst_gm / item.name)

    log('Copying non-user garrysmod subfolders')
    for item in src_gm.iterdir():
        if item.is_dir() and item.name.lower() not in EXCLUDED_GARRYSMOD_DIRS:
            copy_tree(item, dst_gm / item.name)

    (dst_gm / 'addons').mkdir(exist_ok=True)

    log('Linking user-content folders back to vanilla install')
    for name in sorted(EXCLUDED_GARRYSMOD_DIRS - {'addons'}):
        src = src_gm / name
        dst = dst_gm / name
        if src.exists():
            symlink_force(src, dst)


def extract_zip(zip_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)


def find_remix_source(root: Path) -> Path:
    trex_dirs = [p for p in root.rglob('*') if p.is_dir() and p.name.endswith('.trex')]
    if trex_dirs:
        trex_dirs.sort(key=lambda p: len(p.parts), reverse=True)
        chosen = trex_dirs[0]
        if (chosen / 'win64').is_dir():
            return chosen / 'win64'
        return chosen

    bin_dirs = [p for p in root.rglob('bin') if p.is_dir()]
    if bin_dirs:
        bin_dirs.sort(key=lambda p: len(p.parts), reverse=True)
        chosen = bin_dirs[0]
        if (chosen / 'win64').is_dir():
            return chosen / 'win64'
        return chosen

    return root


def install_remix_package(zip_path: Path) -> None:
    log('Installing RTX Remix runtime package')
    with tempfile.TemporaryDirectory(prefix='gmodrtx-remix-') as tmp_s:
        tmp = Path(tmp_s)
        extract_zip(zip_path, tmp)
        source = find_remix_source(tmp)
        target = TARGET / 'bin' / 'win64'
        copied = copy_tree_contents(source, target)
        log(f'Copied {copied} runtime files from {source} to {target}')


def normalize_zip_name(name: str) -> str:
    return name.replace('\\', '/').strip('/')


def should_ignore(rel: str, patterns: list[str]) -> bool:
    rel_l = normalize_zip_name(rel).lower()
    for pattern in patterns:
        pat = normalize_zip_name(pattern).lower()
        if pat.endswith('/*'):
            prefix = pat[:-2]
            if rel_l == prefix or rel_l.startswith(prefix + '/'):
                return True
        elif fnmatch.fnmatchcase(rel_l, pat):
            return True
    return False


def cleanup_old_fixes() -> None:
    for rel in [
        Path('garrysmod/addons/remixbinary'),
        Path('garrysmod/data/remix_map_configs'),
        Path('garrysmod/addons/hl2rtx-model-compat'),
    ]:
        path = TARGET / rel
        if path.exists() and path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
            log(f'Removed outdated folder {path}')
    addons = TARGET / 'garrysmod' / 'addons'
    if addons.exists():
        for path in addons.glob('mount-hl2rtx-*'):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
                log(f'Removed outdated folder {path}')


def install_fixes_package(zip_path: Path) -> None:
    log('Installing Garry\'s Mod RTX fixes package')
    cleanup_old_fixes()
    extracted = 0
    ignored = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            rel = normalize_zip_name(info.filename)
            if not rel:
                continue
            if rel.startswith('../') or '/..' in rel or Path(rel).is_absolute():
                raise RuntimeError(f'Unsafe zip entry: {info.filename}')
            if should_ignore(rel, STANDARD_FIXES_IGNORE_PATTERNS):
                ignored += 1
                continue
            dest = TARGET / rel
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, 'r') as src, dest.open('wb') as out:
                shutil.copyfileobj(src, out)
            mode = (info.external_attr >> 16) & 0o777
            if mode:
                try:
                    dest.chmod(mode)
                except PermissionError:
                    pass
            extracted += 1
    log(f'Extracted {extracted} fixes files; ignored {ignored} runtime duplicate entries')


def run_source_tweaks(patch_script: Path) -> Path | None:
    log('Applying SourceRTXTweaks x64 binary patches')
    patched = TARGET / 'patched'
    if patched.exists():
        shutil.rmtree(patched)
    cmd = [sys.executable, str(patch_script), str(TARGET)]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, file=sys.stderr, end='')
    if result.returncode != 0:
        raise RuntimeError(f'SourceRTXTweaks failed with exit code {result.returncode}')
    if not patched.exists():
        log('SourceRTXTweaks produced no patched directory')
        return None

    patch_files = [p for p in patched.rglob('*') if p.is_file()]
    if not patch_files:
        log('SourceRTXTweaks produced no patched files')
        return None

    backup = TARGET / f'backup_patches_{_dt.datetime.now().strftime("%Y%m%d_%H%M%S")}'
    for src in patch_files:
        rel = src.relative_to(patched)
        dst = TARGET / rel
        if dst.exists():
            copy_file(dst, backup / rel)
        copy_file(src, dst)
    shutil.rmtree(patched)
    log(f'Installed {len(patch_files)} patched binaries; backups in {backup}')
    return backup


# Port of RTXLauncher.Core.Utilities.MaterialSystemFallbackPatch for the current x64 materialsystem.dll guard.
MARKER = b'GMRTXFB1'
MAX_FALLBACK_LOADS = 16
MAX_INIT_SHADER_SIZE = 0x1000
INITIALIZE_SHADER_PROLOGUE = bytes([0x40,0x53,0x55,0x56,0x57,0x41,0x54,0x41,0x56,0x41,0x57,0x48,0x81,0xEC,0x90,0x0B,0x00,0x00])
INITIALIZE_COUNTER_PATCH = bytes([0xC6,0x84,0x24,0x80,0x0B,0x00,0x00,0x00,0x90,0x90,0x90,0x90,0x90,0x90,0x90])
LOAD_VMT_FILE_PROLOGUE = bytes([0x48,0x89,0x5C,0x24,0x20,0x55,0x56,0x57,0x41,0x56,0x41,0x57,0x48,0x81,0xEC,0x60,0x01,0x00,0x00])
INITIALIZE_SHADER_EPILOGUE = bytes([0x48,0x81,0xC4,0x90,0x0B,0x00,0x00,0x41,0x5F,0x41,0x5E,0x41,0x5C,0x5F,0x5E,0x5D,0x5B,0xC3])
COUNTER_DISPLACEMENT = bytes([0x80,0x0B,0x00,0x00])
INITIALIZE_CONTEXT_PATTERN = '40 32 FF 4C 89 AC 24 88 0B 00 00 89 7C 24 40 0F 1F 40 00 66 66 66 0F 1F 84 00 00 00 00 00 48 8B 0D ?? ?? ?? ??'
INITIALIZE_PATCH_OFFSET = 15
FALLBACK_CALL_PATTERN = '48 C7 44 24 20 00 00 00 00 E8 ?? ?? ?? ?? 84 C0 75 ?? 49 8B 06'
FALLBACK_CALL_OPCODE_OFFSET = 9
FALLBACK_CALL_REPLACEMENT_LENGTH = 14


def read_i32(data: bytes | bytearray, off: int) -> int:
    return struct.unpack_from('<i', data, off)[0]


def read_u16(data: bytes | bytearray, off: int) -> int:
    return struct.unpack_from('<H', data, off)[0]


def read_u32(data: bytes | bytearray, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def write_i32(data: bytearray, off: int, value: int) -> None:
    struct.pack_into('<i', data, off, value)


def write_u32(data: bytearray, off: int, value: int) -> None:
    struct.pack_into('<I', data, off, value)


def valid_range(start: int, length: int, total: int) -> bool:
    return start >= 0 and length >= 0 and start <= total - length


def align_up(value: int, alignment: int) -> int:
    if value < 0 or alignment <= 0:
        return -1
    aligned = ((value + alignment - 1) // alignment) * alignment
    return aligned if aligned <= 0x7fffffff else -1


def find_unique(data: bytes | bytearray, start: int, length: int, pattern: bytes) -> tuple[int, bool]:
    if not valid_range(start, length, len(data)) or not pattern or len(pattern) > length:
        return -1, False
    found = -1
    end = start + length - len(pattern)
    for off in range(start, end + 1):
        if data[off:off + len(pattern)] == pattern:
            if found >= 0:
                return found, True
            found = off
    return found, False


def parse_masked(pattern_text: str) -> list[int | None]:
    out: list[int | None] = []
    for token in pattern_text.split():
        out.append(None if token == '??' else int(token, 16))
    return out


def find_unique_masked(data: bytes | bytearray, start: int, length: int, pattern_text: str) -> tuple[int, bool]:
    pattern = parse_masked(pattern_text)
    if not valid_range(start, length, len(data)) or not pattern or len(pattern) > length:
        return -1, False
    found = -1
    end = start + length - len(pattern)
    for off in range(start, end + 1):
        good = True
        for i, value in enumerate(pattern):
            if value is not None and data[off + i] != value:
                good = False
                break
        if good:
            if found >= 0:
                return found, True
            found = off
    return found, False


def raw_to_rva(raw: int, text: dict[str, int]) -> int:
    return text['virtual_address'] + (raw - text['raw_offset'])


def try_rva_to_raw(rva: int, text: dict[str, int]) -> int | None:
    section_offset = rva - text['virtual_address']
    if section_offset < 0 or section_offset >= text['raw_size']:
        return None
    return text['raw_offset'] + section_offset


def try_decode_relative_target(image: bytes | bytearray, instruction_offset: int, text: dict[str, int]) -> int | None:
    if not valid_range(instruction_offset, 5, len(image)) or image[instruction_offset] not in (0xE8, 0xE9):
        return None
    displacement = read_i32(image, instruction_offset + 1)
    target = raw_to_rva(instruction_offset, text) + 5 + displacement
    if target < text['virtual_address'] or target >= text['virtual_address'] + text['raw_size'] or target > 0x7fffffff:
        return None
    return target


def displacement(next_instruction_rva: int, target_rva: int) -> int | None:
    value = target_rva - next_instruction_rva
    if value < -0x80000000 or value > 0x7fffffff:
        return None
    return value


def read_text_section(image: bytes | bytearray) -> tuple[dict[str, int] | None, str]:
    if len(image) < 0x40 or read_u16(image, 0) != 0x5A4D:
        return None, 'File is not a valid PE image.'
    pe = read_i32(image, 0x3C)
    if not valid_range(pe, 24, len(image)) or read_u32(image, pe) != 0x00004550:
        return None, 'PE header is invalid.'
    machine = read_u16(image, pe + 4)
    section_count = read_u16(image, pe + 6)
    optional_size = read_u16(image, pe + 20)
    optional = pe + 24
    if machine != 0x8664 or section_count == 0 or section_count > 96 or not valid_range(optional, optional_size, len(image)) or optional_size < 0x70 or read_u16(image, optional) != 0x20B:
        return None, 'Only a valid AMD64 PE32+ image is supported.'
    section_alignment = read_i32(image, optional + 32)
    if section_alignment <= 0:
        return None, 'PE section alignment is invalid.'
    table = optional + optional_size
    if not valid_range(table, section_count * 40, len(image)):
        return None, 'PE section table is invalid.'

    text: dict[str, int] | None = None
    sections: list[tuple[int, int]] = []
    for i in range(section_count):
        off = table + i * 40
        name = image[off:off + 8].split(b'\0', 1)[0].decode('ascii', errors='ignore')
        virtual_size = read_i32(image, off + 8)
        virtual_address = read_i32(image, off + 12)
        raw_size = read_i32(image, off + 16)
        raw_offset = read_i32(image, off + 20)
        chars = read_u32(image, off + 36)
        sections.append((virtual_address, off))
        if name == '.text':
            if text is not None:
                return None, 'PE image contains multiple .text sections.'
            if virtual_size <= 0 or virtual_address <= 0 or raw_size <= 0 or raw_offset < 0 or virtual_address + raw_size > 0x7fffffff or not valid_range(raw_offset, raw_size, len(image)) or (chars & 0x20000000) == 0:
                return None, 'PE .text section is invalid or not executable.'
            text = {
                'section_header_offset': off,
                'virtual_size': virtual_size,
                'virtual_address': virtual_address,
                'raw_size': raw_size,
                'raw_offset': raw_offset,
                'section_alignment': section_alignment,
                'next_section_offset': 0,
            }
    if text is None:
        return None, 'PE image has no .text section.'

    next_section_offset = 0x7fffffff
    for virtual_address, _ in sections:
        if virtual_address > text['virtual_address']:
            next_section_offset = min(next_section_offset, virtual_address - text['virtual_address'])
    if next_section_offset == 0x7fffffff:
        next_section_offset = align_up(text['raw_size'], section_alignment)
    if next_section_offset <= 0:
        return None, 'PE .text section has an invalid virtual extent.'
    text['next_section_offset'] = next_section_offset
    return text, ''


def build_fallback_stub(stub_rva: int, load_vmt_file_rva: int) -> bytes:
    stub = bytearray([0x80,0xBC,0x24,0x88,0x0B,0x00,0x00,MAX_FALLBACK_LOADS,0x73,0x15,0xFE,0x84,0x24,0x88,0x0B,0x00,0x00,0x48,0xC7,0x44,0x24,0x28,0x00,0x00,0x00,0x00,0xE9,0x00,0x00,0x00,0x00,0x33,0xC0,0xC3])
    disp = displacement(stub_rva + 31, load_vmt_file_rva)
    if disp is None:
        raise RuntimeError('LoadVMTFile is outside JMP rel32 range.')
    write_i32(stub, 27, disp)
    return bytes(stub)


def apply_material_fallback_guard(path: Path, backup_dir: Path | None) -> None:
    if not path.exists():
        log(f'Skipping fallback guard; missing {path}')
        return
    image = bytearray(path.read_bytes())
    text, reason = read_text_section(image)
    if text is None:
        log(f'Skipping fallback guard: {reason}')
        return
    marker_offset, marker_ambiguous = find_unique(image, text['raw_offset'], text['raw_size'], MARKER)
    if marker_ambiguous:
        log('Skipping fallback guard: marker appears more than once')
        return
    if marker_offset >= 0:
        log('Fallback-material recursion guard already installed')
        return

    searchable = min(text['virtual_size'], text['raw_size'])
    init_entry, ambiguous = find_unique(image, text['raw_offset'], searchable, INITIALIZE_SHADER_PROLOGUE)
    if init_entry < 0 or ambiguous:
        log('Skipping fallback guard: CMaterial::InitializeShader prologue not uniquely found')
        return
    function_len = min(MAX_INIT_SHADER_SIZE, text['raw_offset'] + searchable - init_entry)
    init_context, ambiguous = find_unique_masked(image, init_entry, function_len, INITIALIZE_CONTEXT_PATTERN)
    if init_context < 0 or ambiguous:
        log('Skipping fallback guard: InitializeShader counter site not uniquely found')
        return
    init_patch_offset = init_context + INITIALIZE_PATCH_OFFSET
    expected_nop = bytes.fromhex('0F 1F 40 00 66 66 66 0F 1F 84 00 00 00 00 00')
    if image[init_patch_offset:init_patch_offset + len(expected_nop)] != expected_nop:
        log('Skipping fallback guard: InitializeShader no longer has the expected 15-byte NOP site')
        return
    fallback_call, ambiguous = find_unique_masked(image, init_entry, function_len, FALLBACK_CALL_PATTERN)
    if fallback_call < 0 or ambiguous:
        log('Skipping fallback guard: fallback load call not uniquely found')
        return
    original_call_opcode = fallback_call + FALLBACK_CALL_OPCODE_OFFSET
    if fallback_call <= init_patch_offset:
        log('Skipping fallback guard: InitializeShader patch sites are in an unexpected order')
        return
    epilogue, ambiguous = find_unique(image, init_entry, function_len, INITIALIZE_SHADER_EPILOGUE)
    if epilogue < 0 or ambiguous or epilogue <= fallback_call:
        log('Skipping fallback guard: InitializeShader epilogue could not be validated')
        return
    counter_ref, ambiguous = find_unique(image, init_entry, epilogue + len(INITIALIZE_SHADER_EPILOGUE) - init_entry, COUNTER_DISPLACEMENT)
    if counter_ref >= 0 or ambiguous:
        log('Skipping fallback guard: InitializeShader already references the proposed fallback counter slot')
        return
    load_vmt_rva = try_decode_relative_target(image, original_call_opcode, text)
    if load_vmt_rva is None:
        log('Skipping fallback guard: fallback material load is no longer a direct in-section call')
        return
    load_vmt_raw = try_rva_to_raw(load_vmt_rva, text)
    if load_vmt_raw is None or image[load_vmt_raw:load_vmt_raw + len(LOAD_VMT_FILE_PROLOGUE)] != LOAD_VMT_FILE_PROLOGUE:
        log('Skipping fallback guard: fallback call target is not the expected LoadVMTFile function')
        return
    stub_section_offset = align_up(text['virtual_size'], 16)
    if stub_section_offset < 0 or text['virtual_address'] + stub_section_offset > 0x7fffffff:
        log('Skipping fallback guard: .text layout cannot address guard')
        return
    stub = build_fallback_stub(text['virtual_address'] + stub_section_offset, load_vmt_rva)
    payload_len = len(stub) + len(MARKER)
    if stub_section_offset > text['raw_size'] - payload_len:
        log('Skipping fallback guard: .text has no room for guard')
        return
    new_virtual_size = stub_section_offset + payload_len
    aligned_new_virtual_size = align_up(new_virtual_size, text['section_alignment'])
    if new_virtual_size > text['raw_size'] or aligned_new_virtual_size < 0 or aligned_new_virtual_size > text['next_section_offset']:
        log('Skipping fallback guard: guard would overlap another PE section')
        return
    stub_offset = text['raw_offset'] + stub_section_offset
    for b in image[stub_offset:stub_offset + payload_len]:
        if b not in (0x00, 0xCC):
            log('Skipping fallback guard: proposed .text code cave is not empty')
            return
    fallback_call_rva = raw_to_rva(fallback_call, text)
    stub_rva = text['virtual_address'] + stub_section_offset
    call_disp = displacement(fallback_call_rva + 5, stub_rva)
    if call_disp is None:
        log('Skipping fallback guard: guard is outside CALL rel32 range')
        return

    patched = bytearray(image)
    patched[init_patch_offset:init_patch_offset + len(INITIALIZE_COUNTER_PATCH)] = INITIALIZE_COUNTER_PATCH
    patched[fallback_call] = 0xE8
    write_i32(patched, fallback_call + 1, call_disp)
    patched[fallback_call + 5:fallback_call + FALLBACK_CALL_REPLACEMENT_LENGTH] = b'\x90' * (FALLBACK_CALL_REPLACEMENT_LENGTH - 5)
    patched[stub_offset:stub_offset + len(stub)] = stub
    patched[stub_offset + len(stub):stub_offset + len(stub) + len(MARKER)] = MARKER
    write_u32(patched, text['section_header_offset'] + 8, new_virtual_size)

    if backup_dir is None:
        backup_dir = TARGET / f'backup_patches_{_dt.datetime.now().strftime("%Y%m%d_%H%M%S")}'
    rel = path.relative_to(TARGET)
    copy_file(path, backup_dir / rel)
    path.write_bytes(patched)
    log('Installed static $fallbackmaterial recursion guard in bin/win64/materialsystem.dll')


def write_installed_packages() -> None:
    now = _dt.datetime.now().isoformat(timespec='seconds')
    data = {
        'Remix': {
            'Source': REMIX_STABLE['source'],
            'Version': REMIX_STABLE['tag'],
            'ReleaseName': REMIX_STABLE['name'],
            'InstalledAt': now,
            'Branch': None,
        },
        'Fixes': {
            'Source': FIXES_STABLE['source'],
            'Version': FIXES_STABLE['tag'],
            'ReleaseName': FIXES_STABLE['name'],
            'InstalledAt': now,
            'Branch': None,
        },
        'Patches': {
            'Source': SOURCE_TWEAKS['source'],
            'Version': SOURCE_TWEAKS['branch'],
            'ReleaseName': f"Branch: {SOURCE_TWEAKS['branch']}",
            'InstalledAt': now,
            'Branch': SOURCE_TWEAKS['branch'],
        },
        'IsDowngraded': False,
        'DowngradedDepotPath': None,
    }
    (TARGET / 'installed_packages.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    log(f'Wrote {TARGET / "installed_packages.json"}')


def write_launcher_settings() -> None:
    settings_path = TARGET / '.local' / 'share' / 'RTXLauncher' / 'settings.xml'
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    xml = f'''<?xml version="1.0" encoding="utf-8"?>
<SettingsData xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" UseCustomResolution="false" Width="1920" Height="1080" LoadWorkshopAddons="false" DisableChromium="false" ConsoleEnabled="true" DeveloperMode="false" ToolsMode="false" DXLevel="90" CustomLaunchOptions="" ManuallySpecifiedInstallPath="{TARGET}" LinuxProtonPath="" LinuxSteamRootOverride="{STEAM_ROOT}" LinuxEnableProtonLog="false" LinuxSelectedProtonLabel="Proton - Experimental" LinuxVulkanDriver="Auto" LinuxCustomEnvironmentVariables="" LinuxLaunchCommandPrefix="" CheckForUpdatesOnLaunch="true" UseLocalInstallPath="false" Theme="Simple" SetupCompleted="true" CopyLauncherToInstallFolder="false" AddLauncherToStartMenu="false" />
'''
    settings_path.write_text(xml, encoding='utf-8')
    log(f'Wrote RTXLauncher settings to {settings_path}')


def write_helper_scripts() -> None:
    launch = TOOLS / 'run-gmod-rtx.sh'
    launch.write_text(f'''#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)"
exec "$SELF/launch-gmod-rtx.sh" "$@"
''', encoding='utf-8')
    launch.chmod(0o755)

    open_launcher = TOOLS / 'open-rtxlauncher.sh'
    open_launcher.write_text(f'''#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)"
exec "$SELF/open-rtxlauncher.sh" "$@"
''', encoding='utf-8')
    open_launcher.chmod(0o755)

    resume_patch = TOOLS / 'rerun-gmodpatchtool.sh'
    resume_patch.write_text(f'''#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)"
STEAM_ROOT="${{STEAM_ROOT:-{STEAM_ROOT}}}"
cd "$SELF/_tools/GModPatchTool"
exec ./gmodpatchtool --skip-exit-prompt --ignore-gmod-running --steam-path "$STEAM_ROOT"
''', encoding='utf-8')
    resume_patch.chmod(0o755)

    apps = Path('/home/elijah/.local/share/applications')
    apps.mkdir(parents=True, exist_ok=True)
    desktop_game = apps / 'gmod-rtx.desktop'
    desktop_game.write_text(f'''[Desktop Entry]
Type=Application
Name=GMod RTX
Comment=Launch Garry's Mod RTX Remix through RTXLauncher/Proton
Exec={launch}
Path={TARGET}
Terminal=false
Categories=Game;
''', encoding='utf-8')
    desktop_game.chmod(0o755)

    desktop_launcher = apps / 'rtxlauncher-gmod.desktop'
    desktop_launcher.write_text(f'''[Desktop Entry]
Type=Application
Name=RTXLauncher for GMod RTX
Comment=Open RTXLauncher configured for {TARGET}
Exec={open_launcher}
Path={TARGET}
Terminal=false
Categories=Game;
''', encoding='utf-8')
    desktop_launcher.chmod(0o755)
    log(f'Wrote helper scripts in {TOOLS}')
    log(f'Wrote desktop entries in {apps}')


def main() -> int:
    parser = argparse.ArgumentParser(description='Install Garry\'s Mod RTX Remix using RTXLauncher-compatible steps.')
    parser.add_argument('--skip-downloads', action='store_true', help='Use already cached packages only.')
    args = parser.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    remix_zip = CACHE / REMIX_STABLE['asset']
    fixes_zip = CACHE / FIXES_STABLE['asset']
    patch_script = CACHE / SOURCE_TWEAKS['asset']

    if not args.skip_downloads:
        download(REMIX_STABLE['url'], remix_zip, REMIX_STABLE['sha256'])
        download(FIXES_STABLE['url'], fixes_zip, FIXES_STABLE['sha256'])
        download(SOURCE_TWEAKS['url'], patch_script, None)
    else:
        for path in (remix_zip, fixes_zip, patch_script):
            if not path.exists():
                raise RuntimeError(f'--skip-downloads requested but {path} is missing')

    setup_base_install()
    install_remix_package(remix_zip)
    backup_dir = run_source_tweaks(patch_script)
    apply_material_fallback_guard(TARGET / 'bin' / 'win64' / 'materialsystem.dll', backup_dir)
    install_fixes_package(fixes_zip)
    write_installed_packages()
    write_launcher_settings()
    write_helper_scripts()
    log('GMod RTX install complete')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
