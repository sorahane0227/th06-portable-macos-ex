# th06-portable-macos-ex

修改自 [GensokyoClub/th06](https://github.com/GensokyoClub/th06/tree/portable)
⚠️⚠️⚠️ 100% Vibe Coding ⚠️⚠️⚠️

---

## 新增功能

### 打包为 macOS 应用程序
- 详见下方具体步骤

### 画面
- **窗口可自由缩放** — 拖动边框或点击绿色最大化按钮，画面自动等比放大
- **全屏填满桌面** — 使用无边栏桌面全屏（`SDL_WINDOW_FULLSCREEN_DESKTOP`），不再尝试把显示器切成 640×480
- 保持 4:3 比例，宽屏自动左右黑边

### 音频
- **自定义 MIDI 输出设备** — 支持内置 DLS 合成器、IAC Driver 总线、外接 USB MIDI 设备
- **Music Mode 配置** — OFF / WAV / MIDI 三种模式可在配置工具中切换
- **修复切歌卡音符** — 切换歌曲时自动发送 Note Off 清理残留音符（不再卡在 Logic Pro 等 DAW 里）

> **为什么要自定义 MIDI 设备？**
>
> macOS 不允许用户更换系统级 MIDI 音源——系统自带的 DLS 合成器音色质量有限，且无法替换。要实现高质量 MIDI 回放，需要通过一个 **AU 宿主**（如 Logic Pro）加载第三方软音源，再将游戏的 MIDI 输出路由到宿主中播放。
>
> **以 Logic Pro + Sound Canvas VA 为例：**
>
> 1. 打开 Logic Pro → 新建项目 → 默认轨道挂载音源 **Sound Canvas VA**（或任意 AU 音源）
> 2. 展开检查器上方的**轨道: Inst 1** → 将 **MIDI 输入** 设为 `Logic Pro 虚拟输入`
> 3. 运行 `th06_config` → Music Mode 选 **MIDI** → MIDI Device 选 `Logic Pro 虚拟输入` → 保存
> 4. 启动游戏，MIDI 音符将通过Logic Pro → Sound Canvas VA 播放

### 配置工具 (`th06_config`)
- **MIDI Device** — 枚举系统所有 MIDI 输出设备

### 启动方式
- 从任意目录终端运行、Finder 双击、.app bundle 均可自动定位资源文件

---

## 需要准备的文件

从正版東方紅魔郷安装目录复制以下文件到项目根目录（与 `th06` 二进制同目录）：

| 文件 | 说明 |
|---|---|
| `紅魔郷CM.DAT` | PBG3 档案（角色/音乐评论数据） |
| `紅魔郷ED.DAT` | PBG3 档案（结局数据） |
| `紅魔郷IN.DAT` | PBG3 档案（菜单/初始化数据） |
| `紅魔郷MD.DAT` | PBG3 档案（MIDI 数据） |
| `紅魔郷ST.DAT` | PBG3 档案（关卡数据） |
| `紅魔郷TL.DAT` | PBG3 档案（标题/加载数据） |
| `bgm/th06_01.wav` ~ `th06_17.wav` | 背景音乐（WAV 或 MIDI 格式均可） |

可选：

| 文件 | 说明 |
|---|---|
| `NotoSansJP-Regular.ttf` | 备选日文字体 |
| `NotoSans-Regular.ttf` | 配置工具字体（仓库已自带） |
| `icons/` 文件夹 | 图标源文件（打包 .app 时自动使用） |

---

## 编译

### 依赖

- **macOS**：Xcode Command Line Tools + [Homebrew](https://brew.sh)
- **编译器**：Clang（支持 C++20）
- **库**：SDL2、SDL2_image、SDL2_ttf

### 安装依赖

```bash
# Xcode 命令行工具
xcode-select --install

# Homebrew 包
brew install premake sdl2 sdl2_image sdl2_ttf
```

### 编译

```bash
cd th06-portable-macos-ex
premake5 gmake
cd build && make -j16
```

编译产物：
- `th06` — 游戏主程序
- `th06_config` — 配置工具

---

## 运行

```bash
cd th06-portable
./th06
```

首次运行会自动生成 `東方紅魔郷.cfg` 配置文件。音乐模式自动检测：如果 `bgm/th06_01.wav` 存在则默认 WAV，否则 MIDI。

### 配置工具

```bash
./th06_config
```

可修改画面选项、音乐模式、MIDI 设备等。

---

## 打包 macOS .app

### 前提

1. 项目已成功编译（`th06` 和 `th06_config` 存在于项目根目录）
2. 所有资源文件已就位（6 个 DAT + `bgm/` + 字体）
3. `icons/` 文件夹存在（可选，用于生成应用图标）

### 打包

```bash
python3 package_app.py
```

脚本自动完成：
1. 递归发现所有非系统 dylib 依赖
2. 创建 `.app` bundle 结构
3. 复制二进制、资源、dylib
4. 修复 dylib 路径（`@executable_path/../Frameworks/`）
5. 清理 Homebrew 残留 rpath
6. 用 `iconutil` + `actool` 生成图标（支持浅色/深色自动切换）
7. Ad-hoc 代码签名

生成 `th06.app` 后双击即可运行，也可拖入 `/Applications`。

### 使用 IAC Driver 连接 Logic Pro 等 DAW

1. 打开 **Audio MIDI Setup**（应用程序 → 实用工具）
2. 菜单栏 → 窗口 → 显示 MIDI 工作室
3. 双击 **IAC Driver** → 勾选"设备已在线" → 添加所需总线
4. 运行 `th06_config` → Music Mode 选 **MIDI** → MIDI Device 选对应总线
5. 在 Logic Pro 中创建外部 MIDI 轨道，输入端口选 IAC Driver 对应总线

---

## 项目结构

```
th06-portable/
├── th06                    # 游戏主程序（编译产物）
├── th06_config             # 配置工具（编译产物）
├── th06.app/               # macOS 应用程序包（打包产物）
├── package_app.py          # .app 打包脚本
├── premake5.lua            # 构建配置
├── README.md
├── icons/                  # 图标源文件（6 套主题 × 10 分辨率）
├── src/                    # 源代码
│   ├── main.cpp
│   ├── Config/config.cpp   # 配置工具 UI
│   ├── midi/               # MIDI 后端（CoreAudio / Win32 / ALSA）
│   ├── pbg3/               # PBG3 档案解析器
│   └── graphics/           # OpenGL 渲染后端
├── resources/              # 占位资源
├── bgm/                    # 背景音乐（需自行准备）
└── 紅魔郷*.DAT             # PBG3 档案（需从正版游戏复制）
```

---

## 反编译致谢

感谢以下人员对反编译项目的贡献：

- @EstexNT — MSVC7 `var_order` pragma 移植
- [GensokyoClub/th06](https://github.com/GensokyoClub/th06) 全体贡献者

## 東方Project ©上海アリス幻樂団
icons中的图标文件均为上海アリス幻樂団/上海アリスReprise版权所有
