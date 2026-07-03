# th06-portable-macos-ex

Forked from [GensokyoClub/th06](https://github.com/GensokyoClub/th06/tree/portable)
— ⚠️⚠️⚠️ 100% Vibe Coding ⚠️⚠️⚠️

[中文版](README.md)

---

## New Features

### macOS .app Bundle
- See packaging steps below

### Display
- **Resizable window** — drag edges or click the green maximize button; aspect-ratio-correct scaling is automatic
- **Desktop-filling fullscreen** — uses borderless desktop fullscreen (`SDL_WINDOW_FULLSCREEN_DESKTOP`) instead of forcing the display to 640×480
- Preserves 4:3 aspect ratio with automatic letterboxing/pillarboxing

### Audio
- **Custom MIDI output device** — supports the built-in DLS synth, IAC Driver buses, and external USB MIDI interfaces
- **Music Mode setting** — OFF / WAV / MIDI, configurable via the config tool
- **Stuck-note fix** — sends Note Off on song switch to prevent lingering notes in DAWs like Logic Pro

> **Why custom MIDI device selection?**
>
> macOS does not let you change the system-level MIDI sound source. The built-in DLS synth has limited sound quality and cannot be replaced. To get high-quality MIDI playback, you need an **AU host** (such as Logic Pro) to load a third-party software synth, and then route the game's MIDI output into the host.
>
> **Example: Logic Pro + Sound Canvas VA**
>
> 1. Open Logic Pro → New Project → load **Sound Canvas VA** (or any AU synth) on the default instrument track
> 2. Expand the track header above the inspector → **Track: Inst 1** → set **MIDI Input** to `Logic Pro Virtual Input`
> 3. Run `th06_config` → Music Mode: **MIDI** → MIDI Device: `Logic Pro Virtual Input` → Save
> 4. Launch the game — MIDI notes will play through Logic Pro → Sound Canvas VA

### Config Tool (`th06_config`)
- **MIDI Device** — enumerates all system MIDI output destinations

### Launch Flexibility
- Works from any working directory in terminal, via Finder double-click, or from within an .app bundle

---

## Required Files

Copy the following from your legitimate Touhou Koumakyou installation to the project root (same directory as the `th06` binary):

| File | Description |
|---|---|
| `紅魔郷CM.DAT` | PBG3 archive (character / music commentary) |
| `紅魔郷ED.DAT` | PBG3 archive (ending data) |
| `紅魔郷IN.DAT` | PBG3 archive (menu / init data) |
| `紅魔郷MD.DAT` | PBG3 archive (MIDI data) |
| `紅魔郷ST.DAT` | PBG3 archive (stage data) |
| `紅魔郷TL.DAT` | PBG3 archive (title / loading data) |
| `bgm/th06_01.wav` ~ `th06_17.wav` | Background music (WAV or MIDI format) |

Optional:

| File | Description |
|---|---|
| `NotoSansJP-Regular.ttf` | Fallback Japanese font |
| `NotoSans-Regular.ttf` | Config tool font (included in repo) |
| `icons/` folder | Icon source files (used automatically when packaging .app) |

---

## Building

### Dependencies

- **macOS**: Xcode Command Line Tools + [Homebrew](https://brew.sh)
- **Compiler**: Clang (C++20 support required)
- **Libraries**: SDL2, SDL2_image, SDL2_ttf

### Install Dependencies

```bash
# Xcode Command Line Tools
xcode-select --install

# Homebrew packages
brew install premake sdl2 sdl2_image sdl2_ttf
```

### Build

```bash
cd th06-portable-macos-ex
premake5 gmake
cd build && make -j16
```

Build outputs:
- `th06` — game binary
- `th06_config` — configuration tool

---

## Running

```bash
cd th06-portable
./th06
```

On first run, a `東方紅魔郷.cfg` config file is created automatically. Music mode is auto-detected: WAV if `bgm/th06_01.wav` exists, otherwise MIDI.

### Configuration Tool

```bash
./th06_config
```

Allows changing display options, music mode, MIDI device, etc.

---

## Packaging as macOS .app

### Prerequisites

1. Project is compiled (`th06` and `th06_config` exist in project root)
2. All resource files are in place (6 DAT files + `bgm/` + font)
3. `icons/` folder present (optional, for app icon generation)

### Package

```bash
python3 package_app.py
```

The script automatically:
1. Recursively discovers all non-system dylib dependencies
2. Creates the `.app` bundle structure
3. Copies the binaries, resources, and dylibs
4. Fixes dylib paths (`@executable_path/../Frameworks/`)
5. Cleans up extraneous Homebrew rpath entries
6. Generates icons via `iconutil` + `actool` (supports light/dark auto-switching)
7. Ad-hoc code signing

After packaging, double-click `th06.app` to run, or drag it into `/Applications`.

### Using IAC Driver with Logic Pro or other DAWs

1. Open **Audio MIDI Setup** (Applications → Utilities)
2. Menu bar → Window → Show MIDI Studio
3. Double-click **IAC Driver** → check "Device is online" → add desired buses
4. Run `th06_config` → Music Mode: **MIDI** → MIDI Device: choose the IAC bus
5. In Logic Pro, create an external MIDI track with the IAC bus as input

---

## Project Structure

```
th06-portable/
├── th06                    # Game binary (build output)
├── th06_config             # Config tool (build output)
├── th06.app/               # macOS application bundle (package output)
├── package_app.py          # .app packaging script
├── premake5.lua            # Build configuration
├── README.md               # Chinese documentation
├── README_EN.md            # English documentation
├── icons/                  # Icon sources (6 themes × 10 resolutions)
├── src/                    # Source code
│   ├── main.cpp
│   ├── Config/config.cpp   # Config tool UI
│   ├── midi/               # MIDI backends (CoreAudio / Win32 / ALSA)
│   ├── pbg3/               # PBG3 archive parser
│   └── graphics/           # OpenGL rendering backends
├── resources/              # Placeholder resources
├── bgm/                    # Background music (user-supplied)
└── 紅魔郷*.DAT             # PBG3 archives (from original game)
```

---

## Decompilation Credits

Thanks to the following contributors to the decompilation project:

- @EstexNT — MSVC7 `var_order` pragma port
- All [GensokyoClub/th06](https://github.com/GensokyoClub/th06) contributors

## Touhou Project © Team Shanghai Alice

All icon files in `icons/` are copyright of Team Shanghai Alice / Shanghai Alice Reprise.
