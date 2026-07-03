#!/usr/bin/env python3
"""
Automated macOS .app bundler for th06-portable.
Recursively discovers all non-system dylibs, copies them into the .app bundle,
fixes install names and @rpath references, creates Info.plist, and code signs.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path("/Users/hakujinsorahane/DevelopmentStuff/th06-portable")
APP_NAME = "th06.app"
BINARY_NAME = "th06"
BUNDLE_ID = "com.th06-portable.eosd"


# --- Dylib discovery ---

def get_dylib_deps(binary_path: str) -> list[str]:
    """Get all non-system dylib paths (including @rpath refs) that a binary depends on."""
    result = subprocess.run(
        ["otool", "-L", binary_path],
        capture_output=True, text=True
    )
    deps = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.endswith(':'):
            continue
        path = line.split()[0].rstrip(':')
        # Skip system libs
        if (path.startswith("/usr/lib/") or path.startswith("/System/Library/")
                or path.startswith("@executable_path/")):
            continue
        if not path.startswith('/') and not path.startswith('@rpath/'):
            continue
        deps.append(path)
    return deps


def get_rpath_refs(binary_path: str) -> list[str]:
    """Get @rpath-referenced library names from a binary."""
    deps = get_dylib_deps(binary_path)
    return [d for d in deps if d.startswith('@rpath/')]


def discover_all_dylibs(root_binary: str) -> set[str]:
    """Recursively discover all non-system dylib dependencies (absolute paths only)."""
    to_process = [root_binary]
    all_dylibs = set()

    while to_process:
        current = to_process.pop()
        deps = get_dylib_deps(current)
        for dep in deps:
            if dep.startswith('@rpath/'):
                continue
            real_dep = os.path.realpath(dep)
            if real_dep not in all_dylibs and os.path.exists(real_dep):
                all_dylibs.add(real_dep)
                to_process.append(real_dep)

    return all_dylibs


def resolve_rpath_dylibs(frameworks_dir: str) -> dict[str, str]:
    """
    Find @rpath-referenced dylibs (like libjxl_cms, libsharpyuv).
    Returns mapping of rpath_name -> resolved_absolute_path.
    """
    rpath_needed = set()
    for dylib in Path(frameworks_dir).glob("*.dylib"):
        for ref in get_rpath_refs(str(dylib)):
            rpath_needed.add(ref)

    resolved = {}
    for rp in rpath_needed:
        basename = os.path.basename(rp.replace('@rpath/', ''))
        # Search Homebrew for the dylib
        found = list(Path("/opt/homebrew").rglob(basename))
        if found:
            resolved[rp] = str(found[0])
    return resolved


# --- .app structure ---

def create_app_structure() -> tuple[Path, Path]:
    app_dir = PROJECT_ROOT / APP_NAME
    contents = app_dir / "Contents"
    if app_dir.exists():
        shutil.rmtree(app_dir)
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources").mkdir(parents=True)
    (contents / "Frameworks").mkdir(parents=True)
    return app_dir, contents


# --- Copying ---

def copy_binary(contents: Path) -> Path:
    """Copy both th06 and th06_config to MacOS/."""
    for binary_name in [BINARY_NAME, "th06_config"]:
        src = PROJECT_ROOT / binary_name
        if src.exists():
            dst = contents / "MacOS" / binary_name
            shutil.copy2(src, dst)
            os.chmod(dst, 0o755)
    return contents / "MacOS" / BINARY_NAME


def copy_resources(contents: Path):
    resources_dir = contents / "Resources"
    for dat_file in PROJECT_ROOT.glob("紅魔郷*.DAT"):
        shutil.copy2(dat_file, resources_dir / dat_file.name)

    bgm_src = PROJECT_ROOT / "bgm"
    if bgm_src.exists():
        bgm_dst = resources_dir / "bgm"
        if bgm_dst.exists():
            shutil.rmtree(bgm_dst)
        shutil.copytree(bgm_src, bgm_dst)

    for font in ["msgothic.ttc", "NotoSans-Regular.ttf", "NotoSansJP-Regular.ttf"]:
        font_path = PROJECT_ROOT / font
        if font_path.exists():
            shutil.copy2(font_path, resources_dir / font)

    # Build proper .icns + Assets.car from icons/
    icons_dir = PROJECT_ROOT / "icons"
    if icons_dir.exists():
        icns_file, car_file = build_icons(icons_dir)
        if icns_file:
            shutil.copy2(icns_file, resources_dir / "AppIcon.icns")
        if car_file:
            shutil.copy2(car_file, resources_dir / "Assets.car")


def build_icons(icons_dir: Path):
    """Build AppIcon.icns (iconutil) + Assets.car (actool, theme-aware). Returns (icns_path, car_path)."""
    import json
    
    size_map = {
        '16x16@1x.png':    ('16x16', '1x'),
        '16x16@2x.png':    ('16x16', '2x'),
        '32x32@1x.png':    ('32x32', '1x'),
        '32x32@2x.png':    ('32x32', '2x'),
        '128x128@1x.png':  ('128x128', '1x'),
        '128x128@2x.png':  ('128x128', '2x'),
        '256x256@1x.png':  ('256x256', '1x'),
        '256x256@2x.png':  ('256x256', '2x'),
        '512x512@1x.png':  ('512x512', '1x'),
        '1024x1024@1x.png':('512x512', '2x'),
    }
    
    icns_map = {
        '16x16@1x.png':    'icon_16x16.png',
        '16x16@2x.png':    'icon_16x16@2x.png',
        '32x32@1x.png':    'icon_32x32.png',
        '32x32@2x.png':    'icon_32x32@2x.png',
        '128x128@1x.png':  'icon_128x128.png',
        '128x128@2x.png':  'icon_128x128@2x.png',
        '256x256@1x.png':  'icon_256x256.png',
        '256x256@2x.png':  'icon_256x256@2x.png',
        '512x512@1x.png':  'icon_512x512.png',
        '1024x1024@1x.png': 'icon_512x512@2x.png',
    }
    
    themes = {
        'Default':     [],                                                         # 'any' base (light default)
        'Dark':        [{'appearance': 'luminosity', 'value': 'dark'}],           # dark mode
        'TintedLight': [{'appearance': 'luminosity', 'value': 'light'},
                        {'appearance': 'contrast', 'value': 'high'}],             # light high-contrast
        'TintedDark':  [{'appearance': 'luminosity', 'value': 'dark'},
                        {'appearance': 'contrast', 'value': 'high'}],             # dark high-contrast
    }
    
    icns_result = None
    car_result = None
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        
        # --- Step 1: Build proper .icns with iconutil (Default theme only) ---
        iconset = tmp / 'th06.iconset'
        iconset.mkdir()
        for suffix, icns_name in icns_map.items():
            src = icons_dir / f'th06-iOS-Default-{suffix}'
            if src.exists():
                shutil.copy2(src, iconset / icns_name, follow_symlinks=True)
        
        icns_out = tmp / 'AppIcon.icns'
        result = subprocess.run(
            ['iconutil', '-c', 'icns', str(iconset), '-o', str(icns_out)],
            capture_output=True, text=True
        )
        if result.returncode == 0 and icns_out.exists():
            dst = PROJECT_ROOT / 'AppIcon.icns'
            shutil.copy2(icns_out, dst)
            icns_result = dst
            print(f"  Built AppIcon.icns ({icns_out.stat().st_size // 1024}KB)")
        
        # --- Step 2: Build Assets.car with actool (all themes) ---
        catalog = tmp / 'th06_assets'
        appset = catalog / 'AppIcon.appiconset'
        appset.mkdir(parents=True)
        
        images = []
        for suffix, (size, scale) in size_map.items():
            for theme, appearances in themes.items():
                src = icons_dir / f'th06-iOS-{theme}-{suffix}'
                if not src.exists():
                    continue
                name = f'icon_{size}_{theme}.png'
                shutil.copy2(src, appset / name, follow_symlinks=True)
                entry = {'idiom': 'mac', 'scale': scale, 'size': size, 'filename': name}
                if appearances:
                    entry['appearances'] = appearances
                images.append(entry)
        
        with open(appset / 'Contents.json', 'w') as f:
            json.dump({'images': images, 'info': {'author': 'xcode', 'version': 1}}, f, indent=2)
        
        output_dir = tmp / 'output'
        output_dir.mkdir()
        result = subprocess.run([
            'xcrun', 'actool', str(catalog), '--compile', str(output_dir),
            '--output-format', 'human-readable-text',
            '--platform', 'macosx', '--minimum-deployment-target', '10.15',
            '--app-icon', 'AppIcon',
            '--product-type', 'com.apple.product-type.application',
            '--output-partial-info-plist', str(output_dir / 'partial.plist')
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            for name in ['Assets.car', 'AppIcon.icns']:
                src = output_dir / name
                if src.exists():
                    dst = PROJECT_ROOT / name
                    shutil.copy2(src, dst)
                    if name == 'Assets.car':
                        car_result = dst
                    elif icns_result is None:
                        # Use actool's .icns as fallback
                        icns_result = dst
            if car_result:
                print(f"  Built Assets.car ({car_result.stat().st_size // 1024}KB, {len(images)} variants)")
    
    return icns_result, car_result
    frameworks_dir = contents / "Frameworks"
    mapping = {}
    for dylib in all_dylibs:
        basename = os.path.basename(dylib)
        dst = frameworks_dir / basename
        shutil.copy2(dylib, dst, follow_symlinks=True)
        os.chmod(dst, 0o755)
        mapping[dylib] = str(dst)
    
    # SDL2-compat loads SDL3 dynamically at runtime via dlopen.
    # It searches for libSDL3.dylib relative to @loader_path and @executable_path.
    # We bundle SDL3 and provide a symlink so it can be found.
    sdl3_candidates = list(Path("/opt/homebrew/opt/sdl3/lib").glob("libSDL3.*.dylib"))
    if sdl3_candidates:
        sdl3_real = str(sdl3_candidates[0])
        sdl3_basename = os.path.basename(sdl3_real)
        sdl3_dst = frameworks_dir / sdl3_basename
        shutil.copy2(sdl3_real, sdl3_dst, follow_symlinks=True)
        os.chmod(sdl3_dst, 0o755)
        # Create symlink: libSDL3.dylib -> libSDL3.0.dylib
        sdl3_link = frameworks_dir / "libSDL3.dylib"
        if not sdl3_link.exists():
            sdl3_link.symlink_to(sdl3_basename)
        mapping[sdl3_real] = str(sdl3_dst)
    
    return mapping


# --- Fixing paths ---

def run_itool(*args):
    subprocess.run(["install_name_tool"] + list(args), capture_output=True)


def copy_dylibs(all_dylibs, contents):
    frameworks_dir = contents / "Frameworks"
    mapping = {}
    for dylib in all_dylibs:
        basename = os.path.basename(dylib)
        dst = frameworks_dir / basename
        shutil.copy2(dylib, dst, follow_symlinks=True)
        os.chmod(dst, 0o755)
        mapping[dylib] = str(dst)
    sdl3_candidates = list(Path("/opt/homebrew/opt/sdl3/lib").glob("libSDL3.*.dylib"))
    if sdl3_candidates:
        sdl3_real = str(sdl3_candidates[0])
        sdl3_basename = os.path.basename(sdl3_real)
        sdl3_dst = frameworks_dir / sdl3_basename
        shutil.copy2(sdl3_real, sdl3_dst, follow_symlinks=True)
        os.chmod(sdl3_dst, 0o755)
        sdl3_link = frameworks_dir / "libSDL3.dylib"
        if not sdl3_link.exists():
            sdl3_link.symlink_to(sdl3_basename)
        mapping[sdl3_real] = str(sdl3_dst)
    return mapping


def fix_dylib_paths(contents, original_to_bundled, binary_path):
    """
    Fix install names and @rpath references.
    """
    frameworks_dir = contents / "Frameworks"
    bundled_basenames = {os.path.basename(p) for p in original_to_bundled.values()}
    bundled_basename_to_path = {
        os.path.basename(bundled): bundled for bundled in original_to_bundled.values()
    }

    def resolve_to_frameworks(dep_path: str):
        """Try to map a dependency path to a Frameworks-relative path."""
        # Direct match by real path
        real = os.path.realpath(dep_path) if os.path.exists(dep_path) else None
        if real and real in original_to_bundled:
            return f"@executable_path/../Frameworks/{os.path.basename(original_to_bundled[real])}"
        if real and dep_path != real and dep_path in original_to_bundled:
            return f"@executable_path/../Frameworks/{os.path.basename(original_to_bundled[dep_path])}"
        # Match by basename
        basename = os.path.basename(dep_path)
        if basename in bundled_basenames:
            return f"@executable_path/../Frameworks/{basename}"
        return None

    def fix_target(target_path: str):
        """Fix all dylib references in a binary/dylib."""
        deps = get_dylib_deps(target_path)
        for dep in deps:
            new_path = resolve_to_frameworks(dep)
            if new_path:
                run_itool("-change", dep, new_path, target_path)

    # 1. Fix each dylib's own ID
    for original, bundled in original_to_bundled.items():
        basename = os.path.basename(bundled)
        run_itool("-id", f"@executable_path/../Frameworks/{basename}", bundled)

    # 2. Fix each dylib's dependency references
    for original, bundled in original_to_bundled.items():
        fix_target(bundled)

    # 3. Fix the main binary
    fix_target(binary_path)

    # Also fix th06_config if present
    config_path = str(Path(binary_path).parent / "th06_config")
    if os.path.exists(config_path):
        fix_target(config_path)

    # 4. Handle sdl2-compat aliases (for both binaries)
    sdl2_aliases = [
        "/opt/homebrew/opt/sdl2-compat/lib/libSDL2-2.0.0.dylib",
        "/opt/homebrew/opt/sdl2/lib/libSDL2-2.0.0.dylib",
    ]
    sdl2_basename = "libSDL2-2.0.0.dylib"
    for alias in sdl2_aliases:
        run_itool("-change", alias,
                  f"@executable_path/../Frameworks/{sdl2_basename}", binary_path)
        if os.path.exists(config_path):
            run_itool("-change", alias,
                      f"@executable_path/../Frameworks/{sdl2_basename}", config_path)


def fix_rpath_references(contents: Path):
    """
    Fix @rpath references in bundled dylibs and copy any missing rpath dylibs.
    """
    frameworks_dir = contents / "Frameworks"

    # Find @rpath references
    rpath_refs = {}
    for dylib in frameworks_dir.glob("*.dylib"):
        refs = get_rpath_refs(str(dylib))
        if refs:
            rpath_refs[str(dylib)] = refs

    if not rpath_refs:
        return

    # Resolve @rpath dylibs to real paths and copy them
    for dylib_path, refs in rpath_refs.items():
        for ref in refs:
            basename = os.path.basename(ref.replace('@rpath/', ''))
            # Check if already bundled
            if basename in [f.name for f in frameworks_dir.glob("*.dylib")]:
                continue

            # Find in Homebrew
            found = list(Path("/opt/homebrew").rglob(basename))
            if found and found[0].is_file():
                src = str(found[0])
                dst = frameworks_dir / basename
                shutil.copy2(src, dst, follow_symlinks=True)
                os.chmod(dst, 0o755)
                # Set install ID
                run_itool("-id", f"@executable_path/../Frameworks/{basename}", str(dst))

    # Now fix the @rpath references to point to Frameworks
    for dylib_path in frameworks_dir.glob("*.dylib"):
        refs = get_rpath_refs(str(dylib_path))
        for ref in refs:
            basename = os.path.basename(ref.replace('@rpath/', ''))
            bundled = frameworks_dir / basename
            if bundled.exists():
                run_itool("-change", ref,
                          f"@executable_path/../Frameworks/{basename}", str(dylib_path))


def clean_rpaths(contents: Path):
    """Remove extraneous LC_RPATH entries that point outside the bundle."""
    frameworks_dir = contents / "Frameworks"
    for dylib in frameworks_dir.glob("*.dylib"):
        result = subprocess.run(
            ["otool", "-l", str(dylib)], capture_output=True, text=True
        )
        lines = result.stdout.splitlines()
        for i, line in enumerate(lines):
            if 'LC_RPATH' in line:
                # Next line has the path
                path_line = lines[i + 1] if i + 1 < len(lines) else ''
                if 'path ' in path_line:
                    rp = path_line.split('path ')[1].split(' (')[0].strip()
                    if not rp.startswith('@executable_path/../Frameworks'):
                        run_itool("-delete_rpath", rp, str(dylib))


# --- Info.plist ---

def create_info_plist(contents: Path):
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>ja</string>
    <key>CFBundleExecutable</key>
    <string>{BINARY_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>{BUNDLE_ID}</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Touhou Koumakyou</string>
    <key>CFBundleDisplayName</key>
    <string>東方紅魔郷</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.2</string>
    <key>CFBundleVersion</key>
    <string>1.0.2</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSRequiresNativeExecution</key>
    <true/>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIconName</key>
    <string>AppIcon</string>
</dict>
</plist>
"""
    (contents / "Info.plist").write_text(plist_content)


# --- Code sign ---

def code_sign(app_dir: Path):
    """Ad-hoc sign: dylibs first, then binary, then whole bundle."""
    contents = app_dir / "Contents"
    frameworks = contents / "Frameworks"
    for dylib in frameworks.glob("*.dylib"):
        subprocess.run(["codesign", "--force", "--sign", "-", str(dylib)], capture_output=True)
    binary = contents / "MacOS" / BINARY_NAME
    subprocess.run(["codesign", "--force", "--sign", "-", str(binary)], capture_output=True)
    config_tool = contents / "MacOS" / "th06_config"
    if config_tool.exists():
        subprocess.run(["codesign", "--force", "--sign", "-", str(config_tool)], capture_output=True)
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(app_dir)],
        capture_output=True
    )


# --- Main ---

def main():
    print("=== Step 1: Discovering dylib dependencies ===")
    binary = str(PROJECT_ROOT / BINARY_NAME)
    all_dylibs = discover_all_dylibs(binary)
    print(f"Found {len(all_dylibs)} absolute-path dylibs to bundle")

    print("\n=== Step 2: Creating .app structure ===")
    app_dir, contents = create_app_structure()

    print("\n=== Step 3: Copying binary ===")
    bundled_binary = copy_binary(contents)

    print("\n=== Step 4: Copying resources ===")
    copy_resources(contents)

    print("\n=== Step 5: Copying dylibs ===")
    mapping = copy_dylibs(all_dylibs, contents)

    print("\n=== Step 6: Fixing dylib install names ===")
    fix_dylib_paths(contents, mapping, str(bundled_binary))

    print("\n=== Step 7: Fixing @rpath references ===")
    fix_rpath_references(contents)

    print("\n=== Step 8: Cleaning extraneous LC_RPATH entries ===")
    clean_rpaths(contents)

    print("\n=== Step 9: Creating Info.plist ===")
    create_info_plist(contents)

    print("\n=== Step 10: Ad-hoc code signing ===")
    code_sign(app_dir)

    print(f"\n=== Done! App created at: {app_dir} ===")
    print(f"  Frameworks: {len(list((contents / 'Frameworks').glob('*.dylib')))} dylibs")
    print(f"  You can run: open {app_dir}")


if __name__ == "__main__":
    main()
